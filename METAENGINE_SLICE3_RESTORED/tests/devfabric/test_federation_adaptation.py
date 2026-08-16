from __future__ import annotations

import dataclasses

import pytest

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.federation.adaptation import (
    metrics_from_finalization,
    next_producer_concurrency,
    propose_soft_role_genome,
    build_adaptation_receipt,
    verify_shadow_receipt,
)
from metaengine.devfabric.federation.finalization import EpochFinalization, recovery_cut_hash
from metaengine.devfabric.federation.roles import load_role_genome
from metaengine.devfabric.federation.types import SlotId
from pathlib import Path


def _sample_cut(*, reverse: bool = False) -> dict:
    tasks = [
        {
            "task_hash": "1" * 64,
            "task_version": 1,
            "owner_slot": "C2",
            "lease_generation": 1,
            "role_profile_hash": "a" * 64,
            "dependency_task_ids": [],
            "write_set": ["docs/c2.md"],
            "interface_set": ["core-v1"],
            "risk_class": "HIGH",
            "review_slots": ["C6"],
        },
        {
            "task_hash": "2" * 64,
            "task_version": 1,
            "owner_slot": "C4",
            "lease_generation": 1,
            "role_profile_hash": "b" * 64,
            "dependency_task_ids": [],
            "write_set": ["docs/c4.md"],
            "interface_set": ["edge-v1"],
            "risk_class": "NORMAL",
            "review_slots": [],
        },
    ]
    assignments = [
        {"assignment_id": "assign-b", "task_hash": "2" * 64, "assignment_state": "COMPLETED", "lease_generation": 1},
        {"assignment_id": "assign-a", "task_hash": "1" * 64, "assignment_state": "COMPLETED", "lease_generation": 1},
    ]
    candidates = [
        {
            "candidate_hash": "d" * 64,
            "task_hash": "2" * 64,
            "session_id": "session-c4",
            "lease_generation": 1,
            "role_profile_hash": "b" * 64,
            "task_version": 1,
            "eligibility": "ELIGIBLE",
            "verification_hashes": [],
            "privacy_class": "P1",
        },
        {
            "candidate_hash": "c" * 64,
            "task_hash": "1" * 64,
            "session_id": "session-c2",
            "lease_generation": 1,
            "role_profile_hash": "a" * 64,
            "task_version": 1,
            "eligibility": "ELIGIBLE",
            "verification_hashes": ["7" * 64],
            "privacy_class": "P1",
        },
    ]
    reviews = [
        {
            "review_hash": "e" * 64,
            "candidate_hash": "c" * 64,
            "reviewer_slot": "C6",
            "session_id": "session-c6",
            "lease_generation": 1,
            "reviewer_role_profile_hash": "6" * 64,
            "verdict": "PASS",
            "verification_hashes": ["8" * 64],
            "privacy_class": "P1",
        }
    ]
    conflicts = [
        {"conflict_hash": "f" * 64, "conflict_class": "PATH_WRITE_CONFLICT", "resolved": True, "left_ref": "x", "right_ref": "y"}
    ]
    decisions = [
        {"decision_hash": "9" * 64, "candidate_hash": "c" * 64, "decision": "INCLUDE"},
        {"decision_hash": "0" * 64, "candidate_hash": "d" * 64, "decision": "INCLUDE"},
    ]
    witnesses = [
        {"slot_id": "C6", "session_id": "session-c6", "lease_generation": 1, "role_profile_hash": "6" * 64, "revoked": False, "released_at": None},
        {"slot_id": "C4", "session_id": "session-c4", "lease_generation": 1, "role_profile_hash": "b" * 64, "revoked": False, "released_at": None},
        {"slot_id": "C2", "session_id": "session-c2", "lease_generation": 1, "role_profile_hash": "a" * 64, "revoked": False, "released_at": None},
    ]
    if reverse:
        for value in (tasks, assignments, candidates, reviews, conflicts, decisions, witnesses):
            value.reverse()

    snapshot = {
        "epoch_id": "epoch-final-1",
        "base_checkpoint_id": "cp001",
        "policy_hash": "3" * 64,
        "catalog_hash": "4" * 64,
        "eligible_candidates": ["c" * 64, "d" * 64],
        "rejected_candidates": [],
        "stale_candidates": [],
        "conflict_refs": [],
        "integration_order": ["c" * 64, "d" * 64],
        "required_verification_hashes": ["7" * 64, "8" * 64],
    }
    return {
        "cut_version": "D6.FINALIZATION.1",
        "epoch": {
            "epoch_id": "epoch-final-1",
            "base_checkpoint_id": "cp001",
            "base_payload_root": "5" * 64,
            "federation_policy_hash": "3" * 64,
            "role_catalog_hash": "4" * 64,
            "producer_concurrency": 2,
        },
        "tasks": tasks,
        "assignments": assignments,
        "candidates": candidates,
        "reviews": reviews,
        "conflicts": conflicts,
        "integration_decisions": decisions,
        "participant_witnesses": witnesses,
        "terminal_snapshot": {"snapshot_hash": canonical_digest(snapshot), "snapshot": snapshot},
    }


