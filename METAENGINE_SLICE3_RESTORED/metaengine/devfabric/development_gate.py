from __future__ import annotations

from dataclasses import dataclass

from .development_review import (
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewContext,
    verify_receipt_integrity,
)


@dataclass(frozen=True)
class DevelopmentTransitionRequest:
    previous_step_id: str
    previous_step_commit: str
    next_step_id: str
    current_context: DevelopmentReviewContext
    receipt: DevelopmentEvolutionReviewReceipt | None


@dataclass(frozen=True)
class DevelopmentTransitionResult:
    allowed: bool
    reason: str
    previous_step_id: str
    next_step_id: str
    receipt_hash: str | None


def _result(
    request: DevelopmentTransitionRequest,
    *,
    allowed: bool,
    reason: str,
) -> DevelopmentTransitionResult:
    return DevelopmentTransitionResult(
        allowed=allowed,
        reason=reason,
        previous_step_id=request.previous_step_id,
        next_step_id=request.next_step_id,
        receipt_hash=request.receipt.receipt_hash if request.receipt is not None else None,
    )


def verify_development_transition(request: DevelopmentTransitionRequest) -> DevelopmentTransitionResult:
    if request.receipt is None:
        return _result(request, allowed=False, reason="DEVELOPMENT_REVIEW_RECEIPT_REQUIRED")

    integrity = verify_receipt_integrity(request.receipt)
    if not integrity.valid:
        return _result(request, allowed=False, reason=integrity.reason)

    if (
        request.receipt.completed_step_id != request.previous_step_id
        or request.receipt.completed_step_commit != request.previous_step_commit
    ):
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_COMPLETED_STEP_MISMATCH",
        )

    context = request.current_context
    if request.receipt.constitution_hash != context.constitution.snapshot_hash:
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_CONSTITUTION_SNAPSHOT_STALE",
        )
    if request.receipt.architecture_library_snapshot_hash != context.architecture_library.snapshot_hash:
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_LIBRARY_SNAPSHOT_STALE",
        )
    if request.receipt.policy_snapshot_hash != context.policy.snapshot_hash:
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_POLICY_SNAPSHOT_STALE",
        )

    if not request.receipt.next_step_allowed:
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_DECISION_BLOCKS_NEXT_STEP",
        )
    if not str(request.previous_step_id).strip() or not str(request.next_step_id).strip():
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_TRANSITION_ID_REQUIRED",
        )
    if request.previous_step_id == request.next_step_id:
        return _result(
            request,
            allowed=False,
            reason="DEVELOPMENT_REVIEW_SELF_TRANSITION_FORBIDDEN",
        )

    return _result(
        request,
        allowed=True,
        reason="DEVELOPMENT_REVIEW_TRANSITION_ALLOWED",
    )
