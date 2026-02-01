"""
Tests for RLM Retention Tools (Phase 5.6).

Tests cover:
- Immunity detection (tags, access count, keywords)
- Archive/purge candidate detection
- Archive/restore operations
- Purge operations with logging
- Auto-restore on peek
- Preview and run tools
"""

import json
from datetime import datetime, timedelta

import pytest

# Fixtures are automatically discovered from conftest.py by pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def retention_context(temp_context_dir, monkeypatch):
    """Set up context with retention module patched."""
    # Patch paths in retention module
    import mcp_server.tools.retention as retention

    monkeypatch.setattr(retention, "CONTEXT_DIR", temp_context_dir)
    monkeypatch.setattr(retention, "CHUNKS_DIR", temp_context_dir / "chunks")
    monkeypatch.setattr(retention, "ARCHIVE_DIR", temp_context_dir / "archive")
    monkeypatch.setattr(retention, "INDEX_FILE", temp_context_dir / "index.json")
    monkeypatch.setattr(retention, "ARCHIVE_INDEX_FILE", temp_context_dir / "archive_index.json")
    monkeypatch.setattr(retention, "PURGE_LOG_FILE", temp_context_dir / "purge_log.json")

    # Create archive directory
    (temp_context_dir / "archive").mkdir(exist_ok=True)

    return temp_context_dir


@pytest.fixture
def old_chunks(retention_context):
    """Create old chunks for retention testing."""
    chunks_dir = retention_context / "chunks"
    index_file = retention_context / "index.json"

    # Date 45 days ago (past 30-day threshold)
    old_date = datetime.now() - timedelta(days=45)
    old_date_str = old_date.isoformat()

    chunks_data = [
        {
            "id": "old_unused_001",
            "content": "Old unused chunk content for testing retention.",
            "summary": "Old unused chunk",
            "tags": ["test"],
            "created_at": old_date_str,
            "access_count": 0,
        },
        {
            "id": "old_accessed_002",
            "content": "Old but frequently accessed chunk.",
            "summary": "Old accessed chunk",
            "tags": ["test"],
            "created_at": old_date_str,
            "access_count": 5,  # Immune due to access count
        },
        {
            "id": "old_critical_003",
            "content": "Old chunk with critical tag.",
            "summary": "Old critical chunk",
            "tags": ["critical", "test"],  # Immune due to tag
            "created_at": old_date_str,
            "access_count": 0,
        },
        {
            "id": "old_decision_004",
            "content": "DECISION: This is an important decision to keep.",
            "summary": "Old decision chunk",
            "tags": ["test"],  # Immune due to keyword
            "created_at": old_date_str,
            "access_count": 0,
        },
        {
            "id": "recent_005",
            "content": "Recent chunk that should not be archived.",
            "summary": "Recent chunk",
            "tags": ["test"],
            "created_at": datetime.now().isoformat(),  # Too recent
            "access_count": 0,
        },
    ]

    index_chunks = []

    for chunk in chunks_data:
        # Write chunk file
        chunk_file = chunks_dir / f"{chunk['id']}.md"
        chunk_file.write_text(f"""---
summary: {chunk["summary"]}
tags: {", ".join(chunk["tags"])}
created_at: {chunk["created_at"]}
---

{chunk["content"]}
""")

        # Add to index
        index_chunks.append(
            {
                "id": chunk["id"],
                "file": f"chunks/{chunk['id']}.md",
                "summary": chunk["summary"],
                "tags": chunk["tags"],
                "tokens_estimate": len(chunk["content"].split()) * 2,
                "created_at": chunk["created_at"],
                "access_count": chunk["access_count"],
            }
        )

    # Update index
    index = json.loads(index_file.read_text())
    index["chunks"] = index_chunks
    index_file.write_text(json.dumps(index, indent=2))

    return chunks_data


# =============================================================================
# IMMUNITY TESTS
# =============================================================================


def test_is_immune_by_tag(retention_context, old_chunks):
    """Chunks with protected tags (critical, decision, keep, important) are immune."""
    from mcp_server.tools.retention import is_immune

    # Find critical chunk
    critical_chunk = {"id": "old_critical_003", "tags": ["critical", "test"], "access_count": 0}

    assert is_immune(critical_chunk) is True


def test_is_immune_by_access_count(retention_context, old_chunks):
    """Chunks with access_count >= 3 are immune."""
    from mcp_server.tools.retention import is_immune

    # Find accessed chunk
    accessed_chunk = {"id": "old_accessed_002", "tags": ["test"], "access_count": 5}

    assert is_immune(accessed_chunk) is True


def test_is_immune_by_keyword(retention_context, old_chunks):
    """Chunks containing DECISION: or IMPORTANT: keywords are immune."""
    from mcp_server.tools.retention import is_immune

    # Find decision chunk
    decision_chunk = {"id": "old_decision_004", "tags": ["test"], "access_count": 0}

    assert is_immune(decision_chunk) is True


