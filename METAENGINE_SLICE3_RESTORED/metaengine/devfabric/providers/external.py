from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..codec import canonical_digest
from ..models import PrivacyClass, TaskEnvelope


class ConnectorPolicyError(RuntimeError):
    def __init__(self, reason_code: str, message: str | None = None):
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def sanitize_task(task: TaskEnvelope) -> dict[str, object]:
    if task.privacy_class is PrivacyClass.P3:
        raise ConnectorPolicyError("PRIVACY_CLASS_BLOCKED")
    base: dict[str, object] = {
        "task_id": task.task_id,
        "task_hash": task.task_hash,
        "source_checkpoint_id": task.source_checkpoint_id,
        "source_tree_hash": task.source_tree_hash,
        "risk_class": task.risk_class.value,
        "privacy_class": task.privacy_class.value,
        "capabilities_required": tuple(task.capabilities_required),
        "zero_spend": task.zero_spend,
    }
    if task.privacy_class is PrivacyClass.P2:
        base.update(
            {
                "objective": "[REDACTED:P2]",
                "acceptance_test_count": len(task.acceptance_tests),
                "allowed_path_count": len(task.allowed_paths),
                "forbidden_path_count": len(task.forbidden_paths),
            }
        )
        return base
    base.update(
        {
            "objective": task.objective,
            "acceptance_tests": tuple(task.acceptance_tests),
            "allowed_paths": tuple(task.allowed_paths),
            "forbidden_paths": tuple(task.forbidden_paths),
        }
    )
    return base


def require_write_intent(expected: str, provided: str | None) -> str:
    if not provided:
        raise ConnectorPolicyError("WRITE_INTENT_REQUIRED")
    if provided != expected:
        raise ConnectorPolicyError("WRITE_INTENT_MISMATCH")
    return provided


@dataclass(frozen=True)
class ConnectorReceipt:
    receipt_hash: str
    connector_id: str
    operation: str
    object_hash: str
    status: str
    reason_code: str
    remote_id: str | None
    metadata: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        connector_id: str,
        operation: str,
        object_hash: str,
        status: str,
        reason_code: str,
        remote_id: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> "ConnectorReceipt":
        payload = {
            "connector_id": connector_id,
            "operation": operation,
            "object_hash": object_hash,
            "status": status,
            "reason_code": reason_code,
            "remote_id": remote_id,
            "metadata": tuple(sorted((str(k), str(v)) for k, v in (metadata or {}).items())),
        }
        return cls(receipt_hash=canonical_digest(payload), **payload)
