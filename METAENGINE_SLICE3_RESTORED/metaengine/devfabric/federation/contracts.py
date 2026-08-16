from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import CandidateReceipt, PrivacyClass, RiskClass, TaskEnvelope, Verdict

from .types import IntegrationMode, SlotId

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HIGH_RISK = {RiskClass.HIGH, RiskClass.RELEASE}
_P3_CAPABLE = {SlotId.C2, SlotId.C3, SlotId.C6}


def _sorted_unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def _sorted_unique_slots(values: Iterable[SlotId]) -> tuple[SlotId, ...]:
    return tuple(sorted({SlotId(value) for value in values}, key=lambda slot: slot.value))


def require_hex64(name: str, value: str) -> None:
    if not _HEX64.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 64-hex SHA-256 digest")


# Backward-compatible private alias for the existing D6 contracts.
_require_hex64 = require_hex64


@dataclass(frozen=True)
class FederatedTaskEnvelope:
    base_task: TaskEnvelope
    epoch_id: str
    task_version: int
    owner_slot: SlotId
    lease_generation: int
    role_profile_hash: str
    base_checkpoint_id: str
    dependency_task_ids: tuple[str, ...]
    read_set: tuple[str, ...]
    write_set: tuple[str, ...]
    interface_set: tuple[str, ...]
    integration_mode: IntegrationMode
    review_slots: tuple[SlotId, ...]
    blind_group_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.base_task, TaskEnvelope):
            raise TypeError("base_task must be TaskEnvelope")
        if not isinstance(self.owner_slot, SlotId):
            raise TypeError("owner_slot must be SlotId")
        if not isinstance(self.integration_mode, IntegrationMode):
            raise TypeError("integration_mode must be IntegrationMode")
        if not all(isinstance(slot, SlotId) for slot in self.review_slots):
            raise TypeError("review_slots must contain SlotId values")
        if not self.epoch_id:
            raise ValueError("epoch_id is required")
        if self.task_version <= 0:
            raise ValueError("task_version must be positive")
        if self.lease_generation < 0:
            raise ValueError("lease_generation cannot be negative")
        _require_hex64("role_profile_hash", self.role_profile_hash)
        if self.base_checkpoint_id != self.base_task.source_checkpoint_id:
            raise ValueError("base_checkpoint_id must equal base_task.source_checkpoint_id")
        if self.blind_group_id is not None and not self.blind_group_id:
            raise ValueError("blind_group_id must be non-empty when provided")
        if self.owner_slot is SlotId.C0 and self.integration_mode is IntegrationMode.REDUNDANT:
            raise ValueError("C0 cannot author REDUNDANT candidates")
        if self.owner_slot is SlotId.C6 and self.integration_mode not in {
            IntegrationMode.IMPLEMENT_REVIEW,
            IntegrationMode.PARALLEL,
        }:
            raise ValueError("C6 only permits IMPLEMENT_REVIEW or PARALLEL integration")
        if self.base_task.privacy_class is PrivacyClass.P3 and self.owner_slot not in _P3_CAPABLE:
            raise ValueError(f"{self.owner_slot.value} privacy ceiling is P2 and cannot own P3 work")
        if self.owner_slot is SlotId.C6 and SlotId.C6 in self.review_slots:
            raise ValueError("C6 self-review is forbidden")
        if self.base_task.risk_class in _HIGH_RISK:
            mandatory = SlotId.C1 if self.owner_slot is SlotId.C6 else SlotId.C6
            if mandatory not in self.review_slots:
                raise ValueError(f"{mandatory.value} review is required for HIGH/RELEASE work")

    @classmethod
    def create(
        cls,
        *,
        base_task: TaskEnvelope,
        epoch_id: str,
        task_version: int,
        owner_slot: SlotId,
        lease_generation: int,
        role_profile_hash: str,
        base_checkpoint_id: str,
        dependency_task_ids: Iterable[str],
        read_set: Iterable[str],
        write_set: Iterable[str],
        interface_set: Iterable[str],
        integration_mode: IntegrationMode,
        review_slots: Iterable[SlotId],
        blind_group_id: str | None = None,
    ) -> "FederatedTaskEnvelope":
        return cls(
            base_task=base_task,
            epoch_id=str(epoch_id),
            task_version=int(task_version),
            owner_slot=SlotId(owner_slot),
            lease_generation=int(lease_generation),
            role_profile_hash=str(role_profile_hash),
            base_checkpoint_id=str(base_checkpoint_id),
            dependency_task_ids=_sorted_unique_strings(dependency_task_ids),
            read_set=_sorted_unique_strings(read_set),
            write_set=_sorted_unique_strings(write_set),
            interface_set=_sorted_unique_strings(interface_set),
            integration_mode=IntegrationMode(integration_mode),
            review_slots=_sorted_unique_slots(review_slots),
            blind_group_id=None if blind_group_id is None else str(blind_group_id),
        )

    @property
    def task_hash(self) -> str:
        return canonical_digest(
            {
                "base_task_hash": self.base_task.task_hash,
                "epoch_id": self.epoch_id,
                "task_version": self.task_version,
                "owner_slot": self.owner_slot,
                "lease_generation": self.lease_generation,
                "role_profile_hash": self.role_profile_hash,
                "base_checkpoint_id": self.base_checkpoint_id,
                "dependency_task_ids": tuple(sorted(set(self.dependency_task_ids))),
                "read_set": tuple(sorted(set(self.read_set))),
                "write_set": tuple(sorted(set(self.write_set))),
                "interface_set": tuple(sorted(set(self.interface_set))),
                "integration_mode": self.integration_mode,
                "review_slots": tuple(sorted(set(self.review_slots), key=lambda slot: slot.value)),
                "blind_group_id": self.blind_group_id,
            }
        )

    @property
    def task_id(self) -> str:
        return f"ftask-{self.task_hash[:20]}"


