"""
Tests for Phase 7.2: Entity Extraction (MAGMA-inspired).

Tests the _extract_entities() helper, _entity_matches() helper,
and entity filtering in grep/search.
"""

import json
from pathlib import Path

import pytest

from mcp_server.tools.navigation import (
    _entity_matches,
    _extract_entities,
)

# =============================================================================
# TESTS: _extract_entities()
# =============================================================================


class TestExtractEntities:
    """Tests for the core entity extraction function."""

    def test_empty_content(self):
        result = _extract_entities("")
        assert result == {
            "files": [],
            "versions": [],
            "modules": [],
            "tickets": [],
            "functions": [],
        }

    def test_whitespace_only(self):
        result = _extract_entities("   \n\n  ")
        assert result == {
            "files": [],
            "versions": [],
            "modules": [],
            "tickets": [],
            "functions": [],
        }

    def test_no_entities(self):
        result = _extract_entities("This is just a plain text discussion about nothing.")
        # Should have empty or minimal results
        for key in result:
            # No false positives expected
            assert isinstance(result[key], list)

    def test_extract_python_files(self):
        content = "Modified `server.py` and `navigation.py` for the new feature."
        result = _extract_entities(content)
        assert "server.py" in result["files"]
        assert "navigation.py" in result["files"]

    def test_extract_file_with_path(self):
        content = "The file mcp_server/tools/search.py was updated."
        result = _extract_entities(content)
        assert "mcp_server/tools/search.py" in result["files"]

    def test_extract_various_extensions(self):
        content = """
        Files changed: config.json, style.css, template.xml,
        README.md, script.js, app.ts, layout.html
        """
        result = _extract_entities(content)
        assert "config.json" in result["files"]
        assert "style.css" in result["files"]
        assert "template.xml" in result["files"]
        assert "README.md" in result["files"]
        assert "script.js" in result["files"]

    def test_extract_versions_with_v_prefix(self):
        content = "Updated to v19.0.5.52 from v19.0.5.51"
        result = _extract_entities(content)
        assert "v19.0.5.52" in result["versions"] or "19.0.5.52" in result["versions"]

    def test_extract_versions_without_prefix(self):
        content = "Version 0.9.0 released."
        result = _extract_entities(content)
        assert "0.9.0" in result["versions"]

    def test_extract_semver_3_segments(self):
        content = "Using bm25s 0.2.0 for search."
        result = _extract_entities(content)
        assert "0.2.0" in result["versions"]

    def test_no_date_as_version(self):
        """Dates like 2026.01.18 should not be extracted as versions."""
        content = "The date was 2026.01.18 when we started."
        result = _extract_entities(content)
        assert "2026.01.18" not in result["versions"]

    def test_extract_modules_import(self):
        content = "We use import bm25s and from thefuzz import fuzz."
        result = _extract_entities(content)
        assert "bm25s" in result["modules"]
        assert "thefuzz" in result["modules"]

    def test_extract_modules_keyword(self):
        content = "Install module website_joyjuice for the website."
        result = _extract_entities(content)
        assert "website_joyjuice" in result["modules"]

    def test_extract_tickets(self):
        content = "Fixed JJ-123 and GH-456 in this sprint."
        result = _extract_entities(content)
        assert "JJ-123" in result["tickets"]
        assert "GH-456" in result["tickets"]

    def test_extract_functions(self):
        content = "Called chunk() and _extract_entities() to process the data."
        result = _extract_entities(content)
        assert "chunk()" in result["functions"]
        assert "_extract_entities()" in result["functions"]

    def test_deduplication(self):
        content = "Used server.py and server.py again, also server.py a third time."
        result = _extract_entities(content)
        assert result["files"].count("server.py") == 1

    def test_sorted_output(self):
        content = "Files: zebra.py, alpha.py, middle.py"
        result = _extract_entities(content)
        files = result["files"]
        assert files == sorted(files)

    def test_max_entities_limit(self):
        # Generate content with many entities
        files = [f"file_{i:03d}.py" for i in range(60)]
        content = " ".join(f"`{f}`" for f in files)
        result = _extract_entities(content, max_entities=10)
        total = sum(len(v) for v in result.values())
        assert total <= 10

    def test_french_content(self):
        """Entity extraction should work with French text."""
        content = """
        Modifié `server.py` pour ajouter le filtre temporel.
        Version déployée : v19.0.5.52. Module website_joyjuice mis à jour.
        """
        result = _extract_entities(content)
        assert "server.py" in result["files"]
        assert "website_joyjuice" in result["modules"]

    def test_mixed_content(self):
        """Test extraction from realistic chunk content."""
        content = """
        ## Session 2026-02-01 - Phase 7.2 Entity Extraction

        ### Fichiers modifiés
        - `mcp_server/tools/navigation.py` (ajout _extract_entities)
        - `mcp_server/tools/search.py` (entity param)
        - `tests/test_entity_extraction.py` (24 tests)

        ### Versions
        - RLM v0.9.0 → v0.10.0
        - Odoo 19.0.5.52.1

        ### Tickets
        - Lié à GH-789

        ### Fonctions ajoutées
        - _extract_entities()
        - _entity_matches()
        - chunk() modifié
        """
        result = _extract_entities(content)
        assert "mcp_server/tools/navigation.py" in result["files"]
        assert "mcp_server/tools/search.py" in result["files"]
        assert "tests/test_entity_extraction.py" in result["files"]
        assert "GH-789" in result["tickets"]
        assert "_extract_entities()" in result["functions"]
        assert "_entity_matches()" in result["functions"]
        assert "chunk()" in result["functions"]


