import json
from dataclasses import replace
from pathlib import Path

from metaengine.devfabric.development_gate import (
    DevelopmentTransitionRequest,
    verify_development_transition,
)
from metaengine.devfabric.development_review import (
    ContentSnapshot,
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewContext,
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
    / "metaengine-1-slice-0-review.json"
)


def _load_receipt():
    return DevelopmentEvolutionReviewReceipt.from_dict(json.loads(RECEIPT_PATH.read_text()))


def _bound_context(receipt):
    current = load_bootstrap_review_context(PROJECT_ROOT)
    return DevelopmentReviewContext(
        review_context_version=current.review_context_version,
        constitution=ContentSnapshot(current.constitution.snapshot_version, (), receipt.constitution_hash),
        architecture_library=ContentSnapshot(current.architecture_library.snapshot_version, (), receipt.architecture_library_snapshot_hash),
        policy=ContentSnapshot(current.policy.snapshot_version, (), receipt.policy_snapshot_hash),
    )


def test_slice0_self_review_receipt_is_valid_historical_admission():
    assert RECEIPT_PATH.is_file()
    receipt = _load_receipt()
    assert verify_receipt_integrity(receipt).valid is True
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="METAENGINE-1-SLICE-0",
            previous_step_commit=receipt.completed_step_commit,
            next_step_id="METAENGINE-1-SLICE-1",
            current_context=_bound_context(receipt),
            receipt=receipt,
        )
    )
    assert result.allowed is True
    assert result.reason == "DEVELOPMENT_REVIEW_TRANSITION_ALLOWED"


def test_slice0_review_cannot_be_reused_after_constitution_changes():
    receipt = _load_receipt()
    current = load_bootstrap_review_context(PROJECT_ROOT)
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="METAENGINE-1-SLICE-0",
            previous_step_commit=receipt.completed_step_commit,
            next_step_id="METAENGINE-1-SLICE-1",
            current_context=current,
            receipt=receipt,
        )
    )
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_CONSTITUTION_SNAPSHOT_STALE"
