"""
Tests for scripts/retire_chunks.py — review-driven archiving.

The script acts on real memory, so what matters is what it refuses to do:
write in dry-run, run on a count it was not told to expect, or go ahead when the
manifest names something it cannot find.
"""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "retire_chunks.py"
spec = importlib.util.spec_from_file_location("retire_chunks", SCRIPT)
retire_chunks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire_chunks)


@pytest.fixture
def memory(temp_context_dir, monkeypatch):
    """Three active chunks in a throwaway context, retention bound to it."""
    import mcp_server.tools.retention as retention

    monkeypatch.setattr(retention, "CONTEXT_DIR", temp_context_dir)
    monkeypatch.setattr(retention, "CHUNKS_DIR", temp_context_dir / "chunks")
    monkeypatch.setattr(retention, "ARCHIVE_DIR", temp_context_dir / "archive")
    monkeypatch.setattr(retention, "INDEX_FILE", temp_context_dir / "index.json")
    monkeypatch.setattr(retention, "ARCHIVE_INDEX_FILE", temp_context_dir / "archive_index.json")
    monkeypatch.setattr(retention, "PURGE_LOG_FILE", temp_context_dir / "purge_log.json")

    entries = []
    for cid, tags in (("state_jan", ["infra"]), ("state_feb", ["infra"]), ("state_now", ["infra"])):
        (temp_context_dir / "chunks" / f"{cid}.md").write_text(
            f"---\nsummary: {cid}\ntags: infra\n---\n\nbody of {cid}\n"
        )
        entries.append(
            {
                "id": cid,
                "summary": f"summary of {cid}",
                "tags": tags,
                "created_at": "2026-01-01T00:00:00",
                "access_count": 0,
            }
        )
    index_file = temp_context_dir / "index.json"
    index = json.loads(index_file.read_text())
    index["chunks"] = entries
    index_file.write_text(json.dumps(index))
    return temp_context_dir


def write_manifest(tmp_path, chunks, **extra):
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"label": "test review", "chunks": chunks, **extra}))
    return path


CLEARED = {"id": "state_jan", "reason": "replaced", "superseded_by": "state_now", "purge_ok": True}
HELD = {
    "id": "state_feb",
    "reason": "replaced",
    "superseded_by": "",
    "purge_ok": False,
    "hold_reason": "follow-up not verified",
}


def active_ids(memory):
    return [c["id"] for c in json.loads((memory / "index.json").read_text())["chunks"]]


def archive_entries(memory):
    return {a["id"]: a for a in json.loads((memory / "archive_index.json").read_text())["archives"]}


def test_dry_run_writes_nothing(memory, tmp_path, capsys):
    manifest = write_manifest(tmp_path, [CLEARED, HELD])

    assert retire_chunks.main([str(manifest)]) == 0

    assert active_ids(memory) == ["state_jan", "state_feb", "state_now"]
    assert not (memory / "archive_index.json").exists()
    assert "--apply --expect 2" in capsys.readouterr().out


def test_apply_archives_annotates_and_holds(memory, tmp_path):
    from mcp_server.tools import retention

    manifest = write_manifest(tmp_path, [CLEARED, HELD])

    assert retire_chunks.main([str(manifest), "--apply", "--expect", "2"]) == 0

    assert active_ids(memory) == ["state_now"]
    entries = archive_entries(memory)
    assert entries["state_jan"]["summary"] == "[OBSOLETE → state_now] summary of state_jan"
    assert entries["state_jan"]["archive_reason"] == "replaced"
    assert entries["state_jan"]["purge_ok"] is True
    assert "keep" not in entries["state_jan"]["tags"]
    assert entries["state_feb"]["summary"] == "[OBSOLETE] summary of state_feb"
    assert entries["state_feb"]["purge_hold"] == "follow-up not verified"
    assert "keep" in entries["state_feb"]["tags"]
    # Both reachable by peek: nothing was deleted.
    assert retention.is_archived("state_jan") and retention.is_archived("state_feb")


def test_a_held_archive_is_never_a_purge_candidate(memory, tmp_path):
    from mcp_server.tools import retention

    manifest = write_manifest(tmp_path, [CLEARED, HELD])
    retire_chunks.main([str(manifest), "--apply", "--expect", "2"])

    long_ago = (datetime.now() - timedelta(days=400)).isoformat()
    data = json.loads((memory / "archive_index.json").read_text())
    for a in data["archives"]:
        a["archived_at"] = long_ago
    (memory / "archive_index.json").write_text(json.dumps(data))

    assert [c["id"] for c in retention.get_purge_candidates()] == ["state_jan"]


def test_wrong_expected_count_aborts_before_any_write(memory, tmp_path, capsys):
    manifest = write_manifest(tmp_path, [CLEARED, HELD])

    assert retire_chunks.main([str(manifest), "--apply", "--expect", "5"]) == 2
    assert retire_chunks.main([str(manifest), "--apply"]) == 2

    assert active_ids(memory) == ["state_jan", "state_feb", "state_now"]
    assert "Nothing written" in capsys.readouterr().out