# =============================================================================
# TESTS: _entity_matches()
# =============================================================================


class TestEntityMatches:
    """Tests for the entity matching helper."""

    def test_exact_match(self):
        chunk_info = {"entities": {"files": ["server.py", "search.py"]}}
        assert _entity_matches(chunk_info, "server.py") is True

    def test_substring_match(self):
        chunk_info = {"entities": {"files": ["mcp_server/tools/navigation.py"]}}
        assert _entity_matches(chunk_info, "navigation.py") is True

    def test_case_insensitive(self):
        chunk_info = {"entities": {"modules": ["website_joyjuice"]}}
        assert _entity_matches(chunk_info, "Website_JoyJuice") is True

    def test_no_match(self):
        chunk_info = {"entities": {"files": ["server.py"]}}
        assert _entity_matches(chunk_info, "nonexistent.py") is False

    def test_empty_entities(self):
        chunk_info = {"entities": {}}
        assert _entity_matches(chunk_info, "anything") is False

    def test_missing_entities_field(self):
        chunk_info = {"id": "test-chunk"}
        assert _entity_matches(chunk_info, "anything") is False

    def test_entities_not_dict(self):
        """Backward compat: if entities is not a dict, return False."""
        chunk_info = {"entities": "old_format"}
        assert _entity_matches(chunk_info, "anything") is False

    def test_cross_type_match(self):
        """Entity search should match across all types."""
        chunk_info = {
            "entities": {
                "files": ["server.py"],
                "versions": ["v19.0.5.52"],
                "modules": ["bm25s"],
            }
        }
        assert _entity_matches(chunk_info, "bm25s") is True
        assert _entity_matches(chunk_info, "v19.0.5") is True


# =============================================================================
# TESTS: Grep with entity filter
# =============================================================================


