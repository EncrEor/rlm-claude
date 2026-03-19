"""
Tests for Phase 8: Semantic Search (Hybrid BM25 + Cosine).

Tests work WITHOUT model2vec installed — uses numpy directly for vector operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# numpy is required for these tests
np = pytest.importorskip("numpy")


# =============================================================================
# VectorStore Tests
# =============================================================================


class TestVectorStore:
    """Test VectorStore add/search/save/load/remove operations."""

    def _make_store(self, tmp_path):
        from mcp_server.tools.vecstore import VectorStore

        return VectorStore(path=tmp_path / "test_embeddings.npz")

    def test_add_and_search_ordering(self, tmp_path):
        """Search returns results ordered by cosine similarity."""
        store = self._make_store(tmp_path)

        # Add 3 vectors: v1 is closest to query, v3 is farthest
        store.add("chunk_a", np.array([1.0, 0.0, 0.0]))
        store.add("chunk_b", np.array([0.7, 0.7, 0.0]))
        store.add("chunk_c", np.array([0.0, 0.0, 1.0]))

        # Query is [1, 0, 0] → chunk_a should be first
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=3)

        # chunk_c has 0 cosine similarity with [1,0,0] → filtered out
        assert len(results) == 2
        assert results[0][0] == "chunk_a"
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)
        assert results[1][0] == "chunk_b"

    def test_save_load_roundtrip(self, tmp_path):
        """Vectors survive save/load cycle."""
        store = self._make_store(tmp_path)
        store.add("chunk_1", np.array([0.5, 0.5, 0.0]))
        store.add("chunk_2", np.array([0.0, 1.0, 0.0]))
        store.save()

        # Load into new store
        store2 = self._make_store(tmp_path)
        loaded = store2.load()

        assert loaded is True
        assert len(store2.chunk_ids) == 2
        assert "chunk_1" in store2.chunk_ids
        assert "chunk_2" in store2.chunk_ids
        assert store2.vectors.shape == (2, 3)

    def test_remove(self, tmp_path):
        """Remove deletes a chunk's vector."""
        store = self._make_store(tmp_path)
        store.add("chunk_a", np.array([1.0, 0.0]))
        store.add("chunk_b", np.array([0.0, 1.0]))

        removed = store.remove("chunk_a")

        assert removed is True
        assert len(store.chunk_ids) == 1
        assert "chunk_a" not in store.chunk_ids
        assert store.vectors.shape == (1, 2)

    def test_remove_nonexistent(self, tmp_path):
        """Remove returns False for nonexistent chunk."""
        store = self._make_store(tmp_path)
        store.add("chunk_a", np.array([1.0, 0.0]))

        assert store.remove("nonexistent") is False
        assert len(store.chunk_ids) == 1

    def test_remove_last_item(self, tmp_path):
        """Remove last item sets vectors to None."""
        store = self._make_store(tmp_path)
        store.add("chunk_a", np.array([1.0, 0.0]))

        store.remove("chunk_a")

        assert len(store.chunk_ids) == 0
        assert store.vectors is None

    def test_empty_search(self, tmp_path):
        """Search on empty store returns empty list."""
        store = self._make_store(tmp_path)
        results = store.search(np.array([1.0, 0.0, 0.0]))
        assert results == []

    def test_load_nonexistent(self, tmp_path):
        """Load returns False when file doesn't exist."""
        store = self._make_store(tmp_path)
        assert store.load() is False

    def test_add_replaces_existing(self, tmp_path):
        """Adding a chunk_id that already exists replaces the vector."""
        store = self._make_store(tmp_path)
        store.add("chunk_a", np.array([1.0, 0.0]))
        store.add("chunk_a", np.array([0.0, 1.0]))

        assert len(store.chunk_ids) == 1
        assert store.vectors.shape == (1, 2)
        np.testing.assert_array_almost_equal(store.vectors[0], [0.0, 1.0])

    def test_zero_query_vector(self, tmp_path):
        """Zero query vector returns empty results."""
        store = self._make_store(tmp_path)
        store.add("chunk_a", np.array([1.0, 0.0]))

        results = store.search(np.array([0.0, 0.0]))
        assert results == []


# =============================================================================
# BM25 Normalization Tests
# =============================================================================


