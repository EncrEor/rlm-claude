"""
RLM Retention Tools - Archive and purge old chunks.

Phase 5.6: Implements a 3-zone retention system to prevent infinite chunk accumulation.

Zones:
1. ACTIVE (context/chunks/*.md) - Fully searchable, access tracking
2. ARCHIVE (context/archive/*.md.gz) - Compressed, auto-restore on peek
3. PURGE (deleted) - Only metadata logged in purge_log.json

Retention Rules:
- Archive: 30 days + access_count=0 + not immune
- Purge: 180 days in archive + access_count=0 + not immune
- Immunity: protected tags, frequent access, critical keywords
"""

import gzip
import json
from datetime import datetime, timedelta

from .fileutil import (
    CONTEXT_DIR,
    MAX_DECOMPRESSED_SIZE,
    atomic_write_json,
    safe_path,
    validate_chunk_id,
)

CHUNKS_DIR = CONTEXT_DIR / "chunks"
ARCHIVE_DIR = CONTEXT_DIR / "archive"
INDEX_FILE = CONTEXT_DIR / "index.json"
ARCHIVE_INDEX_FILE = CONTEXT_DIR / "archive_index.json"
PURGE_LOG_FILE = CONTEXT_DIR / "purge_log.json"

# =============================================================================
# CONFIGURATION
# =============================================================================

ARCHIVE_AFTER_DAYS = 30  # Archive after 30 days if unused
PURGE_AFTER_DAYS = 180  # Purge after 180 days in archive

MIN_ACCESS_FOR_IMMUNITY = 3  # 3+ accesses = protected from archiving

PROTECTED_TAGS = {"critical", "decision", "keep", "important"}
PROTECTED_KEYWORDS = ["DECISION:", "IMPORTANT:", "A RETENIR:", "CRITICAL:"]


# =============================================================================
# INDEX MANAGEMENT
# =============================================================================


def _load_index() -> dict:
    """Load chunks index from JSON file."""
    if not INDEX_FILE.exists():
        return {
            "version": "2.1.0",
            "created_at": datetime.now().isoformat(),
            "chunks": [],
        }

    with open(INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: dict) -> None:
    """Save chunks index atomically."""
    atomic_write_json(INDEX_FILE, index)


