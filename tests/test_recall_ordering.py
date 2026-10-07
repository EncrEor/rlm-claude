"""
Tests for recall ranking and truncation reporting (v0.10.3).

Motivation, measured on six months of real data: 34 insights were marked
`critical` — the level meant to be loaded at the start of every session — but
`rlm_recall(importance="critical")` defaults to limit=10 and sorted by date,
so the 24 oldest never surfaced. The oldest are the most settled rules, so the
truncation silently discarded exactly what it was supposed to protect.
"""

import json
from datetime import datetime, timedelta

import pytest

import mcp_server.tools.memory as memory


@pytest.fixture
def memory_file(tmp_path, monkeypatch):
    """Point the memory module at an isolated store."""
    path = tmp_path / "session_memory.json"
    monkeypatch.setattr(memory, "MEMORY_FILE", path)
    return path


def _write(memory_file, insights):
    memory_file.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "insights": insights,
                "metadata": {"total_insights": len(insights)},
            }
        )
    )


def _insight(idx, importance, days_old, content=None):
    created = (datetime.now() - timedelta(days=days_old)).isoformat()
    return {
        "id": f"id{idx:03d}",
        "content": content or f"insight {idx}",
        "category": "finding",
        "importance": importance,
        "tags": [],
        "created_at": created,
    }


def test_critical_outranks_recent_noise(memory_file):
    """An old critical rule must outrank a fresh medium one."""
    _write(
        memory_file,
        [_insight(i, "medium", days_old=1) for i in range(20)]
        + [_insight(99, "critical", days_old=400, content="never deploy without validation")],
    )

    result = memory.recall(limit=5)

    assert result["insights"][0]["importance"] == "critical"
    assert "never deploy" in result["insights"][0]["content"]


def test_importance_then_recency(memory_file):
    """Within one importance level, newest first — as before."""
    _write(
        memory_file,
        [
            _insight(1, "critical", days_old=100),
            _insight(2, "critical", days_old=5),
            _insight(3, "high", days_old=1),
        ],
    )

    got = [i["id"] for i in memory.recall(limit=10)["insights"]]
    assert got == ["id002", "id001", "id003"]


def test_truncation_is_reported(memory_file):
    """A cut result set must say how much was cut."""
    _write(memory_file, [_insight(i, "critical", days_old=i) for i in range(34)])

    result = memory.recall(importance="critical", limit=10)

    assert result["count"] == 10
    assert result["total_matching"] == 34
    assert result["truncated"] is True
    assert "34" in result["message"]


def test_complete_result_is_not_flagged(memory_file):
    """No false alarm when everything matching was returned."""
    _write(memory_file, [_insight(i, "high", days_old=i) for i in range(3)])

    result = memory.recall(limit=10)

    assert result["total_matching"] == 3
    assert "truncated" not in result
    assert "message" not in result


def test_query_still_ranks_by_relevance(memory_file):
    """With a query, relevance still wins — importance must not hijack it."""
    _write(
        memory_file,
        [
            _insight(1, "critical", days_old=1, content="something about packaging"),
            _insight(2, "low", days_old=1, content="odoo deployment cache assets"),
        ],
    )

    result = memory.recall(query="odoo deployment", limit=5)

    assert result["insights"][0]["id"] == "id002"
    assert result["total_matching"] == 1


def test_unknown_importance_does_not_crash(memory_file):
    """Insights written by older versions must still rank, not raise."""
    weird = _insight(1, "urgent", days_old=1)
    _write(memory_file, [weird, _insight(2, "critical", days_old=1)])

    result = memory.recall(limit=5)

    assert result["insights"][0]["importance"] == "critical"
    assert result["count"] == 2


# =============================================================================
# Concurrent writers
# =============================================================================


def test_remember_and_forget_round_trip(memory_file):
    """The write path creates the store, stamps it, and removes on demand."""
    saved = memory.remember("first insight", category="fact", importance="medium", tags=["a"])
    memory.remember("second insight")

    data = json.loads(memory_file.read_text())
    assert [i["content"] for i in data["insights"]] == ["first insight", "second insight"]
    assert data["metadata"]["total_insights"] == 2

    assert memory.forget(saved["id"])["remaining_insights"] == 1
    assert memory.forget("missing0")["status"] == "not_found"
    assert [i["content"] for i in json.loads(memory_file.read_text())["insights"]] == [
        "second insight"
    ]


def test_remember_waits_for_a_writer_holding_the_memory_lock(memory_file):
    """Two sessions saving insights must both survive.

    remember() used to load, append and save with no lock: a session that read
    the file before another wrote, and saved after, erased that other insight.
    """
    import threading
    import time

    from mcp_server.tools.fileutil import locked_json_update

    _write(memory_file, [])
    inside, release = threading.Event(), threading.Event()

    def other_session():
        with locked_json_update(memory_file) as data:
            inside.set()
            release.wait(timeout=10)
            data["insights"].append(_insight(1, "medium", 0, content="from the other session"))

    writer = threading.Thread(target=other_session)
    writer.start()
    assert inside.wait(timeout=10)

    saver = threading.Thread(target=lambda: memory.remember("from this session"))
    saver.start()
    time.sleep(0.4)
    assert saver.is_alive(), "remember() raced ahead of a writer holding the memory lock"

    release.set()
    writer.join(timeout=10)
    saver.join(timeout=10)

    contents = {i["content"] for i in json.loads(memory_file.read_text())["insights"]}
    assert contents == {"from the other session", "from this session"}
