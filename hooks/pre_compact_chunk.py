#!/usr/bin/env python3
"""
RLM Hook PreCompact - Force chunk before context compaction

Triggered BEFORE /compact (manual) or auto-compact.
Injects a blocking message requiring Claude to chunk the session
before the context is compacted and potentially lost.

Part of RLM Phase 3 - Context preservation.

Language: Set RLM_LANG=fr for French (default: English).
"""
import json
import sys
from pathlib import Path

# Import i18n from same directory
sys.path.insert(0, str(Path(__file__).parent))
from i18n import t


def get_context_percentage() -> int:
    """Read context usage from stdin (passed by Claude Code)."""
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return 0

        data = json.loads(input_data)
        context_window = data.get("context_window", {})
        usage = context_window.get("current_usage", {})
        size = context_window.get("context_window_size", 1)

        if not usage or size <= 0:
            return 0

        current = (
            usage.get("input_tokens", 0) +
            usage.get("cache_creation_input_tokens", 0) +
            usage.get("cache_read_input_tokens", 0)
        )

        return int(current * 100 / size)
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0


def main():
    ctx_pct = get_context_percentage()
    ctx_info = f" (ctx: {ctx_pct}%)" if ctx_pct > 0 else ""

    message = (
        f"[🔄 {t('compact_title')}]{ctx_info}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{t('compact_body')}"
    )

    result = {"systemMessage": message}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
