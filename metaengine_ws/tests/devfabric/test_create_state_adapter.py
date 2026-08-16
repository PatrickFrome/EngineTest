import json
from pathlib import Path

import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.create_state import CreateStateAdapter
from metaengine.devfabric.providers.external import ConnectorPolicyError


class FakeTransport:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.payloads = []

    def capture(self, payload):
        if self.fail:
            raise RuntimeError("offline")
        self.payloads.append(dict(payload))
        return {"remote_id": "memory-1"}


def task(privacy=PrivacyClass.P1):
    return TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 40,
        objective="Refactor router",
        acceptance_tests=("tests pass",),
        allowed_paths=("metaengine/devfabric/router.py",),
        forbidden_paths=(".env",),
        capabilities_required=("semantic_memory",),
        risk_class=RiskClass.NORMAL,
        privacy_class=privacy,
    )


def test_capture_is_summary_only_and_scrubs_secret_like_content(tmp_path: Path):
    transport = FakeTransport()
    adapter = CreateStateAdapter(transport, outbox_path=tmp_path / "memory.jsonl")
    receipt = adapter.capture_decision(
        task(),
        summary="Selected adapter. password=hunter2 and " + "sk-" + "proj-abcdefghijklmnopqrstuvwxyz",
        decision_hash="b" * 64,
        write_intent="CAPTURE_MEMORY",
    )
    assert receipt.status == "PASS"
    payload = transport.payloads[0]
    blob = json.dumps(payload, sort_keys=True)
    assert "hunter2" not in blob
    assert "sk-proj-" not in blob
    assert "patch" not in blob.lower()
    assert payload["decision_hash"] == "b" * 64


def test_p3_memory_capture_is_blocked(tmp_path: Path):
    adapter = CreateStateAdapter(FakeTransport(), outbox_path=tmp_path / "memory.jsonl")
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.capture_decision(
            task(PrivacyClass.P3), summary="private", decision_hash="c" * 64,
            write_intent="CAPTURE_MEMORY",
        )
    assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"


def test_transport_failure_queues_sanitized_local_outbox(tmp_path: Path):
    outbox = tmp_path / "memory.jsonl"
    adapter = CreateStateAdapter(FakeTransport(fail=True), outbox_path=outbox)
    receipt = adapter.capture_decision(
        task(), summary="safe summary", decision_hash="d" * 64,
        write_intent="CAPTURE_MEMORY",
    )
    assert receipt.status == "QUEUED"
    assert receipt.reason_code == "LOCAL_OUTBOX_FALLBACK"
    row = json.loads(outbox.read_text().strip())
    assert row["payload"]["summary"] == "safe summary"
    assert row["object_hash"] == receipt.object_hash