@dataclass(frozen=True)
class FederatedCandidateReceipt:
    base_candidate_hash: str
    task_hash: str
    epoch_id: str
    task_version: int
    slot_id: SlotId
    session_id: str
    lease_generation: int
    role_profile_hash: str
    base_checkpoint_id: str
    patch_digest: str
    changed_paths: tuple[str, ...]
    interface_changes: tuple[str, ...]
    verification_hashes: tuple[str, ...]
    claims: tuple[str, ...]
    risks: tuple[str, ...]
    dependency_observations: tuple[str, ...]
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.slot_id, SlotId):
            raise TypeError("slot_id must be SlotId")
        _require_hex64("base_candidate_hash", self.base_candidate_hash)
        _require_hex64("task_hash", self.task_hash)
        _require_hex64("role_profile_hash", self.role_profile_hash)
        _require_hex64("patch_digest", self.patch_digest)
        for verification_hash in self.verification_hashes:
            _require_hex64("verification_hash", verification_hash)
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.lease_generation < 0:
            raise ValueError("lease_generation cannot be negative")
        if self.task_version <= 0:
            raise ValueError("task_version must be positive")
        if not self.epoch_id:
            raise ValueError("epoch_id is required")
        if not self.base_checkpoint_id:
            raise ValueError("base_checkpoint_id is required")
        if len(self.summary) > 4096:
            raise ValueError("summary is too large; store large bodies as content-addressed artifacts")

    @classmethod
    def create(
        cls,
        *,
        base_candidate: CandidateReceipt,
        task: FederatedTaskEnvelope,
        slot_id: SlotId,
        session_id: str,
        lease_generation: int,
        patch_digest: str,
        interface_changes: Iterable[str],
        verification_hashes: Iterable[str],
        claims: Iterable[str],
        risks: Iterable[str],
        dependency_observations: Iterable[str],
        summary: str,
    ) -> "FederatedCandidateReceipt":
        if base_candidate.task_id != task.base_task.task_id:
            raise ValueError("base candidate task does not match federated task base")
        if SlotId(slot_id) is not task.owner_slot:
            raise ValueError("candidate owner slot must match federated task owner slot")
        if int(lease_generation) != task.lease_generation:
            raise ValueError("candidate lease_generation must match federated task lease_generation")
        _require_hex64("patch_digest", str(patch_digest))
        if str(patch_digest) != base_candidate.patch_hash:
            raise ValueError("patch_digest must match base candidate patch hash")
        return cls(
            base_candidate_hash=base_candidate.candidate_hash,
            task_hash=task.task_hash,
            epoch_id=task.epoch_id,
            task_version=task.task_version,
            slot_id=SlotId(slot_id),
            session_id=str(session_id),
            lease_generation=int(lease_generation),
            role_profile_hash=task.role_profile_hash,
            base_checkpoint_id=task.base_checkpoint_id,
            patch_digest=str(patch_digest),
            changed_paths=_sorted_unique_strings(base_candidate.changed_paths),
            interface_changes=_sorted_unique_strings(interface_changes),
            verification_hashes=_sorted_unique_strings(verification_hashes),
            claims=_sorted_unique_strings(claims),
            risks=_sorted_unique_strings(risks),
            dependency_observations=_sorted_unique_strings(dependency_observations),
            summary=str(summary),
        )

    @property
    def candidate_hash(self) -> str:
        return canonical_digest(
            {
                "base_candidate_hash": self.base_candidate_hash,
                "task_hash": self.task_hash,
                "epoch_id": self.epoch_id,
                "task_version": self.task_version,
                "slot_id": self.slot_id,
                "session_id": self.session_id,
                "lease_generation": self.lease_generation,
                "role_profile_hash": self.role_profile_hash,
                "base_checkpoint_id": self.base_checkpoint_id,
                "patch_digest": self.patch_digest,
                "changed_paths": tuple(sorted(set(self.changed_paths))),
                "interface_changes": tuple(sorted(set(self.interface_changes))),
                "verification_hashes": tuple(sorted(set(self.verification_hashes))),
                "claims": tuple(sorted(set(self.claims))),
                "risks": tuple(sorted(set(self.risks))),
                "dependency_observations": tuple(sorted(set(self.dependency_observations))),
                "summary": self.summary,
            }
        )