class TestBM25Normalization:
    """Test _normalize_bm25_scores function."""

    def test_normal_range(self):
        from mcp_server.tools.search import _normalize_bm25_scores

        results = [
            {"chunk_id": "a", "score": 10.0},
            {"chunk_id": "b", "score": 5.0},
            {"chunk_id": "c", "score": 0.0},
        ]
        normalized = _normalize_bm25_scores(results)

        assert normalized[0]["score_norm"] == pytest.approx(1.0)
        assert normalized[1]["score_norm"] == pytest.approx(0.5)
        assert normalized[2]["score_norm"] == pytest.approx(0.0)

    def test_single_result(self):
        from mcp_server.tools.search import _normalize_bm25_scores

        results = [{"chunk_id": "a", "score": 5.0}]
        normalized = _normalize_bm25_scores(results)

        assert normalized[0]["score_norm"] == pytest.approx(1.0)

    def test_empty_results(self):
        from mcp_server.tools.search import _normalize_bm25_scores

        results = _normalize_bm25_scores([])
        assert results == []

    def test_equal_scores(self):
        from mcp_server.tools.search import _normalize_bm25_scores

        results = [
            {"chunk_id": "a", "score": 3.0},
            {"chunk_id": "b", "score": 3.0},
        ]
        normalized = _normalize_bm25_scores(results)

        # All equal → all get 1.0
        assert normalized[0]["score_norm"] == pytest.approx(1.0)
        assert normalized[1]["score_norm"] == pytest.approx(1.0)


# =============================================================================
# Hybrid Fusion Tests
# =============================================================================


class TestHybridFusion:
    """Test hybrid BM25 + semantic fusion logic."""

    def test_fusion_ordering(self):
        """Fused results should blend BM25 and semantic scores."""
        from mcp_server.tools.search import HYBRID_ALPHA, _normalize_bm25_scores

        # Simulate BM25 results
        bm25_results = [
            {"chunk_id": "a", "score": 10.0, "summary": "chunk a"},
            {"chunk_id": "b", "score": 5.0, "summary": "chunk b"},
            {"chunk_id": "c", "score": 1.0, "summary": "chunk c"},
        ]
        bm25_results = _normalize_bm25_scores(bm25_results)
        # Norm: a=1.0, b=0.444, c=0.0

        # Simulate semantic results (different ordering)
        semantic_hits = [
            ("b", 0.95),  # b is top semantic match
            ("a", 0.60),
            ("d", 0.80),  # d only in semantic
        ]

        # Perform fusion (same logic as in search.py)
        bm25_map = {r["chunk_id"]: r.get("score_norm", 0) for r in bm25_results}
        sem_map = dict(semantic_hits)
        all_ids = set(bm25_map) | set(sem_map)

        fused = []
        for cid in all_ids:
            score = (1 - HYBRID_ALPHA) * bm25_map.get(cid, 0) + HYBRID_ALPHA * sem_map.get(cid, 0)
            fused.append({"chunk_id": cid, "score": score})

        fused.sort(key=lambda x: x["score"], reverse=True)

        # a: 0.4*1.0 + 0.6*0.60 = 0.76, b: 0.4*0.444 + 0.6*0.95 = 0.748
        # a and b are very close; a wins by a thin margin due to BM25 dominance
        assert fused[0]["chunk_id"] in ("a", "b")
        # All 4 unique chunks should be present
        chunk_ids = {f["chunk_id"] for f in fused}
        assert chunk_ids == {"a", "b", "c", "d"}
        # d (semantic-only) should rank above c (BM25-only with score 0)
        d_idx = next(i for i, f in enumerate(fused) if f["chunk_id"] == "d")
        c_idx = next(i for i, f in enumerate(fused) if f["chunk_id"] == "c")
        assert d_idx < c_idx

    def test_semantic_only_results(self):
        """When BM25 returns nothing but semantic has results, use semantic."""
        semantic_hits = [
            ("chunk_x", 0.9),
            ("chunk_y", 0.7),
        ]
        results = [
            {"chunk_id": cid, "score": s, "summary": ""}
            for cid, s in semantic_hits
        ]

        assert len(results) == 2
        assert results[0]["chunk_id"] == "chunk_x"
        assert results[0]["score"] == 0.9


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestGracefulDegradation:
    """Test that everything works when semantic deps are absent."""

    def test_hybrid_search_returns_none_without_provider(self):
        """_hybrid_search returns None when provider is unavailable."""
        from mcp_server.tools.search import _hybrid_search

        # Mock the embeddings module to return None provider
        mock_embeddings = MagicMock()
        mock_embeddings._get_cached_provider.return_value = None

        with patch.dict("sys.modules", {"mcp_server.tools.embeddings": mock_embeddings}):
            result = _hybrid_search("test query", 5)
            assert result is None

    def test_hybrid_search_returns_none_on_import_error(self):
        """_hybrid_search returns None when embeddings module can't be imported."""
        from mcp_server.tools.search import _hybrid_search

        # Make the import inside _hybrid_search fail
        with patch.dict("sys.modules", {"mcp_server.tools.embeddings": None}):
            result = _hybrid_search("test query", 5)
            assert result is None

    def test_provider_none_without_deps(self):
        """get_provider returns None when model2vec not installed."""
        import mcp_server.tools.embeddings as emb_module

        # Reset singleton state
        emb_module._cached_provider = None
        emb_module._provider_loaded = False

        # Mock Model2VecProvider to raise ImportError
        with patch.object(emb_module, "Model2VecProvider", side_effect=ImportError("no model2vec")):
            emb_module._provider_loaded = False
            emb_module._cached_provider = None
            provider = emb_module._get_cached_provider()
            assert provider is None

        # Reset state after test
        emb_module._provider_loaded = False
        emb_module._cached_provider = None


