#!/usr/bin/env python3
"""
RLM Hook PostToolUse (Write/Edit) — Redirect auto-memory to RLM

Fires after Write or Edit tool is used.
If the target file is in the auto-memory directory, injects a reminder
to use rlm_remember() or rlm_chunk() instead.

Language: Set RLM_LANG=fr for French, RLM_LANG=ja for Japanese (default: English).

Part of RLM Phase 10 - Auto-memory/RLM cohabitation.
"""
import json
import sys
from pathlib import Path

# Import i18n from same directory
sys.path.insert(0, str(Path(__file__).parent))
from i18n import t

MEMORY_DIR = "memory/"
MEMORY_INDICATORS = [
    "/.claude/projects/",
]


def is_memory_path(file_path: str) -> bool:
    """Check if the target file is in an auto-memory directory."""
    if not file_path:
        return False
    for indicator in MEMORY_INDICATORS:
        if indicator in file_path and MEMORY_DIR in file_path:
            return True
    return False


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return

        data = json.loads(input_data)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if is_memory_path(file_path):
            message = (
                f"[📝 {t('memory_redirect_title')}]\n"
                f"{t('memory_redirect_body')}"
            )
            print(json.dumps({"systemMessage": message}))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass


if __name__ == "__main__":
    main()
