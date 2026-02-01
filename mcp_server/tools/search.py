"""
RLM BM25 Search - Fast semantic-free search for chunks

This module provides BM25-based search for RLM chunks, following the
MIT RLM paper approach (no embeddings, keyword-based ranking).

Uses BM25S library (500x faster than rank_bm25) for efficient scoring.

Phase 5.1 implementation.
Phase 5.5c: Added project/domain filtering.
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

from .tokenizer_fr import tokenize_fr

# Paths (same as navigation.py)
CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"
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

        Args:
            chunk_file: Path to the chunk .md file

        Returns:
            Content string without YAML header
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

        return "\n".join(lines[content_start:])

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

    def build_index(self) -> int:
        """
        Build BM25 index from all chunks.

        Reads all .md files in chunks directory, tokenizes content,
        and builds the BM25 index.

        Returns:
            Number of chunks indexed
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

        if not documents:
            return 0

        # Build BM25 index
        self.retriever = bm25s.BM25()
        self.retriever.index(documents)

        return len(documents)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search chunks using BM25 ranking.

        Args:
            query: Natural language search query
            top_k: Maximum number of results to return

        Returns:
            List of dicts with chunk_id, score, and summary
        """
        if not BM25_AVAILABLE:
            raise ImportError("bm25s is required for search. Install with: pip install bm25s")

        # Build index if not already done
        if self.retriever is None:
            indexed = self.build_index()
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
                output.append(
                    {
                        "chunk_id": chunk_id,
                        "score": float(score),
                        "summary": self.chunk_summaries.get(chunk_id, ""),
                    }
                )

        return output


def search(
    query: str,
    limit: int = 5,
    project: str = None,
    domain: str = None,
    date_from: str = None,
    date_to: str = None,
    entity: str = None,
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
        results = searcher.search(query, top_k=limit * 3)
    except ImportError as e:
        return {"status": "error", "message": str(e), "results": []}

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

    return {
        "status": "success",
        "query": query,
        "result_count": len(results),
        "filters": active_filters if active_filters else None,
        "results": results,
    }


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
