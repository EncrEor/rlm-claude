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
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .fileutil import (
    CONTEXT_DIR,
    MAX_CHUNK_CONTENT_SIZE,
    atomic_write_json,
    atomic_write_text,
    locked_json_update,
    safe_path,
)
from .sessions import add_chunk_to_session, register_session

# Phase 5.2: Fuzzy matching (optional dependency)
try:
    from thefuzz import fuzz

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


CHUNKS_DIR = CONTEXT_DIR / "chunks"
ARCHIVE_DIR = CONTEXT_DIR / "archive"
INDEX_FILE = CONTEXT_DIR / "index.json"


# =============================================================================
# PHASE 5.5: Multi-sessions support
# =============================================================================


def _detect_project() -> str:
    """
    Auto-detect project name from environment or git (Phase 5.5).

    Priority:
    1. RLM_PROJECT environment variable (explicit override)
    2. Git repository name (most reliable)
    3. Current working directory name (fallback)

    Returns:
        Project name string
    """
    # 1. Environment variable (explicit)
    if project := os.getenv("RLM_PROJECT"):
        return project

    # 2. Git repository name
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 3. Fallback to current directory
    return Path.cwd().name


def parse_chunk_id(chunk_id: str) -> dict:
    """
    Parse chunk ID into components (Phase 5.5).

    Handles both format 1.0 (legacy) and 2.0 (multi-session).

    Format 1.0: {date}_{seq} (e.g., "2026-01-18_001")
    Format 2.0: {date}_{project}_{seq}[_{ticket}][_{domain}]

    Args:
        chunk_id: The chunk ID to parse

    Returns:
        Dictionary with parsed components:
        - date, sequence, project, ticket, domain, format
    """
    parts = chunk_id.split("_")

    if len(parts) == 2:
        # Format 1.0: 2026-01-18_001
        return {
            "date": parts[0],
            "sequence": parts[1],
            "project": None,
            "ticket": None,
            "domain": None,
            "format": "1.0",
        }

    elif len(parts) >= 3:
        # Format 2.0: 2026-01-18_RLM_001[_ticket][_domain]
        result = {
            "date": parts[0],
            "project": parts[1],
            "sequence": parts[2],
            "ticket": None,
            "domain": None,
            "format": "2.0",
        }

        # Parse optional parts (ticket or domain)
        for part in parts[3:]:
            # Tickets start with common prefixes
            if any(part.upper().startswith(p) for p in ["TIC-", "ISSUE-", "#", "JJ-", "GH-"]):
                result["ticket"] = part
            else:
                # Assume it's a domain
                result["domain"] = part

        return result

    # Unknown format
    return {"raw": chunk_id, "format": "unknown"}


