#!/usr/bin/env python3
"""
RLM MCP Server - Recursive Language Models for Claude Code

A Model Context Protocol server that provides tools for infinite memory
and context management, inspired by MIT CSAIL's RLM paper.

Phase 1: Memory tools (remember, recall)
Phase 2: Navigation tools (peek, grep, chunk)
Phase 3: Sub-agent tools (sub_query)

Usage:
    python server.py              # Run with stdio (for Claude Code)
    python server.py --http       # Run with HTTP (for testing)
"""

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.memory import forget, memory_status, recall, remember
from mcp_server.tools.navigation import chunk, grep, list_chunks, peek
from mcp_server.tools.retention import restore, retention_preview, retention_run
from mcp_server.tools.search import search as bm25_search
from mcp_server.tools.sessions import list_domains, list_sessions

# Initialize the MCP server
mcp = FastMCP("RLM Server")


# =============================================================================
# MEMORY TOOLS
# =============================================================================


@mcp.tool()
def rlm_remember(
    content: str, category: str = "general", importance: str = "medium", tags: str = ""
) -> str:
    """
    Save an important insight to persistent memory.

    Use this to remember key decisions, facts, user preferences, or technical
    findings that should be preserved across the conversation.

    Args:
        content: The insight or fact to remember (be concise but complete)
        category: Type of insight - one of: decision, fact, preference, finding, todo, general
        importance: Priority level - one of: low, medium, high, critical
        tags: Comma-separated keywords for easier retrieval (e.g., "odoo,bug,migration")

    Returns:
        Confirmation with insight ID
    """
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = remember(content, category, importance, tags_list)
    return f"✓ {result['message']} (total: {result['total_insights']})"


@mcp.tool()
def rlm_recall(query: str = "", category: str = "", importance: str = "", limit: int = 10) -> str:
    """
    Retrieve insights from memory.

    Use this to find information discussed earlier, review decisions,
    check user preferences, or get context before answering questions.

    Args:
        query: Search term to filter insights (searches in content and tags)
        category: Filter by type - one of: decision, fact, preference, finding, todo, general
        importance: Filter by priority - one of: low, medium, high, critical
        limit: Maximum number of insights to return (default: 10)

    Returns:
        List of matching insights with their details
    """
    result = recall(
        query=query if query else None,
        category=category if category else None,
        importance=importance if importance else None,
        limit=limit,
    )

    if result["count"] == 0:
        return f"No insights found. Total in memory: {result['total_in_memory']}"

    output_lines = [f"Found {result['count']} insights (total: {result['total_in_memory']}):\n"]

    for i, insight in enumerate(result["insights"], 1):
        tags_str = f" [{', '.join(insight['tags'])}]" if insight.get("tags") else ""
        output_lines.append(
            f"{i}. [{insight['id']}] ({insight['category']}/{insight['importance']}){tags_str}\n"
            f"   {insight['content']}\n"
            f"   — {insight['created_at'][:16]}"
        )

    return "\n\n".join(output_lines)


@mcp.tool()
def rlm_forget(insight_id: str) -> str:
    """
    Remove an insight from memory.

    Args:
        insight_id: The ID of the insight to remove (8-character hex)

    Returns:
        Confirmation of removal
    """
    result = forget(insight_id)
    if result["status"] == "not_found":
        return f"✗ {result['message']}"
    return f"✓ {result['message']} ({result['remaining_insights']} remaining)"


