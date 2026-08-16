from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Mapping

from metaengine.devfabric.codec import canonical_digest

from .contracts import FederatedCandidateReceipt, FederatedTaskEnvelope
from .store import FederationStore
from .types import CandidateEligibility, SLOT_ORDER, SlotId


@dataclass(frozen=True)
class Registration:
    session_id: str
    epoch_id: str
    slot_id: SlotId
    lease_generation: int
    capsule_sha256: str
    protocol_version: str
    role_profile_hash: str


@dataclass(frozen=True)
class CandidateSubmission:
    candidate_hash: str
    eligibility: CandidateEligibility


class FederationSimulator:
    """Deterministic local federation state machine; never a canonical authority."""

    def __init__(self, store: FederationStore) -> None:
        self.store = store

    @staticmethod
    def session_id_for(
        *,
        epoch_id: str,
        slot_id: SlotId,
        lease_generation: int,
        capsule_sha256: str,
        protocol_version: str,
        registration_nonce: str,
    ) -> str:
        if not registration_nonce:
            raise ValueError("registration_nonce is required")
        digest = canonical_digest(
            {
                "epoch_id": epoch_id,
                "slot_id": SlotId(slot_id),
                "lease_generation": int(lease_generation),
                "capsule_sha256": capsule_sha256,
                "protocol_version": protocol_version,
                "registration_nonce": registration_nonce,
            }
        )
        return f"session-{digest[:20]}"

    def _claim_slot(
        self,
        *,
        epoch_id: str,
        slot_id: SlotId,
        capsule_sha256: str,
        protocol_version: str,
        role_profile_hash: str,
        registration_nonce: str,
    ) -> Registration:
        slot_id = SlotId(slot_id)
        with self.store.transaction() as db:
            epoch = db.execute("SELECT 1 FROM epoch WHERE epoch_id=?", (epoch_id,)).fetchone()
            if epoch is None:
                raise KeyError(f"unknown epoch: {epoch_id}")
            slot = db.execute(
                "SELECT lease_generation, slot_state FROM slot WHERE epoch_id=? AND slot_id=?",
                (epoch_id, slot_id.value),
            ).fetchone()
            if slot is None:
                raise KeyError((epoch_id, slot_id))
            if slot["slot_state"] in {"SUSPENDED", "REVIEW_ONLY"} and slot_id is not SlotId.C6:
                raise RuntimeError(f"slot {slot_id.value} is not assignable")
            active = db.execute(
                """SELECT 1 FROM session
                WHERE epoch_id=? AND slot_id=? AND revoked=0 AND released_at IS NULL""",
                (epoch_id, slot_id.value),
            ).fetchone()
            if active is not None:
                raise RuntimeError(f"slot {slot_id.value} already has an active session")
            current = int(slot["lease_generation"])
            generation = current + 1
            updated = db.execute(
                """UPDATE slot SET lease_generation=?
                WHERE epoch_id=? AND slot_id=? AND lease_generation=?""",
                (generation, epoch_id, slot_id.value, current),
            )
            if updated.rowcount != 1:
                raise RuntimeError("slot generation CAS failed")
            session_id = self.session_id_for(
                epoch_id=epoch_id,
                slot_id=slot_id,
                lease_generation=generation,
                capsule_sha256=capsule_sha256,
                protocol_version=protocol_version,
                registration_nonce=registration_nonce,
            )
            db.execute(
                """INSERT INTO session(
                    session_id, epoch_id, slot_id, lease_generation, capsule_sha256, protocol_version, role_profile_hash
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    session_id,
                    epoch_id,
                    slot_id.value,
                    generation,
                    capsule_sha256,
                    protocol_version,
                    role_profile_hash,
                ),
            )
        return Registration(
            session_id=session_id,
            epoch_id=epoch_id,
            slot_id=slot_id,
            lease_generation=generation,
            capsule_sha256=capsule_sha256,
            protocol_version=protocol_version,
            role_profile_hash=role_profile_hash,
        )

    def register(
        self,
        *,
        epoch_id: str,
        requested_slot: SlotId | str | None,
        capsule_sha256: str,
        protocol_version: str,
        role_profile_hash: str | Mapping[SlotId, str] | Mapping[str, str],
        registration_nonce: str,
    ) -> Registration:
        def profile_for(slot: SlotId) -> str:
            if isinstance(role_profile_hash, str):
                return role_profile_hash
            if slot in role_profile_hash:
                return str(role_profile_hash[slot])
            if slot.value in role_profile_hash:
                return str(role_profile_hash[slot.value])
            raise KeyError(f"missing role profile hash for {slot.value}")

        if requested_slot in {None, "AUTO"}:
            last_error: Exception | None = None
            for slot_id in SLOT_ORDER:
                try:
                    return self._claim_slot(
                        epoch_id=epoch_id,
                        slot_id=slot_id,
                        capsule_sha256=capsule_sha256,
                        protocol_version=protocol_version,
                        role_profile_hash=profile_for(slot_id),
                        registration_nonce=registration_nonce,
                    )
                except (RuntimeError, sqlite3.IntegrityError) as exc:
                    last_error = exc
                    continue
            raise RuntimeError("no eligible free federation slot") from last_error
        return self._claim_slot(
            epoch_id=epoch_id,
            slot_id=SlotId(requested_slot),
            capsule_sha256=capsule_sha256,
            protocol_version=protocol_version,
            role_profile_hash=profile_for(SlotId(requested_slot)),
            registration_nonce=registration_nonce,
        )

    def release(self, session_id: str, *, expected_generation: int) -> bool:
        return self.store.release_session(session_id, expected_generation=expected_generation)

    def reclaim(
        self,
        *,
        epoch_id: str,
        slot_id: SlotId,
        capsule_sha256: str,
        protocol_version: str,
        role_profile_hash: str,
        registration_nonce: str,
        expected_generation: int,
    ) -> Registration:
        slot_id = SlotId(slot_id)
        with self.store.transaction() as db:
            active = db.execute(
                """SELECT session_id, lease_generation FROM session
                WHERE epoch_id=? AND slot_id=? AND revoked=0 AND released_at IS NULL""",
                (epoch_id, slot_id.value),
            ).fetchone()
            if active is None or int(active["lease_generation"]) != int(expected_generation):
                raise RuntimeError("reclaim generation CAS failed")
            db.execute("UPDATE session SET revoked=1 WHERE session_id=?", (active["session_id"],))
            slot = db.execute(
                "SELECT lease_generation FROM slot WHERE epoch_id=? AND slot_id=?",
                (epoch_id, slot_id.value),
            ).fetchone()
            if slot is None or int(slot["lease_generation"]) != int(expected_generation):
                raise RuntimeError("slot generation changed during reclaim")
            generation = int(expected_generation) + 1
            db.execute(
                "UPDATE slot SET lease_generation=? WHERE epoch_id=? AND slot_id=?",
                (generation, epoch_id, slot_id.value),
            )
            session_id = self.session_id_for(
                epoch_id=epoch_id,
                slot_id=slot_id,
                lease_generation=generation,
                capsule_sha256=capsule_sha256,
                protocol_version=protocol_version,
                registration_nonce=registration_nonce,
            )
            db.execute(
                """INSERT INTO session(
                    session_id, epoch_id, slot_id, lease_generation, capsule_sha256, protocol_version, role_profile_hash
                ) VALUES(?,?,?,?,?,?,?)""",
                (
                    session_id,
                    epoch_id,
                    slot_id.value,
                    generation,
                    capsule_sha256,
                    protocol_version,
                    role_profile_hash,
                ),
            )
        return Registration(
            session_id=session_id,
            epoch_id=epoch_id,
            slot_id=slot_id,
            lease_generation=generation,
            capsule_sha256=capsule_sha256,
            protocol_version=protocol_version,
            role_profile_hash=role_profile_hash,
        )

    def publish_task(self, task: FederatedTaskEnvelope) -> None:
        active = self.store.active_session_for_slot(task.epoch_id, task.owner_slot)
        if active is None:
            raise RuntimeError("task owner slot has no active session")
        if int(active["lease_generation"]) != task.lease_generation:
            raise RuntimeError("task lease_generation is stale")
        if active["role_profile_hash"] != task.role_profile_hash:
            raise RuntimeError("task role_profile_hash does not match active session")
        self.store.put_task(task)
        self.store.put_assignment(
            task_hash=task.task_hash,
            session_id=active["session_id"],
            lease_generation=task.lease_generation,
        )

    def submit_candidate(self, candidate: FederatedCandidateReceipt) -> CandidateSubmission:
        task = self.store.task_row(candidate.task_hash)
        if task is None:
            eligibility = CandidateEligibility.REJECTED
        elif int(task["task_version"]) != candidate.task_version:
            eligibility = CandidateEligibility.STALE_TASK_VERSION
        else:
            active = self.store.active_session_for_slot(candidate.epoch_id, candidate.slot_id)
            if (
                active is None
                or active["session_id"] != candidate.session_id
                or int(active["lease_generation"]) != candidate.lease_generation
            ):
                eligibility = CandidateEligibility.STALE_FENCED
            elif active["role_profile_hash"] != candidate.role_profile_hash:
                eligibility = CandidateEligibility.REJECTED
            elif int(task["lease_generation"]) != candidate.lease_generation:
                eligibility = CandidateEligibility.STALE_FENCED
            else:
                eligibility = CandidateEligibility.ELIGIBLE
        self.store.put_candidate(candidate, eligibility=eligibility)
        return CandidateSubmission(candidate_hash=candidate.candidate_hash, eligibility=eligibility)