@dataclass(frozen=True)
class FederatedReviewReceipt:
    candidate_hash: str
    reviewer_slot: SlotId
    session_id: str
    lease_generation: int
    reviewer_role_profile_hash: str
    verification_hashes: tuple[str, ...]
    verdict: Verdict

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer_slot, SlotId):
            raise TypeError("reviewer_slot must be SlotId")
        if not isinstance(self.verdict, Verdict):
            raise TypeError("verdict must be Verdict")
        _require_hex64("candidate_hash", self.candidate_hash)
        _require_hex64("reviewer_role_profile_hash", self.reviewer_role_profile_hash)
        for verification_hash in self.verification_hashes:
            _require_hex64("verification_hash", verification_hash)
        if not self.session_id:
            raise ValueError("session_id is required")
        if self.lease_generation < 0:
            raise ValueError("lease_generation cannot be negative")

    @classmethod
    def create(
        cls,
        *,
        candidate_hash: str,
        reviewer_slot: SlotId,
        session_id: str,
        lease_generation: int,
        reviewer_role_profile_hash: str,
        verification_hashes: Iterable[str],
        verdict: Verdict,
    ) -> "FederatedReviewReceipt":
        return cls(
            candidate_hash=str(candidate_hash),
            reviewer_slot=SlotId(reviewer_slot),
            session_id=str(session_id),
            lease_generation=int(lease_generation),
            reviewer_role_profile_hash=str(reviewer_role_profile_hash),
            verification_hashes=_sorted_unique_strings(verification_hashes),
            verdict=Verdict(verdict),
        )

    @property
    def review_hash(self) -> str:
        return canonical_digest(
            {
                "candidate_hash": self.candidate_hash,
                "reviewer_slot": self.reviewer_slot,
                "session_id": self.session_id,
                "lease_generation": self.lease_generation,
                "reviewer_role_profile_hash": self.reviewer_role_profile_hash,
                "verification_hashes": tuple(sorted(set(self.verification_hashes))),
                "verdict": self.verdict,
            }
        )
