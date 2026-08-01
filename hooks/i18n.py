"""
RLM Hook Internationalization (i18n)

Provides translated messages for hook scripts.
Default language: English. Set RLM_LANG=fr for French, RLM_LANG=ja for Japanese.

Supported languages: en, fr, ja
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
        "compact_blocked_header": "COMPACT BLOCKED - no rlm_chunk() for {age}.",
        "compact_relaunch": "Then re-run /compact - it will pass ({minutes} min window).",
        "compact_auto_warning": (
            "Auto-compact with no recent chunk ({age}) - save NOT guaranteed. "
            "Chunk at the end of the sequence."
        ),
        "compact_age_never": "ever",
        # memory_write_redirect.py
        "memory_redirect_title": "AUTO-MEMORY → RLM ?",
        "memory_redirect_body": (
            "You just wrote to auto-memory (cheat sheet).\n"
            "• Decision, rule, insight → rlm_remember()\n"
            "• Session log, snapshot, debug → rlm_chunk()\n"
            "Auto-memory = quick-reference only (patterns, ports, shortcuts)."
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
        "compact_blocked_header": "COMPACT BLOQUÉ - aucun rlm_chunk() depuis {age}.",
        "compact_relaunch": "Puis relancer /compact - il passera (fenêtre {minutes} min).",
        "compact_auto_warning": (
            "Auto-compact sans chunk récent ({age}) - sauvegarde NON garantie. "
            "Penser à chunker en fin de séquence."
        ),
        "compact_age_never": "toujours",
        # memory_write_redirect.py
        "memory_redirect_title": "AUTO-MEMORY → RLM ?",
        "memory_redirect_body": (
            "Tu viens d'écrire dans auto-memory (cheat sheet).\n"
            "• Décision, règle, insight → rlm_remember()\n"
            "• Log session, snapshot, debug → rlm_chunk()\n"
            "Auto-memory = quick-reference seulement (patterns, ports, raccourcis)."
        ),
    },
    "ja": {
        # pre_compact_chunk.py
        "compact_title": "コンパクト検出 - 保存が必要です",
        "compact_body": (
            "コンテキストがコンパクトされます。続行前に:\n\n"
            "1. **rlm_chunk()** - このセッションの要点をまとめる:\n"
            "   - 決定事項\n"
            "   - 解決した問題\n"
            "   - 作業の現状\n"
            "   - 次のステップ\n\n"
            "2. **rlm_remember()** - 以下を保存:\n"
            "   - 発見したルール/規約\n"
            "   - 重要なバグ修正\n"
            "   - 技術的な決定\n\n"
            "⚠️ チャンクされていない情報はコンパクト後に失われます。\n"
            "今すぐチャンクしてください。"
        ),
        "compact_blocked_header": "コンパクトをブロックしました - {age}の間 rlm_chunk() がありません。",
        "compact_relaunch": "その後 /compact を再実行してください（{minutes}分のウィンドウ内なら通ります）。",
        "compact_auto_warning": (
            "最近のチャンクなしで自動コンパクト（{age}）- 保存は保証されません。"
            "処理の最後にチャンクしてください。"
        ),
        "compact_age_never": "開始以来ずっと",
        # memory_write_redirect.py
        "memory_redirect_title": "AUTO-MEMORY → RLM ?",
        "memory_redirect_body": (
            "auto-memory（チートシート）に書き込みました。\n"
            "• 決定、ルール、インサイト → rlm_remember()\n"
            "• セッションログ、スナップショット、デバッグ → rlm_chunk()\n"
            "auto-memory = クイックリファレンスのみ（パターン、ポート、ショートカット）。"
        ),
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = LANG if LANG in MESSAGES else "en"
    return MESSAGES[lang].get(key, MESSAGES["en"].get(key, key))
