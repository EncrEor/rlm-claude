"""
RLM session trace - shared helpers for the hooks.

ABOUTME: One place for the session-trace paths, config, trace I/O and the
ABOUTME: lock-safe index update used by session_trace / reset_chunk_counter / session_orphans.

A session trace is a JSONL file per Claude Code session,
~/.claude/rlm/sessions/<session_id>.jsonl, holding only metadata:

    {"type": "start", "t": ..., "session_id": ..., "transcript_path": ..., "cwd": ...}
    {"type": "edit",  "t": ..., "tool": "Edit", "path": "/abs/file.py"}
    {"type": "bash",  "t": ..., "notable": ["deploy.sh"]}   # never the command line
    {"type": "chunk", "t": ..., "chunk_id": "2026-10-07_MyProject_002"}
    {"type": "ack",   "t": ..., "reason": "test session, nothing to keep"}

Hooks import nothing from the MCP server (loading it costs seconds) and never
raise: memory bookkeeping must not break a Claude Code session.
"""
import fcntl
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_CONFIG = {
    # Bash commands worth knowing a session ran, matched on the program's
    # basename. Arguments are never recorded: they can carry secrets.
    "notable_commands": [
        "ssh", "scp", "rsync", "psql", "kubectl", "terraform", "ansible-playbook",
    ],
    "min_edits": 5,          # a session matters with MORE than this many Edit/Write...
    "idle_hours": 2,         # ...and is considered over after this long without activity
    "retention_days": 30,    # traces older than this are deleted (Claude Code's
                             # default transcript retention: past it, nothing is recoverable)
    "max_listed": 5,         # orphan sessions detailed at startup
}

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Programs that only wrap the real command: look past them.
_WRAPPERS = {"sudo", "time", "nohup", "exec", "command", "env", "bash", "sh", "zsh"}
_SEPARATORS = re.compile(r"&&|\|\||[;|&\n]|\$\(|`")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_.\-]+$")


def rlm_home() -> Path:
    return Path.home() / ".claude" / "rlm"


def traces_dir() -> Path:
    return rlm_home() / "sessions"


def context_dir() -> Path:
    """Where the MCP server keeps its data. Hooks do not inherit the server's
    environment, so RLM_CONTEXT_DIR only applies when it is exported globally."""
    env_dir = os.environ.get("RLM_CONTEXT_DIR")
    return Path(env_dir) if env_dir else rlm_home() / "context"


def load_config() -> dict:
    """DEFAULT_CONFIG overlaid with ~/.claude/rlm/session_trace.json (optional)."""
    config = dict(DEFAULT_CONFIG)
    try:
        user = json.loads((rlm_home() / "session_trace.json").read_text())
        if isinstance(user, dict):
            config.update({k: v for k, v in user.items() if k in DEFAULT_CONFIG})
    except (OSError, ValueError):
        pass
    return config


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def trace_path(session_id: str) -> Path | None:
    """Trace file of a session, or None for an id that is not a plain name."""
    if not session_id or not _SAFE_SESSION_ID.match(session_id):
        return None
    return traces_dir() / f"{session_id}.jsonl"


def append_event(payload: dict, event: dict) -> None:
    """Append one event to the session's trace, writing the start line first."""
    path = trace_path(payload.get("session_id", ""))
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if not path.exists():
        lines.append({
            "type": "start",
            "t": time.time(),
            "session_id": payload.get("session_id"),
            "transcript_path": payload.get("transcript_path"),
            "cwd": payload.get("cwd"),
        })
    lines.append({"t": time.time(), **event})
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read_trace(path: Path) -> list[dict]:
    events = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    events.append(event)
            except ValueError:
                continue
    except OSError:
        pass
    return events


def notable_commands(command: str, allowed: list[str]) -> list[str]:
    """Basenames of allow-listed programs a shell command runs. Nothing else of
    the command line ever leaves this function."""
    allowed_set = set(allowed)
    found = []
    for segment in _SEPARATORS.split(command or ""):
        tokens = segment.strip().split()
        while tokens and (tokens[0] in _WRAPPERS or _ASSIGNMENT.match(tokens[0])):
            tokens.pop(0)
        if not tokens:
            continue
        name = os.path.basename(tokens[0].strip("'\"()"))
        if name in allowed_set and name not in found:
            found.append(name)
    return found


def link_chunk_to_session(chunk_id: str, session_id: str, transcript_path: str) -> bool:
    """Record the session a chunk was written in, inside index.json.

    Same lock protocol as the server's locked_json_update() (flock on
    index.json.lock, atomic replace), so a concurrent writer is never lost.
    An existing link is kept: a duplicate chunk belongs to its first session.
    """
    index_file = context_dir() / "index.json"
    if not index_file.exists():
        return False
    lock_file = index_file.with_suffix(index_file.suffix + ".lock")
    with open(lock_file, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            chunks = data.get("chunks", [])
            entries = chunks.values() if isinstance(chunks, dict) else chunks
            target = next((e for e in entries if isinstance(e, dict) and e.get("id") == chunk_id), None)
            if target is None or target.get("session_id"):
                return False
            target["session_id"] = session_id
            target["transcript_path"] = transcript_path
            fd, tmp = tempfile.mkstemp(dir=index_file.parent, prefix=".index.json.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, index_file)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
            return True
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
