import json
from dataclasses import replace
from pathlib import Path

from metaengine.devfabric.development_gate import (
    DevelopmentTransitionRequest,
    verify_development_transition,
)
from metaengine.devfabric.development_review import (
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewDecision,
    load_bootstrap_review_context,
    verify_receipt_integrity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = (
    PROJECT_ROOT
    / "devfabric"
    / "artifacts"
    / "reviews"
    / "development"
    / "metaengine-1-slice-1-review.json"
)


def _load_receipt() -> DevelopmentEvolutionReviewReceipt:
    return DevelopmentEvolutionReviewReceipt.from_dict(json.loads(RECEIPT_PATH.read_text()))


def _bound_context(receipt: DevelopmentEvolutionReviewReceipt):
    current = load_bootstrap_review_context(PROJECT_ROOT)
    return replace(
        current,
        constitution=replace(current.constitution, snapshot_hash=receipt.constitution_hash),
        architecture_library=replace(
            current.architecture_library,
            snapshot_hash=receipt.architecture_library_snapshot_hash,
        ),
        policy=replace(current.policy, snapshot_hash=receipt.policy_snapshot_hash),
    )


def _request(receipt: DevelopmentEvolutionReviewReceipt, context=None):
    context = context or _bound_context(receipt)
    return DevelopmentTransitionRequest(
        previous_step_id="METAENGINE-1-SLICE-1",
        previous_step_commit=receipt.completed_step_commit,
        next_step_id="METAENGINE-1-SLICE-2",
        current_context=context,
        receipt=receipt,
    )


def test_slice1_review_receipt_admits_exact_slice2_transition():
    assert RECEIPT_PATH.is_file()
    receipt = _load_receipt()
    assert verify_receipt_integrity(receipt).valid is True
    result = verify_development_transition(_request(receipt))
    assert result.allowed is True
    assert result.reason == "DEVELOPMENT_REVIEW_TRANSITION_ALLOWED"


def test_slice1_review_is_blocked_by_constitution_snapshot_drift():
    receipt = _load_receipt()
    context = _bound_context(receipt)
    stale = replace(context, constitution=replace(context.constitution, snapshot_hash="f" * 64))
    result = verify_development_transition(_request(receipt, stale))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_CONSTITUTION_SNAPSHOT_STALE"




def test_slice1_historical_receipt_is_stale_against_current_review_context():
    receipt = _load_receipt()
    current = load_bootstrap_review_context(PROJECT_ROOT)
    assert receipt.constitution_hash != current.constitution.snapshot_hash
    assert receipt.architecture_library_snapshot_hash != current.architecture_library.snapshot_hash
    assert receipt.policy_snapshot_hash != current.policy.snapshot_hash
    result = verify_development_transition(_request(receipt, current))
    assert result.allowed is False
    assert result.reason in {
        "DEVELOPMENT_REVIEW_CONSTITUTION_SNAPSHOT_STALE",
        "DEVELOPMENT_REVIEW_LIBRARY_SNAPSHOT_STALE",
        "DEVELOPMENT_REVIEW_POLICY_SNAPSHOT_STALE",
    }


def test_slice1_blocking_decision_cannot_admit_slice2():
    receipt = _load_receipt()
    fields = receipt.creation_fields()
    fields["decision"] = DevelopmentReviewDecision.REVISE_BEFORE_CONTINUE
    blocked = DevelopmentEvolutionReviewReceipt.create(**fields)
    result = verify_development_transition(_request(blocked))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_DECISION_BLOCKS_NEXT_STEP"
