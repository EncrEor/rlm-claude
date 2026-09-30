"""
Tests for silent-degradation fixes (v0.10.2).

Each test here maps to a failure that ran unnoticed in production for weeks:
- a transient provider error cached forever → chunks stored without vectors
- concurrent chunk writes overwriting each other
- retention archiving chunks that search surfaces daily (access never counted)
- archived chunks unreachable because nothing can find their ID
"""

import json
import os
import subprocess
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import mcp_server.tools.embeddings as embeddings
import mcp_server.tools.navigation as navigation
import mcp_server.tools.retention as retention

# =============================================================================
# Provider cache: a transient failure must not silence embeddings for good
# =============================================================================


class BoomOnce:
    """Fails the first N constructions, then succeeds."""

    def __init__(self, failures):
        self.remaining = failures
        self.built = 0

    def __call__(self):
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("HuggingFace Hub unreachable")
        self.built += 1
        return "provider"


@pytest.fixture(autouse=True)
def clean_provider_cache():
    embeddings.reset_provider_cache()
    yield
    embeddings.reset_provider_cache()


def test_transient_provider_failure_is_retried(monkeypatch):
    """A network blip must not disable embeddings for the process lifetime."""
    factory = BoomOnce(failures=1)
    monkeypatch.setattr(embeddings, "Model2VecProvider", factory)
    monkeypatch.setattr(embeddings, "RETRY_COOLDOWN_SECONDS", 0.0)

    assert embeddings._get_cached_provider() is None
    assert "failed to load" in embeddings.get_provider_error()

    # Second call, after the cooldown, must try again — and succeed.
    assert embeddings._get_cached_provider() == "provider"
    assert embeddings.get_provider_error() == ""


def test_missing_library_is_not_retried(monkeypatch):
    """A missing dependency is permanent: don't pay the load cost every call."""
    attempts = []

    def raise_import():
        attempts.append(1)
        raise ImportError("no module named model2vec")

    monkeypatch.setattr(embeddings, "Model2VecProvider", raise_import)
    monkeypatch.setattr(embeddings, "RETRY_COOLDOWN_SECONDS", 0.0)

    assert embeddings._get_cached_provider() is None
    assert embeddings._get_cached_provider() is None
    assert len(attempts) == 1
    assert "not installed" in embeddings.get_provider_error()


def test_cooldown_prevents_hammering(monkeypatch):
    """Retry is bounded: no reload attempt within the cooldown window."""
    attempts = []

    def always_fail():
        attempts.append(1)
        raise RuntimeError("still down")

    monkeypatch.setattr(embeddings, "Model2VecProvider", always_fail)
    monkeypatch.setattr(embeddings, "RETRY_COOLDOWN_SECONDS", 3600.0)

    embeddings._get_cached_provider()
    embeddings._get_cached_provider()
    embeddings._get_cached_provider()
    assert len(attempts) == 1


# =============================================================================
# The suite itself must never touch the developer's real memory
# =============================================================================


def test_suite_is_bound_to_a_throwaway_context():
    """conftest.py redirects RLM_CONTEXT_DIR before any import; this fails if it stops."""
    import mcp_server.tools.diagnostics as diagnostics
    import mcp_server.tools.fileutil as fileutil
    import mcp_server.tools.vecstore as vecstore

    real = Path.home() / ".claude" / "rlm"
    for bound in (fileutil.CONTEXT_DIR, diagnostics.LOG_FILE, vecstore.DEFAULT_EMBEDDINGS_PATH):
        assert real not in bound.resolve().parents, f"{bound} points at the real RLM context"
    assert str(fileutil.CONTEXT_DIR) == os.environ["RLM_CONTEXT_DIR"]


# =============================================================================
# FastEmbed model cache: must survive the OS sweeping its temp directory
# =============================================================================


def test_fastembed_cache_is_persistent_by_default(monkeypatch):
    """fastembed defaults to the temp dir; macOS sweeps it and the next load fails."""
    monkeypatch.delenv("FASTEMBED_CACHE_PATH", raising=False)

    assert Path(embeddings._fastembed_cache_dir()) == Path.home() / ".cache" / "fastembed"


def test_fastembed_cache_honours_env_override(monkeypatch, tmp_path):
    """FASTEMBED_CACHE_PATH is fastembed's own knob: it keeps the last word."""
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))

    assert embeddings._fastembed_cache_dir() == str(tmp_path)


def test_fastembed_provider_hands_cache_dir_to_fastembed(monkeypatch, tmp_path):
    """The provider must pass the path explicitly, not rely on fastembed's default."""
    seen = {}

    class FakeTextEmbedding:
        def __init__(self, model_name, cache_dir=None, **kwargs):
            seen["model_name"] = model_name
            seen["cache_dir"] = cache_dir

    fake_module = types.ModuleType("fastembed")
    fake_module.TextEmbedding = FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", fake_module)
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))

    embeddings.FastEmbedProvider()

    assert seen["cache_dir"] == str(tmp_path)
    assert seen["model_name"] == embeddings.FastEmbedProvider.MODEL_NAME


# =============================================================================
# Concurrent chunk writes must not overwrite each other
# =============================================================================


