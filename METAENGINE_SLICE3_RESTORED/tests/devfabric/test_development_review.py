from dataclasses import replace

import pytest

from metaengine.devfabric.development_review import (
    DevelopmentAlternative,
    DevelopmentAlternativeKind,
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewDecision,
    verify_receipt_integrity,
)


def _alternatives():
    return tuple(
        DevelopmentAlternative(
            kind=kind,
            summary=f"{kind.value}-summary",
            evidence_hashes=("a" * 64,),
        )
        for kind in DevelopmentAlternativeKind
    )


def _receipt(decision=DevelopmentReviewDecision.ACCEPT_CONTINUE):
    return DevelopmentEvolutionReviewReceipt.create(
        completed_step_id="METAENGINE-1-SLICE-0-TASK-1",
        completed_step_commit="1" * 40,
        completed_step_evidence_hashes=("2" * 64,),
        constitution_hash="3" * 64,
        architecture_library_snapshot_hash="4" * 64,
        policy_snapshot_hash="5" * 64,
        relevant_mechanism_ids=("LEGACY_GUARDRAILS",),
        alternatives_considered=_alternatives(),
        decision=decision,
        rationale="Current design is the minimal deterministic bootstrap gate.",
        complexity_delta="SMALL_BOUNDED",
        capability_hypothesis="Prevents ungated architectural drift between committed steps.",
        required_followup_experiment="NONE",
        constitutional_findings=("NO_K0_CONFLICT_OBSERVED",),
        library_findings=("BOOTSTRAP_LIBRARY_REVIEWED",),
        policy_findings=("NO_POLICY_AUTHORITY_EXPANSION",),
    )


def test_receipt_hash_is_deterministic_and_integrity_verifies():
    left = _receipt()
    right = _receipt()
    assert left.receipt_hash == right.receipt_hash
    assert verify_receipt_integrity(left).valid is True


def test_next_step_allowed_is_derived_from_decision():
    assert _receipt(DevelopmentReviewDecision.ACCEPT_CONTINUE).next_step_allowed is True
    assert _receipt(DevelopmentReviewDecision.ACCEPT_WITH_FOLLOWUP_EXPERIMENT).next_step_allowed is True
    assert _receipt(DevelopmentReviewDecision.REVISE_BEFORE_CONTINUE).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.REVERT_BEFORE_CONTINUE).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.DEFER_EXPERIMENT_REQUIRED).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.BLOCK_CONSTITUTIONAL_CONFLICT).next_step_allowed is False


def test_receipt_tamper_is_detected():
    receipt = _receipt()
    tampered = replace(receipt, rationale="tampered")
    result = verify_receipt_integrity(tampered)
    assert result.valid is False
    assert result.reason == "DEVELOPMENT_REVIEW_RECEIPT_HASH_MISMATCH"


def test_receipt_requires_all_review_domains_and_alternative_kinds():
    fields = _receipt().creation_fields()
    fields["alternatives_considered"] = (
        DevelopmentAlternative(
            kind=DevelopmentAlternativeKind.CURRENT,
            summary="only current",
            evidence_hashes=("a" * 64,),
        ),
    )
    with pytest.raises(ValueError, match="DEVELOPMENT_REVIEW_ALTERNATIVES_INCOMPLETE"):
        DevelopmentEvolutionReviewReceipt.create(**fields)

from pathlib import Path

from metaengine.devfabric.development_review import load_bootstrap_review_context, snapshot_paths


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parents[2]


def test_snapshot_paths_is_order_independent(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    left = snapshot_paths(tmp_path, ("b.txt", "a.txt"))
    right = snapshot_paths(tmp_path, ("a.txt", "b.txt"))
    assert left.snapshot_hash == right.snapshot_hash
    assert tuple(row["path"] for row in left.files) == ("a.txt", "b.txt")


def test_snapshot_detects_content_change(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    before = snapshot_paths(tmp_path, ("a.txt",))
    (tmp_path / "a.txt").write_text("B")
    after = snapshot_paths(tmp_path, ("a.txt",))
    assert before.snapshot_hash != after.snapshot_hash


def test_bootstrap_context_binds_all_three_review_domains(project_root):
    context = load_bootstrap_review_context(project_root)
    assert len(context.constitution.files) >= 3
    assert len(context.architecture_library.files) >= 2
    assert len(context.policy.files) >= 2
    assert all(
        len(value.snapshot_hash) == 64
        for value in (context.constitution, context.architecture_library, context.policy)
    )