def _finalization(cut: dict) -> EpochFinalization:
    return EpochFinalization.create(
        epoch_id=cut["epoch"]["epoch_id"],
        final_snapshot_hash=cut["terminal_snapshot"]["snapshot_hash"],
        recovery_cut_hash=recovery_cut_hash(cut),
        recovery_cut=cut,
        finalized_by_session_id="sync-c0",
        finalized_by_generation=2,
    )


def test_metrics_are_derived_only_from_verified_finalized_cut() -> None:
    metrics = metrics_from_finalization(_finalization(_sample_cut()))

    assert metrics.epoch_id == "epoch-final-1"
    assert metrics.producer_concurrency == 2
    assert metrics.task_count == 2
    assert metrics.candidate_count == 2
    assert metrics.eligible_candidate_count == 2
    assert metrics.rejected_candidate_count == 0
    assert metrics.stale_candidate_count == 0
    assert metrics.review_count == 1
    assert metrics.review_pass_count == 1
    assert metrics.conflict_count == 1
    assert metrics.unresolved_conflict_count == 0
    assert metrics.include_count == 2
    assert metrics.integrated_candidate_count == 2
    assert metrics.participants == (("C2", "a" * 64), ("C4", "b" * 64), ("C6", "6" * 64))


def test_metrics_reject_non_finalization_input_fail_closed() -> None:
    import pytest

    with pytest.raises(ValueError, match="FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED"):
        metrics_from_finalization({"recovery_cut": _sample_cut()})  # type: ignore[arg-type]


def test_metrics_are_order_independent_after_finalization_normalization() -> None:
    left = metrics_from_finalization(_finalization(_sample_cut(reverse=False)))
    right = metrics_from_finalization(_finalization(_sample_cut(reverse=True)))
    assert left == right
    assert left.conflict_rate.numerator == 0
    assert left.conflict_rate.denominator == 2
    assert left.verification_pass_rate.numerator == 1
    assert left.verification_pass_rate.denominator == 1
    assert left.integration_rate.numerator == 2
    assert left.integration_rate.denominator == 2


def test_tampered_store_row_fails_before_adaptation() -> None:
    import pytest

    finalization = _finalization(_sample_cut())
    row = {
        "finalization_hash": finalization.finalization_hash,
        "epoch_id": finalization.epoch_id,
        "final_snapshot_hash": finalization.final_snapshot_hash,
        "recovery_cut_hash": finalization.recovery_cut_hash,
        "recovery_cut": {
            **finalization.recovery_cut,
            "epoch": {**finalization.recovery_cut["epoch"], "producer_concurrency": 6},
        },
        "finalized_by_session_id": finalization.finalized_by_session_id,
        "finalized_by_generation": finalization.finalized_by_generation,
        "protocol_version": finalization.protocol_version,
    }
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CUT_HASH_MISMATCH"):
        EpochFinalization.from_store_row(row)


def _metrics_variant(index: int, *, candidates: int, unresolved: int, policy_hash: str = "3" * 64):
    base = metrics_from_finalization(_finalization(_sample_cut()))
    return dataclasses.replace(
        base,
        finalization_hash=f"{index:x}" * 64,
        recovery_cut_hash=f"{(index + 8):x}" * 64,
        epoch_id=f"epoch-{index}",
        federation_policy_hash=policy_hash,
        candidate_count=candidates,
        unresolved_conflict_count=unresolved,
    )


def test_current_one_epoch_baseline_holds_for_insufficient_evidence() -> None:
    metrics = metrics_from_finalization(_finalization(_sample_cut()))
    decision = next_producer_concurrency(4, (metrics,))
    assert decision.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert decision.current == 4
    assert decision.proposed == 4
    assert decision.reason == "MIN_FINALIZED_EPOCHS"


