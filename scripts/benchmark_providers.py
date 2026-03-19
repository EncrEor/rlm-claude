#!/usr/bin/env python3
"""
Benchmark embedding providers for RLM semantic search.

Compares Model2Vec vs FastEmbed on:
- Embedding speed (per chunk and total)
- Search quality (relevance of top-k results)
- Memory footprint

Usage:
    python3 scripts/benchmark_providers.py
    python3 scripts/benchmark_providers.py --queries "business plan" "créer un module" "bug performance"
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from mcp_server.tools.vecstore import VectorStore

CONTEXT_DIR = ROOT / "context"
INDEX_FILE = CONTEXT_DIR / "index.json"
CHUNKS_DIR = CONTEXT_DIR / "chunks"

# Default test queries — mix of keyword-friendly and semantic-only
DEFAULT_QUERIES = [
    "problème de performance",
    "comment créer un module Python",
    "business plan investisseur",
    "bug page produit",
    "responsive mobile CSS",
    "recherche sémantique embeddings",
    "déploiement VPS production",
    "architecture technique du projet",
]


def extract_content(chunk_file: Path) -> str:
    """Extract content from a chunk file, skipping YAML header."""
    text = chunk_file.read_text(encoding="utf-8")
    lines = text.split("\n")
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


def load_chunks() -> list[tuple[str, str]]:
    """Load all chunks (id, content) from index."""
    with open(INDEX_FILE, encoding="utf-8") as f:
        index = json.load(f)

    chunks = []
    for info in index["chunks"]:
        chunk_file = CONTEXT_DIR / info["file"]
        if chunk_file.exists():
            content = extract_content(chunk_file)
            if content.strip():
                chunks.append((info["id"], content))
    return chunks


def try_load_provider(name: str):
    """Try to instantiate a provider by name."""
    try:
        if name == "model2vec":
            from mcp_server.tools.embeddings import Model2VecProvider
            return Model2VecProvider()
        elif name == "fastembed":
            from mcp_server.tools.embeddings import FastEmbedProvider
            return FastEmbedProvider()
    except (ImportError, Exception) as e:
        print(f"  {name}: NOT AVAILABLE ({e})")
        return None


def benchmark_provider(provider, provider_name: str, chunks: list, queries: list[str]):
    """Run full benchmark for one provider."""
    print(f"\n{'=' * 60}")
    print(f"  {provider_name} (dim={provider.dim()})")
    print(f"{'=' * 60}")

    # --- Embedding speed ---
    contents = [c for _, c in chunks]
    chunk_ids = [cid for cid, _ in chunks]

    print(f"\nEmbedding {len(chunks)} chunks...")
    t0 = time.perf_counter()
    vectors = provider.embed(contents)
    t_embed = time.perf_counter() - t0

    print(f"  Total: {t_embed:.2f}s")
    print(f"  Per chunk: {t_embed / len(chunks) * 1000:.1f}ms")
    print(f"  Throughput: {len(chunks) / t_embed:.0f} chunks/s")

    # Memory footprint
    mem_mb = vectors.nbytes / (1024 * 1024)
    print(f"  Memory: {mem_mb:.2f} MB ({vectors.shape})")

    # --- Build vector store ---
    store = VectorStore(path=ROOT / f"context/bench_{provider_name}.npz")
    for i, cid in enumerate(chunk_ids):
        store.add(cid, vectors[i])

    # --- Search quality ---
    print(f"\nSearch results ({len(queries)} queries):")
    print(f"  {'Query':<40} {'#1 Result':<35} {'Score':<6}")
    print(f"  {'-' * 40} {'-' * 35} {'-' * 6}")

    # Load summaries for display
    with open(INDEX_FILE, encoding="utf-8") as f:
        index = json.load(f)
    summaries = {c["id"]: c.get("summary", "")[:32] for c in index["chunks"]}

    query_times = []
    results_per_query = {}

    for query in queries:
        t0 = time.perf_counter()
        qvec = provider.embed([query])[0]
        hits = store.search(qvec, top_k=5)
        t_search = time.perf_counter() - t0
        query_times.append(t_search)

        top_id = hits[0][0] if hits else "(none)"
        top_score = hits[0][1] if hits else 0
        top_summary = summaries.get(top_id, "")[:32]
        print(f"  {query:<40} {top_summary:<35} {top_score:.3f}")

        results_per_query[query] = [(cid, score) for cid, score in hits]

    avg_search = sum(query_times) / len(query_times) * 1000
    print(f"\n  Avg search time: {avg_search:.1f}ms/query")

    # Cleanup temp file
    bench_file = ROOT / f"context/bench_{provider_name}.npz"
    if bench_file.exists():
        bench_file.unlink()

    return {
        "embed_time": t_embed,
        "per_chunk_ms": t_embed / len(chunks) * 1000,
        "mem_mb": mem_mb,
        "avg_search_ms": avg_search,
        "results": results_per_query,
    }


def compare_results(results: dict, queries: list[str]):
    """Compare search results between providers."""
    provider_names = list(results.keys())
    if len(provider_names) < 2:
        return

    print(f"\n{'=' * 60}")
    print("  COMPARISON")
    print(f"{'=' * 60}")

    # Speed comparison
    p1, p2 = provider_names[0], provider_names[1]
    r1, r2 = results[p1], results[p2]

    print(f"\n  {'Metric':<25} {p1:<15} {p2:<15} {'Winner':<10}")
    print(f"  {'-' * 25} {'-' * 15} {'-' * 15} {'-' * 10}")

    embed_winner = p1 if r1["embed_time"] < r2["embed_time"] else p2
    print(f"  {'Embed time':<25} {r1['embed_time']:.2f}s{'':<9} {r2['embed_time']:.2f}s{'':<9} {embed_winner}")

    search_winner = p1 if r1["avg_search_ms"] < r2["avg_search_ms"] else p2
    print(f"  {'Search time':<25} {r1['avg_search_ms']:.1f}ms{'':<9} {r2['avg_search_ms']:.1f}ms{'':<9} {search_winner}")

    mem_winner = p1 if r1["mem_mb"] < r2["mem_mb"] else p2
    print(f"  {'Memory':<25} {r1['mem_mb']:.1f}MB{'':<10} {r2['mem_mb']:.1f}MB{'':<10} {mem_winner}")

    # Result overlap per query
    print(f"\n  Top-5 overlap per query:")
    for query in queries:
        ids1 = {cid for cid, _ in r1["results"].get(query, [])}
        ids2 = {cid for cid, _ in r2["results"].get(query, [])}
        overlap = len(ids1 & ids2)
        print(f"    {query:<40} {overlap}/5 common")

    # Different #1 results
    print(f"\n  Queries where #1 result differs:")
    any_diff = False
    for query in queries:
        hits1 = r1["results"].get(query, [])
        hits2 = r2["results"].get(query, [])
        top1 = hits1[0][0] if hits1 else None
        top2 = hits2[0][0] if hits2 else None
        if top1 != top2:
            any_diff = True
            print(f"    {query}")
            print(f"      {p1}: {top1}")
            print(f"      {p2}: {top2}")
    if not any_diff:
        print(f"    (none — same #1 for all queries)")


def main():
    # Parse custom queries from args
    queries = DEFAULT_QUERIES
    if "--queries" in sys.argv:
        idx = sys.argv.index("--queries")
        queries = sys.argv[idx + 1:]
        if not queries:
            print("ERROR: --queries requires at least one query string")
            sys.exit(1)

    print("RLM Semantic Search Benchmark")
    print(f"Chunks: {INDEX_FILE}")
    print(f"Queries: {len(queries)}")

    # Load chunks
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    # Try both providers
    providers = {}
    for name in ["model2vec", "fastembed"]:
        print(f"\nLoading {name}...")
        p = try_load_provider(name)
        if p:
            providers[name] = p

    if not providers:
        print("\nERROR: No providers available. Install at least one:")
        print("  pip install mcp-rlm-server[semantic]            # model2vec")
        print("  pip install mcp-rlm-server[semantic-fastembed]   # fastembed")
        sys.exit(1)

    # Benchmark each provider
    results = {}
    for name, provider in providers.items():
        results[name] = benchmark_provider(provider, name, chunks, queries)

    # Compare if both available
    if len(results) >= 2:
        compare_results(results, queries)
    elif len(results) == 1:
        name = list(results.keys())[0]
        other = "fastembed" if name == "model2vec" else "model2vec"
        print(f"\n  To compare, install the other provider:")
        print(f"  pip install mcp-rlm-server[semantic-{other}]" if other == "fastembed"
              else f"  pip install mcp-rlm-server[semantic]")

    print(f"\n{'=' * 60}")
    print("  Done.")


if __name__ == "__main__":
    main()
