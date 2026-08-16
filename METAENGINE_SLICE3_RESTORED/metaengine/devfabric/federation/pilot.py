from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import CandidateReceipt, PrivacyClass, RiskClass, TaskEnvelope, Verdict

from .contracts import FederatedCandidateReceipt, FederatedReviewReceipt, FederatedTaskEnvelope
from .roles import load_role_genome
from .simulator import FederationSimulator, Registration
from .store import FederationStore
from .synchronizer import Synchronizer
from .types import CandidateEligibility, IntegrationMode, SlotId

PROTOCOL_VERSION = "D6.1"
CAPSULE_SHA256 = "2ff64e4c3d0becc9eca73e96f0f411c66ff8e6fbf828c60ba1145993753b3db7"
PILOT_POLICY_HASH = canonical_digest({"stage": "D6-F", "policy": "CONTROLLED_MACHINE_EPOCH"})
PILOT_CATALOG_HASH = canonical_digest({"stage": "D6-F", "slots": tuple(slot.value for slot in SlotId)})


@dataclass(frozen=True)
class PilotRegistration:
    slot_id: str
    session_id: str
    lease_generation: int
    role_profile_hash: str


@dataclass(frozen=True)
class PilotReport:
    status: str
    epoch_id: str
    checkpoint_id: str
    payload_root: str
    registrations: tuple[PilotRegistration, ...]
    task_hashes: tuple[str, ...]
    candidate_hashes: tuple[str, ...]
    eligible_candidates: tuple[str, ...]
    stale_candidates: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    conflict_task_ref: str
    integration_order: tuple[str, ...]
    snapshot_hash: str
    recovered_snapshot_hash: str
    c0_recovered: bool
    old_c0_session_id: str
    new_c0_session_id: str
    old_c3_session_id: str
    new_c3_session_id: str
    replacement_slot: str
    replacement_generation: int
    stale_candidate_hash: str
    c2_candidate_hash: str
    review_hash: str


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _profile_hash(slot: SlotId) -> str:
    return load_role_genome(_root(), slot).profile_hash


def _base_task(
    checkpoint_id: str,
    payload_root: str,
    *,
    objective: str,
    allowed_paths: tuple[str, ...],
    risk: RiskClass = RiskClass.NORMAL,
) -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id=checkpoint_id,
        source_tree_hash=payload_root,
        objective=objective,
        acceptance_tests=("D6-F deterministic pilot",),
        allowed_paths=allowed_paths,
        forbidden_paths=("lineages/",),
        capabilities_required=("federation",),
        risk_class=risk,
        privacy_class=PrivacyClass.P1,
    )


def _task(
    *,
    base: TaskEnvelope,
    epoch_id: str,
    owner: Registration,
    write_set: tuple[str, ...],
    interface_set: tuple[str, ...] = (),
    review_slots: tuple[SlotId, ...] = (),
    mode: IntegrationMode = IntegrationMode.PARALLEL,
    version: int = 1,
) -> FederatedTaskEnvelope:
    return FederatedTaskEnvelope.create(
        base_task=base,
        epoch_id=epoch_id,
        task_version=version,
        owner_slot=owner.slot_id,
        lease_generation=owner.lease_generation,
        role_profile_hash=owner.role_profile_hash,
        base_checkpoint_id=base.source_checkpoint_id,
        dependency_task_ids=(),
        read_set=(),
        write_set=write_set,
        interface_set=interface_set,
        integration_mode=mode,
        review_slots=review_slots,
    )


def _candidate(task: FederatedTaskEnvelope, owner: Registration, *, label: str) -> FederatedCandidateReceipt:
    patch_digest = canonical_digest(
        {
            "stage": "D6-F",
            "kind": "synthetic-patch",
            "label": label,
            "task_hash": task.task_hash,
            "slot": owner.slot_id.value,
            "generation": owner.lease_generation,
        }
    )
    base = CandidateReceipt.create(
        task_id=task.base_task.task_id,
        provider_id=f"pilot-{owner.slot_id.value.lower()}",
        base_tree_hash=task.base_task.source_tree_hash,
        patch_hash=patch_digest,
        changed_paths=task.write_set,
        metadata={"pilot": "D6-F", "label": label},
    )
    return FederatedCandidateReceipt.create(
        base_candidate=base,
        task=task,
        slot_id=owner.slot_id,
        session_id=owner.session_id,
        lease_generation=owner.lease_generation,
        patch_digest=patch_digest,
        interface_changes=task.interface_set,
        verification_hashes=(canonical_digest({"verification": label, "task_hash": task.task_hash}),),
        claims=(f"pilot:{label}",),
        risks=(),
        dependency_observations=(),
        summary=f"D6-F synthetic candidate {label}",
    )


