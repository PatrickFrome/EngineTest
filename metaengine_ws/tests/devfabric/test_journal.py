import sqlite3

import pytest

from metaengine.devfabric.journal import Journal, JournalConflict


def test_journal_is_hash_chained(tmp_path):
    j = Journal(tmp_path / "session.sqlite")
    first = j.append("TASK_CREATED", "task-1", {"x": 1})
    second = j.append("CANDIDATE_RECEIVED", "cand-1", {"y": 2})
    assert second.parent_hash == first.event_hash
    assert j.verify_chain() == []


def test_journal_detects_direct_corruption(tmp_path):
    path = tmp_path / "session.sqlite"
    j = Journal(path)
    j.append("TASK_CREATED", "task-1", {"x": 1})
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE events SET payload_json = ? WHERE seq = 1", ('{"x":999}',))
    assert j.verify_chain()


def test_outbox_replay_is_idempotent_but_conflicts_are_rejected(tmp_path):
    j = Journal(tmp_path / "session.sqlite")
    receipt = j.append("TASK_CREATED", "task-1", {"x": 1})
    assert [x.event_id for x in j.pending_outbox()] == [receipt.event_id]
    j.mark_replayed(receipt.event_id, "a" * 64)
    j.mark_replayed(receipt.event_id, "a" * 64)
    assert j.pending_outbox() == ()
    with pytest.raises(JournalConflict):
        j.mark_replayed(receipt.event_id, "b" * 64)