def test_conflict_budget_uses_summed_exact_counts_and_bounds() -> None:
    low = tuple(_metrics_variant(i, candidates=2, unresolved=0) for i in (1, 2, 3))
    mid = (
        _metrics_variant(1, candidates=2, unresolved=1),
        _metrics_variant(2, candidates=2, unresolved=0),
        _metrics_variant(3, candidates=6, unresolved=0),
    )
    high = tuple(_metrics_variant(i, candidates=2, unresolved=1) for i in (1, 2, 3))

    assert next_producer_concurrency(4, low).proposed == 5
    assert next_producer_concurrency(4, mid).proposed == 4
    assert next_producer_concurrency(4, high).proposed == 3
    assert next_producer_concurrency(6, low).proposed == 6
    assert next_producer_concurrency(2, high).proposed == 2


def test_evidence_window_is_order_independent_and_policy_mismatch_holds() -> None:
    window = tuple(_metrics_variant(i, candidates=2, unresolved=0) for i in (1, 2, 3))
    left = next_producer_concurrency(4, window)
    right = next_producer_concurrency(4, tuple(reversed(window)))
    assert left == right
    assert left.evidence_finalization_hashes == tuple(sorted(m.finalization_hash for m in window))

    mismatch = (window[0], dataclasses.replace(window[1], federation_policy_hash="4" * 64), window[2])
    decision = next_producer_concurrency(4, mismatch)
    assert decision.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert decision.reason == "POLICY_HASH_MISMATCH"


def test_three_epochs_with_too_few_candidates_still_hold() -> None:
    window = (
        _metrics_variant(1, candidates=1, unresolved=0),
        _metrics_variant(2, candidates=2, unresolved=0),
        _metrics_variant(3, candidates=2, unresolved=0),
    )
    decision = next_producer_concurrency(4, window)
    assert decision.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert decision.reason == "MIN_TOTAL_CANDIDATES"


def test_conflicting_duplicate_finalization_identity_fails_closed() -> None:
    import pytest

    first = _metrics_variant(1, candidates=2, unresolved=0)
    conflicting = dataclasses.replace(first, candidate_count=3)
    with pytest.raises(ValueError, match="FEDERATION_ADAPTATION_NONDETERMINISTIC"):
        next_producer_concurrency(4, (first, conflicting))


def test_finalized_metrics_attribute_candidates_and_reviews_to_role_profiles() -> None:
    metrics = metrics_from_finalization(_finalization(_sample_cut()))
    observations = {
        (row.slot_id, row.role_profile_hash): (row.candidate_count, row.review_count)
        for row in metrics.role_observations
    }
    assert observations[("C2", "a" * 64)] == (1, 0)
    assert observations[("C4", "b" * 64)] == (1, 0)
    assert observations[("C6", "6" * 64)] == (0, 1)


def _slot_evidence(parent_hash: str):
    base = metrics_from_finalization(_finalization(_sample_cut()))
    rows = []
    for index in (1, 2, 3):
        observations = tuple(
            dataclasses.replace(row, role_profile_hash=parent_hash) if row.slot_id == "C2" else row
            for row in base.role_observations
        )
        participants = tuple(
            (slot, parent_hash if slot == "C2" else profile_hash)
            for slot, profile_hash in base.participants
        )
        rows.append(dataclasses.replace(
            base,
            finalization_hash=f"{index:x}" * 64,
            recovery_cut_hash=f"{(index + 8):x}" * 64,
            epoch_id=f"role-epoch-{index}",
            participants=participants,
            role_observations=observations,
        ))
    return tuple(rows)


def test_shadow_role_proposal_preserves_hard_genome_and_existing_identity_sets() -> None:
    parent = load_role_genome(Path(__file__).resolve().parents[2], SlotId.C2)
    proposal = propose_soft_role_genome(
        parent=parent,
        evidence_window=_slot_evidence(parent.profile_hash),
        changes={"concurrency_preference": 5},
    )
    assert proposal.status == "SHADOW_PROPOSAL_READY"
    assert proposal.hard == parent.hard
    assert proposal.parent_role_profile_hash == parent.profile_hash
    assert proposal.proposed_role_profile_hash != parent.profile_hash
    assert proposal.soft.concurrency_preference == 5


def test_shadow_role_proposal_rejects_new_capability_identity() -> None:
    import pytest

    parent = load_role_genome(Path(__file__).resolve().parents[2], SlotId.C2)
    with pytest.raises(ValueError, match="FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN"):
        propose_soft_role_genome(
            parent=parent,
            evidence_window=_slot_evidence(parent.profile_hash),
            changes={"capability_weights": {"new-capability": 0.5}},
        )


