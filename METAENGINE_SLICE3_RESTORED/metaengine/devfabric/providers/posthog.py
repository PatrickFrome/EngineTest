from __future__ import annotations

from typing import Any, Mapping, Protocol

from ..codec import canonical_digest
from ..models import PrivacyClass, TaskEnvelope
from ..telemetry_policy import build_telemetry
from .external import ConnectorPolicyError, ConnectorReceipt, require_write_intent


class PostHogTransport(Protocol):
    def capture_event(self, event: str, properties: Mapping[str, object]) -> Mapping[str, Any]: ...


class PostHogTelemetryAdapter:
    connector_id = "posthog"

    def __init__(self, transport: PostHogTransport):
        self._transport = transport

    def emit(
        self,
        task: TaskEnvelope,
        *,
        provider_class: str,
        task_class: str,
        latency_ms: int,
        compute_estimate: int | float,
        result: str,
        test_delta: int,
        patch_size: int,
        verifier_verdict: str,
        promotion_outcome: str,
        quota_state: str,
        fallback: str,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        if task.privacy_class is PrivacyClass.P3:
            raise ConnectorPolicyError("PRIVACY_CLASS_BLOCKED")
        require_write_intent("EMIT_TELEMETRY", write_intent)
        properties = build_telemetry(
            provider_class=provider_class,
            task_class=task_class,
            latency_ms=latency_ms,
            compute_estimate=compute_estimate,
            result=result,
            test_delta=test_delta,
            patch_size=patch_size,
            verifier_verdict=verifier_verdict,
            promotion_outcome=promotion_outcome,
            quota_state=quota_state,
            fallback=fallback,
        )
        object_hash = canonical_digest(properties)
        remote = dict(self._transport.capture_event("metaengine_development_run", properties))
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="EMIT_TELEMETRY",
            object_hash=object_hash,
            status="PASS",
            reason_code="OK",
            remote_id=str(remote.get("remote_id")) if remote.get("remote_id") else None,
        )
