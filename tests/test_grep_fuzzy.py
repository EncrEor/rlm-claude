"""
Tests for Fuzzy Grep (Phase 5.2).

Tests:
- Basic fuzzy matching finds typos
- Threshold controls tolerance
- Score-based ranking
- Integration with project/domain filters
- Graceful degradation without thefuzz
"""

import json
from pathlib import Path

import pytest


class TestGrepFuzzyBasic:
    """Basic fuzzy grep functionality tests."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory for each test."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        # Initialize index
        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
        )

        # Patch the module paths
        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

    def _create_chunk(self, chunk_id: str, content: str, **metadata):
        """Helper to create a chunk for testing."""
        # Create chunk file
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        summary = metadata.get("summary", content.split("\n")[0][:50])
        tags = metadata.get("tags", [])
        project = metadata.get("project", "")
        domain = metadata.get("domain", "")

        file_content = f"""---
summary: {summary}
tags: {", ".join(tags) if tags else ""}
project: {project}
domain: {domain}
created: 2026-01-19T10:00:00
---

{content}
"""
        chunk_file.write_text(file_content)

        # Update index
        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": summary,
                "tags": tags,
                "project": project,
                "domain": domain,
                "tokens_estimate": len(content.split()) * 2,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_fuzzy_finds_exact_match(self):
        """Fuzzy grep should find exact matches."""
        self._create_chunk("test_001", "La validation du process est complete.")

        result = self.nav.grep_fuzzy("validation", threshold=80)

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert any(m["chunk_id"] == "test_001" for m in result["matches"])

    def test_fuzzy_finds_typos(self):
        """Fuzzy grep should find matches despite typos."""
        self._create_chunk("test_002", "La validation du process est complete.")

        # Typo: "validaton" instead of "validation"
        result = self.nav.grep_fuzzy("validaton", threshold=75)

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert result["matches"][0]["chunk_id"] == "test_002"

    def test_fuzzy_threshold_strict(self):
        """High threshold should reject poor matches."""
        self._create_chunk("test_003", "Configuration du systeme complet.")

        # Very different word with strict threshold
        result = self.nav.grep_fuzzy("konfig", threshold=95)

        # Should not match with 95% threshold
        assert result["match_count"] == 0

    def test_fuzzy_threshold_tolerant(self):
        """Low threshold should accept more matches."""
        self._create_chunk("test_004", "Configuration du systeme complet.")

        # With tolerant threshold
        result = self.nav.grep_fuzzy("konfig", threshold=50)

        # Should find "Configuration" with 50% threshold
        assert result["match_count"] >= 1

    def test_fuzzy_score_ranking(self):
        """Results should be ranked by score (best first)."""
        self._create_chunk("test_005", "Le business plan est valide.")
        self._create_chunk("test_006", "Le business planning strategique.")
        self._create_chunk("test_007", "Planning de la semaine prochaine.")

        result = self.nav.grep_fuzzy("business plan", threshold=60)

        assert result["status"] == "success"
        # Check scores are in descending order
        if len(result["matches"]) > 1:
            scores = [m["score"] for m in result["matches"]]
            assert scores == sorted(scores, reverse=True)

    def test_fuzzy_includes_score_in_result(self):
        """Each match should include a similarity score."""
        self._create_chunk("test_008", "Le scenario realiste pour 2026.")

        result = self.nav.grep_fuzzy("scenario", threshold=80)

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert "score" in result["matches"][0]
        assert 0 <= result["matches"][0]["score"] <= 100


class TestGrepFuzzyFilters:
    """Test fuzzy grep with project/domain filters."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory for each test."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
        )

        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

    def _create_chunk(self, chunk_id: str, content: str, **metadata):
        """Helper to create a chunk for testing."""
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        summary = metadata.get("summary", content[:50])
        tags = metadata.get("tags", [])
        project = metadata.get("project", "")
        domain = metadata.get("domain", "")

        file_content = f"""---
summary: {summary}
tags: {", ".join(tags) if tags else ""}
project: {project}
domain: {domain}
created: 2026-01-19T10:00:00
---

{content}
"""
        chunk_file.write_text(file_content)

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": summary,
                "tags": tags,
                "project": project,
                "domain": domain,
                "tokens_estimate": 100,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_fuzzy_filter_by_project(self):
        """Fuzzy grep should filter by project."""
        self._create_chunk("rlm_001", "Business plan RLM.", project="RLM")
        self._create_chunk("jj_001", "Business plan Joy Juice.", project="JoyJuice")

        result = self.nav.grep_fuzzy("business", threshold=80, project="RLM")

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert all(m["chunk_id"].startswith("rlm") for m in result["matches"])

    def test_fuzzy_filter_by_domain(self):
        """Fuzzy grep should filter by domain."""
        self._create_chunk("bp_001", "Scenario optimiste.", domain="bp")
        self._create_chunk("seo_001", "Scenario SEO local.", domain="seo")

        result = self.nav.grep_fuzzy("scenario", threshold=80, domain="bp")

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert all(m["chunk_id"] == "bp_001" for m in result["matches"])


