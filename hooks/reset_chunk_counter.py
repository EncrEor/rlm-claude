#!/usr/bin/env python3
"""
RLM Hook PostToolUse - Reset chunk counter

Called after rlm_chunk tool is used to reset the auto-chunk counter.
This ensures the countdown starts fresh after each chunk save.

Part of RLM Phase 3 - 100% automatic memory management.
"""
import json
import time
from pathlib import Path

STATE_FILE = Path.home() / ".claude/rlm/chunk_state.json"


def main():
    """Reset the chunk state to initial values."""
    state = {
        "turns": 0,
        "last_chunk": time.time()
    }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    # Silent operation - no output needed


if __name__ == "__main__":
    main()
