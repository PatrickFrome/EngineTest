from __future__ import annotations

import dataclasses

import pytest

from metaengine.devfabric.federation.contracts import FederatedTaskEnvelope
from metaengine.devfabric.federation.types import IntegrationMode, SlotId
from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope


def make_base_task(*, risk: RiskClass = RiskClass.HIGH, privacy: PrivacyClass = PrivacyClass.P1) -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id="cp1",
        source_tree_hash="b" * 64,
        objective="change router",
        acceptance_tests=("python -m pytest -q",),
        allowed_paths=("metaengine/",),
        forbidden_paths=("lineages/",),
        capabilities_required=("python",),
        risk_class=risk,
        privacy_class=privacy,
    )


def make_federated_task(**changes) -> FederatedTaskEnvelope:
    params = {
        "base_task": make_base_task(),
        "epoch_id": "epoch-1",
        "task_version": 1,
        "owner_slot": SlotId.C2,
        "lease_generation": 3,
        "role_profile_hash": "a" * 64,
        "base_checkpoint_id": "cp1",
        "dependency_task_ids": (),
        "read_set": ("metaengine/",),
        "write_set": ("metaengine/core.py",),
        "interface_set": ("router-v1",),
        "integration_mode": IntegrationMode.EXCLUSIVE,
        "review_slots": (SlotId.C6,),
    }
    params.update(changes)
    return FederatedTaskEnvelope.create(**params)


def test_federated_task_hash_binds_fencing_and_role_profile_without_changing_base_hash():
    base = make_base_task()
    a = make_federated_task(base_task=base)
    b = dataclasses.replace(a, lease_generation=4)
    c = dataclasses.replace(a, role_profile_hash="c" * 64)
    assert a.base_task.task_hash == base.task_hash
    assert a.task_hash != b.task_hash
    assert a.task_hash != c.task_hash
    assert a.task_id == f"ftask-{a.task_hash[:20]}"


def test_federated_task_canonicalizes_set_like_fields():
    left = make_federated_task(
        dependency_task_ids=("task-b", "task-a", "task-b"),
        read_set=("b/", "a/", "b/"),
        write_set=("z.py", "a.py", "z.py"),
        interface_set=("router-v2", "router-v1", "router-v2"),
        review_slots=(SlotId.C7, SlotId.C6, SlotId.C6),
    )
    right = make_federated_task(
        dependency_task_ids=("task-a", "task-b"),
        read_set=("a/", "b/"),
        write_set=("a.py", "z.py"),
        interface_set=("router-v1", "router-v2"),
        review_slots=(SlotId.C6, SlotId.C7),
    )
    assert left == right
    assert left.task_hash == right.task_hash


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"task_version": 0}, "task_version"),
        ({"lease_generation": -1}, "lease_generation"),
        ({"base_checkpoint_id": "cp-other"}, "base_checkpoint_id"),
        ({"role_profile_hash": "short"}, "role_profile_hash"),
        ({"review_slots": ()}, "C6 review"),
        ({"integration_mode": IntegrationMode.REDUNDANT, "owner_slot": SlotId.C0}, "C0"),
    ],
)
def test_federated_task_rejects_invalid_fencing_review_and_role_constraints(changes, message):
    with pytest.raises(ValueError, match=message):
        make_federated_task(**changes)


def test_c6_high_risk_task_requires_c1_and_rejects_self_review():
    with pytest.raises(ValueError, match="C1 review"):
        make_federated_task(owner_slot=SlotId.C6, integration_mode=IntegrationMode.IMPLEMENT_REVIEW, review_slots=())
    with pytest.raises(ValueError, match="self-review"):
        make_federated_task(
            owner_slot=SlotId.C6,
            integration_mode=IntegrationMode.IMPLEMENT_REVIEW,
            review_slots=(SlotId.C1, SlotId.C6),
        )


def test_role_privacy_ceiling_rejects_p3_for_external_oriented_roles():
    with pytest.raises(ValueError, match="privacy ceiling"):
        make_federated_task(base_task=make_base_task(privacy=PrivacyClass.P3), owner_slot=SlotId.C4)

from metaengine.devfabric.federation.contracts import FederatedCandidateReceipt, FederatedReviewReceipt
from metaengine.devfabric.models import CandidateReceipt, Verdict


def make_base_candidate(task: FederatedTaskEnvelope | None = None) -> CandidateReceipt:
    task = task or make_federated_task()
    return CandidateReceipt.create(
        task_id=task.base_task.task_id,
        provider_id="local-opencode",
        base_tree_hash="d" * 64,
        patch_hash="e" * 64,
        changed_paths=("metaengine/core.py",),
        metadata={"worker": "opencode"},
    )


def make_federated_candidate(**changes) -> FederatedCandidateReceipt:
    task = changes.pop("task", make_federated_task())
    base_candidate = changes.pop("base_candidate", make_base_candidate(task))
    params = {
        "base_candidate": base_candidate,
        "task": task,
        "slot_id": task.owner_slot,
        "session_id": "session-c2-a",
        "lease_generation": task.lease_generation,
        "patch_digest": base_candidate.patch_hash,
        "interface_changes": ("router-v1",),
        "verification_hashes": ("f" * 64,),
        "claims": ("router remains deterministic",),
        "risks": ("routing regression",),
        "dependency_observations": ("task-a unchanged",),
        "summary": "candidate summary",
    }
    params.update(changes)
    return FederatedCandidateReceipt.create(**params)


