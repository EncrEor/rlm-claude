"""
RLM Navigation Tools - Navigate through conversation chunks.

These tools allow Claude to explore conversation history stored externally,
enabling navigation in large contexts without loading everything into memory.

Phase 2 tools:
- chunk: Save content to external chunk
- peek: View portion of a chunk
- grep: Search pattern across chunks
- list_chunks: List all available chunks

Phase 4 additions:
- Auto-summarization when no summary provided
- Duplicate detection via content hash
- Access counting for chunks
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# Paths
CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"
CHUNKS_DIR = CONTEXT_DIR / "chunks"
INDEX_FILE = CONTEXT_DIR / "index.json"


def _load_index() -> dict:
    """Load chunks index from JSON file."""
    if not INDEX_FILE.exists():
        return {
            "version": "2.0.0",
            "created_at": datetime.now().isoformat(),
            "chunks": [],
            "total_chunks": 0,
            "total_tokens_estimate": 0,
            "last_chunking": None
        }

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migrate from v1 if needed
    if data.get("version", "1.0.0") == "1.0.0":
        data["version"] = "2.0.0"
        data["total_chunks"] = len(data.get("chunks", []))

    return data


def _save_index(index: dict) -> None:
    """Save chunks index to JSON file."""
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    index["last_chunking"] = datetime.now().isoformat()
    index["total_chunks"] = len(index.get("chunks", []))

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def _estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ~ 4 chars for French/English)."""
    return len(text) // 4


# =============================================================================
# PHASE 4: Auto-summarization, Deduplication, Access Tracking
# =============================================================================

def _auto_summarize(content: str, max_length: int = 100) -> str:
    """
    Generate automatic summary from content (Phase 4.1).

    Extracts the first non-empty line as summary.
    If too long, truncates with ellipsis.

    Args:
        content: The text content to summarize
        max_length: Maximum length for summary (default: 100)

    Returns:
        Generated summary string
    """
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    if not lines:
        return "Empty content"

    # Take first meaningful line
    first_line = lines[0]

    # Skip markdown headers for better summary
    if first_line.startswith('#'):
        first_line = first_line.lstrip('#').strip()

    # Truncate if too long
    if len(first_line) > max_length:
        return first_line[:max_length - 3] + "..."

    return first_line


