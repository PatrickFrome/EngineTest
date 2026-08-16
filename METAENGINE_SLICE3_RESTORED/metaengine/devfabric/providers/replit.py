from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol

from ..models import CandidateReceipt, PrivacyClass, TaskEnvelope
from .base import HealthSnapshot, ProviderDescriptor, QuotaSnapshot
from .external import ConnectorPolicyError, sanitize_task


class ReplitTransport(Protocol):
    def health(self) -> Mapping[str, Any]: ...
    def quota(self) -> Mapping[str, Any]: ...
    def execute_task(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class ReplitWorkerAdapter:
    def __init__(self, transport: ReplitTransport):
        self._transport = transport
        self.descriptor = ProviderDescriptor(
            provider_id="replit-independent-worker",
            capabilities=("CODE_GENERATOR", "CODE_REVIEWER"),
            external=True,
            billing_mode="PAID_CAPABLE",
            effectiveness=0.35,
            independence_group="replit",
        )

    def health_check(self) -> HealthSnapshot:
        result = dict(self._transport.health())
        return HealthSnapshot(
            healthy=bool(result.get("healthy")),
            latency_ms=int(result["latency_ms"]) if result.get("latency_ms") is not None else None,
            detail=str(result.get("detail") or ""),
        )

    def quota_snapshot(self) -> QuotaSnapshot:
        result = dict(self._transport.quota())
        return QuotaSnapshot(
            known=bool(result.get("known")),
            free_remaining=int(result["free_remaining"]) if result.get("free_remaining") is not None else None,
            paid_fallback_enabled=bool(result.get("paid_fallback_enabled")),
            detail=str(result.get("detail") or ""),
        )

    def execute(self, task: TaskEnvelope, workdir: Path) -> CandidateReceipt:
        del workdir
        if task.privacy_class not in (PrivacyClass.P0, PrivacyClass.P1):
            raise ConnectorPolicyError("PRIVACY_CLASS_BLOCKED")
        payload = {
            "contract": "METAENGINE_INDEPENDENT_WORKER_V1",
            "authority": "NO_CANONICAL_AUTHORITY",
            "task": sanitize_task(task),
            "output": "PATCH_REPORT_ONLY",
        }
        result = dict(self._transport.execute_task(payload))
        metadata = {
            "report_hash": str(result.get("report_hash") or ""),
            "transport": "managed-replit",
        }
        return CandidateReceipt.create(
            task_id=task.task_id,
            provider_id=self.descriptor.provider_id,
            base_tree_hash=str(result["base_tree_hash"]),
            patch_hash=str(result["patch_hash"]),
            changed_paths=tuple(str(x) for x in result.get("changed_paths", ())),
            metadata=metadata,
        )

    def cancel(self, task_id: str) -> bool:
        del task_id
        return False