@mcp.tool()
def rlm_status() -> str:
    """
    Get current status of the RLM memory system.

    Returns statistics about stored insights, chunks, and system health.
    Phase 4 addition: Shows chunk access metrics.
    """
    # Memory stats (Phase 1)
    mem_result = memory_status()
    categories_str = ", ".join(f"{k}: {v}" for k, v in mem_result["by_category"].items()) or "none"
    importance_str = (
        ", ".join(f"{k}: {v}" for k, v in mem_result["by_importance"].items()) or "none"
    )

    # Chunks stats (Phase 2)
    chunks_result = list_chunks(limit=1000)  # Get all chunks for accurate count

    # Phase 4.3: Access metrics
    total_accesses = 0
    most_accessed = []

    for c in chunks_result.get("chunks", []):
        access_count = c.get("access_count", 0)
        total_accesses += access_count
        if access_count > 0:
            most_accessed.append((c["id"], c.get("summary", "")[:30], access_count))

    # Sort by access count and take top 3
    most_accessed.sort(key=lambda x: x[2], reverse=True)
    top_accessed = most_accessed[:3]

    # Build access stats string
    access_stats = ""
    if top_accessed:
        access_stats = "\n  Most accessed:\n"
        for chunk_id, summary, count in top_accessed:
            access_stats += f"    - {chunk_id}: {count}x ({summary}...)\n"
    elif chunks_result["total_chunks"] > 0:
        access_stats = "\n  No chunks accessed yet\n"

    return (
        f"RLM Memory Status (v{mem_result['version']})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Insights: {mem_result['total_insights']}\n"
        f"  By category: {categories_str}\n"
        f"  By importance: {importance_str}\n"
        f"Chunks: {chunks_result['total_chunks']} (~{chunks_result['total_tokens_estimate']} tokens)\n"
        f"  Total accesses: {total_accesses}{access_stats}"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Created: {mem_result['created_at'][:16] if mem_result['created_at'] else 'N/A'}\n"
        f"Last updated: {mem_result['last_updated'][:16] if mem_result['last_updated'] else 'never'}"
    )


# =============================================================================
# NAVIGATION TOOLS (Phase 2)
# =============================================================================


@mcp.tool()
def rlm_chunk(
    content: str,
    summary: str = "",
    tags: str = "",
    project: str = "",
    ticket: str = "",
    domain: str = "",
) -> str:
    """
    Save content to an external chunk file for later retrieval.

    Use this to externalize parts of the conversation that you might need
    to reference later but don't need in active context. This helps manage
    long conversations by keeping important history accessible without
    loading it into the main context window.

    Phase 4 enhancements:
    - Auto-generates summary if not provided
    - Detects duplicate content and returns existing chunk ID

    Phase 5.5 enhancements:
    - Supports project/ticket/domain for multi-session organization
    - New chunk ID format: {date}_{project}_{seq}[_{ticket}][_{domain}]

    Args:
        content: The text content to save as a chunk (conversation history, notes, etc.)
        summary: Brief description of what this chunk contains (auto-generated if empty)
        tags: Comma-separated keywords for easier retrieval (e.g., "bp,scenario,2026")
        project: Project name (auto-detected from git if empty)
        ticket: Optional ticket reference (e.g., "JJ-123", "GH-456")
        domain: Optional domain (e.g., "bp", "seo", "r&d", "website")

    Returns:
        Confirmation with chunk ID and token estimate
    """
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = chunk(
        content=content,
        summary=summary,
        tags=tags_list,
        project=project if project else None,
        ticket=ticket if ticket else None,
        domain=domain if domain else None,
    )

    # Phase 4.2: Handle duplicate detection
    if result["status"] == "duplicate":
        return (
            f"⚠ Duplicate content detected!\n"
            f"  Existing chunk: {result['existing_chunk_id']}\n"
            f"  Summary: {result['existing_summary']}"
        )

    # Include auto-generated summary in response
    return f"✓ {result['message']}\n  Summary: {result.get('summary', 'N/A')}"


@mcp.tool()
def rlm_peek(chunk_id: str, start: int = 0, end: int = -1) -> str:
    """
    Read content from a previously saved chunk.

    Use this to view the contents of a chunk you saved earlier.
    Can read the whole chunk or just a portion by specifying line numbers.

    Args:
        chunk_id: ID of the chunk to read (e.g., "2026-01-18_001")
        start: Starting line number, 0-indexed (default: 0 = beginning)
        end: Ending line number, -1 for all (default: -1 = until end)

    Returns:
        Content of the requested chunk portion
    """
    end_param = None if end == -1 else end
    result = peek(chunk_id, start, end_param)

    if result["status"] == "not_found":
        return f"✗ {result['message']}"

    return (
        f"Chunk {result['chunk_id']} (lines {result['showing_lines']} of {result['total_lines']}):\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{result['content']}"
    )


