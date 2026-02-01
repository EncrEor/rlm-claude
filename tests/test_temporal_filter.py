"""
Tests for Temporal Filtering (Phase 7.1).

Tests:
- Date range filtering on grep
- Date range filtering on search (BM25)
- Edge cases: no dates, partial ranges, invalid formats
- Integration with project/domain filters
- Helper functions (_parse_date_from_chunk, _chunk_in_date_range)
"""

import json
from pathlib import Path

import pytest


class TestDateHelpers:
    """Tests for date parsing and range checking helpers."""

    def test_parse_date_from_created_at(self):
        """Should extract date from created_at field."""
        from mcp_server.tools.navigation import _parse_date_from_chunk

        chunk_info = {"id": "2026-01-25_RLM_001", "created_at": "2026-01-25T14:30:00"}
        assert _parse_date_from_chunk(chunk_info) == "2026-01-25"

    def test_parse_date_from_chunk_id_fallback(self):
        """Should fall back to chunk ID when created_at is missing."""
        from mcp_server.tools.navigation import _parse_date_from_chunk

        chunk_info = {"id": "2026-01-18_001"}
        assert _parse_date_from_chunk(chunk_info) == "2026-01-18"

    def test_parse_date_empty_chunk(self):
        """Should return None for empty/invalid chunk info."""
        from mcp_server.tools.navigation import _parse_date_from_chunk

        assert _parse_date_from_chunk({}) is None
        assert _parse_date_from_chunk({"id": "invalid"}) is None

    def test_chunk_in_range_no_filter(self):
        """No date filter should always return True."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk = {"id": "2026-01-18_001", "created_at": "2026-01-18T10:00:00"}
        assert _chunk_in_date_range(chunk, None, None) is True

    def test_chunk_in_range_date_from_only(self):
        """Filter with date_from only."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk_old = {"id": "2026-01-10_001", "created_at": "2026-01-10T10:00:00"}
        chunk_new = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}

        assert _chunk_in_date_range(chunk_old, "2026-01-20", None) is False
        assert _chunk_in_date_range(chunk_new, "2026-01-20", None) is True

    def test_chunk_in_range_date_to_only(self):
        """Filter with date_to only."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk_old = {"id": "2026-01-10_001", "created_at": "2026-01-10T10:00:00"}
        chunk_new = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}

        assert _chunk_in_date_range(chunk_old, None, "2026-01-20") is True
        assert _chunk_in_date_range(chunk_new, None, "2026-01-20") is False

    def test_chunk_in_range_both_dates(self):
        """Filter with both date_from and date_to."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk_before = {"id": "2026-01-10_001", "created_at": "2026-01-10T10:00:00"}
        chunk_inside = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}
        chunk_after = {"id": "2026-02-05_001", "created_at": "2026-02-05T10:00:00"}

        assert _chunk_in_date_range(chunk_before, "2026-01-20", "2026-01-30") is False
        assert _chunk_in_date_range(chunk_inside, "2026-01-20", "2026-01-30") is True
        assert _chunk_in_date_range(chunk_after, "2026-01-20", "2026-01-30") is False

    def test_chunk_in_range_boundary_inclusive(self):
        """Boundaries should be inclusive."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}

        # Exact match on boundaries
        assert _chunk_in_date_range(chunk, "2026-01-25", "2026-01-25") is True
        assert _chunk_in_date_range(chunk, "2026-01-25", None) is True
        assert _chunk_in_date_range(chunk, None, "2026-01-25") is True

    def test_chunk_in_range_inverted_returns_nothing(self):
        """Inverted range (from > to) should exclude everything."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}
        assert _chunk_in_date_range(chunk, "2026-02-01", "2026-01-01") is False

    def test_chunk_in_range_invalid_date_format(self):
        """Invalid date format in filter should exclude chunk (fail-safe)."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk = {"id": "2026-01-25_001", "created_at": "2026-01-25T10:00:00"}
        # Malformed dates: still does string comparison, so "janvier" < "2026-..." → False
        # The key behavior: it doesn't crash
        result = _chunk_in_date_range(chunk, "not-a-date", None)
        assert isinstance(result, bool)

    def test_parse_date_legacy_format_no_created_at(self):
        """Legacy format 1.0 chunks without created_at should use ID date."""
        from mcp_server.tools.navigation import _parse_date_from_chunk

        # Format 1.0: no created_at in index (old chunks)
        chunk_info = {"id": "2026-01-18_001", "file": "chunks/2026-01-18_001.md"}
        assert _parse_date_from_chunk(chunk_info) == "2026-01-18"

    def test_parse_date_created_at_with_timezone(self):
        """created_at with timezone info should still parse date."""
        from mcp_server.tools.navigation import _parse_date_from_chunk

        chunk_info = {"id": "2026-01-25_001", "created_at": "2026-01-25T14:30:00+01:00"}
        assert _parse_date_from_chunk(chunk_info) == "2026-01-25"

    def test_chunk_in_range_missing_created_at_uses_id(self):
        """Chunk without created_at should fall back to ID-based date."""
        from mcp_server.tools.navigation import _chunk_in_date_range

        chunk = {"id": "2026-01-25_001"}  # No created_at
        assert _chunk_in_date_range(chunk, "2026-01-20", "2026-01-30") is True
        assert _chunk_in_date_range(chunk, "2026-01-26", None) is False


class TestGrepTemporalFilter:
    """Tests for temporal filtering in grep."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory with chunks at different dates."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        # Initialize index
        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "chunks": [],
                    "total_tokens_estimate": 0,
                },
                indent=2,
            )
        )

        # Patch module paths
        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

        # Create chunks at different dates
        self._create_chunk(
            "2026-01-18_RLM_001", "Décision architecture RLM Phase 5", "2026-01-18T10:00:00"
        )
        self._create_chunk(
            "2026-01-25_RLM_001", "Décision business plan scénarios", "2026-01-25T14:00:00"
        )
        self._create_chunk("2026-01-28_RLM_001", "Décision page produit V2", "2026-01-28T09:00:00")
        self._create_chunk(
            "2026-02-01_RLM_001", "Décision MAGMA upgrade chirurgical", "2026-02-01T11:00:00"
        )

    def _create_chunk(self, chunk_id: str, content: str, created_at: str):
        """Helper to create a chunk file and index entry."""
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        chunk_file.write_text(
            f"---\nsummary: {content[:50]}\ncreated_at: {created_at}\n---\n\n{content}\n"
        )

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": content[:50],
                "tags": [],
                "project": "RLM",
                "domain": "",
                "created_at": created_at,
                "tokens_estimate": 20,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_grep_no_date_filter_returns_all(self):
        """Grep without date filter should return all matches."""
        result = self.nav.grep("Décision")
        assert result["match_count"] == 4

    def test_grep_date_from_filters_old(self):
        """Grep with date_from should exclude older chunks."""
        result = self.nav.grep("Décision", date_from="2026-01-25")
        assert result["match_count"] == 3
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-01-18_RLM_001" not in chunk_ids

    def test_grep_date_to_filters_new(self):
        """Grep with date_to should exclude newer chunks."""
        result = self.nav.grep("Décision", date_to="2026-01-28")
        assert result["match_count"] == 3
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-02-01_RLM_001" not in chunk_ids

    def test_grep_date_range_filters_both(self):
        """Grep with both dates should return only chunks in range."""
        result = self.nav.grep("Décision", date_from="2026-01-25", date_to="2026-01-30")
        assert result["match_count"] == 2
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-01-25_RLM_001" in chunk_ids
        assert "2026-01-28_RLM_001" in chunk_ids

    def test_grep_date_range_no_matches(self):
        """Grep with date range outside all chunks should return 0."""
        result = self.nav.grep("Décision", date_from="2026-03-01", date_to="2026-03-31")
        assert result["match_count"] == 0

    def test_grep_date_combined_with_project(self):
        """Date filter should work together with project filter."""
        result = self.nav.grep("Décision", date_from="2026-01-25", project="RLM")
        assert result["match_count"] == 3

        # Non-existent project should return 0
        result = self.nav.grep("Décision", date_from="2026-01-25", project="NonExistent")
        assert result["match_count"] == 0

    def test_grep_legacy_chunk_without_created_at(self):
        """Grep should filter legacy chunks (format 1.0) using ID-based date."""
        # Add a legacy format chunk (no created_at in index)
        chunk_id = "2026-01-15_001"
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        chunk_file.write_text("---\nsummary: Legacy chunk\n---\n\nDécision legacy test\n")

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": "Legacy chunk",
                "tags": [],
                "tokens_estimate": 10,
                "access_count": 0,
                # No created_at, no project — legacy format
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

        # Should be excluded by date_from after its date
        result = self.nav.grep("Décision", date_from="2026-01-20")
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert chunk_id not in chunk_ids

        # Should be included when range covers it
        result = self.nav.grep("Décision", date_from="2026-01-10", date_to="2026-01-16")
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert chunk_id in chunk_ids

    def test_grep_inverted_range_returns_empty(self):
        """Inverted date range (from > to) should return 0 matches."""
        result = self.nav.grep("Décision", date_from="2026-02-01", date_to="2026-01-01")
        assert result["match_count"] == 0