class TestGrepFuzzyIntegration:
    """Integration tests for fuzzy grep via grep() dispatcher."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
        )

        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

    def _create_chunk(self, chunk_id: str, content: str, **metadata):
        """Helper to create a chunk."""
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        summary = metadata.get("summary", content[:50])

        file_content = f"""---
summary: {summary}
created: 2026-01-19T10:00:00
---

{content}
"""
        chunk_file.write_text(file_content)

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": summary,
                "project": metadata.get("project", ""),
                "domain": metadata.get("domain", ""),
                "tokens_estimate": 100,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_grep_dispatches_to_fuzzy(self):
        """grep() with fuzzy=True should use grep_fuzzy()."""
        self._create_chunk("test_001", "La validation est terminee.")

        # Call via grep() dispatcher
        result = self.nav.grep("validaton", fuzzy=True, fuzzy_threshold=75)

        assert result["status"] == "success"
        assert result.get("fuzzy") is True
        assert result["match_count"] >= 1

    def test_grep_exact_by_default(self):
        """grep() without fuzzy should use exact matching."""
        self._create_chunk("test_002", "La validation est terminee.")

        # Exact match mode - typo should not match
        result = self.nav.grep("validaton", fuzzy=False)

        # Exact regex won't find "validaton" in "validation"
        assert result["match_count"] == 0


class TestGrepFuzzyEdgeCases:
    """Edge cases and error handling for fuzzy grep."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
        )

        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

    def test_fuzzy_empty_chunks(self):
        """Fuzzy grep on empty database should return empty results."""
        result = self.nav.grep_fuzzy("test", threshold=80)

        assert result["status"] == "success"
        assert result["match_count"] == 0

    def test_fuzzy_respects_limit(self):
        """Fuzzy grep should respect the limit parameter."""
        # Create many chunks
        for i in range(20):
            chunk_id = f"test_{i:03d}"
            chunk_file = self.chunks_dir / f"{chunk_id}.md"
            chunk_file.write_text(f"---\nsummary: Test {i}\n---\n\nTest content number {i}.")

            index_file = self.context_dir / "index.json"
            index = json.loads(index_file.read_text())
            index["chunks"].append(
                {
                    "id": chunk_id,
                    "file": f"chunks/{chunk_id}.md",
                    "summary": f"Test {i}",
                    "project": "",
                    "domain": "",
                    "tokens_estimate": 10,
                    "access_count": 0,
                }
            )
            index_file.write_text(json.dumps(index, indent=2))

        result = self.nav.grep_fuzzy("test", threshold=50, limit=5)

        assert result["match_count"] <= 5

    def test_fuzzy_without_thefuzz_installed(self):
        """Should return error if thefuzz not available."""
        # Temporarily disable thefuzz
        original_available = self.nav.FUZZY_AVAILABLE
        self.nav.FUZZY_AVAILABLE = False

        try:
            result = self.nav.grep_fuzzy("test", threshold=80)
            assert result["status"] == "error"
            assert "thefuzz" in result["message"]
        finally:
            self.nav.FUZZY_AVAILABLE = original_available


class TestRealWorldScenarios:
    """Real-world fuzzy search scenarios."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
        )

        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

    def _create_chunk(self, chunk_id: str, content: str, **metadata):
        """Helper to create a chunk."""
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        summary = metadata.get("summary", content[:50])

        file_content = f"""---
summary: {summary}
created: 2026-01-19T10:00:00
---

{content}
"""
        chunk_file.write_text(file_content)

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": summary,
                "project": metadata.get("project", ""),
                "domain": metadata.get("domain", ""),
                "tokens_estimate": 100,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_common_typo_buisness(self):
        """'buisness' should find 'business'."""
        self._create_chunk("bp_001", "Le business plan Joy Juice 2026 est pret.")

        result = self.nav.grep_fuzzy("buisness", threshold=75)

        assert result["match_count"] >= 1
        assert "bp_001" in [m["chunk_id"] for m in result["matches"]]

    def test_common_typo_recieve(self):
        """'recieve' should find 'receive'."""
        self._create_chunk("email_001", "We will receive the payment next week.")

        result = self.nav.grep_fuzzy("recieve", threshold=75)

        assert result["match_count"] >= 1

    def test_french_typo_scenario(self):
        """'senario' should find 'scenario'."""
        self._create_chunk("bp_002", "Le scenario optimiste prevoit 100k de CA.")

        result = self.nav.grep_fuzzy("senario", threshold=75)

        assert result["match_count"] >= 1