def _load_index() -> dict:
    """Load chunks index from JSON file."""
    if not INDEX_FILE.exists():
        return {
            "version": "2.0.0",
            "created_at": datetime.now().isoformat(),
            "chunks": [],
            "total_chunks": 0,
            "total_tokens_estimate": 0,
            "last_chunking": None,
        }

    with open(INDEX_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Migrate from v1 if needed
    if data.get("version", "1.0.0") == "1.0.0":
        data["version"] = "2.0.0"
        data["total_chunks"] = len(data.get("chunks", []))

    return data


def _save_index(index: dict) -> None:
    """Save chunks index atomically."""
    index["last_chunking"] = datetime.now().isoformat()
    index["total_chunks"] = len(index.get("chunks", []))
    atomic_write_json(INDEX_FILE, index)


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
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    if not lines:
        return "Empty content"

    # Take first meaningful line
    first_line = lines[0]

    # Skip markdown headers for better summary
    if first_line.startswith("#"):
        first_line = first_line.lstrip("#").strip()

    # Truncate if too long
    if len(first_line) > max_length:
        return first_line[: max_length - 3] + "..."

    return first_line


def _content_hash(content: str) -> str:
    """
    Generate hash of normalized content for duplicate detection (Phase 4.2).

    Normalizes whitespace and lowercases before hashing to catch
    near-duplicates.

    Args:
        content: The text content to hash

    Returns:
        SHA256 hash of normalized content (64 chars)
    """
    # Normalize: lowercase, collapse whitespace
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _parse_date_from_chunk(chunk_info: dict) -> str | None:
    """
    Extract date string (YYYY-MM-DD) from chunk metadata or ID.

    Tries created_at first, then falls back to parsing the chunk ID.

    Args:
        chunk_info: Chunk metadata dict from index.json

    Returns:
        Date string in YYYY-MM-DD format, or None if unparseable
    """
    # Try created_at field first (most reliable)
    created_at = chunk_info.get("created_at", "")
    if created_at and len(created_at) >= 10:
        return created_at[:10]

    # Fallback: parse from chunk ID (format starts with YYYY-MM-DD)
    chunk_id = chunk_info.get("id", "")
    if len(chunk_id) >= 10 and chunk_id[4] == "-" and chunk_id[7] == "-":
        return chunk_id[:10]

    return None


def _chunk_in_date_range(chunk_info: dict, date_from: str | None, date_to: str | None) -> bool:
    """
    Check if a chunk falls within a date range.

    Uses simple string comparison on YYYY-MM-DD format (lexicographic = chronologic).

    Args:
        chunk_info: Chunk metadata dict from index.json
        date_from: Start date inclusive (YYYY-MM-DD) or None
        date_to: End date inclusive (YYYY-MM-DD) or None

    Returns:
        True if within range (or no range specified), False otherwise
    """
    if date_from is None and date_to is None:
        return True

    chunk_date = _parse_date_from_chunk(chunk_info)
    if chunk_date is None:
        return False

    if date_from and chunk_date < date_from:
        return False
    if date_to and chunk_date > date_to:
        return False

    return True


def _extract_entities(content: str, max_entities: int = 50) -> dict:
    """
    Extract named entities from chunk content (Phase 7.2, MAGMA-inspired).

    Uses regex patterns to identify domain-specific entities:
    files, versions, modules, tickets, and functions.

    Zero external dependencies — pattern-based extraction only.

    Args:
        content: Text content to extract entities from
        max_entities: Maximum total entities across all types (default: 50)

    Returns:
        Dictionary with typed entity lists:
        {"files": [...], "versions": [...], "modules": [...],
         "tickets": [...], "functions": [...]}
    """
    entities: dict[str, set[str]] = {
        "files": set(),
        "versions": set(),
        "modules": set(),
        "tickets": set(),
        "functions": set(),
    }

    if not content or not content.strip():
        return {k: sorted(v) for k, v in entities.items()}

    # 1. Files: paths with common extensions
    file_pattern = re.compile(
        r"(?:^|[\s`\"'(,;|])("
        r"(?:[\w./\\-]+/)?"  # optional directory prefix
        r"[\w.-]+"  # filename
        r"\.(?:py|js|ts|jsx|tsx|md|xml|json|css|html|yml|yaml|toml|cfg|conf|sh|sql|csv)"
        r")"
        r"(?:[\s`\"'),:;|]|$)",
        re.MULTILINE,
    )
    for m in file_pattern.finditer(content):
        entities["files"].add(m.group(1))

    # 2. Versions: vX.Y.Z or X.Y.Z.W (3+ segments)
    version_pattern = re.compile(
        r"(?:^|[\s`\"'(,;|v])"
        r"(v?\d+\.\d+\.\d+(?:\.\d+)*)"
        r"(?:[\s`\"'),:;|]|$)",
        re.MULTILINE,
    )
    for m in version_pattern.finditer(content):
        v = m.group(1)
        # Skip dates (YYYY-MM-DD looks like 3 segments but has 4-digit first)
        if re.match(r"^\d{4}\.\d{2}\.\d{2}$", v):
            continue
        entities["versions"].add(v)

    # 3. Modules: snake_case identifiers after keywords
    # Pattern allows optional intermediate keywords (e.g., "install module X")
    module_pattern = re.compile(
        r"(?:pip\s+install|import|from|module|package|install)"
        r"(?:\s+(?:module|package))?"  # optional second keyword
        r"\s+([a-z][a-z0-9_]+(?:\.[a-z][a-z0-9_]+)*)",
        re.IGNORECASE,
    )
    skip_modules = {
        "the",
        "for",
        "and",
        "not",
        "all",
        "module",
        "install",
        "package",
        "import",
        "from",
        "pip",
        "with",
        "this",
        "that",
    }
    for m in module_pattern.finditer(content):
        mod = m.group(1).lower()
        # Skip very short or common words
        if len(mod) > 2 and mod not in skip_modules:
            entities["modules"].add(mod)

    # 4. Tickets: PREFIX-123 format (2+ uppercase letters, dash, 1+ digits)
    ticket_pattern = re.compile(r"\b([A-Z]{2,}-\d+)\b")
    for m in ticket_pattern.finditer(content):
        entities["tickets"].add(m.group(1))

    # 5. Functions: identifier() pattern
    func_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)")
    for m in func_pattern.finditer(content):
        fn = m.group(1)
        # Skip very short or common patterns
        if len(fn) > 1 and fn not in ("if", "for", "in"):
            entities["functions"].add(f"{fn}()")

    # Enforce max_entities limit (distribute evenly then fill)
    result = {}
    total = 0
    for key in entities:
        sorted_vals = sorted(entities[key])
        remaining = max_entities - total
        if remaining <= 0:
            result[key] = []
        else:
            result[key] = sorted_vals[:remaining]
            total += len(result[key])

    return result