@mcp.tool()
def rlm_grep(
    pattern: str,
    limit: int = 10,
    project: str = "",
    domain: str = "",
    fuzzy: bool = False,
    fuzzy_threshold: int = 80,
    date_from: str = "",
    date_to: str = "",
    entity: str = "",
) -> str:
    """
    Search for a pattern across all saved chunks.

    Use this to find where a topic was discussed or where specific
    information is stored in your conversation history.

    Phase 5.2: Supports fuzzy matching (tolerates typos like "validaton" → "validation").
    Phase 5.5c: Supports filtering by project and domain.
    Phase 7.1: Supports temporal filtering by date range.
    Phase 7.2: Supports filtering by entity.

    Args:
        pattern: Text or regex pattern to search for (case-insensitive)
        limit: Maximum number of matches to return (default: 10)
        project: Filter by project name (e.g., "RLM", "JoyJuice")
        domain: Filter by domain (e.g., "bp", "seo", "r&d")
        fuzzy: Enable fuzzy matching (tolerates typos, Phase 5.2)
        fuzzy_threshold: Minimum similarity score 0-100 for fuzzy (default: 80)
        date_from: Start date inclusive, YYYY-MM-DD (e.g., "2026-01-25")
        date_to: End date inclusive, YYYY-MM-DD (e.g., "2026-01-30")
        entity: Filter by entity name (file, module, version, etc.)

    Returns:
        List of matches with chunk IDs and context
    """
    result = grep(
        pattern,
        limit,
        project=project if project else None,
        domain=domain if domain else None,
        fuzzy=fuzzy,
        fuzzy_threshold=fuzzy_threshold,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        entity=entity if entity else None,
    )

    # Handle error (e.g., thefuzz not installed)
    if result.get("status") == "error":
        return f"Error: {result['message']}"

    if result["match_count"] == 0:
        filters = []
        if project:
            filters.append(f"project={project}")
        if domain:
            filters.append(f"domain={domain}")
        if fuzzy:
            filters.append(f"fuzzy≥{fuzzy_threshold}")
        filter_str = f" (filters: {', '.join(filters)})" if filters else ""
        return f"No matches found for pattern: {pattern}{filter_str}"

    # Build output header
    fuzzy_str = f" (fuzzy≥{result.get('threshold', 80)})" if result.get("fuzzy") else ""
    output = [f"Found {result['match_count']} match(es) for '{pattern}'{fuzzy_str}:\n"]

    for i, match in enumerate(result["matches"], 1):
        # Include score if fuzzy
        score_str = f" score:{match['score']}" if "score" in match else ""
        output.append(
            f"{i}. [{match['chunk_id']}] line {match['line_number']}{score_str}\n"
            f"   Summary: {match['chunk_summary']}\n"
            f"   Context: {match['context'][:200]}{'...' if len(match['context']) > 200 else ''}"
        )

    return "\n\n".join(output)


