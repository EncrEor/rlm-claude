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
from tools.memory import remember, recall, forget, memory_status
from tools.navigation import chunk, peek, grep, list_chunks

# Initialize the MCP server
mcp = FastMCP("RLM Server")


# =============================================================================
# MEMORY TOOLS
# =============================================================================

@mcp.tool()
def rlm_remember(
    content: str,
    category: str = "general",
    importance: str = "medium",
    tags: str = ""
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
def rlm_recall(
    query: str = "",
    category: str = "",
    importance: str = "",
    limit: int = 10
) -> str:
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
        limit=limit
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
    importance_str = ", ".join(f"{k}: {v}" for k, v in mem_result["by_importance"].items()) or "none"

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
    elif chunks_result['total_chunks'] > 0:
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
    tags: str = ""
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

    Args:
        content: The text content to save as a chunk (conversation history, notes, etc.)
        summary: Brief description of what this chunk contains (auto-generated if empty)
        tags: Comma-separated keywords for easier retrieval (e.g., "bp,scenario,2026")

    Returns:
        Confirmation with chunk ID and token estimate
    """
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = chunk(content, summary, tags_list)

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
def rlm_peek(
    chunk_id: str,
    start: int = 0,
    end: int = -1
) -> str:
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
    limit: int = 10
) -> str:
    """
    Search for a pattern across all saved chunks.

    Use this to find where a topic was discussed or where specific
    information is stored in your conversation history.

    Args:
        pattern: Text or regex pattern to search for (case-insensitive)
        limit: Maximum number of matches to return (default: 10)

    Returns:
        List of matches with chunk IDs and context
    """
    result = grep(pattern, limit)

    if result["match_count"] == 0:
        return f"No matches found for pattern: {pattern}"

    output = [f"Found {result['match_count']} match(es) for '{pattern}':\n"]

    for i, match in enumerate(result["matches"], 1):
        output.append(
            f"{i}. [{match['chunk_id']}] line {match['line_number']}\n"
            f"   Summary: {match['chunk_summary']}\n"
            f"   Context: {match['context'][:200]}{'...' if len(match['context']) > 200 else ''}"
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
            f"\n{c['id']}{tags_str}\n"
            f"  {c['summary']}\n"
            f"  ~{c['tokens']} tokens | {c['created']}"
        )

    return "".join(output)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        # HTTP mode for testing
        mcp.run(transport="streamable-http")
    else:
        # Default: stdio for Claude Code
        mcp.run()
