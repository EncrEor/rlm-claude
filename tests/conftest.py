"""
RLM Test Fixtures and Configuration.

Provides:
- Temporary directories for test isolation
- Sample data fixtures
- Helper functions for test setup/teardown
"""

import json
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def temp_context_dir(tmp_path):
    """Create a temporary context directory with proper structure."""
    context_dir = tmp_path / "context"
    chunks_dir = context_dir / "chunks"
    chunks_dir.mkdir(parents=True)

    # Initialize empty index
    index_file = context_dir / "index.json"
    index_file.write_text(
        json.dumps({"version": "2.1.0", "chunks": [], "total_tokens_estimate": 0}, indent=2)
    )

    # Initialize empty memory
    memory_file = context_dir / "session_memory.json"
    memory_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "insights": [],
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            indent=2,
        )
    )

    # Initialize empty sessions
    sessions_file = context_dir / "sessions.json"
    sessions_file.write_text(
        json.dumps({"version": "1.0.0", "current_session": None, "sessions": {}}, indent=2)
    )

    # Initialize default domains
    domains_file = context_dir / "domains.json"
    domains_file.write_text(
        json.dumps(
            {
                "domains": {
                    "default": {"description": "Default domains", "list": ["test", "dev", "prod"]}
                }
            },
            indent=2,
        )
    )

    yield context_dir

    # Cleanup is automatic with tmp_path


@pytest.fixture
def sample_chunks(temp_context_dir):
    """Create sample chunks for testing."""
    chunks_dir = temp_context_dir / "chunks"
    index_file = temp_context_dir / "index.json"

    chunks_data = [
        {
            "id": "2026-01-18_001",
            "content": "Discussion sur le business plan Joy Juice pour 2026.",
            "summary": "BP Joy Juice 2026",
            "tags": ["bp", "planning"],
        },
        {
            "id": "2026-01-18_002",
            "content": "Configuration Odoo 19 et modules website_joyjuice.",
            "summary": "Config Odoo",
            "tags": ["odoo", "config"],
        },
        {
            "id": "2026-01-18_RLM_001_r&d",
            "content": "Session R&D sur Phase 5 BM25 implementation.",
            "summary": "RLM Phase 5",
            "tags": ["rlm", "bm25"],
            "project": "RLM",
            "domain": "r&d",
        },
    ]

    index_chunks = []

    for chunk in chunks_data:
        # Write chunk file
        chunk_file = chunks_dir / f"{chunk['id']}.md"
        content = f"""---
summary: {chunk["summary"]}
tags: {", ".join(chunk["tags"])}
created: 2026-01-18T10:00:00
---

{chunk["content"]}
"""
        chunk_file.write_text(content)

        # Add to index
        index_chunks.append(
            {
                "id": chunk["id"],
                "summary": chunk["summary"],
                "tags": chunk["tags"],
                "tokens_estimate": len(chunk["content"].split()) * 2,
                "created": "2026-01-18T10:00:00",
                "access_count": 0,
                "project": chunk.get("project", ""),
                "domain": chunk.get("domain", ""),
            }
        )

    # Update index
    index = json.loads(index_file.read_text())
    index["chunks"] = index_chunks
    index["total_tokens_estimate"] = sum(c["tokens_estimate"] for c in index_chunks)
    index_file.write_text(json.dumps(index, indent=2))

    return chunks_data


@pytest.fixture
def sample_insights(temp_context_dir):
    """Create sample insights for testing."""
    memory_file = temp_context_dir / "session_memory.json"

    insights = [
        {
            "id": "abc12345",
            "content": "Le client prefere les formats 500ml.",
            "category": "preference",
            "importance": "high",
            "tags": ["client", "format"],
            "created": "2026-01-18T09:00:00",
        },
        {
            "id": "def67890",
            "content": "Decision: Utiliser BM25 au lieu d'embeddings.",
            "category": "decision",
            "importance": "critical",
            "tags": ["rlm", "architecture"],
            "created": "2026-01-18T10:00:00",
        },
    ]

    memory = json.loads(memory_file.read_text())
    memory["insights"] = insights
    memory_file.write_text(json.dumps(memory, indent=2))

    return insights


@pytest.fixture
def mock_context_paths(temp_context_dir, monkeypatch):
    """Patch the CONTEXT_DIR paths in navigation module."""
    # This fixture will be used to inject temp paths into the actual module
    # Implementation depends on how we want to handle module imports
    return temp_context_dir


# =============================================================================
# Helper functions
# =============================================================================


def create_chunk(chunks_dir: Path, chunk_id: str, content: str, **metadata) -> Path:
    """Helper to create a chunk file."""
    chunk_file = chunks_dir / f"{chunk_id}.md"

    summary = metadata.get("summary", content.split("\n")[0][:50])
    tags = metadata.get("tags", [])

    chunk_content = f"""---
summary: {summary}
tags: {", ".join(tags) if tags else ""}
created: {datetime.now().isoformat()}
---

{content}
"""
    chunk_file.write_text(chunk_content)
    return chunk_file


def assert_chunk_exists(chunks_dir: Path, chunk_id: str) -> bool:
    """Assert that a chunk file exists."""
    chunk_file = chunks_dir / f"{chunk_id}.md"
    assert chunk_file.exists(), f"Chunk {chunk_id} does not exist"
    return True
