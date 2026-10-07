#!/usr/bin/env python3
# ABOUTME: Retire a reviewed list of chunks from active memory (archived, never deleted), recording why.
# ABOUTME: Manifest-driven, dry-run by default, idempotent, aborts on an unknown id or a count mismatch.
"""
Retire chunks that a review found obsolete.

`rlm_retention_run()` archives by age and use. This tool archives by *review*: a
manifest lists the chunks judged obsolete and, for each one, why, what supersedes
it, and whether it is cleared for a later purge.

Manifest (JSON):

    {
      "label": "what this review was",
      "summary_prefix": "[OBSOLETE → {superseded_by}] ",      (optional)
      "chunks": [
        {"id": "2026-02-08_Project_003_infra",
         "reason": "state replaced by the 19 July incident fix",
         "superseded_by": "2026-07-19_Project_008_infra",
         "purge_ok": true},
        {"id": "2026-03-02_Project_001",
         "reason": "plan abandoned",
         "superseded_by": "",
         "purge_ok": false,
         "hold_reason": "follow-up lives in a CRM we could not read"}
      ]
    }

For each chunk:
- `archive_chunk()` compresses it to archive/ and takes it out of the index and
  of the vector store. `rlm_peek(id)` restores it; nothing is deleted.
- The archive entry is annotated: `archive_reason`, `superseded_by`, `purge_ok`,
  `review`, `retired_at`.
- The summary gets a prefix. `rlm_search` lists archived matches by summary, so a
  reader who meets the archive learns it is obsolete and where the current state
  is, instead of restoring it as if it were true.
- `purge_ok: false` adds the protected tag `keep`: `get_purge_candidates()` never
  returns that archive, whatever its age. A later run with `purge_ok: true`
  removes the tag this tool added (never one the chunk already had).

Safety:
- Dry-run by default. `--apply` writes and requires `--expect N`, the number of
  chunks the dry-run announced; any other count aborts before the first write.
- An id that is neither active nor archived aborts the whole run.
- Re-running is safe: chunks already archived are skipped, annotations are
  re-applied from the manifest.
- Safe while sessions are live: every index write goes through the writers' lock.

Usage:
    python3 scripts/retire_chunks.py review.json                    # dry-run
    python3 scripts/retire_chunks.py review.json --apply --expect 42
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import mcp_server.tools.retention as retention  # noqa: E402
from mcp_server.tools.fileutil import locked_json_update  # noqa: E402

HOLD_TAG = "keep"  # in retention.PROTECTED_TAGS: an archive carrying it is never purged
DEFAULT_PREFIX = "[OBSOLETE → {superseded_by}] "
DEFAULT_PREFIX_BARE = "[OBSOLETE] "


class ManifestError(ValueError):
    """The manifest cannot be acted on."""


def load_manifest(path: Path) -> dict:
    """Read and validate a manifest. Raises ManifestError on anything ambiguous."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f"unreadable manifest: {e}") from e

    entries = manifest.get("chunks")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest has no 'chunks' list")
    if not str(manifest.get("label", "")).strip():
        raise ManifestError("manifest has no 'label'")

    seen = set()
    for e in entries:
        cid = e.get("id")
        if not isinstance(cid, str) or not retention.validate_chunk_id(cid):
            raise ManifestError(f"invalid chunk id: {cid!r}")
        if cid in seen:
            raise ManifestError(f"chunk listed twice: {cid}")
        seen.add(cid)
        if not str(e.get("reason", "")).strip():
            raise ManifestError(f"{cid}: no 'reason'")
        if not isinstance(e.get("purge_ok"), bool):
            raise ManifestError(f"{cid}: 'purge_ok' must be true or false")
        if not e["purge_ok"] and not str(e.get("hold_reason", "")).strip():
            raise ManifestError(f"{cid}: purge_ok is false but no 'hold_reason'")
    return manifest


def plan(manifest: dict) -> dict:
    """Sort the manifest ids by what would happen to them. Reads only."""
    to_archive, already, unknown = [], [], []
    for e in manifest["chunks"]:
        cid = e["id"]
        if (retention.CHUNKS_DIR / f"{cid}.md").exists():
            to_archive.append(cid)
        elif (retention.ARCHIVE_DIR / f"{cid}.md.gz").exists():
            already.append(cid)
        else:
            unknown.append(cid)
    return {"to_archive": to_archive, "already_archived": already, "unknown": unknown}


def _prefix(manifest: dict, entry: dict) -> str:
    superseded_by = str(entry.get("superseded_by") or "").strip()
    if not superseded_by:
        return manifest.get("summary_prefix_bare", DEFAULT_PREFIX_BARE)
    return manifest.get("summary_prefix", DEFAULT_PREFIX).format(superseded_by=superseded_by)


