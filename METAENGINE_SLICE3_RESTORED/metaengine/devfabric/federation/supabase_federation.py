from __future__ import annotations

import re
from typing import Any, Mapping, Protocol

from .adaptation import ADAPTATION_PROTOCOL_VERSION
from .finalization import FINALIZATION_PROTOCOL_VERSION
from .types import SlotId

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_DECISIONS = {"INCLUDE", "EXCLUDE", "CONFLICT_TASK", "STALE"}


class FederationRpcTransport(Protocol):
    def call_rpc(self, rpc_name: str, params: Mapping[str, object]) -> object: ...


def _require_text(name: str, value: str) -> str:
    value = str(value)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _require_hex64(name: str, value: str) -> str:
    value = str(value)
    if not _HEX64.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-hex SHA-256 digest")
    return value


def _optional_hex64(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _require_hex64(name, value)


def _require_generation(value: int) -> int:
    value = int(value)
    if value < 0:
        raise ValueError("expected_generation cannot be negative")
    return value


def _require_slot(value: SlotId | str, *, allow_auto: bool = False) -> str:
    if allow_auto and str(value) == "AUTO":
        return "AUTO"
    try:
        return SlotId(value).value
    except (TypeError, ValueError) as exc:
        raise ValueError("slot_id must be C0..C7") from exc


def _mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("payload must be a mapping")
    return dict(value)


class SupabaseFederationAdapter:
    """Fixed-function federation RPC adapter with no arbitrary SQL/RPC surface."""

    def __init__(self, transport: FederationRpcTransport):
        self._transport = transport

    def _call(self, rpc_name: str, params: Mapping[str, object]) -> object:
        return self._transport.call_rpc(rpc_name, dict(params))

    # Read RPCs.
    def status(self, epoch_id: str) -> object:
        return self._call("metaengine_federation_status_v1", {"p_epoch_id": _require_text("epoch_id", epoch_id)})

    def slot_catalog(self) -> object:
        return self._call("metaengine_federation_slot_catalog_v1", {})

    def session_status(self, session_id: str) -> object:
        return self._call("metaengine_federation_session_status_v1", {"p_session_id": _require_text("session_id", session_id)})

    def epoch_status(self, epoch_id: str) -> object:
        return self._call("metaengine_federation_epoch_status_v1", {"p_epoch_id": _require_text("epoch_id", epoch_id)})

    def task_get(self, *, session_id: str, task_hash: str) -> object:
        return self._call(
            "metaengine_federation_task_get_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_task_hash": _require_hex64("task_hash", task_hash)},
        )

    def task_dependencies(self, *, session_id: str, task_hash: str) -> object:
        return self._call(
            "metaengine_federation_task_dependencies_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_task_hash": _require_hex64("task_hash", task_hash)},
        )

    def candidate_status(self, *, session_id: str, candidate_hash: str) -> object:
        return self._call(
            "metaengine_federation_candidate_status_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_candidate_hash": _require_hex64("candidate_hash", candidate_hash)},
        )

    def conflict_status(self, *, session_id: str, epoch_id: str) -> object:
        return self._call(
            "metaengine_federation_conflict_status_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_epoch_id": _require_text("epoch_id", epoch_id)},
        )

    def sync_snapshot_get(self, *, session_id: str, epoch_id: str) -> object:
        return self._call(
            "metaengine_federation_sync_snapshot_get_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_epoch_id": _require_text("epoch_id", epoch_id)},
        )

    # Guarded chat-facing write RPCs.
    def register(
        self,
        *,
        epoch_id: str,
        requested_slot: SlotId | str,
        session_id: str,
        capsule_sha256: str,
        protocol_version: str,
        role_profile_hash: str,
    ) -> object:
        return self._call(
            "metaengine_federation_register_v1",
            {
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_requested_slot": _require_slot(requested_slot, allow_auto=True),
                "p_session_id": _require_text("session_id", session_id),
                "p_capsule_sha256": _require_hex64("capsule_sha256", capsule_sha256),
                "p_protocol_version": _require_text("protocol_version", protocol_version),
                "p_role_profile_hash": _require_hex64("role_profile_hash", role_profile_hash),
            },
        )

    def release(self, *, session_id: str, expected_generation: int) -> object:
        return self._call(
            "metaengine_federation_release_v1",
            {"p_session_id": _require_text("session_id", session_id), "p_expected_generation": _require_generation(expected_generation)},
        )

    def claim_task(self, *, session_id: str, task_hash: str, expected_generation: int) -> object:
        return self._call(
            "metaengine_federation_claim_task_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_task_hash": _require_hex64("task_hash", task_hash),
                "p_expected_generation": _require_generation(expected_generation),
            },
        )

    def progress(self, *, session_id: str, task_hash: str, expected_generation: int, progress: Mapping[str, Any]) -> object:
        return self._call(
            "metaengine_federation_progress_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_task_hash": _require_hex64("task_hash", task_hash),
                "p_expected_generation": _require_generation(expected_generation),
                "p_progress": _mapping(progress),
            },
        )

    def submit_candidate(
        self,
        *,
        session_id: str,
        expected_generation: int,
        candidate_hash: str,
        task_hash: str,
        receipt: Mapping[str, Any],
    ) -> object:
        return self._call(
            "metaengine_federation_submit_candidate_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_candidate_hash": _require_hex64("candidate_hash", candidate_hash),
                "p_task_hash": _require_hex64("task_hash", task_hash),
                "p_receipt": _mapping(receipt),
            },
        )

    def submit_review(
        self,
        *,
        session_id: str,
        expected_generation: int,
        review_hash: str,
        candidate_hash: str,
        receipt: Mapping[str, Any],
    ) -> object:
        return self._call(
            "metaengine_federation_submit_review_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_review_hash": _require_hex64("review_hash", review_hash),
                "p_candidate_hash": _require_hex64("candidate_hash", candidate_hash),
                "p_receipt": _mapping(receipt),
            },
        )

    def submit_conflict(
        self,
        *,
        session_id: str,
        expected_generation: int,
        conflict_hash: str,
        epoch_id: str,
        payload: Mapping[str, Any],
    ) -> object:
        return self._call(
            "metaengine_federation_submit_conflict_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_conflict_hash": _require_hex64("conflict_hash", conflict_hash),
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_payload": _mapping(payload),
            },
        )

    def propose_integration(
        self,
        *,
        session_id: str,
        expected_generation: int,
        decision_hash: str,
        epoch_id: str,
        candidate_hash: str | None,
        decision: str,
        reason: str,
    ) -> object:
        decision = str(decision)
        if decision not in _DECISIONS:
            raise ValueError("decision must be INCLUDE, EXCLUDE, CONFLICT_TASK, or STALE")
        return self._call(
            "metaengine_federation_propose_integration_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_decision_hash": _require_hex64("decision_hash", decision_hash),
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_candidate_hash": _optional_hex64("candidate_hash", candidate_hash),
                "p_decision": decision,
                "p_reason": _require_text("reason", reason),
            },
        )

    def publish_snapshot(
        self,
        *,
        session_id: str,
        expected_generation: int,
        snapshot_hash: str,
        epoch_id: str,
        snapshot: Mapping[str, Any],
        checkpoint_proposal_hash: str | None,
    ) -> object:
        return self._call(
            "metaengine_federation_publish_snapshot_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_snapshot_hash": _require_hex64("snapshot_hash", snapshot_hash),
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_snapshot": _mapping(snapshot),
                "p_checkpoint_proposal_hash": _optional_hex64("checkpoint_proposal_hash", checkpoint_proposal_hash),
            },
        )

    # Internal synchronizer control plane; these methods are not intended for MCP registration.
    def open_epoch_internal(
        self,
        *,
        epoch_id: str,
        base_checkpoint_id: str,
        base_payload_root: str,
        federation_policy_hash: str,
        role_catalog_hash: str,
        producer_concurrency: int,
    ) -> object:
        producer_concurrency = int(producer_concurrency)
        if not 2 <= producer_concurrency <= 6:
            raise ValueError("producer_concurrency must be between 2 and 6")
        return self._call(
            "metaengine_federation_open_epoch_v1",
            {
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_base_checkpoint_id": _require_text("base_checkpoint_id", base_checkpoint_id),
                "p_base_payload_root": _require_hex64("base_payload_root", base_payload_root),
                "p_federation_policy_hash": _require_hex64("federation_policy_hash", federation_policy_hash),
                "p_role_catalog_hash": _require_hex64("role_catalog_hash", role_catalog_hash),
                "p_producer_concurrency": producer_concurrency,
            },
        )

    def seed_task_internal(
        self,
        *,
        task_hash: str,
        epoch_id: str,
        task_version: int,
        owner_slot: SlotId | str,
        role_profile_hash: str,
        base_checkpoint_id: str,
        envelope: Mapping[str, Any],
    ) -> object:
        task_version = int(task_version)
        if task_version <= 0:
            raise ValueError("task_version must be positive")
        return self._call(
            "metaengine_federation_seed_task_v1",
            {
                "p_task_hash": _require_hex64("task_hash", task_hash),
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_task_version": task_version,
                "p_owner_slot": _require_slot(owner_slot),
                "p_role_profile_hash": _require_hex64("role_profile_hash", role_profile_hash),
                "p_base_checkpoint_id": _require_text("base_checkpoint_id", base_checkpoint_id),
                "p_envelope": _mapping(envelope),
            },
        )

    def seed_role_genome_internal(
        self,
        *,
        role_profile_hash: str,
        slot_id: SlotId | str,
        genome_version: str,
        parent_profile_hash: str | None,
        hard_genome: Mapping[str, Any],
        soft_genome: Mapping[str, Any],
    ) -> object:
        return self._call(
            "metaengine_federation_seed_role_genome_v1",
            {
                "p_role_profile_hash": _require_hex64("role_profile_hash", role_profile_hash),
                "p_slot_id": _require_slot(slot_id),
                "p_genome_version": _require_text("genome_version", genome_version),
                "p_parent_profile_hash": _optional_hex64("parent_profile_hash", parent_profile_hash),
                "p_hard_genome": _mapping(hard_genome),
                "p_soft_genome": _mapping(soft_genome),
            },
        )

    def reclaim_slot_internal(self, *, epoch_id: str, slot_id: SlotId | str, expected_generation: int) -> object:
        return self._call(
            "metaengine_federation_reclaim_slot_v1",
            {
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_slot_id": _require_slot(slot_id),
                "p_expected_generation": _require_generation(expected_generation),
            },
        )

    def finalize_epoch_internal(
        self,
        *,
        session_id: str,
        expected_generation: int,
        epoch_id: str,
        finalization_hash: str,
        final_snapshot_hash: str,
        recovery_cut_hash: str,
        recovery_cut: Mapping[str, Any],
        protocol_version: str,
    ) -> object:
        protocol_version = _require_text("protocol_version", protocol_version)
        if protocol_version != FINALIZATION_PROTOCOL_VERSION:
            raise ValueError(f"protocol_version must be {FINALIZATION_PROTOCOL_VERSION}")
        return self._call(
            "metaengine_federation_finalize_epoch_v1",
            {
                "p_session_id": _require_text("session_id", session_id),
                "p_expected_generation": _require_generation(expected_generation),
                "p_epoch_id": _require_text("epoch_id", epoch_id),
                "p_finalization_hash": _require_hex64("finalization_hash", finalization_hash),
                "p_final_snapshot_hash": _require_hex64("final_snapshot_hash", final_snapshot_hash),
                "p_recovery_cut_hash": _require_hex64("recovery_cut_hash", recovery_cut_hash),
                "p_recovery_cut": _mapping(recovery_cut),
                "p_protocol_version": protocol_version,
            },
        )

    def finalization_get_internal(self, epoch_id: str) -> object:
        return self._call(
            "metaengine_federation_finalization_get_v1",
            {"p_epoch_id": _require_text("epoch_id", epoch_id)},
        )
    def record_adaptation_receipt_internal(
        self,
        *,
        adaptation_receipt_hash: str,
        adaptation_input_hash: str,
        protocol_version: str,
        evidence_finalization_hashes: tuple[str, ...],
        evidence_metrics_hash: str,
        status: str,
        receipt: Mapping[str, Any],
    ) -> object:
        protocol_version = _require_text("protocol_version", protocol_version)
        if protocol_version != ADAPTATION_PROTOCOL_VERSION:
            raise ValueError(f"protocol_version must be {ADAPTATION_PROTOCOL_VERSION}")
        allowed_statuses = {
            "HOLD_INSUFFICIENT_EVIDENCE",
            "HOLD_UNOBSERVED_METRIC",
            "SHADOW_PROPOSAL_READY",
            "SHADOW_REPLAY_PASS",
            "SHADOW_REPLAY_FAIL",
        }
        if status not in allowed_statuses:
            raise ValueError("status must be a supported D6 adaptation status")
        if not evidence_finalization_hashes:
            raise ValueError("evidence_finalization_hashes must not be empty")
        evidence = tuple(
            _require_hex64("evidence_finalization_hash", value)
            for value in evidence_finalization_hashes
        )
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence_finalization_hashes must be unique")
        return self._call(
            "metaengine_federation_record_adaptation_receipt_v1",
            {
                "p_adaptation_receipt_hash": _require_hex64("adaptation_receipt_hash", adaptation_receipt_hash),
                "p_adaptation_input_hash": _require_hex64("adaptation_input_hash", adaptation_input_hash),
                "p_protocol_version": protocol_version,
                "p_evidence_finalization_hashes": list(evidence),
                "p_evidence_metrics_hash": _require_hex64("evidence_metrics_hash", evidence_metrics_hash),
                "p_status": status,
                "p_receipt": _mapping(receipt),
            },
        )

    def adaptation_receipt_get_internal(self, adaptation_input_hash: str) -> object:
        return self._call(
            "metaengine_federation_adaptation_receipt_get_v1",
            {"p_adaptation_input_hash": _require_hex64("adaptation_input_hash", adaptation_input_hash)},
        )