def _content_hash(content: str) -> str:
    """
    Generate hash of normalized content for duplicate detection (Phase 4.2).

    Normalizes whitespace and lowercases before hashing to catch
    near-duplicates.

    Args:
        content: The text content to hash

    Returns:
        MD5 hash of normalized content (32 chars)
    """
    # Normalize: lowercase, collapse whitespace
    normalized = ' '.join(content.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()


def _check_duplicate(content_hash: str) -> dict | None:
    """
    Check if content with this hash already exists (Phase 4.2).

    Args:
        content_hash: MD5 hash of normalized content

    Returns:
        Existing chunk info if duplicate found, None otherwise
    """
    index = _load_index()

    for chunk_info in index.get("chunks", []):
        if chunk_info.get("content_hash") == content_hash:
            return chunk_info

    return None


def _increment_access(chunk_id: str) -> None:
    """
    Increment access counter for a chunk (Phase 4.3).

    Updates both access_count and last_accessed timestamp.

    Args:
        chunk_id: ID of the chunk being accessed
    """
    index = _load_index()

    for chunk_info in index.get("chunks", []):
        if chunk_info["id"] == chunk_id:
            chunk_info["access_count"] = chunk_info.get("access_count", 0) + 1
            chunk_info["last_accessed"] = datetime.now().isoformat()
            break

    _save_index(index)


def _generate_chunk_id() -> str:
    """Generate a unique chunk ID based on date and sequence."""
    today = datetime.now().strftime("%Y-%m-%d")
    index = _load_index()

    # Find existing chunks for today
    existing_today = [
        c for c in index["chunks"]
        if c["id"].startswith(today)
    ]

    sequence = len(existing_today) + 1
    return f"{today}_{sequence:03d}"


def chunk(
    content: str,
    summary: str = "",
    tags: Optional[list[str]] = None
) -> dict:
    """
    Save content to an external chunk file.

    Use this to externalize parts of the conversation that you might need
    to reference later but don't need in active context.

    Phase 4 enhancements:
    - Auto-generates summary if not provided
    - Detects duplicate content via hash
    - Stores content hash for future duplicate checks

    Args:
        content: The text content to save as a chunk
        summary: Brief description of what this chunk contains (auto-generated if empty)
        tags: Keywords for easier retrieval

    Returns:
        Dictionary with chunk_id and confirmation, or duplicate status
    """
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 4.2: Check for duplicates
    content_hash = _content_hash(content)
    existing = _check_duplicate(content_hash)

    if existing:
        return {
            "status": "duplicate",
            "existing_chunk_id": existing["id"],
            "existing_summary": existing.get("summary", ""),
            "message": f"Content already exists in chunk {existing['id']}"
        }

    # Phase 4.1: Auto-generate summary if not provided
    if not summary:
        summary = _auto_summarize(content)

    chunk_id = _generate_chunk_id()
    chunk_file = CHUNKS_DIR / f"{chunk_id}.md"
    tokens = _estimate_tokens(content)

    # Create chunk file with metadata header
    header = f"""---
id: {chunk_id}
summary: {summary}
tags: {', '.join(tags or [])}
created_at: {datetime.now().isoformat()}
tokens_estimate: {tokens}
content_hash: {content_hash}
---

"""

    with open(chunk_file, "w", encoding="utf-8") as f:
        f.write(header + content)

    # Update index
    index = _load_index()
    index["chunks"].append({
        "id": chunk_id,
        "file": f"chunks/{chunk_id}.md",
        "summary": summary,
        "tags": tags or [],
        "tokens_estimate": tokens,
        "content_hash": content_hash,
        "access_count": 0,
        "last_accessed": None,
        "created_at": datetime.now().isoformat()
    })
    index["total_tokens_estimate"] = sum(c["tokens_estimate"] for c in index["chunks"])
    _save_index(index)

    return {
        "status": "created",
        "chunk_id": chunk_id,
        "tokens_estimate": tokens,
        "summary": summary,
        "message": f"Chunk {chunk_id} created ({tokens} tokens estimated)"
    }


def peek(
    chunk_id: str,
    start: int = 0,
    end: Optional[int] = None
) -> dict:
    """
    Read content from a chunk file.

    Use this to view the contents of a previously saved chunk.
    Can read the whole chunk or just a portion (by line numbers).

    Phase 4.3: Increments access counter on successful read.

    Args:
        chunk_id: ID of the chunk to read
        start: Starting line number (0-indexed, default: 0)
        end: Ending line number (exclusive, default: all)

    Returns:
        Dictionary with chunk content and metadata
    """
    chunk_file = CHUNKS_DIR / f"{chunk_id}.md"

    if not chunk_file.exists():
        return {
            "status": "not_found",
            "message": f"Chunk {chunk_id} not found"
        }

    with open(chunk_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Skip YAML header (find end of ---)
    content_start = 0
    in_header = False
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_header:
                in_header = True
            else:
                content_start = i + 1
                break

    content_lines = lines[content_start:]

    # Apply start/end
    if end is None:
        end = len(content_lines)

    selected_lines = content_lines[start:end]

    # Phase 4.3: Track access
    _increment_access(chunk_id)

    return {
        "status": "success",
        "chunk_id": chunk_id,
        "total_lines": len(content_lines),
        "showing_lines": f"{start}-{min(end, len(content_lines))}",
        "content": "".join(selected_lines)
    }


def grep(
    pattern: str,
    limit: int = 10,
    context_lines: int = 1
) -> dict:
    """
    Search for a pattern across all chunks.

    Use this to find where a topic was discussed or where
    specific information is stored.

    Args:
        pattern: Text or regex pattern to search for
        limit: Maximum number of matches to return
        context_lines: Number of lines before/after match to include

    Returns:
        Dictionary with list of matches
    """
    index = _load_index()
    matches = []

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If invalid regex, treat as literal string
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    for chunk_info in index.get("chunks", []):
        chunk_file = CONTEXT_DIR / chunk_info["file"]

        if not chunk_file.exists():
            continue

        with open(chunk_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Skip YAML header
        content_start = 0
        in_header = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_header:
                    in_header = True
                else:
                    content_start = i + 1
                    break

        content_lines = lines[content_start:]

        for i, line in enumerate(content_lines):
            if regex.search(line):
                # Get context
                start_ctx = max(0, i - context_lines)
                end_ctx = min(len(content_lines), i + context_lines + 1)
                context = "".join(content_lines[start_ctx:end_ctx])

                matches.append({
                    "chunk_id": chunk_info["id"],
                    "chunk_summary": chunk_info.get("summary", ""),
                    "line_number": i + 1,
                    "context": context.strip()
                })

                if len(matches) >= limit:
                    break

        if len(matches) >= limit:
            break

    return {
        "status": "success",
        "pattern": pattern,
        "match_count": len(matches),
        "matches": matches
    }


def list_chunks(limit: int = 20) -> dict:
    """
    List all available chunks with their metadata.

    Use this to see what conversation history is available
    in external storage.

    Args:
        limit: Maximum number of chunks to return (default: 20)

    Returns:
        Dictionary with list of chunks and their summaries
    """
    index = _load_index()
    chunks = index.get("chunks", [])

    # Sort by creation date (newest first)
    chunks_sorted = sorted(
        chunks,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )[:limit]

    return {
        "status": "success",
        "total_chunks": index.get("total_chunks", 0),
        "total_tokens_estimate": index.get("total_tokens_estimate", 0),
        "chunks": [
            {
                "id": c["id"],
                "summary": c.get("summary", "No summary"),
                "tags": c.get("tags", []),
                "tokens": c.get("tokens_estimate", 0),
                "created": c.get("created_at", "")[:16],
                # Phase 4.3: Access metrics
                "access_count": c.get("access_count", 0),
                "last_accessed": c.get("last_accessed", "")[:16] if c.get("last_accessed") else None
            }
            for c in chunks_sorted
        ]
    }