def test_not_immune_regular_chunk(retention_context, old_chunks):
    """Regular old chunks without protection are not immune."""
    from mcp_server.tools.retention import is_immune

    # Find regular old chunk
    regular_chunk = {"id": "old_unused_001", "tags": ["test"], "access_count": 0}

    assert is_immune(regular_chunk) is False


# =============================================================================
# CANDIDATE DETECTION TESTS
# =============================================================================


def test_get_archive_candidates(retention_context, old_chunks):
    """get_archive_candidates returns only eligible chunks."""
    from mcp_server.tools.retention import get_archive_candidates

    candidates = get_archive_candidates()
    candidate_ids = [c["id"] for c in candidates]

    # Should include: old_unused_001 (old, no access, no immunity)
    assert "old_unused_001" in candidate_ids

    # Should NOT include:
    assert "old_accessed_002" not in candidate_ids  # High access count
    assert "old_critical_003" not in candidate_ids  # Critical tag
    assert "old_decision_004" not in candidate_ids  # DECISION: keyword
    assert "recent_005" not in candidate_ids  # Too recent


def test_get_archive_candidates_empty_when_all_protected(retention_context):
    """No candidates when all chunks are protected or recent."""
    from mcp_server.tools.retention import get_archive_candidates

    chunks_dir = retention_context / "chunks"
    index_file = retention_context / "index.json"

    # Create only protected chunks
    recent_date = datetime.now().isoformat()

    chunk_file = chunks_dir / "protected_001.md"
    chunk_file.write_text(f"""---
summary: Protected chunk
tags: critical
created_at: {recent_date}
---

This is protected.
""")

    index = json.loads(index_file.read_text())
    index["chunks"] = [
        {
            "id": "protected_001",
            "file": "chunks/protected_001.md",
            "summary": "Protected chunk",
            "tags": ["critical"],
            "created_at": recent_date,
            "access_count": 0,
        }
    ]
    index_file.write_text(json.dumps(index, indent=2))

    candidates = get_archive_candidates()
    assert len(candidates) == 0


# =============================================================================
# ARCHIVE OPERATION TESTS
# =============================================================================


def test_archive_chunk(retention_context, old_chunks):
    """archive_chunk compresses and moves chunk to archive."""
    from mcp_server.tools.retention import archive_chunk

    chunks_dir = retention_context / "chunks"
    archive_dir = retention_context / "archive"

    # Verify chunk exists
    assert (chunks_dir / "old_unused_001.md").exists()

    # Archive it
    result = archive_chunk("old_unused_001")

    assert result["status"] == "archived"
    assert result["chunk_id"] == "old_unused_001"
    assert "compression_ratio" in result

    # Original should be gone
    assert not (chunks_dir / "old_unused_001.md").exists()

    # Archive should exist
    assert (archive_dir / "old_unused_001.md.gz").exists()


def test_archive_chunk_not_found(retention_context):
    """archive_chunk returns error for non-existent chunk."""
    from mcp_server.tools.retention import archive_chunk

    result = archive_chunk("nonexistent_chunk")

    assert result["status"] == "error"
    assert "not found" in result["message"]


def test_archive_chunk_already_archived(retention_context, old_chunks):
    """archive_chunk returns error if already archived."""
    from mcp_server.tools.retention import archive_chunk

    # Archive once
    archive_chunk("old_unused_001")

    # Try to archive again (would need chunk file which is now deleted)
    result = archive_chunk("old_unused_001")

    assert result["status"] == "error"


# =============================================================================
# RESTORE OPERATION TESTS
# =============================================================================


def test_restore_chunk(retention_context, old_chunks):
    """restore_chunk decompresses archive back to active storage."""
    from mcp_server.tools.retention import archive_chunk, restore_chunk

    chunks_dir = retention_context / "chunks"
    archive_dir = retention_context / "archive"

    # Archive first
    archive_chunk("old_unused_001")
    assert (archive_dir / "old_unused_001.md.gz").exists()
    assert not (chunks_dir / "old_unused_001.md").exists()

    # Restore
    result = restore_chunk("old_unused_001")

    assert result["status"] == "restored"
    assert result["chunk_id"] == "old_unused_001"

    # Archive should be gone
    assert not (archive_dir / "old_unused_001.md.gz").exists()

    # Chunk should be back
    assert (chunks_dir / "old_unused_001.md").exists()


def test_restore_chunk_not_found(retention_context):
    """restore_chunk returns error for non-existent archive."""
    from mcp_server.tools.retention import restore_chunk

    result = restore_chunk("nonexistent_archive")

    assert result["status"] == "error"
    assert "not found" in result["message"]


# =============================================================================
# PURGE OPERATION TESTS
# =============================================================================


