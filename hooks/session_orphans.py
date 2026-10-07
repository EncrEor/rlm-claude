#!/usr/bin/env python3
"""
RLM Hook SessionStart - sessions that ended without a chunk.

ABOUTME: At session start, lists past sessions that changed things but were never
ABOUTME: chunked nor acknowledged, with their transcript and the way to recover them.

A past session is reported when ALL of these hold:
- it is over: no activity for `idle_hours` (a parallel session still running
  is left alone);
- it mattered: more than `min_edits` Edit/Write, or at least one notable
  program run (see session_common.DEFAULT_CONFIG);
- it has neither a chunk nor an acknowledgement in its trace.

It is the ABSENCE of a chunk that is detected, not a clean exit, so crashes,
closed terminals and auto-compacts are covered alike.

Traces older than `retention_days` are deleted first: past Claude Code's
transcript retention, a session can no longer be recovered, so reporting it
would only be noise.

Acknowledge a session that holds nothing worth keeping:
    python3 ~/.claude/rlm/hooks/session_orphans.py --ack <session_id> "reason"
"""
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from i18n import t
from session_common import (
    load_config,
    read_payload,
    read_trace,
    trace_path,
    traces_dir,
)

DAY = 86400


def purge_old_traces(retention_days: float, now: float) -> None:
    for path in traces_dir().glob("*.jsonl"):
        try:
            if now - path.stat().st_mtime > retention_days * DAY:
                path.unlink()
        except OSError:
            continue


def same_project(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def summarize(events: list[dict]) -> dict:
    start = next((e for e in events if e.get("type") == "start"), {})
    edits = [e for e in events if e.get("type") == "edit"]
    notable = []
    for e in events:
        for name in e.get("notable") or []:
            if name not in notable:
                notable.append(name)
    return {
        "session_id": start.get("session_id"),
        "cwd": start.get("cwd"),
        "transcript_path": start.get("transcript_path"),
        "last_t": max((e.get("t", 0) for e in events), default=0),
        "edits": edits,
        "notable": notable,
        "saved": any(e.get("type") in ("chunk", "ack") for e in events),
    }


def find_orphans(config: dict, current_session: str | None, now: float) -> list[dict]:
    orphans = []
    for path in traces_dir().glob("*.jsonl"):
        info = summarize(read_trace(path))
        if not info["session_id"] or info["session_id"] == current_session or info["saved"]:
            continue
        if now - info["last_t"] < config["idle_hours"] * 3600:
            continue
        if len(info["edits"]) <= config["min_edits"] and not info["notable"]:
            continue
        orphans.append(info)
    return sorted(orphans, key=lambda o: o["last_t"], reverse=True)


def top_dirs(edits: list[dict], cwd: str | None, n: int = 2) -> str:
    counts = Counter()
    for e in edits:
        path = e.get("path", "")
        if cwd and path.startswith(cwd.rstrip("/") + "/"):
            path = path[len(cwd.rstrip("/")) + 1:]
        counts[os.path.dirname(path) or "."] += 1
    return ", ".join(d for d, _ in counts.most_common(n))


def describe(info: dict, retention_days: float) -> str:
    when = datetime.fromtimestamp(info["last_t"]).strftime("%Y-%m-%d %H:%M")
    files = len({e.get("path") for e in info["edits"]})
    line = t("orphan_line").format(
        when=when, edits=len(info["edits"]), files=files,
        dirs=top_dirs(info["edits"], info["cwd"]) or "-",
        session_id=info["session_id"],
    )
    if info["notable"]:
        line += t("orphan_notable").format(names=", ".join(info["notable"]))
    transcript = info["transcript_path"]
    if transcript and Path(transcript).exists():
        until = datetime.fromtimestamp(Path(transcript).stat().st_mtime + retention_days * DAY)
        line += "\n" + t("orphan_transcript").format(path=transcript, until=until.strftime("%Y-%m-%d"))
    else:
        line += "\n" + t("orphan_transcript_gone")
    return line


def report(payload: dict) -> None:
    config = load_config()
    now = time.time()
    purge_old_traces(config["retention_days"], now)
    orphans = find_orphans(config, payload.get("session_id"), now)
    if not orphans:
        return

    here = [o for o in orphans if same_project(o["cwd"], payload.get("cwd"))]
    elsewhere = len(orphans) - len(here)
    if not here:
        here, elsewhere = orphans, 0   # no cwd to compare with: show them all

    shown = here[: config["max_listed"]]
    parts = [t("orphan_header").format(n=len(here))]
    parts += [describe(o, config["retention_days"]) for o in shown]
    if len(here) > len(shown):
        parts.append(t("orphan_more").format(n=len(here) - len(shown)))
    if elsewhere:
        parts.append(t("orphan_elsewhere").format(n=elsewhere))
    parts.append(t("orphan_repair"))
    text = "[RLM] " + "\n".join(parts)

    print(json.dumps({
        "systemMessage": "[RLM] " + t("orphan_header").format(n=len(here)),
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
    }, ensure_ascii=False))


def acknowledge(session_id: str, reason: str) -> int:
    path = trace_path(session_id)
    if path is None or not path.exists():
        print(t("ack_unknown").format(session_id=session_id))
        return 1
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "ack", "t": time.time(), "reason": reason}, ensure_ascii=False) + "\n")
    print(t("ack_done").format(session_id=session_id))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--ack":
        return acknowledge(argv[1], " ".join(argv[2:]).strip() or "-")
    try:
        report(read_payload())
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
