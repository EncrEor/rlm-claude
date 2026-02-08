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
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = LANG if LANG in MESSAGES else "en"
    return MESSAGES[lang].get(key, MESSAGES["en"].get(key, key))
