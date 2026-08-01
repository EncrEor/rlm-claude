#!/usr/bin/env python3
"""
RLM Hook PreCompact - protect memory before context compaction.

Behaviour (v2, 2026-07-01, decision D2 Option A of track rlm-memory):
- MANUAL /compact: BLOCKED (exit 2) when no recent rlm_chunk() (< FRESH_MINUTES).
  The user sees the message, asks Claude to chunk, re-runs /compact -> it passes.
- AUTO-compact: NEVER blocked (blocking would trap a session at context
  saturation); a systemMessage reminder is shown, with no save guarantee.

Neither branch ever creates a chunk: chunking stays a deliberate act.

Freshness is read from ~/.claude/rlm/chunk_state.json, written by the PostToolUse
hook reset_chunk_counter.py on every mcp__rlm-server__rlm_chunk call.

Language: set RLM_LANG=fr for French, ja for Japanese (default: English).
"""
import json
import sys
import time
from pathlib import Path

# Import i18n from same directory
sys.path.insert(0, str(Path(__file__).parent))
from i18n import t

STATE_FILE = Path.home() / ".claude/rlm/chunk_state.json"
FRESH_MINUTES = 15


def last_chunk_age_minutes() -> float:
    """Minutes since the last rlm_chunk(), or inf when unknown."""
    try:
        data = json.loads(STATE_FILE.read_text())
        return (time.time() - float(data.get("last_chunk", 0))) / 60.0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return float("inf")


def read_payload() -> dict:
    """Read the hook payload from stdin (trigger + context window usage)."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def context_percentage(payload: dict) -> int:
    """Context usage in percent, 0 when unavailable."""
    try:
        window = payload.get("context_window", {})
        usage = window.get("current_usage", {})
        size = window.get("context_window_size", 1)

        if not usage or size <= 0:
            return 0

        current = (
            usage.get("input_tokens", 0) +
            usage.get("cache_creation_input_tokens", 0) +
            usage.get("cache_read_input_tokens", 0)
        )
        return int(current * 100 / size)
    except (AttributeError, KeyError, TypeError, ZeroDivisionError):
        return 0


def format_age(age: float) -> str:
    return t("compact_age_never") if age == float("inf") else f"{age:.0f} min"


def main():
    payload = read_payload()
    age = last_chunk_age_minutes()

    # Recent chunk -> compact allowed with no friction.
    if age <= FRESH_MINUTES:
        sys.exit(0)

    ctx_pct = context_percentage(payload)
    ctx_info = f" (ctx: {ctx_pct}%)" if ctx_pct > 0 else ""

    if payload.get("trigger") == "manual":
        sys.stderr.write(
            f"[RLM] {t('compact_blocked_header').format(age=format_age(age))}"
            f"{ctx_info}\n\n"
            f"{t('compact_body')}\n"
            f"{t('compact_relaunch').format(minutes=FRESH_MINUTES)}\n"
        )
        sys.exit(2)

    # Auto-compact: never block, best-effort reminder only.
    print(json.dumps({
        "systemMessage": (
            f"[RLM] {t('compact_auto_warning').format(age=format_age(age))}"
            f"{ctx_info}"
        )
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
