#!/usr/bin/env python3
"""
Backfill entity extraction on existing chunks.

Phase 7.2 added automatic entity extraction at chunk creation time,
but ~100 existing chunks don't have entities yet. This script
retroactively extracts and stores entities for all chunks.

Usage:
    python3 scripts/backfill_entities.py [--dry-run]
"""

import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_server.tools.navigation import _extract_entities


CONTEXT_DIR = ROOT / "context"
INDEX_FILE = CONTEXT_DIR / "index.json"
CHUNKS_DIR = CONTEXT_DIR / "chunks"


def parse_chunk_file(filepath: Path) -> tuple[dict, str]:
    """Parse a chunk .md file into (frontmatter_lines, content).

    Returns:
        Tuple of (frontmatter_dict with raw lines, content after frontmatter)
    """
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    # Find end of frontmatter
    end_idx = text.index("---", 3)
    frontmatter_raw = text[4:end_idx].strip()
    content = text[end_idx + 3:].strip()

    return frontmatter_raw, content


def rebuild_frontmatter(original_fm: str, entities: dict) -> str:
    """Insert or replace entities section in YAML frontmatter."""
    lines = original_fm.split("\n")
    result_lines = []
    skip_entity_block = False

    for line in lines:
        # Skip existing entities block
        if line.startswith("entities:"):
            skip_entity_block = True
            continue
        if skip_entity_block:
            if line.startswith("  ") and not line.startswith("  ("):
                # Still in entities block (indented subfields)
                continue
            elif line.strip() == "(none)":
                continue
            else:
                skip_entity_block = False

        result_lines.append(line)

    # Insert entities before project/ticket/domain or at end
    insert_idx = len(result_lines)
    for i, line in enumerate(result_lines):
        if line.startswith("project:") or line.startswith("ticket:") or line.startswith("domain:"):
            insert_idx = i
            break

    # Build entities YAML
    entities_lines = ["entities:"]
    has_any = False
    for etype, evals in entities.items():
        if evals:
            entities_lines.append(f"  {etype}: {', '.join(evals)}")
            has_any = True
    if not has_any:
        entities_lines.append("  (none)")

    result_lines[insert_idx:insert_idx] = entities_lines

    return "\n".join(result_lines)


def main():
    dry_run = "--dry-run" in sys.argv

    # Load index
    with open(INDEX_FILE, encoding="utf-8") as f:
        index = json.load(f)

    chunks = index["chunks"]
    updated = 0
    skipped = 0
    errors = 0
    total_entities = 0

    for chunk_info in chunks:
        chunk_id = chunk_info["id"]
        chunk_file = CONTEXT_DIR / chunk_info["file"]

        # Skip if already has entities
        if "entities" in chunk_info and chunk_info["entities"]:
            skipped += 1
            continue

        if not chunk_file.exists():
            print(f"  SKIP {chunk_id}: file not found")
            errors += 1
            continue

        # Parse chunk file
        try:
            fm_raw, content = parse_chunk_file(chunk_file)
        except Exception as e:
            print(f"  ERROR {chunk_id}: {e}")
            errors += 1
            continue

        if not content:
            # Empty content, set empty entities
            entities = {"files": [], "versions": [], "modules": [], "tickets": [], "functions": []}
        else:
            entities = _extract_entities(content)

        # Count entities
        n_entities = sum(len(v) for v in entities.values())
        total_entities += n_entities

        if dry_run:
            if n_entities > 0:
                print(f"  {chunk_id}: {n_entities} entities → {entities}")
            else:
                print(f"  {chunk_id}: (no entities)")
            updated += 1
            continue

        # Update index.json entry
        chunk_info["entities"] = entities

        # Update .md file frontmatter
        if isinstance(fm_raw, str) and fm_raw:
            new_fm = rebuild_frontmatter(fm_raw, entities)
            # Reconstruct file
            new_text = f"---\n{new_fm}\n---\n\n{content}\n"
            chunk_file.write_text(new_text, encoding="utf-8")

        updated += 1

    # Save index.json
    if not dry_run and updated > 0:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            f.write("\n")

    # Summary
    mode = "[DRY RUN] " if dry_run else ""
    print(f"\n{mode}Backfill complete:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already had entities): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total entities extracted: {total_entities}")


if __name__ == "__main__":
    main()