@mcp.tool()
def rlm_search(
    query: str,
    limit: int = 5,
    project: str = "",
    domain: str = "",
    date_from: str = "",
    date_to: str = "",
    entity: str = "",
) -> str:
    """
    Search chunks using BM25 ranking (Phase 5.1).

    More effective than grep for natural language queries.
    Returns chunks ranked by relevance score.

    Uses French/English tokenization with accent normalization.

    Phase 5.5c: Supports filtering by project and domain.
    Phase 7.1: Supports temporal filtering by date range.
    Phase 7.2: Supports filtering by entity.

    Args:
        query: Natural language search query (e.g., "business plan discussion")
        limit: Maximum results (default: 5)
        project: Filter by project name (e.g., "RLM", "JoyJuice")
        domain: Filter by domain (e.g., "bp", "seo", "r&d")
        date_from: Start date inclusive, YYYY-MM-DD (e.g., "2026-01-25")
        date_to: End date inclusive, YYYY-MM-DD (e.g., "2026-01-30")
        entity: Filter by entity name (file, module, version, etc.)

    Returns:
        Ranked list of matching chunks with scores
    """
    result = bm25_search(
        query,
        limit,
        project=project if project else None,
        domain=domain if domain else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        entity=entity if entity else None,
    )

    if result["status"] == "error":
        return f"Error: {result['message']}"

    if result["result_count"] == 0:
        return f"No matching chunks found for: {query}"

    output = [f"Top {result['result_count']} results for '{query}':\n"]

    for i, r in enumerate(result["results"], 1):
        output.append(
            f"{i}. [{r['chunk_id']}] score: {r['score']:.2f}\n"
            f"   {r['summary'][:80]}{'...' if len(r['summary']) > 80 else ''}"
        )

    return "\n\n".join(output)


