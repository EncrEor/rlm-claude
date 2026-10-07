#!/usr/bin/env python3
# ABOUTME: Permanently delete the archives a review has cleared for purge (purge_ok: true in the
# ABOUTME: archive index). Dry-run by default; --apply requires --expect N; held archives are never touched.
"""
Purge reviewed archives.

`rlm_retention_run(purge=True)` purges by age and use. This tool purges by
*review*: only archive entries carrying `purge_ok: true` — written by
`scripts/retire_chunks.py` from a reviewed manifest — and, when `--review` is
given, only those of that review. Entries on hold (`purge_ok: false`, tag
`keep`) and entries never reviewed are left alone whatever their age.

A purge is final: the content is gone, only metadata stays in purge_log.json.
Get an explicit go from the person who owns the memory before running --apply.

Usage:
    python3 scripts/purge_reviewed.py                                # dry-run, all reviews
    python3 scripts/purge_reviewed.py --review "label"               # dry-run, one review
    python3 scripts/purge_reviewed.py --review "label" --apply --expect 42
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import mcp_server.tools.retention as retention  # noqa: E402


def candidates(review: str | None) -> list[dict]:
    """Archive entries cleared for purge (and not immune), optionally of one review."""
    out = []
    for a in retention._load_archive_index().get("archives", []):
        if a.get("purge_ok") is not True or retention.is_immune(a):
            continue
        if review and a.get("review") != review:
            continue
        out.append(a)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge archives cleared by a review.")
    parser.add_argument("--review", help="only entries of this review label")
    parser.add_argument("--apply", action="store_true", help="delete (default: dry-run)")
    parser.add_argument("--expect", type=int, help="number of archives the dry-run announced")
    args = parser.parse_args(argv)

    cands = candidates(args.review)
    print(f"Context          : {retention.CONTEXT_DIR}")
    print(f"Cleared for purge: {len(cands)}" + (f" (review: {args.review})" if args.review else ""))
    for a in cands[:10]:
        print(f"  {a.get('id')}  {str(a.get('summary', ''))[:70]}")
    if len(cands) > 10:
        print(f"  ... and {len(cands) - 10} more")

    if not args.apply:
        print(f"\nDry-run. To delete for good: --apply --expect {len(cands)}")
        return 0
    if args.expect is None or args.expect != len(cands):
        print(f"ABORT — expected {args.expect}, found {len(cands)}. Nothing deleted.")
        return 2

    purged, errors = [], []
    for a in cands:
        result = retention.purge_chunk(a["id"])
        (purged if result.get("status") == "purged" else errors).append(
            result.get("chunk_id") or f"{a['id']}: {result.get('message')}"
        )
    print(f"\nPurged           : {len(purged)}")
    for e in errors:
        print(f"  PROBLEM {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