def test_federated_candidate_hash_binds_session_fencing_and_semantic_evidence():
    base = make_federated_candidate()
    variants = [
        dataclasses.replace(base, session_id="session-c2-b"),
        dataclasses.replace(base, lease_generation=4),
        make_federated_candidate(task=dataclasses.replace(make_federated_task(), task_version=2)),
        dataclasses.replace(base, interface_changes=("router-v2",)),
        dataclasses.replace(base, verification_hashes=("1" * 64,)),
        dataclasses.replace(base, claims=("different claim",)),
        dataclasses.replace(base, risks=("different risk",)),
    ]
    assert all(item.candidate_hash != base.candidate_hash for item in variants)


def test_federated_candidate_binds_existing_candidate_without_mutating_base_receipt():
    task = make_federated_task()
    base_candidate = make_base_candidate(task)
    federated = make_federated_candidate(task=task, base_candidate=base_candidate)
    assert federated.base_candidate_hash == base_candidate.candidate_hash
    assert federated.changed_paths == base_candidate.changed_paths
    assert federated.task_hash == task.task_hash
    assert federated.role_profile_hash == task.role_profile_hash
    assert federated.base_checkpoint_id == task.base_checkpoint_id


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"session_id": ""}, "session_id"),
        ({"lease_generation": 99}, "lease_generation"),
        ({"patch_digest": "bad"}, "patch_digest"),
        ({"verification_hashes": ("bad",)}, "verification_hash"),
        ({"slot_id": SlotId.C3}, "owner slot"),
    ],
)
def test_federated_candidate_rejects_unbound_or_invalid_receipts(changes, message):
    with pytest.raises(ValueError, match=message):
        make_federated_candidate(**changes)


def test_federated_candidate_requires_patch_digest_to_match_base_candidate():
    with pytest.raises(ValueError, match="base candidate patch"):
        make_federated_candidate(patch_digest="1" * 64)


def test_review_receipt_hash_binds_reviewer_session_generation_verifiers_and_verdict():
    candidate = make_federated_candidate()
    review = FederatedReviewReceipt.create(
        candidate_hash=candidate.candidate_hash,
        reviewer_slot=SlotId.C6,
        session_id="session-c6-a",
        lease_generation=7,
        reviewer_role_profile_hash="4" * 64,
        verification_hashes=("2" * 64, "3" * 64),
        verdict=Verdict.PASS,
    )
    assert len(review.review_hash) == 64
    assert dataclasses.replace(review, session_id="session-c6-b").review_hash != review.review_hash
    assert dataclasses.replace(review, lease_generation=8).review_hash != review.review_hash
    assert dataclasses.replace(review, verdict=Verdict.FAIL).review_hash != review.review_hash


def test_review_receipt_rejects_invalid_digest_and_empty_session():
    with pytest.raises(ValueError, match="candidate_hash"):
        FederatedReviewReceipt.create(
            candidate_hash="bad",
            reviewer_slot=SlotId.C6,
            session_id="session-c6-a",
            lease_generation=1,
            reviewer_role_profile_hash="4" * 64,
            verification_hashes=(),
            verdict=Verdict.PASS,
        )
    with pytest.raises(ValueError, match="session_id"):
        FederatedReviewReceipt.create(
            candidate_hash="a" * 64,
            reviewer_slot=SlotId.C6,
            session_id="",
            lease_generation=1,
            reviewer_role_profile_hash="4" * 64,
            verification_hashes=(),
            verdict=Verdict.PASS,
        )


def test_stage_a_task_and_candidate_hashes_remain_byte_compatible():
    base = make_base_task()
    candidate = make_base_candidate(make_federated_task(base_task=base))
    assert base.task_hash == "d555c500b904c89fc42253f0ec8eeed03df4b61c588d56f43d900587e422aaf0"
    assert candidate.candidate_hash == "184c72ccfca59a41ef284d287826d4af1f942a1ea109a0df0d6f7b7c8bd66344"


def test_review_receipt_hash_binds_reviewer_role_profile_hash():
    candidate = make_federated_candidate()
    review = FederatedReviewReceipt.create(
        candidate_hash=candidate.candidate_hash,
        reviewer_slot=SlotId.C6,
        session_id="session-c6-a",
        lease_generation=7,
        reviewer_role_profile_hash="4" * 64,
        verification_hashes=("2" * 64,),
        verdict=Verdict.PASS,
    )
    assert dataclasses.replace(review, reviewer_role_profile_hash="5" * 64).review_hash != review.review_hash


def test_direct_federation_dataclass_constructors_reject_unnormalized_runtime_types():
    task = make_federated_task()
    with pytest.raises(TypeError, match="owner_slot"):
        dataclasses.replace(task, owner_slot="C2")
    candidate = make_federated_candidate(task=task)
    with pytest.raises(TypeError, match="slot_id"):
        dataclasses.replace(candidate, slot_id="C2")