def test_unobserved_soft_metric_holds_without_changing_profile() -> None:
    parent = load_role_genome(Path(__file__).resolve().parents[2], SlotId.C2)
    proposal = propose_soft_role_genome(
        parent=parent,
        evidence_window=_slot_evidence(parent.profile_hash),
        changes={"capability_weights": {"coding": 0.8}},
    )
    assert proposal.status == "HOLD_UNOBSERVED_METRIC"
    assert proposal.proposed_role_profile_hash == parent.profile_hash
    assert proposal.soft == parent.soft


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"provider_priors": {"new-provider": 0.5}}, "FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN"),
        ({"preferred_workers": ["opencode", "new-worker"]}, "FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN"),
        ({"preferred_task_classes": ["python-core", "new-task-class"]}, "FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN"),
        ({"review_pairings": ["C6", "C7"]}, "FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN"),
        ({"hard": {"role": "ARCHITECTURE"}}, "FEDERATION_ADAPTATION_UNKNOWN_SOFT_KEY"),
        ({"concurrency_preference": 7}, "FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS"),
    ],
)
def test_shadow_role_proposal_fails_closed_on_new_identity_unknown_key_or_bounds(changes, error) -> None:
    parent = load_role_genome(Path(__file__).resolve().parents[2], SlotId.C2)
    with pytest.raises(ValueError, match=error):
        propose_soft_role_genome(parent=parent, evidence_window=_slot_evidence(parent.profile_hash), changes=changes)


def test_shadow_role_proposal_holds_when_role_evidence_is_too_small() -> None:
    parent = load_role_genome(Path(__file__).resolve().parents[2], SlotId.C2)
    proposal = propose_soft_role_genome(
        parent=parent,
        evidence_window=_slot_evidence(parent.profile_hash)[:1],
        changes={"concurrency_preference": 5},
    )
    assert proposal.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert proposal.reason == "MIN_ROLE_FINALIZED_EPOCHS"
    assert proposal.proposed_role_profile_hash == parent.profile_hash


def test_pure_adaptation_module_has_no_persistence_dependency() -> None:
    source = (Path(__file__).resolve().parents[2] / "metaengine/devfabric/federation/adaptation.py").read_text()
    assert "SupabaseFederationAdapter" not in source
    assert "supabase_federation" not in source
    assert "store." not in source


def test_receipt_hash_is_order_independent_and_runtime_independent() -> None:
    window = tuple(_metrics_variant(i, candidates=2, unresolved=0) for i in (1, 2, 3))
    left = build_adaptation_receipt(
        metrics_window=window,
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    right = build_adaptation_receipt(
        metrics_window=tuple(reversed(window)),
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    assert left == right
    assert left.status == "SHADOW_PROPOSAL_READY"
    assert "implementation_commit" not in repr(left)
    assert "branch" not in repr(left).lower()


def test_adaptation_input_hash_changes_only_for_explicit_model_inputs() -> None:
    window = tuple(_metrics_variant(i, candidates=2, unresolved=0) for i in (1, 2, 3))
    first = build_adaptation_receipt(
        metrics_window=window,
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    second = build_adaptation_receipt(
        metrics_window=window,
        current_policy_hash="4" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    assert first.adaptation_input_hash != second.adaptation_input_hash


def test_shadow_receipt_replay_detects_tampering() -> None:
    window = tuple(_metrics_variant(i, candidates=2, unresolved=0) for i in (1, 2, 3))
    receipt = build_adaptation_receipt(
        metrics_window=window,
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    assert verify_shadow_receipt(
        receipt,
        metrics_window=window,
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    ) == "SHADOW_REPLAY_PASS"

    tampered = dataclasses.replace(receipt, adaptation_receipt_hash="f" * 64)
    with pytest.raises(ValueError, match="FEDERATION_ADAPTATION_RECEIPT_HASH_MISMATCH"):
        verify_shadow_receipt(
            tampered,
            metrics_window=window,
            current_policy_hash="3" * 64,
            current_producer_concurrency=4,
            role_proposals=(),
            telemetry_schema_hash="a" * 64,
        )


def test_single_finalized_epoch_receipt_is_hold_not_mutation() -> None:
    metrics = metrics_from_finalization(_finalization(_sample_cut()))
    receipt = build_adaptation_receipt(
        metrics_window=(metrics,),
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    assert receipt.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert receipt.concurrency_decision.current == receipt.concurrency_decision.proposed == 4
