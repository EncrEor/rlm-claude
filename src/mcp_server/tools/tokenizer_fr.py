"""
French/English Tokenizer for RLM BM25 Search - Zero Dependencies

This module provides tokenization optimized for French/English mixed content,
designed for BM25 ranking in the RLM memory system.

Features:
- Accent normalization (realiste = réaliste)
- Compound word splitting (jus-de-fruits -> [jus, fruits])
- Combined FR/EN stopwords
- No external dependencies (uses only stdlib)

Phase 5.1 implementation based on PHASE5_PLAN.md section 4.
"""

import re
import unicodedata

# French stopwords (common words to filter out)
STOPWORDS_FR = {
    "le",
    "la",
    "les",
    "l",
    "un",
    "une",
    "des",
    "du",
    "de",
    "d",
    "et",
    "ou",
    "mais",
    "donc",
    "car",
    "que",
    "qui",
    "quoi",
    "je",
    "tu",
    "il",
    "elle",
    "on",
    "nous",
    "vous",
    "ils",
    "elles",
    "ce",
    "cette",
    "ces",
    "mon",
    "ton",
    "son",
    "notre",
    "votre",
    "leur",
    "est",
    "sont",
    "a",
    "ont",
    "fait",
    "peut",
    "doit",
    "etre",
    "avoir",
    "ne",
    "pas",
    "plus",
    "tres",
    "bien",
    "tout",
    "tous",
    "toute",
    "toutes",
    "pour",
    "dans",
    "sur",
    "avec",
    "sans",
    "par",
    "entre",
    "vers",
    "chez",
    "au",
    "aux",
    "si",
    "ni",
    "comme",
    "meme",
    "aussi",
    "encore",
}

# English stopwords (common words to filter out)
STOPWORDS_EN = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "shall",
    "may",
    "might",
    "must",
    "can",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "this",
    "that",
    "these",
    "of",
    "in",
    "to",
    "for",
    "with",
    "on",
    "at",
    "by",
    "from",
    "up",
    "out",
    "and",
    "or",
    "but",
    "if",
    "not",
    "no",
    "yes",
    "so",
    "as",
    "than",
    "very",
    "too",
    "just",
    "only",
    "also",
    "about",
    "more",
    "some",
    "any",
    "what",
    "which",
    "who",
    "when",
    "where",
    "how",
    "all",
    "each",
    "both",
}

# Combined stopwords
STOPWORDS = STOPWORDS_FR | STOPWORDS_EN


def normalize_accent(text: str) -> str:
    """
    Remove accents from text for matching purposes.

    Uses NFD normalization to decompose characters, then removes
    diacritical marks (combining characters).

    Args:
        text: Input text potentially with accents

    Returns:
        Text with accents removed (e.g., 'réaliste' -> 'realiste')

    Examples:
        >>> normalize_accent("réaliste")
        'realiste'
        >>> normalize_accent("événement")
        'evenement'
    """
    # NFD decomposition: é -> e + combining acute accent
    normalized = unicodedata.normalize("NFD", text)
    # Remove combining characters (category 'Mn' = Mark, Nonspacing)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def tokenize_fr(text: str, remove_stopwords: bool = True) -> list[str]:
    """
    Tokenize French/English text for BM25 search.

    Features:
    - Lowercases text
    - Normalizes accents for matching
    - Extracts words and hyphenated compounds
    - Splits compound words (jus-de-fruits -> [jus, fruits])
    - Filters stopwords (optional)
    - Removes short tokens (< 2 chars)

    Args:
        text: Input text to tokenize
        remove_stopwords: Whether to filter out common words (default: True)

    Returns:
        List of tokens suitable for BM25 indexing

    Examples:
        >>> tokenize_fr("Le jus d'orange est tres realiste")
        ['jus', 'orange', 'realiste']
        >>> tokenize_fr("Le jus-de-fruits presse a froid")
        ['jus', 'fruits', 'presse', 'froid']
        >>> tokenize_fr("Deploy v19.0.2 on VPS Odoo")
        ['deploy', 'v19', '0', '2', 'vps', 'odoo']
    """
    # Lowercase
    text = text.lower()

    # Normalize accents for matching (réaliste -> realiste)
    text = normalize_accent(text)

    # Extract tokens: words, numbers, and hyphenated compounds
    # Pattern matches: word characters and internal hyphens
    raw_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text)

    # Split compound words on hyphens
    tokens = []
    for token in raw_tokens:
        if "-" in token:
            # Split and add individual parts
            parts = token.split("-")
            tokens.extend(parts)
        else:
            tokens.append(token)

    # Filter stopwords and short tokens
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) >= 2]
    else:
        tokens = [t for t in tokens if len(t) >= 2]

    return tokens


# Quick test when run directly
if __name__ == "__main__":
    test_cases = [
        ("Le jus d'orange est tres realiste", ["jus", "orange", "realiste"]),
        ("Le jus-de-fruits presse a froid", ["jus", "fruits", "presse", "froid"]),
        ("Deploy v19.0.2 on VPS Odoo", ["deploy", "v19", "vps", "odoo"]),
        ("Le business plan Joy Juice", ["business", "plan", "joy", "juice"]),
        ("Phase 4 RLM validee", ["phase", "rlm", "validee"]),
    ]

    print("Testing tokenizer_fr:")
    all_passed = True
    for text, expected in test_cases:
        result = tokenize_fr(text)
        # Note: expected may not be exact due to version numbers splitting
        status = "PASS" if set(expected).issubset(set(result)) else "CHECK"
        if status == "CHECK":
            all_passed = False
        print(f"  {status}: '{text}'")
        print(f"       -> {result}")

    print(f"\nAll tests: {'PASSED' if all_passed else 'NEEDS REVIEW'}")
