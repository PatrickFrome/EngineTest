from dataclasses import replace
from pathlib import Path

from metaengine.devfabric.development_gate import (
    DevelopmentTransitionRequest,
    verify_development_transition,
)
from metaengine.devfabric.development_review import (
    DevelopmentAlternative,
    DevelopmentAlternativeKind,
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewDecision,
    load_bootstrap_review_context,
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


def _context():
    return load_bootstrap_review_context(Path(__file__).resolve().parents[2])


def _receipt(context, decision=DevelopmentReviewDecision.ACCEPT_CONTINUE):
    return DevelopmentEvolutionReviewReceipt.create(
        completed_step_id="S0",
        completed_step_commit="1" * 40,
        completed_step_evidence_hashes=("2" * 64,),
        constitution_hash=context.constitution.snapshot_hash,
        architecture_library_snapshot_hash=context.architecture_library.snapshot_hash,
        policy_snapshot_hash=context.policy.snapshot_hash,
        relevant_mechanism_ids=("CONTENT_ADDRESSED_GATE",),
        alternatives_considered=_alternatives(),
        decision=decision,
        rationale="Current transition checker is minimal and fail closed.",
        complexity_delta="SMALL_BOUNDED",
        capability_hypothesis="Prevents an unreviewed next development step.",
        required_followup_experiment="NONE",
        constitutional_findings=("NO_CONSTITUTIONAL_CONFLICT",),
        library_findings=("CONTENT_ADDRESSED_GATE_REUSED",),
        policy_findings=("NO_POLICY_MUTATION",),
    )


def _request(context, receipt, *, previous_commit="1" * 40):
    return DevelopmentTransitionRequest(
        previous_step_id="S0",
        previous_step_commit=previous_commit,
        next_step_id="S1",
        current_context=context,
        receipt=receipt,
    )


def test_next_step_without_receipt_is_blocked():
    context = _context()
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="S0",
            previous_step_commit="1" * 40,
            next_step_id="S1",
            current_context=context,
            receipt=None,
        )
    )
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_RECEIPT_REQUIRED"


def test_stale_completed_step_commit_is_blocked():
    context = _context()
    result = verify_development_transition(_request(context, _receipt(context), previous_commit="9" * 40))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_COMPLETED_STEP_MISMATCH"


def test_stale_review_context_is_blocked():
    context = _context()
    receipt = _receipt(context)
    stale = replace(context, policy=replace(context.policy, snapshot_hash="f" * 64))
    result = verify_development_transition(_request(stale, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_POLICY_SNAPSHOT_STALE"


def test_blocking_decision_cannot_advance():
    context = _context()
    receipt = _receipt(context, DevelopmentReviewDecision.BLOCK_CONSTITUTIONAL_CONFLICT)
    result = verify_development_transition(_request(context, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_DECISION_BLOCKS_NEXT_STEP"


def test_valid_accept_continue_allows_exact_requested_transition():
    context = _context()
    receipt = _receipt(context)
    result = verify_development_transition(_request(context, receipt))
    assert result.allowed is True
    assert result.reason == "DEVELOPMENT_REVIEW_TRANSITION_ALLOWED"
    assert result.next_step_id == "S1"


def test_tampered_receipt_is_blocked():
    context = _context()
    receipt = replace(_receipt(context), rationale="tampered")
    result = verify_development_transition(_request(context, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_RECEIPT_HASH_MISMATCH"


def test_stale_constitution_snapshot_is_blocked():
    context = _context()
    receipt = _receipt(context)
    stale = replace(context, constitution=replace(context.constitution, snapshot_hash="e" * 64))
    result = verify_development_transition(_request(stale, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_CONSTITUTION_SNAPSHOT_STALE"


def test_stale_library_snapshot_is_blocked():
    context = _context()
    receipt = _receipt(context)
    stale = replace(context, architecture_library=replace(context.architecture_library, snapshot_hash="d" * 64))
    result = verify_development_transition(_request(stale, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_LIBRARY_SNAPSHOT_STALE"