def test_purge_chunk(retention_context, old_chunks):
    """purge_chunk deletes archive and logs metadata."""
    from mcp_server.tools.retention import _load_purge_log, archive_chunk, purge_chunk

    archive_dir = retention_context / "archive"

    # Archive first
    archive_chunk("old_unused_001")

    # Purge
    result = purge_chunk("old_unused_001")

    assert result["status"] == "purged"

    # Archive file should be gone
    assert not (archive_dir / "old_unused_001.md.gz").exists()

    # Check purge log
    purge_log = _load_purge_log()
    purged_ids = [p["id"] for p in purge_log["purged"]]
    assert "old_unused_001" in purged_ids


def test_purge_log_contains_metadata(retention_context, old_chunks):
    """Purge log contains metadata but not content."""
    from mcp_server.tools.retention import _load_purge_log, archive_chunk, purge_chunk

    # Archive and purge
    archive_chunk("old_unused_001")
    purge_chunk("old_unused_001")

    purge_log = _load_purge_log()
    purge_entry = purge_log["purged"][0]

    # Should have metadata
    assert "id" in purge_entry
    assert "purged_at" in purge_entry
    assert "summary" in purge_entry

    # Should NOT have content
    assert "content" not in purge_entry


# =============================================================================
# PREVIEW AND RUN TESTS
# =============================================================================


def test_retention_preview(retention_context, old_chunks):
    """retention_preview shows candidates without executing."""
    from mcp_server.tools.retention import retention_preview

    result = retention_preview()

    assert result["status"] == "preview"
    assert "archive_candidates" in result
    assert "purge_candidates" in result
    assert result["archive_count"] >= 1  # At least old_unused_001


def test_retention_run_archive(retention_context, old_chunks):
    """retention_run with archive=True archives candidates."""
    from mcp_server.tools.retention import retention_run

    archive_dir = retention_context / "archive"

    result = retention_run(archive=True, purge=False)

    assert result["status"] == "completed"
    assert result["archived_count"] >= 1

    # Check archive was created
    assert (archive_dir / "old_unused_001.md.gz").exists()


def test_retention_run_no_purge_by_default(retention_context, old_chunks):
    """retention_run does not purge by default."""
    from mcp_server.tools.retention import retention_run

    result = retention_run(archive=True, purge=False)

    assert result["purged_count"] == 0


def test_retention_run_empty_when_no_candidates(retention_context):
    """retention_run with no candidates completes without errors."""
    from mcp_server.tools.retention import retention_run

    # Empty context, no chunks
    result = retention_run(archive=True, purge=True)

    assert result["status"] == "completed"
    assert result["archived_count"] == 0
    assert result["purged_count"] == 0
    assert result["error_count"] == 0


# =============================================================================
# AUTO-RESTORE TESTS
# =============================================================================


def test_auto_restore_on_peek(retention_context, old_chunks, monkeypatch):
    """peek() auto-restores archived chunks."""
    import mcp_server.tools.navigation as navigation
    from mcp_server.tools.retention import archive_chunk

    # Patch navigation paths too
    monkeypatch.setattr(navigation, "CONTEXT_DIR", retention_context)
    monkeypatch.setattr(navigation, "CHUNKS_DIR", retention_context / "chunks")
    monkeypatch.setattr(navigation, "ARCHIVE_DIR", retention_context / "archive")
    monkeypatch.setattr(navigation, "INDEX_FILE", retention_context / "index.json")

    chunks_dir = retention_context / "chunks"

    # Archive the chunk
    archive_chunk("old_unused_001")
    assert not (chunks_dir / "old_unused_001.md").exists()

    # Peek should auto-restore
    result = navigation.peek("old_unused_001")

    assert result["status"] == "success"
    assert (chunks_dir / "old_unused_001.md").exists()


# =============================================================================
# INDEX CONSISTENCY TESTS
# =============================================================================


def test_index_updated_after_archive(retention_context, old_chunks):
    """Index is updated correctly after archiving."""
    from mcp_server.tools.retention import _load_archive_index, _load_index, archive_chunk

    index_before = _load_index()
    ids_before = [c["id"] for c in index_before["chunks"]]
    assert "old_unused_001" in ids_before

    # Archive
    archive_chunk("old_unused_001")

    # Check main index
    index_after = _load_index()
    ids_after = [c["id"] for c in index_after["chunks"]]
    assert "old_unused_001" not in ids_after

    # Check archive index
    archive_index = _load_archive_index()
    archive_ids = [a["id"] for a in archive_index["archives"]]
    assert "old_unused_001" in archive_ids


def test_index_updated_after_restore(retention_context, old_chunks):
    """Index is updated correctly after restoring."""
    from mcp_server.tools.retention import (
        _load_archive_index,
        _load_index,
        archive_chunk,
        restore_chunk,
    )

    # Archive first
    archive_chunk("old_unused_001")

    # Restore
    restore_chunk("old_unused_001")

    # Check main index
    index = _load_index()
    ids = [c["id"] for c in index["chunks"]]
    assert "old_unused_001" in ids

    # Check archive index
    archive_index = _load_archive_index()
    archive_ids = [a["id"] for a in archive_index["archives"]]
    assert "old_unused_001" not in archive_ids