def _report_registration(registration: Registration) -> PilotRegistration:
    return PilotRegistration(
        slot_id=registration.slot_id.value,
        session_id=registration.session_id,
        lease_generation=registration.lease_generation,
        role_profile_hash=registration.role_profile_hash,
    )


def run_controlled_epoch(store: FederationStore, checkpoint_id: str, payload_root: str) -> PilotReport:
    """Run a deterministic non-canonical machine pilot over one persisted federation store."""
    if len(payload_root) != 64 or any(ch not in "0123456789abcdef" for ch in payload_root):
        raise ValueError("payload_root must be a lowercase 64-hex digest")
    epoch_id = "d6f-machine-e001"
    if store.get_epoch(epoch_id) is not None:
        raise ValueError(f"pilot epoch already exists: {epoch_id}")
    store.put_epoch(
        epoch_id=epoch_id,
        base_checkpoint_id=checkpoint_id,
        policy_hash=PILOT_POLICY_HASH,
        catalog_hash=PILOT_CATALOG_HASH,
    )
    sim = FederationSimulator(store)

    registrations: dict[SlotId, Registration] = {}
    for slot in (SlotId.C0, SlotId.C2, SlotId.C3, SlotId.C4, SlotId.C6, SlotId.C7):
        registrations[slot] = sim.register(
            epoch_id=epoch_id,
            requested_slot=slot,
            capsule_sha256=CAPSULE_SHA256,
            protocol_version=PROTOCOL_VERSION,
            role_profile_hash=_profile_hash(slot),
            registration_nonce=f"d6f-{slot.value.lower()}-g1",
        )

    c2_task = _task(
        base=_base_task(
            checkpoint_id,
            payload_root,
            objective="C2 core engine implementation",
            allowed_paths=("metaengine/core/",),
            risk=RiskClass.HIGH,
        ),
        epoch_id=epoch_id,
        owner=registrations[SlotId.C2],
        write_set=("metaengine/core/federation_runtime.py",),
        interface_set=("federation-runtime-v1",),
        review_slots=(SlotId.C6,),
        mode=IntegrationMode.IMPLEMENT_REVIEW,
    )
    c4_task = _task(
        base=_base_task(
            checkpoint_id,
            payload_root,
            objective="C4 edge MCP implementation",
            allowed_paths=("devfabric/cloudflare/",),
        ),
        epoch_id=epoch_id,
        owner=registrations[SlotId.C4],
        write_set=("devfabric/cloudflare/src/federation_bridge.ts",),
        interface_set=("federation-runtime-v1",),
    )
    c7_task = _task(
        base=_base_task(
            checkpoint_id,
            payload_root,
            objective="C7 federation benchmark",
            allowed_paths=("benchmarks/federation/",),
        ),
        epoch_id=epoch_id,
        owner=registrations[SlotId.C7],
        write_set=("benchmarks/federation/d6f.json",),
    )
    c3_base = _base_task(
        checkpoint_id,
        payload_root,
        objective="C3 AI swarm parallel implementation",
        allowed_paths=("metaengine/swarm/",),
    )
    c3_old_task = _task(
        base=c3_base,
        epoch_id=epoch_id,
        owner=registrations[SlotId.C3],
        write_set=("metaengine/swarm/d6f_worker.py",),
    )

    for task in (c2_task, c4_task, c7_task, c3_old_task):
        sim.publish_task(task)

    stale_candidate = _candidate(c3_old_task, registrations[SlotId.C3], label="c3-old")
    old_c3 = registrations[SlotId.C3]
    if not sim.release(old_c3.session_id, expected_generation=old_c3.lease_generation):
        raise RuntimeError("failed to release C3 pilot session")
    new_c3 = sim.register(
        epoch_id=epoch_id,
        requested_slot=SlotId.C3,
        capsule_sha256=CAPSULE_SHA256,
        protocol_version=PROTOCOL_VERSION,
        role_profile_hash=_profile_hash(SlotId.C3),
        registration_nonce="d6f-c3-g2",
    )
    stale_submission = sim.submit_candidate(stale_candidate)
    if stale_submission.eligibility is not CandidateEligibility.STALE_FENCED:
        raise RuntimeError("old C3 candidate was not stale-fenced")

    c3_new_task = _task(
        base=c3_base,
        epoch_id=epoch_id,
        owner=new_c3,
        write_set=("metaengine/swarm/d6f_worker.py",),
        version=2,
    )
    sim.publish_task(c3_new_task)

    c2_candidate = _candidate(c2_task, registrations[SlotId.C2], label="c2-core")
    c4_candidate = _candidate(c4_task, registrations[SlotId.C4], label="c4-edge")
    c7_candidate = _candidate(c7_task, registrations[SlotId.C7], label="c7-benchmark")
    c3_candidate = _candidate(c3_new_task, new_c3, label="c3-replacement")
    for candidate in (c2_candidate, c4_candidate, c7_candidate, c3_candidate):
        submission = sim.submit_candidate(candidate)
        if submission.eligibility is not CandidateEligibility.ELIGIBLE:
            raise RuntimeError(f"candidate unexpectedly ineligible: {candidate.candidate_hash}")

    c6 = registrations[SlotId.C6]
    review = FederatedReviewReceipt.create(
        candidate_hash=c2_candidate.candidate_hash,
        reviewer_slot=SlotId.C6,
        session_id=c6.session_id,
        lease_generation=c6.lease_generation,
        reviewer_role_profile_hash=c6.role_profile_hash,
        verification_hashes=(canonical_digest({"verification": "c6-review", "candidate": c2_candidate.candidate_hash}),),
        verdict=Verdict.PASS,
    )
    store.put_review(review)

    synchronizer = Synchronizer(store)
    graph = synchronizer.graph(epoch_id)
    for edge in graph.conflicts:
        if edge.conflict_class.value != "VERIFICATION_CONFLICT":
            store.put_conflict(
                conflict_hash=edge.conflict_hash,
                epoch_id=epoch_id,
                conflict_class=edge.conflict_class,
                left_ref=edge.left,
                right_ref=edge.right,
                payload=edge,
            )

    first_snapshot = synchronizer.snapshot(epoch_id)
    interface_refs = tuple(ref for ref in first_snapshot.conflict_refs if ref.startswith("INTERFACE_CONTRACT_CONFLICT:"))
    if not interface_refs:
        raise RuntimeError("intentional C2/C4 interface conflict was not detected")
    conflict_task_ref = f"conflict-task-{canonical_digest({'epoch_id': epoch_id, 'refs': interface_refs})[:20]}"

    old_c0 = registrations[SlotId.C0]
    if not sim.release(old_c0.session_id, expected_generation=old_c0.lease_generation):
        raise RuntimeError("failed to release C0 pilot session")
    new_c0 = sim.register(
        epoch_id=epoch_id,
        requested_slot=SlotId.C0,
        capsule_sha256=CAPSULE_SHA256,
        protocol_version=PROTOCOL_VERSION,
        role_profile_hash=_profile_hash(SlotId.C0),
        registration_nonce="d6f-c0-recovered",
    )
    # The replacement synchronizer receives no prior C0 prose or in-memory state.
    recovered_snapshot = Synchronizer(store).recover(epoch_id)
    c0_recovered = (
        first_snapshot.snapshot_hash == recovered_snapshot.snapshot_hash
        and first_snapshot.integration_order == recovered_snapshot.integration_order
    )
    if not c0_recovered:
        raise RuntimeError("C0 recovery changed deterministic synchronization result")

    report_regs = tuple(
        _report_registration(new_c0 if slot is SlotId.C0 else new_c3 if slot is SlotId.C3 else registrations[slot])
        for slot in (SlotId.C0, SlotId.C2, SlotId.C3, SlotId.C4, SlotId.C6, SlotId.C7)
    )
    all_tasks = (c2_task, c3_old_task, c3_new_task, c4_task, c7_task)
    all_candidates = (stale_candidate, c2_candidate, c3_candidate, c4_candidate, c7_candidate)
    return PilotReport(
        status="PASS",
        epoch_id=epoch_id,
        checkpoint_id=checkpoint_id,
        payload_root=payload_root,
        registrations=report_regs,
        task_hashes=tuple(sorted(task.task_hash for task in all_tasks)),
        candidate_hashes=tuple(sorted(candidate.candidate_hash for candidate in all_candidates)),
        eligible_candidates=recovered_snapshot.eligible_candidates,
        stale_candidates=recovered_snapshot.stale_candidates,
        conflict_refs=recovered_snapshot.conflict_refs,
        conflict_task_ref=conflict_task_ref,
        integration_order=recovered_snapshot.integration_order,
        snapshot_hash=first_snapshot.snapshot_hash,
        recovered_snapshot_hash=recovered_snapshot.snapshot_hash,
        c0_recovered=c0_recovered,
        old_c0_session_id=old_c0.session_id,
        new_c0_session_id=new_c0.session_id,
        old_c3_session_id=old_c3.session_id,
        new_c3_session_id=new_c3.session_id,
        replacement_slot=SlotId.C3.value,
        replacement_generation=new_c3.lease_generation,
        stale_candidate_hash=stale_candidate.candidate_hash,
        c2_candidate_hash=c2_candidate.candidate_hash,
        review_hash=review.review_hash,
    )
