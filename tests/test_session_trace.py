"""
Session trace hooks: session_trace.py, reset_chunk_counter.py, session_orphans.py.

ABOUTME: Runs the real hook scripts as Claude Code does (JSON on stdin) against a
ABOUTME: throwaway HOME, and checks what is traced, what is never traced, and what is reported.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
HOUR = 3600


def run_hook(name, payload, home, *args, stdin_raw=None):
    env = {**os.environ, "HOME": str(home), "RLM_CONTEXT_DIR": str(home / "ctx"), "RLM_LANG": "en"}
    return subprocess.run(
        [sys.executable, str(HOOKS / name), *args],
        input=stdin_raw if stdin_raw is not None else json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30,
    )


def trace_file(home, session_id):
    return home / ".claude" / "rlm" / "sessions" / f"{session_id}.jsonl"


def events(home, session_id):
    return [json.loads(line) for line in trace_file(home, session_id).read_text().splitlines()]


def write_trace(home, session_id, evts, cwd="/work/proj"):
    path = trace_file(home, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = {"type": "start", "t": evts[0]["t"], "session_id": session_id,
             "transcript_path": str(home / f"{session_id}.transcript.jsonl"), "cwd": cwd}
    path.write_text("\n".join(json.dumps(e) for e in [start, *evts]) + "\n")
    return path


def edits(n, t, cwd="/work/proj"):
    return [{"type": "edit", "t": t, "tool": "Edit", "path": f"{cwd}/src/f{i}.py"} for i in range(n)]


def base_payload(session_id="s1", tool="Edit", tool_input=None):
    return {"session_id": session_id, "transcript_path": "/tmp/t.jsonl", "cwd": "/work/proj",
            "tool_name": tool, "tool_input": tool_input or {}}


class TestTrace:
    def test_edit_records_path_with_start_line(self, tmp_path):
        run_hook("session_trace.py", base_payload(tool_input={"file_path": "/work/proj/a.py"}), tmp_path)
        evts = events(tmp_path, "s1")
        assert evts[0]["type"] == "start" and evts[0]["transcript_path"] == "/tmp/t.jsonl"
        assert evts[1] == {**evts[1], "type": "edit", "tool": "Edit", "path": "/work/proj/a.py"}

    def test_bash_never_records_the_command(self, tmp_path):
        command = "sshpass -p S3cr3tPass ssh deploy@host 'psql -c \"x\"' && TOKEN=abc123 curl https://api"
        run_hook("session_trace.py", base_payload(tool="Bash", tool_input={"command": command}), tmp_path)
        raw = trace_file(tmp_path, "s1").read_text()
        for secret in ("S3cr3tPass", "abc123", "deploy@host", "curl", "sshpass"):
            assert secret not in raw
        assert events(tmp_path, "s1")[1]["notable"] == []

    def test_bash_records_allow_listed_basenames_only(self, tmp_path):
        config = tmp_path / ".claude" / "rlm" / "session_trace.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"notable_commands": ["deploy.sh", "update.sh"]}))
        command = "cd /x && ./scripts/deploy.sh MOD --force && sudo VAR=1 ./update.sh MOD; ls -la"
        run_hook("session_trace.py", base_payload(tool="Bash", tool_input={"command": command}), tmp_path)
        assert events(tmp_path, "s1")[1]["notable"] == ["deploy.sh", "update.sh"]
        assert "--force" not in trace_file(tmp_path, "s1").read_text()

    def test_garbage_stdin_is_silent(self, tmp_path):
        result = run_hook("session_trace.py", None, tmp_path, stdin_raw="not json")
        assert result.returncode == 0 and result.stdout == ""

    def test_unsafe_session_id_writes_nothing(self, tmp_path):
        run_hook("session_trace.py", base_payload(session_id="../evil",
                 tool_input={"file_path": "/a"}), tmp_path)
        assert not (tmp_path / ".claude" / "rlm").exists() or not list((tmp_path / ".claude").rglob("*.jsonl"))


class TestChunkLink:
    def make_index(self, home, chunk_id):
        ctx = home / "ctx"
        ctx.mkdir(parents=True)
        (ctx / "index.json").write_text(json.dumps({"version": "2.1.0", "chunks": [{"id": chunk_id}]}))
        return ctx / "index.json"

    def test_chunk_marks_trace_index_and_state(self, tmp_path):
        index = self.make_index(tmp_path, "2026-10-07_P_002")
        payload = {**base_payload(tool="mcp__rlm-server__rlm_chunk"),
                   "tool_response": "✓ Chunk 2026-10-07_P_002 created (120 tokens estimated)\n  Type: session"}
        run_hook("reset_chunk_counter.py", payload, tmp_path)
        assert events(tmp_path, "s1")[-1]["chunk_id"] == "2026-10-07_P_002"
        entry = json.loads(index.read_text())["chunks"][0]
        assert entry["session_id"] == "s1" and entry["transcript_path"] == "/tmp/t.jsonl"
        state = json.loads((tmp_path / ".claude" / "rlm" / "chunk_state.json").read_text())
        assert time.time() - state["last_chunk"] < 60

    def test_duplicate_keeps_first_session(self, tmp_path):
        index = self.make_index(tmp_path, "2026-10-01_P_001_r&d")
        first = {**base_payload(session_id="first"), "tool_response": {"result": "✓ Chunk 2026-10-01_P_001_r&d created"}}
        dup = {**base_payload(session_id="second"),
               "tool_response": {"result": "⚠ Duplicate content detected!\n  Existing chunk: 2026-10-01_P_001_r&d\n  Summary: x"}}
        run_hook("reset_chunk_counter.py", first, tmp_path)
        run_hook("reset_chunk_counter.py", dup, tmp_path)
        assert json.loads(index.read_text())["chunks"][0]["session_id"] == "first"
        assert events(tmp_path, "second")[-1]["chunk_id"] == "2026-10-01_P_001_r&d"

    def test_state_still_written_on_garbage(self, tmp_path):
        result = run_hook("reset_chunk_counter.py", None, tmp_path, stdin_raw="")
        assert result.returncode == 0
        assert (tmp_path / ".claude" / "rlm" / "chunk_state.json").exists()


class TestOrphans:
    def report(self, home, session_id="current", cwd="/work/proj"):
        result = run_hook("session_orphans.py", {"session_id": session_id, "cwd": cwd, "source": "startup"}, home)
        assert result.returncode == 0
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_unchunked_busy_session_is_reported(self, tmp_path):
        write_trace(tmp_path, "old", edits(6, time.time() - 3 * HOUR))
        out = self.report(tmp_path)
        context = out["hookSpecificOutput"]["additionalContext"]
        assert "session old" in context and "6 edits on 6 files (src)" in context
        assert "--ack <session_id>" in context and out["systemMessage"]

    @pytest.mark.parametrize("extra,hours,n", [
        ([{"type": "chunk", "t": 0, "chunk_id": "x"}], 3, 6),   # chunked
        ([{"type": "ack", "t": 0, "reason": "test"}], 3, 6),    # acknowledged
        ([], 1, 6),                                             # maybe still running
        ([], 3, 5),                                             # too small to matter
    ])
    def test_not_reported(self, tmp_path, extra, hours, n):
        t = time.time() - hours * HOUR
        write_trace(tmp_path, "old", edits(n, t) + [{**e, "t": t} for e in extra])
        assert self.report(tmp_path) is None

    def test_one_notable_command_is_enough(self, tmp_path):
        write_trace(tmp_path, "old", [{"type": "bash", "t": time.time() - 3 * HOUR, "notable": ["ssh"]}])
        assert "ran: ssh" in self.report(tmp_path)["hookSpecificOutput"]["additionalContext"]

    def test_current_session_is_skipped(self, tmp_path):
        write_trace(tmp_path, "current", edits(9, time.time() - 3 * HOUR))
        assert self.report(tmp_path, session_id="current") is None

    def test_other_projects_are_only_counted(self, tmp_path):
        t = time.time() - 3 * HOUR
        write_trace(tmp_path, "here", edits(6, t))
        write_trace(tmp_path, "there", edits(6, t, cwd="/elsewhere"), cwd="/elsewhere")
        context = self.report(tmp_path)["hookSpecificOutput"]["additionalContext"]
        assert "session here" in context and "session there" not in context
        assert "+ 1 in other projects." in context

    def test_traces_past_retention_are_purged(self, tmp_path):
        path = write_trace(tmp_path, "ancient", edits(9, time.time() - 40 * 24 * HOUR))
        old = time.time() - 40 * 24 * HOUR
        os.utime(path, (old, old))
        assert self.report(tmp_path) is None
        assert not path.exists()

    def test_ack_cli(self, tmp_path):
        write_trace(tmp_path, "old", edits(6, time.time() - 3 * HOUR))
        result = run_hook("session_orphans.py", None, tmp_path, "--ack", "old", "nothing", "to", "keep", stdin_raw="")
        assert result.returncode == 0 and "acknowledged" in result.stdout
        assert events(tmp_path, "old")[-1]["reason"] == "nothing to keep"
        assert self.report(tmp_path) is None

    def test_ack_unknown_session_fails_loud(self, tmp_path):
        result = run_hook("session_orphans.py", None, tmp_path, "--ack", "nope", stdin_raw="")
        assert result.returncode == 1 and "No trace" in result.stdout