def test_unknown_id_aborts_the_whole_run(memory, tmp_path):
    ghost = {"id": "never_existed", "reason": "x", "superseded_by": "", "purge_ok": True}
    manifest = write_manifest(tmp_path, [CLEARED, ghost])

    assert retire_chunks.main([str(manifest), "--apply", "--expect", "1"]) == 2

    assert active_ids(memory) == ["state_jan", "state_feb", "state_now"]


def test_rerun_is_idempotent_and_can_lift_a_hold(memory, tmp_path):
    manifest = write_manifest(tmp_path, [CLEARED, HELD])
    retire_chunks.main([str(manifest), "--apply", "--expect", "2"])

    # Same manifest again: nothing left to archive, annotations unchanged.
    assert retire_chunks.main([str(manifest), "--apply", "--expect", "0"]) == 0
    entries = archive_entries(memory)
    assert entries["state_jan"]["summary"] == "[OBSOLETE → state_now] summary of state_jan"
    assert entries["state_feb"]["tags"].count("keep") == 1

    # The follow-up got verified: the hold this tool placed comes off.
    cleared_now = {**HELD, "purge_ok": True, "superseded_by": "state_now"}
    cleared_now.pop("hold_reason")
    manifest = write_manifest(tmp_path, [CLEARED, cleared_now])
    assert retire_chunks.main([str(manifest), "--apply", "--expect", "0"]) == 0
    entry = archive_entries(memory)["state_feb"]
    assert "keep" not in entry["tags"]
    assert "purge_hold" not in entry
    assert entry["summary"] == "[OBSOLETE → state_now] summary of state_feb"


def test_a_keep_tag_the_chunk_already_had_is_left_alone(memory, tmp_path):
    index_file = memory / "index.json"
    index = json.loads(index_file.read_text())
    index["chunks"][0]["tags"] = ["infra", "keep"]
    index_file.write_text(json.dumps(index))

    manifest = write_manifest(tmp_path, [CLEARED])
    assert retire_chunks.main([str(manifest), "--apply", "--expect", "1"]) == 0

    assert "keep" in archive_entries(memory)["state_jan"]["tags"]


def test_search_surfaces_the_archive_as_obsolete(memory, tmp_path):
    from mcp_server.tools import retention

    manifest = write_manifest(tmp_path, [CLEARED], summary_prefix="[PÉRIMÉ → {superseded_by}] ")
    retire_chunks.main([str(manifest), "--apply", "--expect", "1"])

    hits = retention.search_archives("summary state_jan")
    assert hits[0]["summary"].startswith("[PÉRIMÉ → state_now] ")


@pytest.mark.parametrize(
    "broken",
    [
        {"id": "state_jan", "reason": "", "superseded_by": "", "purge_ok": True},
        {"id": "state_jan", "reason": "x", "superseded_by": ""},
        {"id": "state_jan", "reason": "x", "superseded_by": "", "purge_ok": False},
        {"id": "../etc/passwd", "reason": "x", "superseded_by": "", "purge_ok": True},
    ],
)
def test_ambiguous_manifest_is_refused(memory, tmp_path, broken):
    manifest = write_manifest(tmp_path, [broken])

    assert retire_chunks.main([str(manifest), "--apply", "--expect", "1"]) == 2
    assert active_ids(memory) == ["state_jan", "state_feb", "state_now"]


def test_duplicate_id_is_refused(memory, tmp_path):
    manifest = write_manifest(tmp_path, [CLEARED, CLEARED])

    assert retire_chunks.main([str(manifest)]) == 2


# =============================================================================
# scripts/purge_reviewed.py
# =============================================================================

PURGE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "purge_reviewed.py"
pspec = importlib.util.spec_from_file_location("purge_reviewed", PURGE_SCRIPT)
purge_reviewed = importlib.util.module_from_spec(pspec)
pspec.loader.exec_module(purge_reviewed)


def test_purge_only_touches_cleared_entries_of_the_review(memory, tmp_path, capsys):
    from mcp_server.tools import retention

    manifest = write_manifest(tmp_path, [CLEARED, HELD])
    retire_chunks.main([str(manifest), "--apply", "--expect", "2"])
    # A third archive from an age-based run: never reviewed, must be left alone.
    retention.archive_chunk("state_now")

    assert purge_reviewed.main([]) == 0
    assert "Cleared for purge: 1" in capsys.readouterr().out

    assert purge_reviewed.main(["--apply", "--expect", "3"]) == 2  # wrong count: nothing happens
    assert len(archive_entries(memory)) == 3

    assert purge_reviewed.main(["--review", "other review", "--apply", "--expect", "0"]) == 0
    assert len(archive_entries(memory)) == 3

    assert purge_reviewed.main(["--review", "test review", "--apply", "--expect", "1"]) == 0
    left = archive_entries(memory)
    assert set(left) == {"state_feb", "state_now"}
    assert not (memory / "archive" / "state_jan.md.gz").exists()
    purged = json.loads((memory / "purge_log.json").read_text())["purged"]
    assert [p["id"] for p in purged] == ["state_jan"]
