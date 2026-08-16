from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..codec import canonical_digest
from ..models import TaskEnvelope
from .external import ConnectorReceipt, require_write_intent, sanitize_task


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(service[_-]?role\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


class CreateStateTransport(Protocol):
    def capture(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _scrub_summary(text: str) -> str:
    value = str(text)
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


class CreateStateAdapter:
    connector_id = "create_state"

    def __init__(self, transport: CreateStateTransport, *, outbox_path: str | Path):
        self._transport = transport
        self._outbox_path = Path(outbox_path)

    def capture_decision(
        self,
        task: TaskEnvelope,
        *,
        summary: str,
        decision_hash: str,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        require_write_intent("CAPTURE_MEMORY", write_intent)
        payload = {
            "kind": "METAENGINE_DECISION_SUMMARY",
            "task": sanitize_task(task),
            "summary": _scrub_summary(summary),
            "decision_hash": str(decision_hash),
        }
        object_hash = canonical_digest(payload)
        try:
            result = dict(self._transport.capture(payload))
        except Exception as exc:
            self._outbox_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "object_hash": object_hash,
                "payload": payload,
                "reason_code": "LOCAL_OUTBOX_FALLBACK",
                "error_type": type(exc).__name__,
            }
            with self._outbox_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            return ConnectorReceipt.create(
                connector_id=self.connector_id,
                operation="CAPTURE_MEMORY",
                object_hash=object_hash,
                status="QUEUED",
                reason_code="LOCAL_OUTBOX_FALLBACK",
            )
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="CAPTURE_MEMORY",
            object_hash=object_hash,
            status="PASS",
            reason_code="OK",
            remote_id=str(result["remote_id"]) if result.get("remote_id") is not None else None,
        )