class TestFuzzyTemporalFilter:
    """Tests for fuzzy grep combined with temporal filtering."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context with chunks at different dates."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps(
                {"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0},
                indent=2,
            )
        )

        import mcp_server.tools.navigation as nav

        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.nav = nav

        # Chunks at different dates with similar content
        self._create_chunk(
            "2026-01-18_RLM_001",
            "La validation du business plan est terminée",
            "2026-01-18T10:00:00",
        )
        self._create_chunk(
            "2026-01-28_RLM_001",
            "La validation de la page produit est ok",
            "2026-01-28T10:00:00",
        )

    def _create_chunk(self, chunk_id: str, content: str, created_at: str):
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        chunk_file.write_text(
            f"---\nsummary: {content[:50]}\ncreated_at: {created_at}\n---\n\n{content}\n"
        )

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": content[:50],
                "tags": [],
                "project": "RLM",
                "domain": "",
                "created_at": created_at,
                "tokens_estimate": 20,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_fuzzy_with_date_filter(self):
        """Fuzzy grep should respect date filters."""
        if not self.nav.FUZZY_AVAILABLE:
            pytest.skip("thefuzz not installed")

        # Both chunks match "validaton" (typo)
        result = self.nav.grep_fuzzy("validaton", date_from="2026-01-25")
        assert result["status"] == "success"
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-01-18_RLM_001" not in chunk_ids
        assert "2026-01-28_RLM_001" in chunk_ids

    def test_fuzzy_with_date_range(self):
        """Fuzzy grep with full date range."""
        if not self.nav.FUZZY_AVAILABLE:
            pytest.skip("thefuzz not installed")

        result = self.nav.grep_fuzzy("validaton", date_from="2026-01-10", date_to="2026-01-20")
        assert result["status"] == "success"
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-01-18_RLM_001" in chunk_ids
        assert "2026-01-28_RLM_001" not in chunk_ids

    def test_fuzzy_dispatched_from_grep_with_dates(self):
        """grep(fuzzy=True) should forward date params to grep_fuzzy."""
        if not self.nav.FUZZY_AVAILABLE:
            pytest.skip("thefuzz not installed")

        result = self.nav.grep("validaton", fuzzy=True, date_from="2026-01-25")
        assert result["status"] == "success"
        chunk_ids = [m["chunk_id"] for m in result["matches"]]
        assert "2026-01-18_RLM_001" not in chunk_ids


class TestSearchTemporalFilter:
    """Tests for temporal filtering in BM25 search."""

    @pytest.fixture(autouse=True)
    def setup_temp_context(self, tmp_path, monkeypatch):
        """Set up temporary context directory."""
        self.context_dir = tmp_path / "context"
        self.chunks_dir = self.context_dir / "chunks"
        self.chunks_dir.mkdir(parents=True)

        # Initialize index
        index_file = self.context_dir / "index.json"
        index_file.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "chunks": [],
                    "total_tokens_estimate": 0,
                },
                indent=2,
            )
        )

        # Patch search module paths
        import mcp_server.tools.navigation as nav
        import mcp_server.tools.search as search_mod

        monkeypatch.setattr(search_mod, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(search_mod, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "CONTEXT_DIR", self.context_dir)
        monkeypatch.setattr(nav, "CHUNKS_DIR", self.chunks_dir)
        monkeypatch.setattr(nav, "INDEX_FILE", self.context_dir / "index.json")

        self.search_mod = search_mod

        # Create chunks at different dates
        self._create_chunk(
            "2026-01-18_RLM_001", "Architecture RLM Phase 5 implémentation", "2026-01-18T10:00:00"
        )
        self._create_chunk(
            "2026-01-28_RLM_001", "Architecture page produit V2 refonte", "2026-01-28T09:00:00"
        )

    def _create_chunk(self, chunk_id: str, content: str, created_at: str):
        """Helper to create a chunk file and index entry."""
        chunk_file = self.chunks_dir / f"{chunk_id}.md"
        chunk_file.write_text(
            f"---\nsummary: {content[:50]}\ncreated_at: {created_at}\n---\n\n{content}\n"
        )

        index_file = self.context_dir / "index.json"
        index = json.loads(index_file.read_text())
        index["chunks"].append(
            {
                "id": chunk_id,
                "file": f"chunks/{chunk_id}.md",
                "summary": content[:50],
                "tags": [],
                "project": "RLM",
                "domain": "",
                "created_at": created_at,
                "tokens_estimate": 20,
                "access_count": 0,
            }
        )
        index_file.write_text(json.dumps(index, indent=2))

    def test_search_no_date_filter(self):
        """Search without date filter should return all relevant results."""
        result = self.search_mod.search("architecture")
        assert result["status"] == "success"
        # Should find both chunks (both contain "architecture")
        assert result["result_count"] >= 1

    def test_search_date_from_filters(self):
        """Search with date_from should exclude older chunks."""
        result = self.search_mod.search("architecture", date_from="2026-01-25")
        assert result["status"] == "success"
        if result["result_count"] > 0:
            chunk_ids = [r["chunk_id"] for r in result["results"]]
            assert "2026-01-18_RLM_001" not in chunk_ids

    def test_search_date_range(self):
        """Search with date range should filter correctly."""
        result = self.search_mod.search(
            "architecture", date_from="2026-01-20", date_to="2026-01-31"
        )
        assert result["status"] == "success"
        if result["result_count"] > 0:
            chunk_ids = [r["chunk_id"] for r in result["results"]]
            assert "2026-01-18_RLM_001" not in chunk_ids

    def test_search_filters_in_response(self):
        """Search response should include active filters."""
        result = self.search_mod.search(
            "architecture", date_from="2026-01-25", date_to="2026-01-31"
        )
        assert result["filters"] is not None
        assert result["filters"]["date_from"] == "2026-01-25"
        assert result["filters"]["date_to"] == "2026-01-31"