def annotate(manifest: dict) -> list[str]:
    """Write the review onto the archive entries. Returns the ids it could not find."""
    by_id = {e["id"]: e for e in manifest["chunks"]}
    found = set()
    with locked_json_update(
        retention.ARCHIVE_INDEX_FILE, default=retention._empty_archive_index()
    ) as archive_index:
        for a in archive_index.get("archives", []):
            e = by_id.get(a.get("id"))
            if e is None:
                continue
            found.add(a["id"])
            a["archive_reason"] = str(e["reason"]).strip()
            a["superseded_by"] = str(e.get("superseded_by") or "").strip()
            a["purge_ok"] = e["purge_ok"]
            a["review"] = manifest["label"]
            a.setdefault("retired_at", datetime.now().isoformat())

            a.setdefault("summary_original", a.get("summary", ""))
            a["summary"] = _prefix(manifest, e) + a["summary_original"]

            tags = list(a.get("tags") or [])
            has_hold = HOLD_TAG in {t.lower() for t in tags}
            if not e["purge_ok"]:
                a["purge_hold"] = str(e["hold_reason"]).strip()
                if not has_hold:
                    tags.append(HOLD_TAG)
                    a["hold_tag_added"] = True
            else:
                a.pop("purge_hold", None)
                if a.pop("hold_tag_added", False):
                    tags = [t for t in tags if t.lower() != HOLD_TAG]
            a["tags"] = tags
    return [cid for cid in by_id if cid not in found]


def apply(manifest: dict, planned: dict) -> dict:
    """Archive what the plan says, then annotate every manifest entry."""
    archived, errors = [], []
    for cid in planned["to_archive"]:
        result = retention.archive_chunk(cid)
        if result.get("status") == "archived":
            archived.append(cid)
        else:
            errors.append(f"{cid}: {result.get('message', 'archive failed')}")
    for cid in annotate(manifest):
        errors.append(f"{cid}: no archive entry to annotate")
    return {"archived": archived, "errors": errors}


def verify(manifest: dict) -> list[str]:
    """Check the end state of every manifest id. Returns the problems found."""
    problems = []
    active_ids = {c.get("id") for c in retention._load_index().get("chunks", [])}
    archives = {a.get("id"): a for a in retention._load_archive_index().get("archives", [])}
    purgeable = {c["id"] for c in retention.get_purge_candidates()}

    vector_ids = None
    try:
        from mcp_server.tools.vecstore import VectorStore

        store = VectorStore()
        if store.load():
            vector_ids = {str(i) for i in store.chunk_ids}
    except Exception:
        vector_ids = None  # semantic search is optional

    for e in manifest["chunks"]:
        cid = e["id"]
        if (retention.CHUNKS_DIR / f"{cid}.md").exists():
            problems.append(f"{cid}: still in active storage")
        if not (retention.ARCHIVE_DIR / f"{cid}.md.gz").exists():
            problems.append(f"{cid}: no archive file")
        if cid in active_ids:
            problems.append(f"{cid}: still in index.json")
        entry = archives.get(cid)
        if entry is None:
            problems.append(f"{cid}: missing from archive_index.json")
        elif not entry.get("archive_reason"):
            problems.append(f"{cid}: archive entry not annotated")
        elif not e["purge_ok"] and not retention.is_immune(entry):
            problems.append(f"{cid}: purge hold not effective")
        if not e["purge_ok"] and cid in purgeable:
            problems.append(f"{cid}: on hold but listed as purge candidate")
        if vector_ids is not None and cid in vector_ids:
            problems.append(f"{cid}: vector still in the semantic store")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retire reviewed chunks (archive, never delete).")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    parser.add_argument("--expect", type=int, help="number of chunks the dry-run announced")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as e:
        print(f"ABORT — {e}")
        return 2

    planned = plan(manifest)
    n_hold = sum(1 for e in manifest["chunks"] if not e["purge_ok"])
    print(f"Review           : {manifest['label']}")
    print(f"Context          : {retention.CONTEXT_DIR}")
    print(f"In manifest      : {len(manifest['chunks'])}")
    print(f"  to archive     : {len(planned['to_archive'])}")
    print(f"  already archived: {len(planned['already_archived'])}")
    print(f"  unknown        : {len(planned['unknown'])}")
    print(f"Purge hold (keep): {n_hold}   cleared for purge: {len(manifest['chunks']) - n_hold}")

    if planned["unknown"]:
        for cid in planned["unknown"]:
            print(f"  unknown id: {cid}")
        print("ABORT — ids that are neither active nor archived. Nothing written.")
        return 2

    if not args.apply:
        print(f"\nDry-run. To write: --apply --expect {len(planned['to_archive'])}")
        return 0

    if args.expect is None or args.expect != len(planned["to_archive"]):
        print(
            f"ABORT — expected {args.expect}, found {len(planned['to_archive'])} to archive. "
            "Nothing written."
        )
        return 2

    done = apply(manifest, planned)
    problems = verify(manifest)
    print(f"\nArchived now     : {len(done['archived'])}")
    for line in done["errors"] + problems:
        print(f"  PROBLEM {line}")
    if done["errors"] or problems:
        print("DONE WITH PROBLEMS — see above.")
        return 1
    print(
        f"Verified         : {len(manifest['chunks'])} chunks archived, annotated, out of search."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
