"""
RLM BM25 Search - Fast semantic-free search for chunks

This module provides BM25-based search for RLM chunks, following the
MIT RLM paper approach (no embeddings, keyword-based ranking).

Uses BM25S library (500x faster than rank_bm25) for efficient scoring.

Phase 5.1 implementation.
Phase 5.5c: Added project/domain filtering.
Phase 8: Hybrid search (BM25 + cosine similarity) when semantic deps available.
"""

import json
import re
from pathlib import Path

# BM25S import with fallback
try:
    import bm25s

    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

from .fileutil import CONTEXT_DIR
from .tokenizer_fr import tokenize_fr

CHUNKS_DIR = CONTEXT_DIR / "chunks"


class RLMSearch:
    """
    BM25-based search engine for RLM chunks.

    Features:
    - French/English tokenization
    - Fast BM25S scoring
    - Returns ranked results with scores
    """

    def __init__(self, chunks_dir: Path | None = None):
        """
        Initialize the search engine.

        Args:
            chunks_dir: Path to chunks directory (default: RLM/context/chunks)
        """
        self.chunks_dir = chunks_dir or CHUNKS_DIR
        self.retriever = None
        self.chunk_ids = []
        self.chunk_summaries = {}

    def _extract_content(self, chunk_file: Path) -> str:
        """
        Extract content from a chunk file, skipping YAML header.

        Phase 8.1: Prepends summary, tags, project, and domain from the
        YAML header so BM25 can match on metadata keywords too.

        Args:
            chunk_file: Path to the chunk .md file

        Returns:
            Content string with metadata keywords prepended
        """
        with open(chunk_file, encoding="utf-8") as f:
            content = f.read()

        # Skip YAML header (between --- markers)
        lines = content.split("\n")
        content_start = 0
        in_header = False

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_header:
                    in_header = True
                else:
                    content_start = i + 1
                    break

        body = "\n".join(lines[content_start:])

        # Phase 8.1: Prepend metadata to boost keyword matching
        meta_parts = []
        for line in lines[:content_start]:
            if line.startswith("summary:"):
                val = line.split(":", 1)[1].strip()
                if val:
                    meta_parts.append(val)
            elif line.startswith("tags:"):
                val = line.split(":", 1)[1].strip().replace(",", " ")
                if val:
                    meta_parts.append(val)
            elif line.startswith("project:"):
                val = line.split(":", 1)[1].strip()
                if val:
                    meta_parts.append(val)
            elif line.startswith("domain:"):
                val = line.split(":", 1)[1].strip()
                if val:
                    meta_parts.append(val)

        if meta_parts:
            body = " ".join(meta_parts) + "\n" + body

        return body

    def _extract_summary(self, chunk_file: Path) -> str:
        """
        Extract summary from chunk YAML header.

        Args:
            chunk_file: Path to the chunk .md file

        Returns:
            Summary string or empty string
        """
        with open(chunk_file, encoding="utf-8") as f:
            content = f.read()

        # Find summary in YAML header
        match = re.search(r"^summary:\s*(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def build_index(self, include_insights: bool = True) -> int:
        """
        Build BM25 index from all chunks and optionally insights.

        Reads all .md files in chunks directory, tokenizes content,
        and builds the BM25 index. When include_insights is True,
        also indexes insights from session_memory.

        Args:
            include_insights: Whether to index insights too (default: True)

        Returns:
            Number of documents indexed
        """
        if not BM25_AVAILABLE:
            raise ImportError("bm25s is required for search. Install with: pip install bm25s")

        documents = []
        self.chunk_ids = []
        self.chunk_summaries = {}

        # Collect all chunks
        chunk_files = sorted(self.chunks_dir.glob("*.md"))

        for chunk_file in chunk_files:
            content = self._extract_content(chunk_file)
            tokens = tokenize_fr(content)

            if tokens:  # Only index non-empty chunks
                documents.append(tokens)
                chunk_id = chunk_file.stem
                self.chunk_ids.append(chunk_id)
                self.chunk_summaries[chunk_id] = self._extract_summary(chunk_file)

        # Index insights from session_memory
        if include_insights:
            from .memory import MEMORY_FILE, _load_memory

            if MEMORY_FILE.exists():
                memory = _load_memory()
                for insight in memory.get("insights", []):
                    content = insight["content"]
                    if insight.get("tags"):
                        content += " " + " ".join(insight["tags"])
                    tokens = tokenize_fr(content)
                    if tokens:
                        documents.append(tokens)
                        iid = f"insight:{insight['id']}"
                        self.chunk_ids.append(iid)
                        self.chunk_summaries[iid] = insight["content"][:80]

        if not documents:
            return 0

        # Build BM25 index
        self.retriever = bm25s.BM25()
        self.retriever.index(documents)

        return len(documents)

    def search(self, query: str, top_k: int = 5, include_insights: bool = True) -> list[dict]:
        """
        Search chunks (and optionally insights) using BM25 ranking.

        Args:
            query: Natural language search query
            top_k: Maximum number of results to return
            include_insights: Whether to include insights in search (default: True)

        Returns:
            List of dicts with chunk_id, type, score, and summary
        """
        if not BM25_AVAILABLE:
            raise ImportError("bm25s is required for search. Install with: pip install bm25s")

        # Build index if not already done
        if self.retriever is None:
            indexed = self.build_index(include_insights=include_insights)
            if indexed == 0:
                return []

        # Tokenize query
        query_tokens = tokenize_fr(query)

        if not query_tokens:
            return []

        # BM25S retrieve
        # Note: bm25s.retrieve expects 2D array for queries
        results, scores = self.retriever.retrieve([query_tokens], k=min(top_k, len(self.chunk_ids)))

        # Format results
        output = []
        for _i, (idx, score) in enumerate(zip(results[0], scores[0], strict=False)):
            if score > 0:  # Only include positive scores
                chunk_id = self.chunk_ids[idx]
                type_ = "insight" if chunk_id.startswith("insight:") else "chunk"
                output.append(
                    {
                        "chunk_id": chunk_id,
                        "type": type_,
                        "score": float(score),
                        "summary": self.chunk_summaries.get(chunk_id, ""),
                    }
                )

        return output


# =============================================================================
# PHASE 8: Hybrid Search (BM25 + Cosine Similarity)
# =============================================================================

HYBRID_ALPHA = 0.6  # Weight for semantic score (0.6 semantic, 0.4 BM25)


def _normalize_bm25_scores(results: list[dict]) -> list[dict]:
    """Normalize BM25 scores to [0, 1] range using min-max scaling.

    Adds a 'score_norm' field to each result dict.

    Args:
        results: List of BM25 result dicts with 'score' field

    Returns:
        Same list with 'score_norm' added to each dict
    """
    if not results:
        return results

    scores = [r["score"] for r in results]
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score

    for r in results:
        if score_range > 0:
            r["score_norm"] = (r["score"] - min_score) / score_range
        else:
            r["score_norm"] = 1.0  # All scores equal → all get 1.0

    return results


def _hybrid_search(query: str, top_k: int) -> list[tuple[str, float]] | None:
    """Perform semantic vector search if available.

    Returns None if semantic search is not available (deps missing),
    allowing the caller to fall back to BM25-only.

    Args:
        query: Natural language search query
        top_k: Maximum number of results

    Returns:
        List of (chunk_id, score) tuples with scores in [0,1], or None
    """
    try:
        from .embeddings import _get_cached_provider
        from .vecstore import VectorStore

        provider = _get_cached_provider()
        if provider is None:
            return None

        store = VectorStore()
        if not store.load():
            return None

        query_vec = provider.embed([query])[0]
        return store.search(query_vec, top_k=top_k)
    except Exception:
        return None


def search(
    query: str,
    limit: int = 5,
    project: str = None,
    domain: str = None,
    date_from: str = None,
    date_to: str = None,
    entity: str = None,
    include_insights: bool = True,
) -> dict:
    """
    Convenience function for searching chunks.

    Phase 5.5c: Supports filtering by project and domain.
    Phase 7.1: Supports temporal filtering by date range.
    Phase 7.2: Supports filtering by entity.

    Args:
        query: Natural language search query
        limit: Maximum results (default: 5)
        project: Filter by project name (Phase 5.5c)
        domain: Filter by domain (Phase 5.5c)
        date_from: Start date inclusive, YYYY-MM-DD (Phase 7.1)
        date_to: End date inclusive, YYYY-MM-DD (Phase 7.1)
        entity: Filter by entity name, case-insensitive substring (Phase 7.2)

    Returns:
        Dictionary with search results
    """
    from .navigation import _chunk_in_date_range, _entity_matches

    searcher = RLMSearch()

    try:
        # Get more results than needed for filtering
        results = searcher.search(query, top_k=limit * 3, include_insights=include_insights)
    except ImportError as e:
        return {"status": "error", "message": str(e), "results": []}

    # Phase 8: Hybrid fusion if semantic available
    semantic_hits = _hybrid_search(query, limit * 3)
    if semantic_hits is not None and results:
        results = _normalize_bm25_scores(results)
        bm25_map = {r["chunk_id"]: r.get("score_norm", 0) for r in results}
        sem_map = dict(semantic_hits)
        all_ids = set(bm25_map) | set(sem_map)
        fused = []
        for cid in all_ids:
            score = (1 - HYBRID_ALPHA) * bm25_map.get(cid, 0) + HYBRID_ALPHA * sem_map.get(cid, 0)
            fused.append(
                {
                    "chunk_id": cid,
                    "score": score,
                    "summary": searcher.chunk_summaries.get(cid, ""),
                }
            )
        fused.sort(key=lambda x: x["score"], reverse=True)
        results = fused
    elif semantic_hits is not None:
        # BM25 returned nothing but semantic has results
        results = [
            {"chunk_id": cid, "score": s, "summary": searcher.chunk_summaries.get(cid, "")}
            for cid, s in semantic_hits
        ]

    # Phase 5.5c + 7.1 + 7.2: Filter by project/domain/date/entity if specified
    has_filters = project or domain or date_from or date_to or entity
    if has_filters:
        # Load index to get chunk metadata
        index_file = CONTEXT_DIR / "index.json"
        if index_file.exists():
            with open(index_file, encoding="utf-8") as f:
                index = json.load(f)

            # Build lookup for metadata
            chunk_meta = {c["id"]: c for c in index.get("chunks", [])}

            filtered = []
            for r in results:
                meta = chunk_meta.get(r["chunk_id"], {})
                # Phase 7.1: Temporal filter
                if not _chunk_in_date_range(meta, date_from, date_to):
                    continue
                if project and meta.get("project") != project:
                    continue
                if domain and meta.get("domain") != domain:
                    continue
                # Phase 7.2: Entity filter
                if entity and not _entity_matches(meta, entity):
                    continue
                filtered.append(r)
            results = filtered

    # Apply final limit
    results = results[:limit]

    # Surfacing a chunk counts as using it. Without this, retention reads
    # access_count == 0 on chunks search returns every week and archives them.
    try:
        from .navigation import _increment_access_many

        _increment_access_many(
            [r["chunk_id"] for r in results if r.get("type", "chunk") != "insight"]
        )
    except Exception:
        pass  # Bookkeeping must never break a search

    # Build filters summary
    active_filters = {}
    if project:
        active_filters["project"] = project
    if domain:
        active_filters["domain"] = domain
    if date_from:
        active_filters["date_from"] = date_from
    if date_to:
        active_filters["date_to"] = date_to
    if entity:
        active_filters["entity"] = entity

    # Archived chunks live outside the active index: surface them by metadata
    # so they stay reachable (rlm_peek restores on access) instead of being
    # findable only by someone who already knows the ID.
    archived = []
    try:
        from .retention import search_archives

        archived = search_archives(query, limit=3)
    except Exception:
        pass

    response = {
        "status": "success",
        "query": query,
        "result_count": len(results),
        "filters": active_filters if active_filters else None,
        "results": results,
    }
    if archived:
        response["archived_matches"] = archived
        response["archived_hint"] = "Archived chunks — rlm_peek(chunk_id) restores them in full."
    return response


# Quick test when run directly
if __name__ == "__main__":
    print("Testing RLM BM25 Search:")

    if not BM25_AVAILABLE:
        print("  ERROR: bm25s not installed. Run: pip install bm25s")
    else:
        searcher = RLMSearch()
        indexed = searcher.build_index()
        print(f"  Indexed {indexed} chunks")

        if indexed > 0:
            test_queries = [
                "Phase 4 RLM",
                "business plan",
                "tokenization francaise",
            ]

            for query in test_queries:
                results = searcher.search(query, top_k=3)
                print(f"\n  Query: '{query}'")
                for r in results:
                    print(f"    - {r['chunk_id']}: {r['score']:.2f} ({r['summary'][:40]}...)")
