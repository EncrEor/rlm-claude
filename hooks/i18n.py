"""
RLM Hook Internationalization (i18n)

Provides translated messages for hook scripts.
Default language: English. Set RLM_LANG=fr for French.

Supported languages: en, fr
"""
import os

LANG = os.environ.get("RLM_LANG", "en")

MESSAGES = {
    "en": {
        # pre_compact_chunk.py
        "compact_title": "COMPACT DETECTED - SAVE REQUIRED",
        "compact_body": (
            "Context is about to be compacted. BEFORE continuing:\n\n"
            "1. **rlm_chunk()** - Summarize key points from this session:\n"
            "   - Decisions made\n"
            "   - Problems solved\n"
            "   - Current work state\n"
            "   - Next steps identified\n\n"
            "2. **rlm_remember()** - Save each:\n"
            "   - Rule/convention discovered\n"
            "   - Important bug fix\n"
            "   - Technical decision\n\n"
            "What isn't chunked will be LOST after compact.\n"
            "Chunk now, then compact will continue."
        ),
        # auto_chunk_check.py - critical
        "critical_title": "CRITICAL MEMORY - ACTION REQUIRED",
        "critical_body": (
            "BEFORE responding to the user, you MUST:\n"
            "1. Call rlm_chunk() with a session summary\n"
            "2. Call rlm_remember() for each key decision\n\n"
            "This is NON-NEGOTIABLE. Chunk first, respond after."
        ),
        # auto_chunk_check.py - medium
        "medium_title": "MEMORY - Save recommended",
        "medium_body": (
            "If there's important content in this session:\n"
            "→ rlm_chunk() to save context\n"
            "→ rlm_remember() for key decisions\n\n"
            "You can respond AND chunk in the same message."
        ),
        # auto_chunk_check.py - soft
        "soft_prefix": "Memory",
        "soft_body": "Consider saving if there's important content.",
        # shared
        "turns": "turns",
    },
    "fr": {
        # pre_compact_chunk.py
        "compact_title": "COMPACT DÉTECTÉ - SAUVEGARDE OBLIGATOIRE",
        "compact_body": (
            "Le contexte va être compacté. AVANT de continuer:\n\n"
            "1. **rlm_chunk()** - Résumer les points clés de cette session:\n"
            "   - Décisions prises\n"
            "   - Problèmes résolus\n"
            "   - État actuel du travail en cours\n"
            "   - Prochaines étapes identifiées\n\n"
            "2. **rlm_remember()** - Sauvegarder chaque:\n"
            "   - Règle/convention découverte\n"
            "   - Bug fix important\n"
            "   - Décision technique\n\n"
            "⚠️ Ce qui n'est pas chunké sera PERDU après le compact.\n"
            "Chunk maintenant, puis le compact continuera."
        ),
        # auto_chunk_check.py - critical
        "critical_title": "MÉMOIRE CRITIQUE - ACTION REQUISE",
        "critical_body": (
            "AVANT de répondre à l'utilisateur, tu DOIS:\n"
            "1. Appeler rlm_chunk() avec un résumé de la session\n"
            "2. Appeler rlm_remember() pour chaque décision clé\n\n"
            "C'est NON-NÉGOCIABLE. Chunk d'abord, réponds ensuite."
        ),
        # auto_chunk_check.py - medium
        "medium_title": "MÉMOIRE - Sauvegarde recommandée",
        "medium_body": (
            "Si contenu important dans cette session:\n"
            "→ rlm_chunk() pour sauvegarder le contexte\n"
            "→ rlm_remember() pour les décisions clés\n\n"
            "Tu peux répondre ET chunker dans le même message."
        ),
        # auto_chunk_check.py - soft
        "soft_prefix": "Mémoire",
        "soft_body": "Pense à sauvegarder si contenu important.",
        # shared
        "turns": "tours",
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = LANG if LANG in MESSAGES else "en"
    return MESSAGES[lang].get(key, MESSAGES["en"].get(key, key))
