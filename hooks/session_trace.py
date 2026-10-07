#!/usr/bin/env python3
"""
RLM Hook PostToolUse - session trace.

ABOUTME: Appends what a session touches (file paths, allow-listed program names)
ABOUTME: to ~/.claude/rlm/sessions/<session_id>.jsonl, so an unchunked session can be spotted later.

Matcher: Edit|Write|MultiEdit|NotebookEdit|Bash

Records metadata only:
- Edit / Write / MultiEdit / NotebookEdit -> the file path
- Bash -> the basenames of allow-listed programs ("notable_commands"), never
  the command line itself, which can carry passwords or tokens. A Bash call
  with no notable program still records its time, so a session that keeps
  working is not mistaken for an abandoned one.

Silent, never blocks, never raises.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from session_common import EDIT_TOOLS, append_event, load_config, notable_commands, read_payload


def main():
    payload = read_payload()
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    if tool in EDIT_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path:
            append_event(payload, {"type": "edit", "tool": tool, "path": str(path)})
    elif tool == "Bash":
        names = notable_commands(str(tool_input.get("command", "")), load_config()["notable_commands"])
        append_event(payload, {"type": "bash", "notable": names})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
