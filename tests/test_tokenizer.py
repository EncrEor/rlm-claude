"""
Tests for FR/EN tokenizer (Phase 5.1).

Tests:
- Basic tokenization
- Accent normalization
- Stopwords filtering
- Compound word splitting
"""

from mcp_server.tools.tokenizer_fr import normalize_accent, tokenize_fr


class TestNormalizeAccent:
    """Tests for accent normalization."""

    def test_french_accents_removed(self):
        """French accents should be normalized."""
        assert normalize_accent("realiste") == "realiste"
        assert normalize_accent("réaliste") == "realiste"
        assert normalize_accent("événement") == "evenement"
        assert normalize_accent("où") == "ou"

    def test_preserves_non_accented(self):
        """Non-accented text should pass through unchanged."""
        assert normalize_accent("hello world") == "hello world"
        assert normalize_accent("test123") == "test123"

    def test_mixed_content(self):
        """Mixed content with accents and regular text."""
        assert normalize_accent("café au lait") == "cafe au lait"
        assert normalize_accent("scénario réaliste 2026") == "scenario realiste 2026"


class TestTokenizeFr:
    """Tests for French/English tokenization."""

    def test_basic_tokenization(self):
        """Basic word extraction."""
        tokens = tokenize_fr("Hello world test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_french_stopwords_removed(self):
        """French stopwords should be filtered out."""
        tokens = tokenize_fr("Le jus d'orange est tres bon")
        assert "le" not in tokens
        assert "est" not in tokens
        assert "tres" not in tokens
        assert "jus" in tokens
        assert "orange" in tokens
        assert "bon" in tokens

    def test_english_stopwords_removed(self):
        """English stopwords should be filtered out."""
        tokens = tokenize_fr("The quick brown fox is very fast")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "very" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_accent_normalization_in_tokenization(self):
        """Accents should be normalized during tokenization."""
        tokens = tokenize_fr("Scenario realiste pour 2026")
        assert "scenario" in tokens
        assert "realiste" in tokens

        # Same query with accents should produce same tokens
        tokens_accented = tokenize_fr("Scénario réaliste pour 2026")
        assert "scenario" in tokens_accented
        assert "realiste" in tokens_accented

    def test_compound_words_split(self):
        """Hyphenated compound words should be split."""
        tokens = tokenize_fr("Le jus-de-fruits presse a froid")
        assert "jus" in tokens
        assert "fruits" in tokens
        assert "presse" in tokens
        assert "froid" in tokens
        # "de" should be filtered as stopword
        assert "de" not in tokens

    def test_short_words_filtered(self):
        """Words shorter than 2 characters should be filtered."""
        tokens = tokenize_fr("I a am an test x y z")
        # Single char words filtered
        assert "x" not in tokens
        assert "y" not in tokens
        assert "z" not in tokens
        # But "am", "an" are stopwords anyway
        assert "test" in tokens

    def test_numbers_preserved(self):
        """Numbers and version strings should be preserved."""
        tokens = tokenize_fr("Deploy v19 on VPS Odoo 2026")
        assert "deploy" in tokens
        assert "v19" in tokens
        assert "vps" in tokens
        assert "odoo" in tokens
        assert "2026" in tokens

    def test_empty_input(self):
        """Empty input should return empty list."""
        assert tokenize_fr("") == []
        assert tokenize_fr("   ") == []

    def test_only_stopwords(self):
        """Input with only stopwords should return empty list."""
        tokens = tokenize_fr("le la les de du des")
        assert tokens == []

    def test_case_insensitive(self):
        """Tokenization should be case-insensitive."""
        tokens_lower = tokenize_fr("business plan")
        tokens_upper = tokenize_fr("BUSINESS PLAN")
        tokens_mixed = tokenize_fr("Business Plan")

        assert tokens_lower == tokens_upper == tokens_mixed

    def test_special_characters_ignored(self):
        """Special characters should not appear in tokens."""
        tokens = tokenize_fr("Hello, world! Test@email.com #hashtag")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "email" in tokens
        assert "com" in tokens
        assert "hashtag" in tokens
        # No special chars
        assert "," not in tokens
        assert "!" not in tokens
        assert "@" not in tokens
        assert "#" not in tokens

    def test_real_world_french_text(self):
        """Test with realistic French business text."""
        text = "Discussion sur le business plan Joy Juice - scenarios realistes pour 2026"
        tokens = tokenize_fr(text)

        expected = [
            "discussion",
            "business",
            "plan",
            "joy",
            "juice",
            "scenarios",
            "realistes",
            "2026",
        ]
        for word in expected:
            assert word in tokens, f"Expected '{word}' in tokens"

    def test_real_world_technical_text(self):
        """Test with realistic technical text."""
        text = "Phase 5.1 BM25 implementation avec tokenizer FR/EN zero dependance"
        tokens = tokenize_fr(text)

        assert "phase" in tokens
        assert "bm25" in tokens
        assert "implementation" in tokens
        assert "tokenizer" in tokens
        assert "zero" in tokens
        assert "dependance" in tokens


class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_handling(self):
        """Unicode characters should be handled gracefully."""
        tokens = tokenize_fr("Test avec emoji \U0001f600 et symboles")
        assert "test" in tokens
        assert "emoji" in tokens
        assert "symboles" in tokens

    def test_very_long_input(self):
        """Long input should be handled without issues."""
        long_text = " ".join(["word"] * 10000)
        tokens = tokenize_fr(long_text)
        assert len(tokens) == 10000
        assert all(t == "word" for t in tokens)

    def test_no_stopwords_removal(self):
        """Test with stopword removal disabled."""
        tokens = tokenize_fr("Le jus est bon", remove_stopwords=False)
        assert "le" in tokens
        assert "jus" in tokens
        assert "est" in tokens
        assert "bon" in tokens
