"""
Tests for retention <-> semantic store sync (Phase 8.2).

Verify that archiving/purging a chunk drops its vector from the embedding
store, and that restoring re-embeds it — without ever blocking the retention
operation when semantic search is unavailable.
"""

from datetime import datetime, timedelta

import pytest

import mcp_server.tools.retention as retention


class FakeStore:
    """Records VectorStore calls so tests can assert sync happened."""

    calls: list = []

    def __init__(self, *a, **k):
        pass

    def load(self):
        return True

    def remove(self, chunk_id):
        FakeStore.calls.append(("remove", chunk_id))
        return True

    def add(self, chunk_id, vec):
        FakeStore.calls.append(("add", chunk_id))

    def save(self):
        FakeStore.calls.append(("save",))


class FakeProvider:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def dim(self):
        return 3


@pytest.fixture
def retention_context(temp_context_dir, monkeypatch):
    """Patch retention module paths onto a temp context (mirrors test_retention.py)."""
    monkeypatch.setattr(retention, "CONTEXT_DIR", temp_context_dir)
    monkeypatch.setattr(retention, "CHUNKS_DIR", temp_context_dir / "chunks")
    monkeypatch.setattr(retention, "ARCHIVE_DIR", temp_context_dir / "archive")
    monkeypatch.setattr(retention, "INDEX_FILE", temp_context_dir / "index.json")
    monkeypatch.setattr(retention, "ARCHIVE_INDEX_FILE", temp_context_dir / "archive_index.json")
    monkeypatch.setattr(retention, "PURGE_LOG_FILE", temp_context_dir / "purge_log.json")
    (temp_context_dir / "archive").mkdir(exist_ok=True)
    return temp_context_dir


@pytest.fixture
def patched_semantic(monkeypatch):
    """Patch VectorStore and provider so retention syncs against fakes."""
    FakeStore.calls = []
    import mcp_server.tools.embeddings as embeddings
    import mcp_server.tools.vecstore as vecstore

    monkeypatch.setattr(vecstore, "VectorStore", FakeStore)
    monkeypatch.setattr(embeddings, "_get_cached_provider", lambda: FakeProvider())
    return FakeStore


def _add_active_chunk(retention_context, chunk_id, days_old):
    """Create an active chunk file + index entry old enough to archive."""
    import json

    chunks_dir = retention_context / "chunks"
    created = (datetime.now() - timedelta(days=days_old)).isoformat()
    (chunks_dir / f"{chunk_id}.md").write_text(
        f"---\nsummary: test {chunk_id}\ntags: test\ncreated: {created}\n---\n\nbody {chunk_id}\n"
    )
    index_file = retention_context / "index.json"
    index = json.loads(index_file.read_text())
    index["chunks"].append(
        {
            "id": chunk_id,
            "file": f"chunks/{chunk_id}.md",
            "summary": f"test {chunk_id}",
            "tags": ["test"],
            "created_at": created,
            "access_count": 0,
            "tokens_estimate": 10,
        }
    )
    index_file.write_text(json.dumps(index))


def test_archive_removes_embedding(retention_context, patched_semantic):
    _add_active_chunk(retention_context, "sem_arch_001", days_old=45)

    result = retention.archive_chunk("sem_arch_001")

    assert result["status"] == "archived"
    assert ("remove", "sem_arch_001") in patched_semantic.calls


def test_purge_removes_embedding(retention_context, patched_semantic):
    _add_active_chunk(retention_context, "sem_purge_001", days_old=45)
    retention.archive_chunk("sem_purge_001")
    patched_semantic.calls = []  # reset after archive's own remove

    result = retention.purge_chunk("sem_purge_001")

    assert result["status"] == "purged"
    assert ("remove", "sem_purge_001") in patched_semantic.calls


def test_restore_readds_embedding(retention_context, patched_semantic):
    _add_active_chunk(retention_context, "sem_restore_001", days_old=45)
    retention.archive_chunk("sem_restore_001")
    patched_semantic.calls = []  # reset after archive

    result = retention.restore_chunk("sem_restore_001")

    assert result["status"] == "restored"
    assert ("add", "sem_restore_001") in patched_semantic.calls


def test_archive_succeeds_when_semantic_unavailable(retention_context, monkeypatch):
    """A broken/absent semantic store must never block archiving."""
    import mcp_server.tools.vecstore as vecstore

    def boom(*a, **k):
        raise RuntimeError("no numpy here")

    monkeypatch.setattr(vecstore, "VectorStore", boom)
    _add_active_chunk(retention_context, "sem_safe_001", days_old=45)

    result = retention.archive_chunk("sem_safe_001")

    assert result["status"] == "archived"  # archive still succeeds