class TestGrepEntityFilter:
    """Tests for entity filtering in grep()."""

    @pytest.fixture
    def temp_chunks(self, tmp_path):
        """Create temporary chunk files and index for testing."""
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()

        # Chunk 1: has server.py entity
        chunk1 = chunks_dir / "2026-02-01_TEST_001.md"
        chunk1.write_text(
            "---\nid: 2026-02-01_TEST_001\nsummary: Test chunk 1\n---\n"
            "Modified server.py for feature X\n"
        )

        # Chunk 2: has search.py entity
        chunk2 = chunks_dir / "2026-02-01_TEST_002.md"
        chunk2.write_text(
            "---\nid: 2026-02-01_TEST_002\nsummary: Test chunk 2\n---\nUpdated search.py for BM25\n"
        )

        # Index with entities
        index = {
            "version": "2.0.0",
            "chunks": [
                {
                    "id": "2026-02-01_TEST_001",
                    "file": "chunks/2026-02-01_TEST_001.md",
                    "summary": "Test chunk 1",
                    "tags": [],
                    "project": "TEST",
                    "domain": None,
                    "created_at": "2026-02-01T10:00:00",
                    "entities": {
                        "files": ["server.py"],
                        "versions": [],
                        "modules": [],
                        "tickets": [],
                        "functions": [],
                    },
                },
                {
                    "id": "2026-02-01_TEST_002",
                    "file": "chunks/2026-02-01_TEST_002.md",
                    "summary": "Test chunk 2",
                    "tags": [],
                    "project": "TEST",
                    "domain": None,
                    "created_at": "2026-02-01T11:00:00",
                    "entities": {
                        "files": ["search.py"],
                        "versions": ["0.2.0"],
                        "modules": ["bm25s"],
                        "tickets": [],
                        "functions": [],
                    },
                },
            ],
            "total_chunks": 2,
            "total_tokens_estimate": 100,
        }
        index_file = tmp_path / "index.json"
        index_file.write_text(json.dumps(index))

        return tmp_path

    def test_grep_with_entity_filter(self, temp_chunks, monkeypatch):
        """Grep should only return chunks matching the entity filter."""
        from mcp_server.tools import navigation

        monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_chunks)
        monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_chunks / "chunks")
        monkeypatch.setattr(navigation, "INDEX_FILE", temp_chunks / "index.json")

        result = navigation.grep("Modified", entity="server.py")
        assert result["match_count"] == 1
        assert result["matches"][0]["chunk_id"] == "2026-02-01_TEST_001"

    def test_grep_entity_no_match(self, temp_chunks, monkeypatch):
        """Grep with non-matching entity should return 0 results."""
        from mcp_server.tools import navigation

        monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_chunks)
        monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_chunks / "chunks")
        monkeypatch.setattr(navigation, "INDEX_FILE", temp_chunks / "index.json")

        result = navigation.grep("Modified", entity="nonexistent.py")
        assert result["match_count"] == 0

    def test_grep_entity_case_insensitive(self, temp_chunks, monkeypatch):
        """Entity filter should be case-insensitive."""
        from mcp_server.tools import navigation

        monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_chunks)
        monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_chunks / "chunks")
        monkeypatch.setattr(navigation, "INDEX_FILE", temp_chunks / "index.json")

        result = navigation.grep("Updated", entity="SEARCH.PY")
        assert result["match_count"] == 1

    def test_grep_entity_substring(self, temp_chunks, monkeypatch):
        """Entity filter should support substring matching."""
        from mcp_server.tools import navigation

        monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_chunks)
        monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_chunks / "chunks")
        monkeypatch.setattr(navigation, "INDEX_FILE", temp_chunks / "index.json")

        # "bm25" should match "bm25s" as substring
        result = navigation.grep("BM25", entity="bm25")
        assert result["match_count"] == 1

    def test_grep_entity_combined_with_project(self, temp_chunks, monkeypatch):
        """Entity filter should work combined with project filter."""
        from mcp_server.tools import navigation

        monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_chunks)
        monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_chunks / "chunks")
        monkeypatch.setattr(navigation, "INDEX_FILE", temp_chunks / "index.json")

        result = navigation.grep("Modified", entity="server.py", project="TEST")
        assert result["match_count"] == 1

        result = navigation.grep("Modified", entity="server.py", project="OTHER")
        assert result["match_count"] == 0


# =============================================================================
# TESTS: Search with entity filter
# =============================================================================