def _load_archive_index() -> dict:
    """Load archive index from JSON file."""
    if not ARCHIVE_INDEX_FILE.exists():
        return {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "archives": [],
        }

    with open(ARCHIVE_INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_archive_index(archive_index: dict) -> None:
    """Save archive index atomically."""
    atomic_write_json(ARCHIVE_INDEX_FILE, archive_index)


def _load_purge_log() -> dict:
    """Load purge log from JSON file."""
    if not PURGE_LOG_FILE.exists():
        return {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "purged": [],
        }

    with open(PURGE_LOG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_purge_log(purge_log: dict) -> None:
    """Save purge log atomically."""
    atomic_write_json(PURGE_LOG_FILE, purge_log)


# =============================================================================
# IMMUNITY DETECTION
# =============================================================================


def is_immune(chunk: dict) -> bool:
    """
    Determine if a chunk is protected from archiving/purging.

    A chunk is IMMUNE if ANY of these apply:
    - Has a protected tag (critical, decision, keep, important)
    - Has access_count >= MIN_ACCESS_FOR_IMMUNITY (3)
    - Content contains protected keywords (DECISION:, IMPORTANT:, A RETENIR:)

    Args:
        chunk: Chunk metadata dictionary from index

    Returns:
        True if chunk is immune, False otherwise
    """
    # Check protected tags
    chunk_tags = {t.lower() for t in chunk.get("tags", [])}
    protected_lower = {t.lower() for t in PROTECTED_TAGS}

    if chunk_tags & protected_lower:
        return True

    # Check access count
    if chunk.get("access_count", 0) >= MIN_ACCESS_FOR_IMMUNITY:
        return True

    # Check content for protected keywords
    chunk_id = chunk.get("id", "")
    chunk_file = safe_path(CHUNKS_DIR, chunk_id, ".md") if chunk_id else None

    if chunk_file and chunk_file.exists():
        try:
            content = chunk_file.read_text(encoding="utf-8").upper()
            if any(kw.upper() in content for kw in PROTECTED_KEYWORDS):
                return True
        except Exception:
            pass  # If we can't read, assume not immune

    return False


# =============================================================================
# CANDIDATE DETECTION
# =============================================================================


def get_archive_candidates() -> list[dict]:
    """
    Get list of chunks eligible for archiving.

    A chunk is an archive candidate if:
    - Age > ARCHIVE_AFTER_DAYS (30 days)
    - access_count == 0
    - NOT immune

    Returns:
        List of chunk metadata dictionaries
    """
    index = _load_index()
    candidates = []
    threshold = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)

    for chunk in index.get("chunks", []):
        # Skip already archived (shouldn't be in main index, but defensive)
        if chunk.get("archived", False):
            continue

        # Check age
        created_str = chunk.get("created_at", chunk.get("created", ""))
        if not created_str:
            continue

        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            # Remove timezone info for comparison if present
            if created.tzinfo is not None:
                created = created.replace(tzinfo=None)
        except (ValueError, AttributeError):
            continue

        if created >= threshold:
            continue  # Too recent

        # Check access count
        if chunk.get("access_count", 0) > 0:
            continue  # Has been accessed

        # Check immunity
        if is_immune(chunk):
            continue

        candidates.append(chunk)

    return candidates


def get_purge_candidates() -> list[dict]:
    """
    Get list of archived chunks eligible for purging.

    A chunk is a purge candidate if:
    - In archive for > PURGE_AFTER_DAYS (180 days)
    - access_count == 0 during archive period
    - NOT immune

    Returns:
        List of archive metadata dictionaries
    """
    archive_index = _load_archive_index()
    candidates = []
    threshold = datetime.now() - timedelta(days=PURGE_AFTER_DAYS)

    for archive in archive_index.get("archives", []):
        # Check archive age
        archived_str = archive.get("archived_at", "")
        if not archived_str:
            continue

        try:
            archived_date = datetime.fromisoformat(archived_str.replace("Z", "+00:00"))
            if archived_date.tzinfo is not None:
                archived_date = archived_date.replace(tzinfo=None)
        except (ValueError, AttributeError):
            continue

        if archived_date >= threshold:
            continue  # Not old enough in archive

        # Check access count (should still be 0)
        if archive.get("access_count", 0) > 0:
            continue

        # Check immunity (based on original chunk metadata)
        if is_immune(archive):
            continue

        candidates.append(archive)

    return candidates


# =============================================================================
# ARCHIVE OPERATIONS
# =============================================================================


def archive_chunk(chunk_id: str) -> dict:
    """
    Archive a chunk by compressing it to archive/.

    Steps:
    1. Read chunk file
    2. Compress to archive/*.md.gz
    3. Remove from main index
    4. Add to archive index
    5. Delete original file

    Args:
        chunk_id: ID of the chunk to archive

    Returns:
        Dictionary with status and details
    """
    # Validate chunk ID against path traversal
    if not validate_chunk_id(chunk_id):
        return {"status": "error", "message": f"Invalid chunk ID format: {chunk_id}"}

    src_file = CHUNKS_DIR / f"{chunk_id}.md"

    if not src_file.exists():
        return {"status": "error", "message": f"Chunk {chunk_id} not found in active storage"}

    # Ensure archive directory exists
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    dst_file = ARCHIVE_DIR / f"{chunk_id}.md.gz"

    # Check if already archived
    if dst_file.exists():
        return {"status": "error", "message": f"Chunk {chunk_id} already archived"}

    try:
        # Read original content
        content = src_file.read_bytes()
        original_size = len(content)

        # Compress to archive
        with gzip.open(dst_file, "wb") as f_out:
            f_out.write(content)

        compressed_size = dst_file.stat().st_size

        # Get chunk metadata from index
        index = _load_index()
        chunk_meta = None
        remaining_chunks = []

        for chunk in index.get("chunks", []):
            if chunk.get("id") == chunk_id:
                chunk_meta = chunk.copy()
            else:
                remaining_chunks.append(chunk)

        if chunk_meta is None:
            # Chunk not in index, create minimal metadata
            chunk_meta = {"id": chunk_id}

        # Update main index (remove chunk)
        index["chunks"] = remaining_chunks
        index["total_chunks"] = len(remaining_chunks)
        _save_index(index)

        # Add to archive index
        archive_index = _load_archive_index()
        archive_entry = chunk_meta.copy()
        archive_entry["archived_at"] = datetime.now().isoformat()
        archive_entry["original_size"] = original_size
        archive_entry["compressed_size"] = compressed_size
        archive_index["archives"].append(archive_entry)
        _save_archive_index(archive_index)

        # Delete original file
        src_file.unlink()

        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        return {
            "status": "archived",
            "chunk_id": chunk_id,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "message": f"Chunk {chunk_id} archived ({compression_ratio:.1f}% compression)",
        }

    except Exception as e:
        # Cleanup on error
        if dst_file.exists():
            dst_file.unlink()
        return {"status": "error", "message": f"Failed to archive {chunk_id}: {str(e)}"}


def restore_chunk(chunk_id: str) -> dict:
    """
    Restore an archived chunk back to active storage.

    Steps:
    1. Find in archive index
    2. Decompress to chunks/
    3. Remove from archive index
    4. Add back to main index
    5. Delete archive file

    Args:
        chunk_id: ID of the chunk to restore

    Returns:
        Dictionary with status and details
    """
    # Validate chunk ID against path traversal
    if not validate_chunk_id(chunk_id):
        return {"status": "error", "message": f"Invalid chunk ID format: {chunk_id}"}

    archive_file = ARCHIVE_DIR / f"{chunk_id}.md.gz"

    if not archive_file.exists():
        return {"status": "error", "message": f"Chunk {chunk_id} not found in archives"}

    dst_file = CHUNKS_DIR / f"{chunk_id}.md"

    # Check if already exists in active storage
    if dst_file.exists():
        return {"status": "error", "message": f"Chunk {chunk_id} already exists in active storage"}

    try:
        # Decompress with size limit (gzip bomb protection)
        with gzip.open(archive_file, "rb") as f_in:
            content = f_in.read(MAX_DECOMPRESSED_SIZE + 1)
            if len(content) > MAX_DECOMPRESSED_SIZE:
                return {
                    "status": "error",
                    "message": f"Decompressed size exceeds {MAX_DECOMPRESSED_SIZE} bytes limit",
                }

        # Ensure chunks directory exists
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

        # Write to active storage
        dst_file.write_bytes(content)

        # Get archive metadata
        archive_index = _load_archive_index()
        archive_meta = None
        remaining_archives = []

        for archive in archive_index.get("archives", []):
            if archive.get("id") == chunk_id:
                archive_meta = archive.copy()
            else:
                remaining_archives.append(archive)

        # Update archive index (remove)
        archive_index["archives"] = remaining_archives
        _save_archive_index(archive_index)

        # Add back to main index
        if archive_meta:
            # Clean up archive-specific fields
            archive_meta.pop("archived_at", None)
            archive_meta.pop("original_size", None)
            archive_meta.pop("compressed_size", None)

            index = _load_index()
            index["chunks"].append(archive_meta)
            index["total_chunks"] = len(index["chunks"])
            _save_index(index)

        # Delete archive file
        archive_file.unlink()

        return {
            "status": "restored",
            "chunk_id": chunk_id,
            "message": f"Chunk {chunk_id} restored to active storage",
        }

    except Exception as e:
        # Cleanup on error
        if dst_file.exists() and not archive_file.exists():
            dst_file.unlink()
        return {"status": "error", "message": f"Failed to restore {chunk_id}: {str(e)}"}


def purge_chunk(chunk_id: str) -> dict:
    """
    Permanently delete an archived chunk.

    Steps:
    1. Find in archive index
    2. Log metadata to purge_log.json (NOT content)
    3. Remove from archive index
    4. Delete archive file

    Args:
        chunk_id: ID of the chunk to purge

    Returns:
        Dictionary with status and details
    """
    # Validate chunk ID against path traversal
    if not validate_chunk_id(chunk_id):
        return {"status": "error", "message": f"Invalid chunk ID format: {chunk_id}"}

    archive_file = ARCHIVE_DIR / f"{chunk_id}.md.gz"

    if not archive_file.exists():
        return {"status": "error", "message": f"Chunk {chunk_id} not found in archives"}

    try:
        # Get archive metadata
        archive_index = _load_archive_index()
        archive_meta = None
        remaining_archives = []

        for archive in archive_index.get("archives", []):
            if archive.get("id") == chunk_id:
                archive_meta = archive.copy()
            else:
                remaining_archives.append(archive)

        # Log to purge log (metadata only, no content)
        purge_log = _load_purge_log()
        purge_entry = {
            "id": chunk_id,
            "purged_at": datetime.now().isoformat(),
            "summary": archive_meta.get("summary", "") if archive_meta else "",
            "tags": archive_meta.get("tags", []) if archive_meta else [],
            "created_at": archive_meta.get("created_at", "") if archive_meta else "",
            "archived_at": archive_meta.get("archived_at", "") if archive_meta else "",
        }
        purge_log["purged"].append(purge_entry)
        _save_purge_log(purge_log)

        # Update archive index (remove)
        archive_index["archives"] = remaining_archives
        _save_archive_index(archive_index)

        # Delete archive file
        archive_file.unlink()

        return {
            "status": "purged",
            "chunk_id": chunk_id,
            "message": f"Chunk {chunk_id} permanently deleted (metadata logged)",
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to purge {chunk_id}: {str(e)}"}


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================


def retention_preview() -> dict:
    """
    Preview retention actions without executing.

    Shows what would be archived or purged based on current rules.

    Returns:
        Dictionary with preview of actions
    """
    archive_candidates = get_archive_candidates()
    purge_candidates = get_purge_candidates()

    return {
        "status": "preview",
        "archive_candidates": [
            {
                "id": c["id"],
                "summary": c.get("summary", "")[:50],
                "created_at": c.get("created_at", c.get("created", ""))[:10],
                "access_count": c.get("access_count", 0),
                "tags": c.get("tags", []),
            }
            for c in archive_candidates
        ],
        "purge_candidates": [
            {
                "id": c["id"],
                "summary": c.get("summary", "")[:50],
                "archived_at": c.get("archived_at", "")[:10],
            }
            for c in purge_candidates
        ],
        "archive_count": len(archive_candidates),
        "purge_count": len(purge_candidates),
    }


def retention_run(archive: bool = True, purge: bool = False) -> dict:
    """
    Execute retention actions.

    Args:
        archive: Archive old unused chunks (default: True)
        purge: Purge very old archives (default: False, requires explicit)

    Returns:
        Dictionary with results of actions
    """
    results = {
        "status": "completed",
        "archived": [],
        "purged": [],
        "errors": [],
    }

    if archive:
        candidates = get_archive_candidates()
        for chunk in candidates:
            result = archive_chunk(chunk["id"])
            if result["status"] == "archived":
                results["archived"].append(result["chunk_id"])
            else:
                results["errors"].append(f"{chunk['id']}: {result['message']}")

    if purge:
        candidates = get_purge_candidates()
        for chunk in candidates:
            result = purge_chunk(chunk["id"])
            if result["status"] == "purged":
                results["purged"].append(result["chunk_id"])
            else:
                results["errors"].append(f"{chunk['id']}: {result['message']}")

    results["archived_count"] = len(results["archived"])
    results["purged_count"] = len(results["purged"])
    results["error_count"] = len(results["errors"])

    return results


def restore(chunk_id: str) -> dict:
    """
    Restore an archived chunk back to active storage.

    Args:
        chunk_id: ID of the archived chunk

    Returns:
        Dictionary with status and message
    """
    return restore_chunk(chunk_id)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_archive_stats() -> dict:
    """
    Get statistics about archived chunks.

    Returns:
        Dictionary with archive statistics
    """
    archive_index = _load_archive_index()
    archives = archive_index.get("archives", [])

    total_original = sum(a.get("original_size", 0) for a in archives)
    total_compressed = sum(a.get("compressed_size", 0) for a in archives)

    return {
        "archive_count": len(archives),
        "total_original_size": total_original,
        "total_compressed_size": total_compressed,
        "compression_ratio": f"{(1 - total_compressed / total_original) * 100:.1f}%"
        if total_original > 0
        else "N/A",
    }


def is_archived(chunk_id: str) -> bool:
    """
    Check if a chunk is in the archive.

    Args:
        chunk_id: ID of the chunk to check

    Returns:
        True if chunk is archived, False otherwise
    """
    if not validate_chunk_id(chunk_id):
        return False
    archive_file = ARCHIVE_DIR / f"{chunk_id}.md.gz"
    return archive_file.exists()
