from __future__ import annotations

from typing import Any, Mapping, Protocol

from ..codec import canonical_digest
from .external import ConnectorPolicyError, ConnectorReceipt, require_write_intent


class SupabaseTransport(Protocol):
    def read_current_checkpoint(self) -> Mapping[str, Any]: ...
    def read_champion(self) -> Mapping[str, Any]: ...
    def append_development_receipt(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def propose_checkpoint(self, payload: Mapping[str, Any], expected_parent: str) -> Mapping[str, Any]: ...


class SupabaseCanonicalAdapter:
    connector_id = "supabase"

    def __init__(self, transport: SupabaseTransport, *, read_only: bool = True):
        self._transport = transport
        self._read_only = bool(read_only)

    def read_current_checkpoint(self) -> dict[str, Any]:
        return dict(self._transport.read_current_checkpoint())

    def read_champion(self) -> dict[str, Any]:
        return dict(self._transport.read_champion())

    def append_development_receipt(
        self,
        payload: Mapping[str, Any],
        *,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        if self._read_only:
            raise ConnectorPolicyError("CONNECTOR_READ_ONLY")
        require_write_intent("APPEND_RECEIPT", write_intent)
        safe_payload = dict(payload)
        object_hash = canonical_digest(safe_payload)
        result = dict(self._transport.append_development_receipt(safe_payload))
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="APPEND_RECEIPT",
            object_hash=object_hash,
            status="PASS",
            reason_code="OK",
            remote_id=str(result["remote_id"]) if result.get("remote_id") is not None else None,
        )

    def propose_checkpoint(
        self,
        payload: Mapping[str, Any],
        *,
        expected_parent: str,
        write_intent: str | None,
    ) -> ConnectorReceipt:
        if self._read_only:
            raise ConnectorPolicyError("CONNECTOR_READ_ONLY")
        require_write_intent("PROPOSE_CHECKPOINT", write_intent)
        safe_payload = dict(payload)
        safe_payload["parent_checkpoint_id"] = expected_parent
        safe_payload["is_current"] = False
        safe_payload["verification_status"] = "NON_CANONICAL"
        object_hash = canonical_digest(safe_payload)
        result = dict(self._transport.propose_checkpoint(safe_payload, expected_parent))
        if not result.get("applied"):
            return ConnectorReceipt.create(
                connector_id=self.connector_id,
                operation="PROPOSE_CHECKPOINT",
                object_hash=object_hash,
                status="REJECTED",
                reason_code=str(result.get("reason_code") or "CAS_CONFLICT"),
            )
        return ConnectorReceipt.create(
            connector_id=self.connector_id,
            operation="PROPOSE_CHECKPOINT",
            object_hash=object_hash,
            status="PASS",
            reason_code="OK",
            remote_id=str(result["remote_id"]) if result.get("remote_id") is not None else None,
        )
