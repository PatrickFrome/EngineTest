from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ..codec import canonical_digest
from ..models import PrivacyClass, TaskEnvelope
from .external import ConnectorPolicyError, ConnectorReceipt, require_write_intent


_ALLOWED_SENSITIVE_POLICIES = {"SCHEMA_ONLY", "APPROVED_SYNTHETIC_FIXTURES"}


class NeonTransport(Protocol):
    def create_branch(self, name: str, tags: Mapping[str, str], ttl_minutes: int) -> Mapping[str, Any]: ...
    def run_sql(self, branch_id: str, sql: str) -> Mapping[str, Any]: ...
    def delete_branch(self, branch_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class NeonSandboxHandle:
    branch_id: str
    task_id: str
    candidate_hash: str
    ttl_minutes: int
    data_policy: str


class NeonSandboxAdapter:
    connector_id = "neon"

    def __init__(self, transport: NeonTransport, *, enabled: bool = False):
        self._transport = transport
        self._enabled = bool(enabled)

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise ConnectorPolicyError("NEON_RETIRED_BY_POLICY")

    def create_sandbox(
        self,
        task: TaskEnvelope,
        *,
        candidate_hash: str,
        ttl_minutes: int,
        data_policy: str,
        write_intent: str | None,
    ) -> tuple[NeonSandboxHandle, ConnectorReceipt]:
        self._ensure_enabled()
        require_write_intent("CREATE_SANDBOX", write_intent)
        if task.privacy_class is PrivacyClass.P3:
            raise ConnectorPolicyError("PRIVACY_CLASS_BLOCKED")
        if task.privacy_class is PrivacyClass.P2 and data_policy not in _ALLOWED_SENSITIVE_POLICIES:
            raise ConnectorPolicyError("SENSITIVE_DATA_POLICY_BLOCKED")
        if not (5 <= int(ttl_minutes) <= 180):
            raise ConnectorPolicyError("SANDBOX_TTL_OUT_OF_RANGE")
        tags = {"task_id": task.task_id, "candidate_hash": str(candidate_hash)}
        name = f"metaengine-{task.task_id[-10:]}-{str(candidate_hash)[:8]}"
        result = dict(self._transport.create_branch(name, tags, int(ttl_minutes)))
        branch_id = str(result["branch_id"])
        handle = NeonSandboxHandle(
            branch_id=branch_id,
            task_id=task.task_id,
            candidate_hash=str(candidate_hash),
            ttl_minutes=int(ttl_minutes),
            data_policy=str(data_policy),
        )
        object_hash = canonical_digest(handle)
        receipt = ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="CREATE_SANDBOX",
            object_hash=object_hash,
            status="PASS",
            reason_code="OK",
            remote_id=branch_id,
            metadata={"ttl_minutes": str(ttl_minutes), "data_policy": str(data_policy)},
        )
        return handle, receipt

    def run_migration_test(
        self,
        handle: NeonSandboxHandle,
        sql: str,
        *,
        canonical_role: bool = False,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        if canonical_role:
            raise ConnectorPolicyError("CANONICAL_ROLE_FORBIDDEN")
        return dict(self._transport.run_sql(handle.branch_id, str(sql)))

    def destroy_sandbox(
        self,
        handle: NeonSandboxHandle,
        *,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        self._ensure_enabled()
        require_write_intent("DESTROY_SANDBOX", write_intent)
        result = dict(self._transport.delete_branch(handle.branch_id))
        status = "PASS" if result.get("deleted") else "REJECTED"
        reason = "OK" if result.get("deleted") else "DELETE_NOT_CONFIRMED"
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="DESTROY_SANDBOX",
            object_hash=canonical_digest(handle),
            status=status,
            reason_code=reason,
            remote_id=handle.branch_id,
        )
