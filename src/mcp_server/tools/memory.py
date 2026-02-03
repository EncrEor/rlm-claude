"""
RLM Memory Tools - remember and recall insights across conversation.

These tools allow Claude to save and retrieve key insights, decisions,
and facts discovered during a conversation, enabling "infinite" memory
by offloading to persistent storage.
"""

import hashlib
import json
from datetime import datetime

from .fileutil import CONTEXT_DIR, atomic_write_json
from .tokenizer_fr import tokenize_fr

MEMORY_FILE = CONTEXT_DIR / "session_memory.json"


def _load_memory() -> dict:
    """Load session memory from JSON file."""
    if not MEMORY_FILE.exists():
        return {
            "version": "1.0.0",
            "insights": [],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": None,
                "total_insights": 0,
            },
        }

    with open(MEMORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_memory(memory: dict) -> None:
    """Save session memory atomically."""
    memory["metadata"]["last_updated"] = datetime.now().isoformat()
    memory["metadata"]["total_insights"] = len(memory["insights"])
    atomic_write_json(MEMORY_FILE, memory)


def _generate_id(content: str) -> str:
    """Generate a short unique ID for an insight."""
    hash_obj = hashlib.sha256(content.encode())
    return hash_obj.hexdigest()[:8]


def remember(
    content: str,
    category: str = "general",
    importance: str = "medium",
    tags: list[str] | None = None,
) -> dict:
    """
    Save an important insight to persistent memory.

    Use this to remember:
    - Key decisions made during conversation
    - Important facts discovered
    - User preferences or requirements
    - Technical findings worth preserving

    Args:
        content: The insight or fact to remember (be concise but complete)
        category: Type of insight (decision, fact, preference, finding, todo)
        importance: Priority level (low, medium, high, critical)
        tags: Optional list of keywords for easier retrieval

    Returns:
        Confirmation with insight ID
    """
    memory = _load_memory()

    insight = {
        "id": _generate_id(content + datetime.now().isoformat()),
        "content": content,
        "category": category,
        "importance": importance,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }

    memory["insights"].append(insight)
    _save_memory(memory)

    return {
        "status": "saved",
        "id": insight["id"],
        "message": f"Insight saved with ID {insight['id']}",
        "total_insights": len(memory["insights"]),
    }


def recall(
    query: str | None = None,
    category: str | None = None,
    importance: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Retrieve insights from memory.

    Use this to:
    - Find information discussed earlier in conversation
    - Review decisions made
    - Check user preferences
    - Get context before answering questions

    Args:
        query: Search term to filter insights (searches in content and tags)
        category: Filter by category (decision, fact, preference, finding, todo)
        importance: Filter by importance (low, medium, high, critical)
        limit: Maximum number of insights to return (default: 10)

    Returns:
        List of matching insights
    """
    memory = _load_memory()
    insights = memory["insights"]

    # Filter by category
    if category:
        insights = [i for i in insights if i["category"] == category]

    # Filter by importance
    if importance:
        insights = [i for i in insights if i["importance"] == importance]

    # Filter by query (tokenized search in content and tags)
    if query:
        query_tokens = tokenize_fr(query)

        # Fallback: si tokenize_fr vide la query (que des stopwords), utiliser le raw
        if not query_tokens:
            query_tokens = [query.lower()]

        scored_insights = []
        for insight in insights:
            content_lower = insight["content"].lower()
            tags_lower = [tag.lower() for tag in insight.get("tags", [])]

            # Compter les tokens qui matchent
            matching = sum(
                1
                for token in query_tokens
                if token in content_lower or any(token in tag for tag in tags_lower)
            )

            if matching > 0:
                relevance = matching / len(query_tokens)
                scored_insights.append((insight, relevance))

        # Trier par relevance desc, puis date desc
        scored_insights.sort(key=lambda x: (x[1], x[0]["created_at"]), reverse=True)
        insights = [ins for ins, _ in scored_insights]

    # Sort by creation date (newest first) and limit
    # (déjà trié par relevance si query, sinon tri par date)
    if not query:
        insights = sorted(insights, key=lambda x: x["created_at"], reverse=True)
    insights = insights[:limit]

    return {
        "status": "success",
        "count": len(insights),
        "total_in_memory": memory["metadata"]["total_insights"],
        "insights": insights,
    }


def forget(insight_id: str) -> dict:
    """
    Remove an insight from memory.

    Args:
        insight_id: The ID of the insight to remove

    Returns:
        Confirmation of removal
    """
    memory = _load_memory()

    original_count = len(memory["insights"])
    memory["insights"] = [i for i in memory["insights"] if i["id"] != insight_id]

    if len(memory["insights"]) == original_count:
        return {"status": "not_found", "message": f"No insight found with ID {insight_id}"}

    _save_memory(memory)

    return {
        "status": "deleted",
        "message": f"Insight {insight_id} removed from memory",
        "remaining_insights": len(memory["insights"]),
    }


def memory_status() -> dict:
    """
    Get current status of the memory system.

    Returns:
        Statistics about stored insights
    """
    memory = _load_memory()

    # Count by category
    categories = {}
    for insight in memory["insights"]:
        cat = insight.get("category", "general")
        categories[cat] = categories.get(cat, 0) + 1

    # Count by importance
    importance_counts = {}
    for insight in memory["insights"]:
        imp = insight.get("importance", "medium")
        importance_counts[imp] = importance_counts.get(imp, 0) + 1

    return {
        "status": "ok",
        "version": memory["version"],
        "total_insights": memory["metadata"]["total_insights"],
        "by_category": categories,
        "by_importance": importance_counts,
        "created_at": memory["metadata"]["created_at"],
        "last_updated": memory["metadata"]["last_updated"],
    }
