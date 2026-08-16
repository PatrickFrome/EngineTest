"""METAENGINE — cloud persister tests.

Tests use the live Turso cloud DB (created in Task ID 20). They are
integration tests: they require TURSO_DB_TOKEN in the environment. If the
token is absent, the tests are skipped (not failed) — persistence is a
convenience layer, not a constitutional guard.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import pytest

from metaengine.cloud_persister import (
    CloudPersister,
    CloudPersisterDisabled,
    CloudPersisterError,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("TURSO_DB_TOKEN"),
    reason="TURSO_DB_TOKEN not set; cloud persister tests require the live Turso DB",
)


@pytest.fixture
def persister():
    return CloudPersister.from_env()


def test_persister_enabled_with_token(persister):
    assert persister.enabled is True


def test_save_and_read_dev_step(persister):
    unique = uuid.uuid4().hex[:8]
    step_id = f"test.step.{unique}"
    payload = {
        "step_id": step_id,
        "decision": "TEST_ACCEPT",
        "receipt_hash": "a" * 64,
        "constitution_hash": "b" * 64,
        "architecture_library_snapshot_hash": "c" * 64,
        "policy_snapshot_hash": "d" * 64,
        "test_marker": unique,
    }
    key = persister.save_dev_step(payload, kind="test")
    assert key == f"{step_id}:test"

    steps = persister.read_dev_steps()
    found = [s for s in steps if s["step_id"] == key]
    assert found, f"saved step {key} not found in cloud DB"
    assert found[0]["decision"] == "TEST_ACCEPT"
    assert found[0]["receipt_hash"] == "a" * 64


def test_save_dev_step_is_idempotent(persister):
    unique = uuid.uuid4().hex[:8]
    step_id = f"test.idempotent.{unique}"
    payload = {"step_id": step_id, "decision": "FIRST", "receipt_hash": "e" * 64}
    persister.save_dev_step(payload, kind="test")
    payload2 = {**payload, "decision": "SECOND"}
    persister.save_dev_step(payload2, kind="test")

    steps = [s for s in persister.read_dev_steps() if s["step_id"] == f"{step_id}:test"]
    assert len(steps) == 1  # INSERT OR REPLACE -> no duplicate
    assert steps[0]["decision"] == "SECOND"  # last write wins


def test_save_and_read_artifact(persister):
    unique = uuid.uuid4().hex[:8]
    artifact_id = f"test_artifact_{unique}"
    payload = {"registry_hash": "f" * 64, "test_marker": unique, "records": []}
    persister.save_artifact(
        artifact_id, payload, artifact_kind="source_registry", slice_id="TEST"
    )
    arts = persister.read_artifacts()
    found = [a for a in arts if a["artifact_id"] == artifact_id]
    assert found
    assert found[0]["artifact_hash"] == "f" * 64
    assert found[0]["slice_id"] == "TEST"


def test_save_and_read_worklog(persister):
    unique = uuid.uuid4().hex[:8]
    task_id = f"test.task.{unique}"
    row_id = persister.save_worklog_entry(
        task_id, "test_agent", f"test task {unique}", f"worklog content {unique}"
    )
    assert row_id > 0
    entries = persister.read_worklog_entries()
    found = [e for e in entries if e["task_id"] == task_id]
    assert found
    assert found[0]["agent"] == "test_agent"


def test_read_row_counts(persister):
    counts = persister.read_row_counts()
    assert "metaengine_dev_steps" in counts
    assert "metaengine_worklog" in counts
    assert counts["metaengine_worklog"] >= 11  # 11 migrated + test entries


def test_read_canonical_anchors(persister):
    anchors = persister.read_canonical_anchors()
    assert anchors.get("checkpoint_id") == "metaengine-chat-2.3.0-alpha.1-cp001"
    assert anchors.get("active_policy_hash", "").startswith("1868b3c7")


def test_read_project_meta(persister):
    meta = persister.read_project_meta()
    assert meta.get("cloud_store_kind") == "TURSO_LIBSQL_CLOUD_DB"
    assert meta.get("canonical_authority") == "false"


def test_disabled_persister_raises():
    # Construct a disabled persister by clearing the env temporarily
    saved = os.environ.pop("TURSO_DB_TOKEN", None)
    try:
        p = CloudPersister.from_env()
        assert p.enabled is False
        with pytest.raises(CloudPersisterDisabled):
            p.save_dev_step({"step_id": "x"}, kind="test")
        with pytest.raises(CloudPersisterDisabled):
            p.read_dev_steps()
    finally:
        if saved is not None:
            os.environ["TURSO_DB_TOKEN"] = saved