@mcp.tool()
def rlm_list_chunks(limit: int = 20) -> str:
    """
    List all available chunks with their metadata.

    Use this to see what conversation history is available in external
    storage before deciding what to peek or grep.

    Args:
        limit: Maximum number of chunks to list (default: 20)

    Returns:
        List of chunks with summaries, tags, and token counts
    """
    result = list_chunks(limit)

    if result["total_chunks"] == 0:
        return "No chunks stored yet. Use rlm_chunk to save conversation history."

    output = [
        f"Chunks in storage: {result['total_chunks']} (~{result['total_tokens_estimate']} tokens)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for c in result["chunks"]:
        tags_str = f" [{', '.join(c['tags'])}]" if c["tags"] else ""
        output.append(
            f"\n{c['id']}{tags_str}\n  {c['summary']}\n  ~{c['tokens']} tokens | {c['created']}"
        )

    return "".join(output)


# =============================================================================
# SESSION TOOLS (Phase 5.5b)
# =============================================================================


@mcp.tool()
def rlm_sessions(project: str = "", domain: str = "", limit: int = 10) -> str:
    """
    List available sessions, optionally filtered by project or domain.

    Sessions group chunks by working context. Use this to navigate
    conversation history across different projects or work domains.

    Args:
        project: Filter by project name (e.g., "RLM", "JoyJuice")
        domain: Filter by domain (e.g., "bp", "seo", "r&d")
        limit: Maximum number of sessions to return (default: 10)

    Returns:
        List of sessions with their metadata
    """
    result = list_sessions(
        project=project if project else None, domain=domain if domain else None, limit=limit
    )

    if result["total"] == 0:
        filters = []
        if project:
            filters.append(f"project={project}")
        if domain:
            filters.append(f"domain={domain}")
        filter_str = f" (filters: {', '.join(filters)})" if filters else ""
        return f"No sessions found{filter_str}. Sessions are created when you chunk with project/domain."

    output = [
        f"Sessions: {result['showing']}/{result['total']}\n"
        f"Current: {result['current_session'] or 'None'}\n"
        f"{'=' * 40}"
    ]

    for s in result["sessions"]:
        domain_str = f" [{s['domain']}]" if s.get("domain") else ""
        ticket_str = f" ({s['ticket']})" if s.get("ticket") else ""
        output.append(
            f"\n{s['id']}{domain_str}{ticket_str}\n"
            f"  Project: {s['project']}\n"
            f"  Chunks: {len(s.get('chunks', []))}\n"
            f"  Started: {s['started'][:16]}"
        )

    return "".join(output)


@mcp.tool()
def rlm_domains() -> str:
    """
    List available domains from domains.json.

    Domains help categorize chunks by topic/area. This returns the
    suggested domains, but you can use any domain string you want.

    Returns:
        List of domains organized by category
    """
    result = list_domains()

    output = [
        f"RLM Domains (v{result['version']})\n"
        f"{result['description']}\n"
        f"{'=' * 40}\n"
        f"Total: {result['total']} domains\n"
    ]

    for category, info in result["domains"].items():
        domains_list = ", ".join(info.get("list", []))
        output.append(f"\n[{category}] {info.get('description', '')}\n  {domains_list}")

    output.append("\n\nNote: You can use any domain, these are just suggestions.")

    return "".join(output)


# =============================================================================
# RETENTION TOOLS (Phase 5.6)
# =============================================================================


@mcp.tool()
def rlm_retention_preview() -> str:
    """
    Preview retention actions without executing.

    Shows what would be archived or purged based on current rules.
    Use this to validate before running rlm_retention_run().
    """
    result = retention_preview()

    output = ["Retention Preview (dry-run)\n=" * 40]

    # Archive candidates
    archive_count = result["archive_count"]
    output.append(f"\nArchive candidates ({archive_count}):")

    if archive_count == 0:
        output.append("  None - all chunks are recent, accessed, or immune")
    else:
        for c in result["archive_candidates"][:10]:
            tags_str = f" [{', '.join(c['tags'][:3])}]" if c.get("tags") else ""
            output.append(
                f"  - {c['id']}{tags_str}\n    {c['summary']}... (access: {c['access_count']})"
            )
        if archive_count > 10:
            output.append(f"  ... and {archive_count - 10} more")

    # Purge candidates
    purge_count = result["purge_count"]
    output.append(f"\nPurge candidates ({purge_count}):")

    if purge_count == 0:
        output.append("  None - no archives old enough for purging")
    else:
        for c in result["purge_candidates"][:10]:
            output.append(f"  - {c['id']} (archived: {c['archived_at']})\n    {c['summary']}...")
        if purge_count > 10:
            output.append(f"  ... and {purge_count - 10} more")

    return "\n".join(output)


@mcp.tool()
def rlm_retention_run(archive: bool = True, purge: bool = False) -> str:
    """
    Execute retention actions.

    Args:
        archive: Archive old unused chunks (default: True)
        purge: Purge very old archives (default: False, requires explicit)

    Returns:
        Summary of actions taken
    """
    result = retention_run(archive=archive, purge=purge)

    output = ["Retention Execution\n=" * 40]

    # Archived
    if result["archived_count"] > 0:
        output.append(f"\n✓ Archived {result['archived_count']} chunk(s):")
        for chunk_id in result["archived"][:5]:
            output.append(f"  - {chunk_id}")
        if result["archived_count"] > 5:
            output.append(f"  ... and {result['archived_count'] - 5} more")
    else:
        output.append("\n✓ No chunks archived")

    # Purged
    if result["purged_count"] > 0:
        output.append(f"\n✓ Purged {result['purged_count']} archive(s):")
        for chunk_id in result["purged"][:5]:
            output.append(f"  - {chunk_id}")
        if result["purged_count"] > 5:
            output.append(f"  ... and {result['purged_count'] - 5} more")
    elif purge:
        output.append("\n✓ No archives purged")

    # Errors
    if result["error_count"] > 0:
        output.append(f"\n✗ Errors ({result['error_count']}):")
        for error in result["errors"][:3]:
            output.append(f"  - {error}")

    return "\n".join(output)


@mcp.tool()
def rlm_restore(chunk_id: str) -> str:
    """
    Restore an archived chunk back to active storage.

    Args:
        chunk_id: ID of the archived chunk

    Returns:
        Confirmation message
    """
    result = restore(chunk_id)

    if result["status"] == "restored":
        return f"✓ {result['message']}"
    else:
        return f"✗ {result['message']}"


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Entry point for the MCP RLM server."""
    import sys

    if "--http" in sys.argv:
        # HTTP mode for testing
        mcp.run(transport="streamable-http")
    else:
        # Default: stdio for Claude Code
        mcp.run()


if __name__ == "__main__":
    main()