def _entity_matches(chunk_info: dict, entity: str) -> bool:
    """
    Check if a chunk's entities contain a given entity (Phase 7.2).

    Performs case-insensitive substring matching across all entity types.

    Args:
        chunk_info: Chunk metadata dict from index.json
        entity: Entity string to search for

    Returns:
        True if any stored entity matches, False otherwise
    """
    chunk_entities = chunk_info.get("entities", {})
    if not chunk_entities or not isinstance(chunk_entities, dict):
        return False

    entity_lower = entity.lower()
    for vals in chunk_entities.values():
        if isinstance(vals, list):
            for e in vals:
                if entity_lower in str(e).lower():
                    return True
    return False


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

    Uses file locking to prevent race conditions on concurrent access.

    Args:
        chunk_id: ID of the chunk being accessed
    """
    default_index = {
        "version": "2.0.0",
        "created_at": datetime.now().isoformat(),
        "chunks": [],
        "total_chunks": 0,
        "total_tokens_estimate": 0,
        "last_chunking": None,
    }

    with locked_json_update(INDEX_FILE, default=default_index) as index:
        for chunk_info in index.get("chunks", []):
            if chunk_info["id"] == chunk_id:
                chunk_info["access_count"] = chunk_info.get("access_count", 0) + 1
                chunk_info["last_accessed"] = datetime.now().isoformat()
                break
        index["last_chunking"] = datetime.now().isoformat()
        index["total_chunks"] = len(index.get("chunks", []))


def _generate_chunk_id(project: str = None, ticket: str = None, domain: str = None) -> str:
    """
    Generate a unique chunk ID (Phase 5.5 enhanced).

    Format 2.0: {date}_{project}_{seq}[_{ticket}][_{domain}]

    Args:
        project: Project name (auto-detected if None)
        ticket: Optional ticket reference (e.g., "JJ-123")
        domain: Optional domain (e.g., "bp", "seo")

    Returns:
        Unique chunk ID string
    """
    today = datetime.now().strftime("%Y-%m-%d")
    index = _load_index()

    # Auto-detect project if not provided
    if project is None:
        project = _detect_project()

    # Find existing chunks for today + project
    existing_today = [
        c for c in index["chunks"] if c["id"].startswith(today) and c.get("project") == project
    ]

    sequence = len(existing_today) + 1

    # Build ID parts
    parts = [today, project, f"{sequence:03d}"]

    if ticket:
        parts.append(ticket)
    if domain:
        parts.append(domain)

    return "_".join(parts)


def chunk(
    content: str,
    summary: str = "",
    tags: list[str] | None = None,
    project: str = None,
    ticket: str = None,
    domain: str = None,
) -> dict:
    """
    Save content to an external chunk file.

    Use this to externalize parts of the conversation that you might need
    to reference later but don't need in active context.

    Phase 4 enhancements:
    - Auto-generates summary if not provided
    - Detects duplicate content via hash
    - Stores content hash for future duplicate checks

    Phase 5.5 enhancements:
    - Supports project/ticket/domain for multi-session organization
    - New chunk ID format: {date}_{project}_{seq}[_{ticket}][_{domain}]

    Args:
        content: The text content to save as a chunk
        summary: Brief description of what this chunk contains (auto-generated if empty)
        tags: Keywords for easier retrieval
        project: Project name (auto-detected if None)
        ticket: Optional ticket reference (e.g., "JJ-123")
        domain: Optional domain (e.g., "bp", "seo", "r&d")

    Returns:
        Dictionary with chunk_id and confirmation, or duplicate status
    """
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 6: Content size limit
    if len(content) > MAX_CHUNK_CONTENT_SIZE:
        return {
            "status": "error",
            "message": f"Content too large ({len(content)} bytes). Maximum: {MAX_CHUNK_CONTENT_SIZE} bytes.",
        }

    # Phase 4.2: Check for duplicates
    content_hash = _content_hash(content)
    existing = _check_duplicate(content_hash)

    if existing:
        return {
            "status": "duplicate",
            "existing_chunk_id": existing["id"],
            "existing_summary": existing.get("summary", ""),
            "message": f"Content already exists in chunk {existing['id']}",
        }

    # Phase 4.1: Auto-generate summary if not provided
    if not summary:
        summary = _auto_summarize(content)

    # Phase 7.2: Extract entities from content
    entities = _extract_entities(content)

    # Phase 5.5: Generate ID with project/ticket/domain
    chunk_id = _generate_chunk_id(project=project, ticket=ticket, domain=domain)
    chunk_file = CHUNKS_DIR / f"{chunk_id}.md"
    tokens = _estimate_tokens(content)

    # Resolve project for metadata (in case it was auto-detected)
    resolved_project = project if project else _detect_project()

    # Build entities string for YAML header
    entities_yaml_parts = []
    for etype, evals in entities.items():
        if evals:
            entities_yaml_parts.append(f"  {etype}: {', '.join(evals)}")
    entities_yaml = "\n".join(entities_yaml_parts) if entities_yaml_parts else "  (none)"

    # Create chunk file with metadata header
    header = f"""---
