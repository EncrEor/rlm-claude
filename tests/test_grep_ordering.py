"""
Tests for grep recency ordering.

Regression guard: grep must return the MOST RECENT matches when results exceed
`limit`, not the oldest. Before the fix, grep iterated chunks in index insertion
order (oldest first) and broke at `limit`, hiding all recent occurrences of any
recurring term.
"""

import json
from datetime import datetime

import pytest

import mcp_server.tools.navigation as navigation


@pytest.fixture
def grep_context(temp_context_dir, monkeypatch):
    monkeypatch.setattr(navigation, "CONTEXT_DIR", temp_context_dir)
    monkeypatch.setattr(navigation, "CHUNKS_DIR", temp_context_dir / "chunks")
    monkeypatch.setattr(navigation, "INDEX_FILE", temp_context_dir / "index.json")
    return temp_context_dir


def _make_chunks(ctx, dates):
    """Create one chunk per date, all containing the term 'deployment',
    appended to the index in chronological (oldest-first) order."""
    chunks_dir = ctx / "chunks"
    index_file = ctx / "index.json"
    index = json.loads(index_file.read_text())
    for d in dates:  # oldest first, mimicking real insertion order
        cid = f"{d}_proj_001"
        (chunks_dir / f"{cid}.md").write_text(
            f"---\nsummary: s\ntags: t\ncreated: {d}T10:00:00\n---\n\nThe deployment went fine.\n"
        )
        index["chunks"].append(
            {
                "id": cid,
                "file": f"chunks/{cid}.md",
                "summary": "s",
                "tags": ["t"],
                "created_at": f"{d}T10:00:00",
                "access_count": 0,
                "tokens_estimate": 5,
            }
        )
    index_file.write_text(json.dumps(index))


def test_grep_returns_most_recent_within_limit(grep_context):
    _make_chunks(grep_context, ["2026-01-10", "2026-02-10", "2026-03-10", "2026-04-10"])

    result = navigation.grep("deployment", limit=2)

    ids = [m["chunk_id"] for m in result["matches"]]
    assert ids == ["2026-04-10_proj_001", "2026-03-10_proj_001"], (
        f"grep should return the 2 newest matches, got {ids}"
    )


def test_grep_full_set_unaffected(grep_context):
    _make_chunks(grep_context, ["2026-01-10", "2026-02-10", "2026-03-10"])

    result = navigation.grep("deployment", limit=10)

    assert result["match_count"] == 3
    # Still sorted newest-first
    ids = [m["chunk_id"] for m in result["matches"]]
    assert ids[0] == "2026-03-10_proj_001"
