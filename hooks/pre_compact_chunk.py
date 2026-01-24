#!/usr/bin/env python3
"""
RLM Hook PreCompact - Force chunk before context compaction

Triggered BEFORE /compact (manual) or auto-compact.
Injects a blocking message requiring Claude to chunk the session
before the context is compacted and potentially lost.

Part of RLM Phase 3 - Context preservation.
"""
import json
import sys


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
        f"[🔄 COMPACT DÉTECTÉ - SAUVEGARDE OBLIGATOIRE]{ctx_info}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Le contexte va être compacté. AVANT de continuer:\n\n"
        f"1. **rlm_chunk()** - Résumer les points clés de cette session:\n"
        f"   - Décisions prises\n"
        f"   - Problèmes résolus\n"
        f"   - État actuel du travail en cours\n"
        f"   - Prochaines étapes identifiées\n\n"
        f"2. **rlm_remember()** - Sauvegarder chaque:\n"
        f"   - Règle/convention découverte\n"
        f"   - Bug fix important\n"
        f"   - Décision technique\n\n"
        f"⚠️ Ce qui n'est pas chunké sera PERDU après le compact.\n"
        f"Chunk maintenant, puis le compact continuera."
    )

    result = {"systemMessage": message}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
