#!/usr/bin/env python3
# ABOUTME: Reconcile the 4 RLM stores (active .md / archive .md.gz / index.json / embeddings.npz)
# ABOUTME: against the source of truth = active chunk files. Removes orphans, re-embeds missing.
"""
Reconcile RLM stores.

Over time the four stores drift apart:
- index.json keeps entries for chunks whose .md file no longer exists (purged/deleted).
- embeddings.npz keeps vectors for archived chunks (archive_chunk() doesn't call
  store.remove()) and for purged chunks (ghosts), and misses freshly added chunks.

Source of truth = the active chunk files in context/chunks/*.md.
This tool brings index.json and embeddings.npz back in sync with that truth:

  index.json    : drop entries whose .md file is gone.
  embeddings.npz: drop vectors not matching an active chunk, embed active chunks
                  that have no vector.

Safety:
- Dry-run by default. Pass --apply to write.
- Timestamped backups of index.json and embeddings.npz before any write.
- Safe while sessions are live: vectors are computed outside the lock and written
  inside VectorStore.locked() on a fresh load; index.json goes through
  locked_json_update() — never a rewrite of the snapshot read at startup.
- A healed chunk loses the `embedded: false` flag set by navigation._mark_not_embedded().
- Aborts if the embedding provider dimension != existing vectors' dimension
  (prevents mixing a 256-dim Model2Vec vector into a 384-dim FastEmbed store).

Usage:
    RLM_EMBEDDING_PROVIDER=fastembed python3 scripts/reconcile_stores.py            # dry-run
    RLM_EMBEDDING_PROVIDER=fastembed python3 scripts/reconcile_stores.py --apply
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import mcp_server.tools.fileutil as fileutil  # noqa: E402
from mcp_server.tools.embeddings import _get_cached_provider  # noqa: E402
from mcp_server.tools.vecstore import VectorStore  # noqa: E402

# Reuse the exact same YAML-aware content extraction used at embed time.
from backfill_embeddings import extract_content  # noqa: E402

# Honour RLM_CONTEXT_DIR like the server does: hardcoding ROOT/context made
# this tool silently target a stale directory once the data moved out of the
# repo (the recommended setup, so the data isn't sitting in a public checkout).
CONTEXT_DIR = fileutil.CONTEXT_DIR
INDEX_FILE = CONTEXT_DIR / "index.json"
CHUNKS_DIR = CONTEXT_DIR / "chunks"
ARCHIVE_DIR = CONTEXT_DIR / "archive"
EMBEDDINGS_FILE = CONTEXT_DIR / "embeddings.npz"


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _active_ids() -> set[str]:
    return {p.stem for p in CHUNKS_DIR.glob("*.md")}


def _archived_ids() -> set[str]:
    return {p.name[: -len(".md.gz")] for p in ARCHIVE_DIR.glob("*.md.gz")}


def main() -> None:
    apply = "--apply" in sys.argv

    active = _active_ids()
    archived = _archived_ids()

    # ---- Load index ----
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    idx_chunks = index.get("chunks", [])
    idx_keep = [c for c in idx_chunks if c.get("id") in active]
    idx_drop = [c for c in idx_chunks if c.get("id") not in active]

    # ---- Load vector store ----
    store = VectorStore()
    store.load()
    store_ids = set(store.chunk_ids)
    vec_drop = sorted(store_ids - active)  # archived + ghost vectors
    vec_add = sorted(active - store_ids)  # active chunks with no vector

    # ---- Report ----
    print("=== RÉCONCILIATION DES STORES RLM ===")
    print(f"source de vérité : {len(active)} fichiers .md actifs\n")
    print(f"index.json : {len(idx_chunks)} entrées -> garder {len(idx_keep)}, "
          f"retirer {len(idx_drop)} (fichier absent)")
    n_arch = len([i for i in vec_drop if i in archived])
    n_ghost = len(vec_drop) - n_arch
    print(f"embeddings : {len(store_ids)} vecteurs -> retirer {len(vec_drop)} "
          f"({n_arch} archivés + {n_ghost} fantômes), ajouter {len(vec_add)}")
    print(f"cible finale : {len(active)} entrées index ET {len(active)} vecteurs\n")

    if not apply:
        print("DRY-RUN. Relancer avec --apply pour exécuter.")
        if idx_drop:
            print("\nEntrées d'index à retirer (extrait) :")
            for c in idx_drop[:10]:
                print(f"  - {c.get('id')}")
        if vec_add:
            print("\nChunks à vectoriser (extrait) :")
            for cid in vec_add[:10]:
                print(f"  + {cid}")
        return

    # ---- Provider dimension guard (critical) ----
    provider = None
    if vec_add:
        provider = _get_cached_provider()
        if provider is None:
            print("ERREUR : aucun provider d'embedding disponible, impossible de "
                  "vectoriser les chunks manquants. Abort.")
            sys.exit(1)
        existing_dim = store.vectors.shape[1] if store.vectors is not None else provider.dim()
        if provider.dim() != existing_dim:
            print(f"ERREUR : dimension provider ({provider.dim()}) != vecteurs existants "
                  f"({existing_dim}). Mélange interdit. Abort. "
                  f"(as-tu bien RLM_EMBEDDING_PROVIDER=fastembed ?)")
            sys.exit(1)
        print(f"Provider : {type(provider).__name__} (dim={provider.dim()}) — OK\n")

    # ---- Embed the missing chunks first: slow, and done outside any lock ----
    new_vectors = {}
    for cid in vec_add:
        content = extract_content(CHUNKS_DIR / f"{cid}.md")
        if not content.strip():
            print(f"  SKIP {cid}: contenu vide")
            continue
        new_vectors[cid] = provider.embed([content])[0]

    # ---- Backups ----
    ts = _ts()
    idx_bak = CONTEXT_DIR / f"index.backup_{ts}.json"
    idx_bak.write_text(INDEX_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backup index    -> {idx_bak.name}")
    if EMBEDDINGS_FILE.exists():
        emb_bak = CONTEXT_DIR / f"embeddings.backup_{ts}.npz"
        emb_bak.write_bytes(EMBEDDINGS_FILE.read_bytes())
        print(f"Backup embeddings -> {emb_bak.name}")

    # ---- Apply: index (locked read-modify-write on the LIVE file) ----
    # Sessions keep writing index.json while this runs. Rewriting the snapshot
    # read at startup would silently drop every chunk they indexed meanwhile,
    # so the change is recomputed on fresh data, under the same lock they use.
    stale_at_start = {c.get("id") for c in idx_drop}
    with fileutil.locked_json_update(INDEX_FILE) as live:
        live_active = _active_ids()
        n_before = len(live.get("chunks", []))
        # Drop only what was file-less at startup AND still is: never an entry
        # that appeared (or whose file moved) during the run.
        live["chunks"] = [
            c
            for c in live.get("chunks", [])
            if not (c.get("id") in stale_at_start and c.get("id") not in live_active)
        ]
        flags_cleared = 0
        for c in live["chunks"]:
            # navigation._mark_not_embedded() flags a chunk written without a
            # vector; once healed, the flag would be a lie.
            if c.get("id") in new_vectors and c.pop("embedded", None) is False:
                flags_cleared += 1
        live["total_chunks"] = len(live["chunks"])
        n_after = len(live["chunks"])
    print(f"\nindex.json : {n_before} -> {n_after} entrées, "
          f"{flags_cleared} drapeau(x) « embedded: false » levé(s)")

    # ---- Apply: vecstore (same rule: fresh load inside the lock) ----
    with store.locked():
        store.load()
        for cid in vec_drop:
            store.remove(cid)
        for cid, vec in new_vectors.items():
            store.add(cid, vec)
        store.save()
    print(f"embeddings : retirés {len(vec_drop)}, ajoutés {len(new_vectors)} -> "
          f"{len(store.chunk_ids)} vecteurs")

    # ---- Verify (against the state NOW, not the startup snapshot) ----
    active_now = _active_ids()
    final_store = VectorStore()
    final_store.load()
    fids = set(final_store.chunk_ids)
    final_index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    n_index = len(final_index.get("chunks", []))
    ok = (fids == active_now) and (n_index == len(active_now))
    print("\n=== VÉRIFICATION ===")
    print(f"vecstore == actifs ? {'OUI' if fids == active_now else 'NON'} "
          f"({len(fids)} vs {len(active_now)})")
    print(f"index == actifs ?    {'OUI' if n_index == len(active_now) else 'NON'} "
          f"({n_index} vs {len(active_now)})")
    print("\n✅ Réconciliation réussie." if ok else "\n⚠️  Incohérence résiduelle, vérifier.")

if __name__ == "__main__":
    main()