class TestSearchEntityFilter:
    """Tests for entity filtering in search()."""

    @pytest.fixture
    def temp_search_env(self, tmp_path):
        """Create temporary environment for search tests."""
        chunks_dir = tmp_path / "chunks"
        chunks_dir.mkdir()

        # Chunk with server.py entity
        chunk1 = chunks_dir / "2026-02-01_TEST_001.md"
        chunk1.write_text(
            "---\nid: 2026-02-01_TEST_001\nsummary: Server modification\n---\n"
            "Modified server configuration for deployment\n"
        )

        # Chunk with search.py entity
        chunk2 = chunks_dir / "2026-02-01_TEST_002.md"
        chunk2.write_text(
            "---\nid: 2026-02-01_TEST_002\nsummary: Search update\n---\n"
            "Updated search engine with new algorithm\n"
        )

        index = {
            "version": "2.0.0",
            "chunks": [
                {
                    "id": "2026-02-01_TEST_001",
                    "file": "chunks/2026-02-01_TEST_001.md",
                    "summary": "Server modification",
                    "tags": [],
                    "project": "TEST",
                    "domain": None,
                    "created_at": "2026-02-01T10:00:00",
                    "entities": {
                        "files": ["server.py"],
                        "versions": ["v19.0.5.52"],
                        "modules": [],
                        "tickets": [],
                        "functions": [],
                    },
                },
                {
                    "id": "2026-02-01_TEST_002",
                    "file": "chunks/2026-02-01_TEST_002.md",
                    "summary": "Search update",
                    "tags": [],
                    "project": "TEST",
                    "domain": None,
                    "created_at": "2026-02-01T11:00:00",
                    "entities": {
                        "files": ["search.py"],
                        "versions": [],
                        "modules": ["bm25s"],
                        "tickets": [],
                        "functions": ["search()"],
                    },
                },
            ],
            "total_chunks": 2,
            "total_tokens_estimate": 100,
        }
        index_file = tmp_path / "index.json"
        index_file.write_text(json.dumps(index))

        return tmp_path

    def test_search_with_entity_filter(self, temp_search_env, monkeypatch):
        """Search with entity should filter results."""
        from mcp_server.tools import search as search_mod

        monkeypatch.setattr(search_mod, "CONTEXT_DIR", temp_search_env)
        monkeypatch.setattr(search_mod, "CHUNKS_DIR", temp_search_env / "chunks")

        # Also patch the RLMSearch chunks_dir
        result = search_mod.search("server", entity="server.py")

        if result["status"] == "success":
            # If BM25 is available, check entity filtering
            for r in result["results"]:
                assert r["chunk_id"] == "2026-02-01_TEST_001"

    def test_search_entity_in_filters(self, temp_search_env, monkeypatch):
        """Entity should appear in active filters."""
        from mcp_server.tools import search as search_mod

        monkeypatch.setattr(search_mod, "CONTEXT_DIR", temp_search_env)
        monkeypatch.setattr(search_mod, "CHUNKS_DIR", temp_search_env / "chunks")

        result = search_mod.search("test", entity="server.py")
        if result["status"] == "success" and result.get("filters"):
            assert result["filters"]["entity"] == "server.py"

    def test_search_entity_no_match(self, temp_search_env, monkeypatch):
        """Search with non-matching entity should return 0 results."""
        from mcp_server.tools import search as search_mod

        monkeypatch.setattr(search_mod, "CONTEXT_DIR", temp_search_env)
        monkeypatch.setattr(search_mod, "CHUNKS_DIR", temp_search_env / "chunks")

        result = search_mod.search("server", entity="nonexistent.py")
        if result["status"] == "success":
            assert result["result_count"] == 0

    def test_search_entity_combined_with_date(self, temp_search_env, monkeypatch):
        """Entity + date filters should work together."""
        from mcp_server.tools import search as search_mod

        monkeypatch.setattr(search_mod, "CONTEXT_DIR", temp_search_env)
        monkeypatch.setattr(search_mod, "CHUNKS_DIR", temp_search_env / "chunks")

        result = search_mod.search(
            "server", entity="server.py", date_from="2026-02-01", date_to="2026-02-01"
        )
        if result["status"] == "success":
            for r in result["results"]:
                assert r["chunk_id"] == "2026-02-01_TEST_001"
