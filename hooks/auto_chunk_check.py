#!/usr/bin/env python3
"""
RLM Hook Stop - Auto-chunk detection

Checks if auto-chunking is needed based on:
- Number of turns since last chunk (threshold: 10)
- Time since last chunk (threshold: 30 minutes)

When triggered, injects a message into Claude's context requesting
automatic chunking of the conversation.

Part of RLM Phase 3 - 100% automatic memory management.
"""
import json
import time
from pathlib import Path

# Configuration
STATE_FILE = Path.home() / ".claude/rlm/chunk_state.json"
TURNS_THRESHOLD = 10
TIME_THRESHOLD = 1800  # 30 minutes in seconds


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


def main():
    # Load current state
    state = load_state()

    # Increment turn counter
    state["turns"] += 1

    # Check if chunking is needed
    time_since_last = time.time() - state.get("last_chunk", time.time())
    needs_chunk = (
        state["turns"] >= TURNS_THRESHOLD or
        time_since_last >= TIME_THRESHOLD
    )

    # Save updated state
    save_state(state)

    # If chunking needed, output message for Claude
    if needs_chunk:
        turns = state["turns"]
        minutes = int(time_since_last / 60)

        result = {
            "systemMessage": (
                f"AUTO-CHUNK REQUIS: {turns} tours depuis dernier chunk "
                f"({minutes} min). "
                "INSTRUCTIONS AUTOMATIQUES:\n"
                "1. Resume les points IMPORTANTS de cette conversation\n"
                "2. Appelle rlm_chunk(resume, summary='Session auto', tags='auto,session')\n"
                "3. Sauvegarde les decisions cles via rlm_remember()\n"
                "C'est AUTOMATIQUE - pas besoin de demander permission."
            )
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