id: {chunk_id}
summary: {summary}
tags: {", ".join(tags or [])}
entities:
{entities_yaml}
project: {resolved_project}
ticket: {ticket or ""}
domain: {domain or ""}
created_at: {datetime.now().isoformat()}
tokens_estimate: {tokens}
content_hash: {content_hash}
format_version: "2.0"
---

"""

    atomic_write_text(chunk_file, header + content)

    # Update index
    index = _load_index()
    index["chunks"].append(
        {
            "id": chunk_id,
            "file": f"chunks/{chunk_id}.md",
            "summary": summary,
            "tags": tags or [],
            "tokens_estimate": tokens,
            "content_hash": content_hash,
            "access_count": 0,
            "last_accessed": None,
            "created_at": datetime.now().isoformat(),
            # Phase 5.5 fields
            "project": resolved_project,
            "ticket": ticket,
            "domain": domain,
            "format_version": "2.0",
            # Phase 7.2 fields
            "entities": entities,
        }
    )
    index["total_tokens_estimate"] = sum(c["tokens_estimate"] for c in index["chunks"])
    _save_index(index)

    # Phase 5.5: Register session and link chunk
    if resolved_project:
        # Create or get session for this project/domain combo
        session_id = f"{datetime.now().strftime('%Y-%m-%d')}_{resolved_project}"
        if domain:
            session_id += f"_{domain}"

        register_session(
            session_id=session_id,
            project=resolved_project,
            path=str(Path.cwd()),
            domain=domain or "",
            ticket=ticket or "",
        )
        add_chunk_to_session(chunk_id, session_id)

    return {
        "status": "created",
        "chunk_id": chunk_id,
        "tokens_estimate": tokens,
        "summary": summary,
        "message": f"Chunk {chunk_id} created ({tokens} tokens estimated)",
    }


def peek(chunk_id: str, start: int = 0, end: int | None = None) -> dict:
    """
    Read content from a chunk file.

    Use this to view the contents of a previously saved chunk.
    Can read the whole chunk or just a portion (by line numbers).

    Phase 4.3: Increments access counter on successful read.
    Phase 5.6: Auto-restores from archive if not in active storage.

    Args:
        chunk_id: ID of the chunk to read
        start: Starting line number (0-indexed, default: 0)
        end: Ending line number (exclusive, default: all)

    Returns:
        Dictionary with chunk content and metadata
    """
    # Phase 6: Validate chunk ID against path traversal
    chunk_file = safe_path(CHUNKS_DIR, chunk_id, ".md")
    if chunk_file is None:
        return {"status": "error", "message": f"Invalid chunk ID format: {chunk_id}"}

    # Phase 5.6: Check archives if not in active storage
    if not chunk_file.exists():
        archive_file = safe_path(ARCHIVE_DIR, chunk_id, ".md.gz")
        if archive_file is None:
            return {"status": "error", "message": f"Invalid chunk ID format: {chunk_id}"}
        if archive_file.exists():
            # Auto-restore from archive
            try:
                from .retention import restore_chunk

                result = restore_chunk(chunk_id)
                if result["status"] != "restored":
                    return {
                        "status": "error",
                        "message": f"Failed to restore {chunk_id} from archive: {result['message']}",
                    }
                # Now chunk_file should exist
            except ImportError:
                return {
                    "status": "error",
                    "message": f"Chunk {chunk_id} is archived but retention module unavailable",
                }
        else:
            return {"status": "not_found", "message": f"Chunk {chunk_id} not found"}

    with open(chunk_file, encoding="utf-8") as f:
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
        "content": "".join(selected_lines),
    }


def grep(
    pattern: str,
    limit: int = 10,
    context_lines: int = 1,
    project: str = None,
    domain: str = None,
    fuzzy: bool = False,
    fuzzy_threshold: int = 80,
    date_from: str = None,
    date_to: str = None,
    entity: str = None,
) -> dict:
    """
    Search for a pattern across all chunks.

    Use this to find where a topic was discussed or where
    specific information is stored.

    Phase 5.2: Supports fuzzy matching (tolerates typos).
    Phase 5.5c: Supports filtering by project and domain.
    Phase 7.1: Supports temporal filtering by date range.
    Phase 7.2: Supports filtering by entity.

    Args:
        pattern: Text or regex pattern to search for
        limit: Maximum number of matches to return
        context_lines: Number of lines before/after match to include
        project: Filter by project name (Phase 5.5c)
        domain: Filter by domain (Phase 5.5c)
        fuzzy: Enable fuzzy matching (Phase 5.2)
        fuzzy_threshold: Minimum similarity score 0-100 (Phase 5.2)
        date_from: Start date inclusive, YYYY-MM-DD (Phase 7.1)
        date_to: End date inclusive, YYYY-MM-DD (Phase 7.1)
        entity: Filter by entity name, case-insensitive substring (Phase 7.2)

    Returns:
        Dictionary with list of matches
    """
    # Phase 5.2: Dispatch to fuzzy search if enabled
    if fuzzy:
        return grep_fuzzy(
            pattern, fuzzy_threshold, limit, project, domain, date_from, date_to, entity
        )

    index = _load_index()
    matches = []

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If invalid regex, treat as literal string
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    for chunk_info in index.get("chunks", []):
        # Phase 7.1: Apply temporal filter
        if not _chunk_in_date_range(chunk_info, date_from, date_to):
            continue
        # Phase 5.5c: Apply project/domain filters
        if project and chunk_info.get("project") != project:
            continue
        if domain and chunk_info.get("domain") != domain:
            continue
        # Phase 7.2: Apply entity filter
        if entity and not _entity_matches(chunk_info, entity):
            continue
        chunk_file = CONTEXT_DIR / chunk_info["file"]

        if not chunk_file.exists():
            continue

        with open(chunk_file, encoding="utf-8") as f:
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

                matches.append(
                    {
                        "chunk_id": chunk_info["id"],
                        "chunk_summary": chunk_info.get("summary", ""),
                        "line_number": i + 1,
                        "context": context.strip(),
                    }
                )

                if len(matches) >= limit:
                    break

        if len(matches) >= limit:
            break

    return {
        "status": "success",
        "pattern": pattern,
        "match_count": len(matches),
        "matches": matches,
    }


# =============================================================================
# PHASE 5.2: Fuzzy Search (Grep++)
# =============================================================================


def grep_fuzzy(
    pattern: str,
    threshold: int = 80,
    limit: int = 10,
    project: str = None,
    domain: str = None,
    date_from: str = None,
    date_to: str = None,
    entity: str = None,
) -> dict:
    """
    Fuzzy grep - find matches even with typos (Phase 5.2).

    Uses thefuzz library for approximate string matching.
    Tolerates typos like "validaton" finding "validation".

    Phase 7.1: Supports temporal filtering by date range.
    Phase 7.2: Supports filtering by entity.

    Args:
        pattern: Text to search for (not regex, fuzzy matching)
        threshold: Minimum similarity score 0-100 (default: 80)
        limit: Maximum number of matches to return
        project: Filter by project name (Phase 5.5c)
        domain: Filter by domain (Phase 5.5c)
        date_from: Start date inclusive, YYYY-MM-DD (Phase 7.1)
        date_to: End date inclusive, YYYY-MM-DD (Phase 7.1)
        entity: Filter by entity name, case-insensitive substring (Phase 7.2)

    Returns:
        Dictionary with matches sorted by similarity score
    """
    if not FUZZY_AVAILABLE:
        return {
            "status": "error",
            "message": "Fuzzy search requires thefuzz: pip install mcp-rlm-server[fuzzy]",
        }

    index = _load_index()
    matches = []

    for chunk_info in index.get("chunks", []):
        # Phase 7.1: Apply temporal filter
        if not _chunk_in_date_range(chunk_info, date_from, date_to):
            continue
        # Phase 5.5c: Apply project/domain filters
        if project and chunk_info.get("project") != project:
            continue
        if domain and chunk_info.get("domain") != domain:
            continue
        # Phase 7.2: Apply entity filter
        if entity and not _entity_matches(chunk_info, entity):
            continue

        chunk_file = CONTEXT_DIR / chunk_info["file"]

        if not chunk_file.exists():
            continue

        with open(chunk_file, encoding="utf-8") as f:
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

        # Search line by line with fuzzy matching
        for i, line in enumerate(content_lines):
            line_text = line.strip()
            if not line_text:
                continue

            # partial_ratio finds best partial match (handles substrings)
            score = fuzz.partial_ratio(pattern.lower(), line_text.lower())

            if score >= threshold:
                matches.append(
                    {
                        "chunk_id": chunk_info["id"],
                        "chunk_summary": chunk_info.get("summary", ""),
                        "line_number": i + 1,
                        "score": score,
                        "context": line_text[:150],  # Truncate for readability
                    }
                )

    # Sort by score (highest first)
    matches.sort(key=lambda x: x["score"], reverse=True)

    return {
        "status": "success",
        "pattern": pattern,
        "fuzzy": True,
        "threshold": threshold,
        "match_count": len(matches[:limit]),
        "matches": matches[:limit],
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
    chunks_sorted = sorted(chunks, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

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
                "last_accessed": c.get("last_accessed", "")[:16]
                if c.get("last_accessed")
                else None,
            }
            for c in chunks_sorted
        ],
    }
