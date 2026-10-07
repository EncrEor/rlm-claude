#!/usr/bin/env python3
"""
RLM Hook PostToolUse - after rlm_chunk.

ABOUTME: Marks the time of the last chunk (read by pre_compact_chunk.py) and ties
ABOUTME: the chunk to its session: trace line + session_id/transcript_path in index.json.

Matcher: mcp__rlm-server__rlm_chunk

1. chunk_state.json -> "last_chunk" timestamp. pre_compact_chunk.py blocks a
   manual /compact when it is older than 15 minutes: do not remove this step.
2. The session trace gets a "chunk" event, so session_orphans.py knows the
   session was saved.
3. index.json gets session_id + transcript_path on that chunk: a summary can
   be traced back to the raw transcript while Claude Code still keeps it.

Steps 2-3 are best effort; step 1 always runs first.
"""
import json
import re
import sys
import time
from pathlib import Path

STATE_FILE = Path.home() / ".claude/rlm/chunk_state.json"

# Server replies: "✓ Chunk <id> created ..." or "Existing chunk: <id>" (duplicate).
_CHUNK_ID = re.compile(r"(?:Chunk|Existing chunk:)\s+([A-Za-z0-9_&#.\-]+)")


def mark_last_chunk():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"turns": 0, "last_chunk": time.time()}, indent=2))


def chunk_id_from(payload: dict) -> str | None:
    response = payload.get("tool_response")
    text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    match = _CHUNK_ID.search(text or "")
    return match.group(1) if match else None


def tie_chunk_to_session():
    sys.path.insert(0, str(Path(__file__).parent))
    from session_common import append_event, link_chunk_to_session, read_payload

    payload = read_payload()
    chunk_id = chunk_id_from(payload)
    if not chunk_id:
        return
    append_event(payload, {"type": "chunk", "chunk_id": chunk_id})
    session_id = payload.get("session_id")
    if session_id:
        link_chunk_to_session(chunk_id, session_id, payload.get("transcript_path"))


def main():
    mark_last_chunk()
    try:
        tie_chunk_to_session()
    except Exception:
        pass


if __name__ == "__main__":
    main()
