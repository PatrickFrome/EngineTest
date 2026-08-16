import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.external import (
    ConnectorPolicyError,
    ConnectorReceipt,
    require_write_intent,
    sanitize_task,
)


def make_task(privacy: PrivacyClass) -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 40,
        objective="Fix private algorithm using secret-design-note",
        acceptance_tests=("secret acceptance condition",),
        allowed_paths=("metaengine/private_module.py",),
        forbidden_paths=("secrets/.env",),
        capabilities_required=("task_projection",),
        risk_class=RiskClass.NORMAL,
        privacy_class=privacy,
    )


def test_p3_is_blocked_from_external_serialization():
    with pytest.raises(ConnectorPolicyError) as exc:
        sanitize_task(make_task(PrivacyClass.P3))
    assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"


def test_p2_is_metadata_only_and_does_not_leak_text_or_paths():
    task = make_task(PrivacyClass.P2)
    safe = sanitize_task(task)
    blob = repr(safe)
    assert safe["task_id"] == task.task_id
    assert safe["task_hash"] == task.task_hash
    assert safe["objective"] == "[REDACTED:P2]"
    assert safe["acceptance_test_count"] == 1
    assert safe["allowed_path_count"] == 1
    assert "secret-design-note" not in blob
    assert "secret acceptance condition" not in blob
    assert "private_module.py" not in blob
    assert "secrets/.env" not in blob


def test_missing_or_wrong_write_intent_is_rejected():
    with pytest.raises(ConnectorPolicyError) as exc:
        require_write_intent("APPEND_RECEIPT", None)
    assert exc.value.reason_code == "WRITE_INTENT_REQUIRED"

    with pytest.raises(ConnectorPolicyError) as exc:
        require_write_intent("APPEND_RECEIPT", "PROJECT_TASK")
    assert exc.value.reason_code == "WRITE_INTENT_MISMATCH"

    assert require_write_intent("APPEND_RECEIPT", "APPEND_RECEIPT") == "APPEND_RECEIPT"


def test_connector_receipt_digest_is_stable_across_metadata_order():
    a = ConnectorReceipt.create(
        connector_id="drive",
        operation="UPLOAD_ARTIFACT",
        object_hash="b" * 64,
        status="PASS",
        reason_code="OK",
        remote_id="file-1",
        metadata={"b": "2", "a": "1"},
    )
    b = ConnectorReceipt.create(
        connector_id="drive",
        operation="UPLOAD_ARTIFACT",
        object_hash="b" * 64,
        status="PASS",
        reason_code="OK",
        remote_id="file-1",
        metadata={"a": "1", "b": "2"},
    )
    assert a == b
    assert len(a.receipt_hash) == 64