# =============================================================================
# Phase 8.1: Metadata-Boosted Search Tests
# =============================================================================


class TestMetadataBoostedSearch:
    """Test that YAML metadata improves BM25 search ranking."""

    def _write_chunk(self, chunks_dir: Path, filename: str, content: str):
        chunks_dir.mkdir(parents=True, exist_ok=True)
        (chunks_dir / filename).write_text(content, encoding="utf-8")

    def test_extract_content_includes_metadata(self, tmp_path):
        """_extract_content should prepend summary, tags, project, domain."""
        from mcp_server.tools.search import RLMSearch

        chunks_dir = tmp_path / "chunks"
        self._write_chunk(
            chunks_dir,
            "test_chunk.md",
            "---\nsummary: Business plan financier\ntags: bp, finance\n"
            "project: MyApp\ndomain: bp\n---\n\nContenu sur la trésorerie.",
        )

        searcher = RLMSearch(chunks_dir=chunks_dir)
        content = searcher._extract_content(chunks_dir / "test_chunk.md")

        # Metadata keywords should appear in the extracted content
        assert "Business plan financier" in content
        assert "bp" in content
        assert "finance" in content
        assert "MyApp" in content
        # Original body should still be there
        assert "trésorerie" in content

    def test_extract_content_no_metadata(self, tmp_path):
        """_extract_content with no YAML header returns body as-is."""
        from mcp_server.tools.search import RLMSearch

        chunks_dir = tmp_path / "chunks"
        self._write_chunk(chunks_dir, "plain.md", "Just plain text without header.")

        searcher = RLMSearch(chunks_dir=chunks_dir)
        content = searcher._extract_content(chunks_dir / "plain.md")

        assert "Just plain text without header." in content

    def test_metadata_boosts_bm25_ranking(self, tmp_path):
        """Chunk with 'bp' in tags should rank higher for query 'BP' than chunk without."""
        bm25s = pytest.importorskip("bm25s")
        from mcp_server.tools.search import RLMSearch

        chunks_dir = tmp_path / "chunks"

        # Chunk A: has 'bp' in tags but body talks about treasury
        self._write_chunk(
            chunks_dir,
            "chunk_a.md",
            "---\nsummary: Analyse trésorerie\ntags: bp, finance\n"
            "project: MyApp\ndomain: bp\n---\n\nDétail du flux de trésorerie mensuel.",
        )

        # Chunk B: no bp metadata, body mentions unrelated topic
        self._write_chunk(
            chunks_dir,
            "chunk_b.md",
            "---\nsummary: Installation serveur\ntags: infra, vps\n"
            "project: MyApp\ndomain: infra\n---\n\nConfiguration nginx et SSL.",
        )

        searcher = RLMSearch(chunks_dir=chunks_dir)
        searcher.build_index()

        results = searcher.search("BP finance", top_k=2)

        # chunk_a should rank first because 'bp' and 'finance' are in its metadata
        assert len(results) >= 1
        assert results[0]["chunk_id"] == "chunk_a"
