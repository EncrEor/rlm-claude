"""
RLM Sessions Management - Phase 5.5b

Handles session tracking and domain listing for multi-session navigation.
Sessions group chunks by working context (project/domain/ticket).
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# Paths
CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"
SESSIONS_FILE = CONTEXT_DIR / "sessions.json"
DOMAINS_FILE = CONTEXT_DIR / "domains.json"


def _load_sessions() -> dict:
    """Load sessions index from disk."""
    if not SESSIONS_FILE.exists():
        return {
            "version": "1.0.0",
            "current_session": None,
            "sessions": {}
        }

    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_sessions(data: dict) -> None:
    """Save sessions index to disk."""
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_domains() -> dict:
    """Load domains configuration from disk. Creates default if not exists."""
    default_domains = {
        "version": "1.0.0",
        "description": "Suggested domains for RLM chunks. You can use any domain - these are just suggestions.",
        "domains": {
            "default": {
                "description": "Generic domains for any project",
                "list": [
                    "dev", "research", "planning", "debug", "test",
                    "docs", "review", "deploy", "feature", "bugfix",
                    "refactor", "meeting", "decision"
                ]
            }
        },
        "_note": "Customize this file for your project. See domains.json.example for an extended example."
    }

    if not DOMAINS_FILE.exists():
        # Create default domains file
        DOMAINS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DOMAINS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_domains, f, indent=2, ensure_ascii=False)
        return default_domains

    with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_session() -> Optional[str]:
    """Get the current active session ID."""
    data = _load_sessions()
    return data.get("current_session")


def set_current_session(session_id: str) -> dict:
    """Set the current active session."""
    data = _load_sessions()
    data["current_session"] = session_id
    _save_sessions(data)
    return {"status": "ok", "current_session": session_id}


def register_session(
    session_id: str,
    project: str,
    path: str = "",
    domain: str = "",
    ticket: str = "",
    tags: list = None
) -> dict:
    """
    Register a new session in the index.

    Args:
        session_id: Unique session identifier (e.g., "2026-01-18_RLM_001")
        project: Project name
        path: Working directory path
        domain: Primary domain for this session
        ticket: Optional ticket reference
        tags: Optional list of tags

    Returns:
        dict with status and session info
    """
    data = _load_sessions()

    if session_id in data["sessions"]:
        return {
            "status": "exists",
            "message": f"Session {session_id} already exists",
            "session": data["sessions"][session_id]
        }

    session = {
        "project": project,
        "path": path,
        "domain": domain,
        "ticket": ticket,
        "started": datetime.now().isoformat(),
        "chunks": [],
        "tags": tags or []
    }

    data["sessions"][session_id] = session
    data["current_session"] = session_id
    _save_sessions(data)

    return {
        "status": "created",
        "message": f"Session {session_id} created",
        "session": session
    }


def add_chunk_to_session(chunk_id: str, session_id: str = None) -> dict:
    """
    Add a chunk ID to a session's chunk list.

    Args:
        chunk_id: The chunk ID to add
        session_id: Target session (uses current if not specified)

    Returns:
        dict with status
    """
    data = _load_sessions()

    target_session = session_id or data.get("current_session")

    if not target_session:
        return {
            "status": "no_session",
            "message": "No active session. Create one first."
        }

    if target_session not in data["sessions"]:
        return {
            "status": "not_found",
            "message": f"Session {target_session} not found"
        }

    if chunk_id not in data["sessions"][target_session]["chunks"]:
        data["sessions"][target_session]["chunks"].append(chunk_id)
        _save_sessions(data)

    return {
        "status": "ok",
        "session": target_session,
        "chunk_count": len(data["sessions"][target_session]["chunks"])
    }


def list_sessions(
    project: str = None,
    domain: str = None,
    limit: int = 10
) -> dict:
    """
    List available sessions with optional filtering.

    Args:
        project: Filter by project name
        domain: Filter by domain
        limit: Maximum number of sessions to return

    Returns:
        dict with sessions list and metadata
    """
    data = _load_sessions()
    sessions = data.get("sessions", {})

    # Apply filters
    filtered = []
    for sid, session in sessions.items():
        if project and session.get("project") != project:
            continue
        if domain and session.get("domain") != domain:
            continue
        filtered.append({
            "id": sid,
            **session
        })

    # Sort by started date (most recent first)
    filtered.sort(key=lambda x: x.get("started", ""), reverse=True)

    return {
        "status": "ok",
        "total": len(filtered),
        "showing": min(limit, len(filtered)),
        "current_session": data.get("current_session"),
        "sessions": filtered[:limit]
    }


def list_domains() -> dict:
    """
    List all available domains from domains.json.

    Returns:
        dict with domains organized by category
    """
    data = _load_domains()

    # Flatten all domains into a single list with categories
    all_domains = []
    for category, info in data.get("domains", {}).items():
        for domain in info.get("list", []):
            all_domains.append({
                "name": domain,
                "category": category
            })

    return {
        "status": "ok",
        "version": data.get("version", "unknown"),
        "description": data.get("description", ""),
        "total": len(all_domains),
        "domains": data.get("domains", {}),
        "flat_list": all_domains
    }
