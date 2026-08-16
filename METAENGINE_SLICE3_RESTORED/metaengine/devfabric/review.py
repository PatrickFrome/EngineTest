from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .codec import canonical_digest
from .models import Verdict, VerificationReceipt


class ReviewRecommendation(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class AIReviewReceipt:
    review_hash: str
    candidate_hash: str
    reviewer_id: str
    recommendation: ReviewRecommendation
    confidence: float
    evidence_hashes: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        candidate_hash: str,
        reviewer_id: str,
        recommendation: ReviewRecommendation,
        confidence: float,
        evidence_hashes: Iterable[str] = (),
    ) -> "AIReviewReceipt":
        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        payload = {
            "candidate_hash": str(candidate_hash),
            "reviewer_id": str(reviewer_id),
            "recommendation": recommendation,
            "confidence": confidence,
            "evidence_hashes": tuple(sorted(str(x) for x in evidence_hashes)),
        }
        return cls(review_hash=canonical_digest(payload), **payload)


@dataclass(frozen=True)
class ReviewOutcome:
    eligible: bool
    reason: str
    review_hashes: tuple[str, ...]


def adjudicate_reviews(
    verification: VerificationReceipt,
    reviews: Iterable[AIReviewReceipt],
) -> ReviewOutcome:
    reviews = tuple(reviews)
    hashes = tuple(sorted(review.review_hash for review in reviews))

    if verification.verdict is Verdict.FAIL:
        return ReviewOutcome(False, "DETERMINISTIC_FAIL", hashes)
    if verification.verdict is not Verdict.PASS:
        return ReviewOutcome(False, "DETERMINISTIC_NOT_PASS", hashes)
    if any(review.candidate_hash != verification.candidate_hash for review in reviews):
        return ReviewOutcome(False, "REVIEW_CANDIDATE_MISMATCH", hashes)
    if any(review.recommendation is ReviewRecommendation.REJECT for review in reviews):
        return ReviewOutcome(False, "REVIEW_REJECT", hashes)
    return ReviewOutcome(True, "ELIGIBLE", hashes)
