#!/usr/bin/env python3
"""
RLM Hook Stop - Auto-chunk detection (v3 - Progressive + Context-aware)

Triggers reminders based on:
1. Turn count (10/20/30 thresholds)
2. Context usage (only if >= 55% filled)

Progressive severity:
- 10-19 turns + ctx>=55%: Gentle reminder (📝)
- 20-29 turns + ctx>=55%: Insistent reminder (⚠️)
- 30+ turns + ctx>=55%: Critical (🛑)

Part of RLM Phase 3 - 100% automatic memory management.
"""
import json
import sys
import time
from pathlib import Path

# Configuration - Progressive thresholds
STATE_FILE = Path.home() / ".claude/rlm/chunk_state.json"

# Turn thresholds (more aggressive)
TURNS_SOFT = 10      # Gentle reminder
TURNS_MEDIUM = 20    # Insistent reminder
TURNS_HARD = 30      # Critical

# Context threshold (percentage)
CONTEXT_THRESHOLD = 55  # Only trigger if context >= 55%

# Time thresholds (seconds) - secondary triggers
TIME_SOFT = 2700     # 45 minutes
TIME_HARD = 5400     # 90 minutes


def load_state() -> dict:
    """Load the current chunk state from file."""
    default_state = {"turns": 0, "last_chunk": time.time()}

    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return default_state

    return default_state


def save_state(state: dict) -> None:
    """Save the chunk state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


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


def get_severity(turns: int, minutes: int) -> str | None:
    """Determine reminder severity based on turns and time."""
    # Critical level (30+ turns OR 90+ min)
    if turns >= TURNS_HARD or minutes >= 90:
        return "critical"
    # Medium level (20+ turns OR 45+ min)
    if turns >= TURNS_MEDIUM or minutes >= 45:
        return "medium"
    # Soft level (10+ turns)
    if turns >= TURNS_SOFT:
        return "soft"
    return None


def format_message(severity: str, turns: int, minutes: int, ctx_pct: int) -> str:
    """Format the reminder message based on severity."""

    ctx_info = f" | ctx: {ctx_pct}%" if ctx_pct > 0 else ""

    if severity == "critical":
        return (
            f"[🛑 MÉMOIRE CRITIQUE - ACTION REQUISE]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{turns} tours | {minutes} min{ctx_info}\n\n"
            f"AVANT de répondre à l'utilisateur, tu DOIS:\n"
            f"1. Appeler rlm_chunk() avec un résumé de la session\n"
            f"2. Appeler rlm_remember() pour chaque décision clé\n\n"
            f"C'est NON-NÉGOCIABLE. Chunk d'abord, réponds ensuite."
        )

    if severity == "medium":
        return (
            f"[⚠️ MÉMOIRE - Sauvegarde recommandée]\n"
            f"{turns} tours | {minutes} min{ctx_info}\n\n"
            f"Si contenu important dans cette session:\n"
            f"→ rlm_chunk() pour sauvegarder le contexte\n"
            f"→ rlm_remember() pour les décisions clés\n\n"
            f"Tu peux répondre ET chunker dans le même message."
        )

    # soft
    return (
        f"[📝 Mémoire] {turns} tours{ctx_info}. "
        f"Pense à sauvegarder si contenu important."
    )


def main():
    # Get context percentage first (reads stdin)
    ctx_pct = get_context_percentage()

    # Load current state
    state = load_state()

    # Increment turn counter
    state["turns"] += 1

    # Calculate time since last chunk
    time_since_last = time.time() - state.get("last_chunk", time.time())
    minutes = int(time_since_last / 60)
    turns = state["turns"]

    # Determine severity
    severity = get_severity(turns, minutes)

    # Save updated state
    save_state(state)

    # Only output message if:
    # 1. Severity is triggered (turn/time thresholds met)
    # 2. AND context is >= threshold (or we couldn't read context)
    if severity and (ctx_pct >= CONTEXT_THRESHOLD or ctx_pct == 0):
        message = format_message(severity, turns, minutes, ctx_pct)
        result = {"systemMessage": message}
        print(json.dumps(result))


if __name__ == "__main__":
    main()