# Run in a fresh interpreter, NOT via multiprocessing: this test module imports
# mcp_server at module level, and a "spawn" child re-imports it before the
# worker can set RLM_CONTEXT_DIR — so the child would bind to the developer's
# real context directory and write test chunks into it (it did, once).
# subprocess with an explicit env resolves the context before any import.
_WORKER_SRC = """
import sys
sys.path.insert(0, {src!r})
import mcp_server.tools.navigation as nav

project = sys.argv[1]
for i in range({count}):
    result = nav.chunk(
        content="body %s %d " % (project, i) * 30,
        summary="s%s%d" % (project, i),
        project=project,
    )
    if result.get("status") != "created":
        sys.exit("chunk rejected: %r" % (result,))
"""


def test_concurrent_chunks_are_not_lost(tmp_path):
    """Concurrent sessions chunking at once used to share a sequence number.

    Reproduced before the fix: 18 writes produced 16 files.
    """
    context = tmp_path / "ctx"
    (context / "chunks").mkdir(parents=True)

    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    env = {**os.environ, "RLM_CONTEXT_DIR": str(context)}
    code = _WORKER_SRC.format(src=src_dir, count=5)

    procs = [
        subprocess.Popen([sys.executable, "-c", code, f"P{n}"], env=env, stderr=subprocess.PIPE)
        for n in (1, 2, 3)
    ]
    errors = []
    for p in procs:
        _, err = p.communicate(timeout=120)
        if p.returncode != 0:
            errors.append(err.decode(errors="replace").strip())
    assert not errors, f"worker failed: {errors}"

    written = list((context / "chunks").glob("*.md"))
    assert len(written) == 15, f"expected 15 chunks, found {len(written)}"

    index = json.loads((context / "index.json").read_text())
    ids = [c["id"] for c in index["chunks"]]
    assert len(ids) == 15
    assert len(set(ids)) == 15, "duplicate chunk IDs in index"


def test_next_chunk_id_skips_ids_present_on_disk(tmp_path, monkeypatch):
    """An ID free in the index but present on disk must never be reused."""
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    monkeypatch.setattr(navigation, "CHUNKS_DIR", chunks_dir)

    today = datetime.now().strftime("%Y-%m-%d")
    (chunks_dir / f"{today}_Proj_001.md").write_text("orphan from a crashed run")

    got = navigation._next_chunk_id({"chunks": []}, "Proj")
    assert got == f"{today}_Proj_002"


# =============================================================================
# Access counting drives retention: every retrieval path must count
# =============================================================================


def test_grep_counts_access(tmp_path, monkeypatch):
    """A chunk surfaced by grep is used — retention must not see it as idle."""
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    index_file = tmp_path / "index.json"
    monkeypatch.setattr(navigation, "CONTEXT_DIR", tmp_path)
    monkeypatch.setattr(navigation, "CHUNKS_DIR", chunks_dir)
    monkeypatch.setattr(navigation, "INDEX_FILE", index_file)

    (chunks_dir / "c1.md").write_text("---\nsummary: s\n---\n\nneedle in here\n")
    index_file.write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "id": "c1",
                        "file": "chunks/c1.md",
                        "summary": "s",
                        "access_count": 0,
                        "created_at": datetime.now().isoformat(),
                        "tokens_estimate": 10,
                    }
                ]
            }
        )
    )

    result = navigation.grep("needle")
    assert result["match_count"] == 1

    after = json.loads(index_file.read_text())
    assert after["chunks"][0]["access_count"] == 1
    assert after["chunks"][0]["last_accessed"]


def test_access_immunity_protects_from_archiving(tmp_path, monkeypatch):
    """Counted accesses reach the immunity threshold and stop archiving."""
    monkeypatch.setattr(retention, "INDEX_FILE", tmp_path / "index.json")
    old = (datetime.now() - timedelta(days=90)).isoformat()
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "chunks": [
                    {"id": "cold", "created_at": old, "access_count": 0, "tags": []},
                    {"id": "warm", "created_at": old, "access_count": 3, "tags": []},
                ]
            }
        )
    )
    monkeypatch.setattr(retention, "CHUNKS_DIR", tmp_path / "chunks")

    candidates = {c["id"] for c in retention.get_archive_candidates()}
    assert candidates == {"cold"}


# =============================================================================
# Archived chunks must remain discoverable
# =============================================================================


def test_search_archives_finds_by_metadata(tmp_path, monkeypatch):
    """Archiving demotes a chunk; it must not make it unfindable."""
    archive_index = tmp_path / "archive_index.json"
    monkeypatch.setattr(retention, "ARCHIVE_INDEX_FILE", archive_index)
    archive_index.write_text(
        json.dumps(
            {
                "archives": [
                    {
                        "id": "2026-03-01_Proj_001",
                        "summary": "Deployment of the invoicing module",
                        "tags": ["odoo", "invoicing"],
                        "archived_at": "2026-04-01T10:00:00",
                    },
                    {
                        "id": "2026-03-02_Proj_002",
                        "summary": "Packaging label design",
                        "tags": ["design"],
                        "archived_at": "2026-04-01T10:00:00",
                    },
                ]
            }
        )
    )

    hits = retention.search_archives("invoicing module")
    assert len(hits) == 1
    assert hits[0]["id"] == "2026-03-01_Proj_001"

    assert retention.search_archives("") == []
    assert retention.search_archives("nonexistent topic") == []
