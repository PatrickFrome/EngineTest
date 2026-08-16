from __future__ import annotations

import dataclasses

from metaengine.devfabric.federation.conflicts import detect_candidate_conflicts
from metaengine.devfabric.federation.contracts import FederatedCandidateReceipt, FederatedReviewReceipt, FederatedTaskEnvelope
from metaengine.devfabric.federation.types import ConflictClass, IntegrationMode, SlotId
from metaengine.devfabric.models import CandidateReceipt, PrivacyClass, RiskClass, TaskEnvelope, Verdict


def make_task(*, marker: str, write_set=("metaengine/a.py",), interface_set=(), dependency_task_ids=(), checkpoint="cp1", risk=RiskClass.NORMAL, review_slots=()):
    base = TaskEnvelope.create(
        source_checkpoint_id=checkpoint,
        source_tree_hash=(marker * 64)[:64],
        objective=f"task {marker}",
        acceptance_tests=("pytest",),
        allowed_paths=("metaengine/",),
        forbidden_paths=("lineages/",),
        capabilities_required=("python",),
        risk_class=risk,
        privacy_class=PrivacyClass.P1,
    )
    return FederatedTaskEnvelope.create(
        base_task=base,
        epoch_id="e1", task_version=1, owner_slot=SlotId.C2, lease_generation=1,
        role_profile_hash="a" * 64, base_checkpoint_id=checkpoint,
        dependency_task_ids=dependency_task_ids, read_set=(), write_set=write_set, interface_set=interface_set,
        integration_mode=IntegrationMode.PARALLEL, review_slots=review_slots,
    )


def make_candidate(task: FederatedTaskEnvelope, *, patch: str, session="session-c2"):
    base = CandidateReceipt.create(
        task_id=task.base_task.task_id, provider_id="local", base_tree_hash="b" * 64,
        patch_hash=patch * 64, changed_paths=task.write_set,
    )
    return FederatedCandidateReceipt.create(
        base_candidate=base, task=task, slot_id=task.owner_slot, session_id=session,
        lease_generation=task.lease_generation, patch_digest=base.patch_hash,
        interface_changes=task.interface_set, verification_hashes=("c" * 64,), claims=(), risks=(),
        dependency_observations=(), summary="candidate",
    )


def classes(graph):
    return tuple(edge.conflict_class for edge in graph.conflicts)


def test_overlapping_write_sets_create_path_conflict_and_output_is_deterministic():
    left = make_task(marker="1", write_set=("metaengine/shared.py",))
    right = make_task(marker="2", write_set=("metaengine/shared.py",))
    lc, rc = make_candidate(left, patch="3"), make_candidate(right, patch="4")
    graph_a = detect_candidate_conflicts((left, right), (lc, rc))
    graph_b = detect_candidate_conflicts((right, left), (rc, lc))
    assert ConflictClass.PATH_WRITE_CONFLICT in classes(graph_a)
    assert graph_a == graph_b
    assert graph_a.graph_hash == graph_b.graph_hash


def test_interface_overlap_creates_interface_contract_conflict():
    left = make_task(marker="1", write_set=("a.py",), interface_set=("router-v1",))
    right = make_task(marker="2", write_set=("b.py",), interface_set=("router-v1",))
    graph = detect_candidate_conflicts((left, right), (make_candidate(left, patch="3"), make_candidate(right, patch="4")))
    assert ConflictClass.INTERFACE_CONTRACT_CONFLICT in classes(graph)


def test_dependency_creates_ordering_edge_not_conflict_by_itself():
    first = make_task(marker="1", write_set=("a.py",))
    second0 = make_task(marker="2", write_set=("b.py",))
    second = dataclasses.replace(second0, dependency_task_ids=(first.task_id,))
    graph = detect_candidate_conflicts((second, first), (make_candidate(first, patch="3"), make_candidate(second, patch="4")))
    assert graph.ordering_edges == ((first.task_hash, second.task_hash),)
    assert graph.conflicts == ()


def test_different_undeclared_base_checkpoints_create_stale_base_conflict():
    left = make_task(marker="1", write_set=("a.py",), checkpoint="cp1")
    right = make_task(marker="2", write_set=("b.py",), checkpoint="cp2")
    graph = detect_candidate_conflicts((left, right), (make_candidate(left, patch="3"), make_candidate(right, patch="4")))
    assert ConflictClass.STALE_BASE_CONFLICT in classes(graph)


def test_required_review_missing_or_fail_creates_verification_conflict():
    task = make_task(marker="1", risk=RiskClass.HIGH, review_slots=(SlotId.C6,))
    candidate = make_candidate(task, patch="3")
    missing = detect_candidate_conflicts((task,), (candidate,), reviews=())
    assert ConflictClass.VERIFICATION_CONFLICT in classes(missing)
    failed_review = FederatedReviewReceipt.create(
        candidate_hash=candidate.candidate_hash, reviewer_slot=SlotId.C6, session_id="session-c6",
        lease_generation=1, reviewer_role_profile_hash="d" * 64, verification_hashes=("e" * 64,), verdict=Verdict.FAIL,
    )
    failed = detect_candidate_conflicts((task,), (candidate,), reviews=(failed_review,))
    assert ConflictClass.VERIFICATION_CONFLICT in classes(failed)
