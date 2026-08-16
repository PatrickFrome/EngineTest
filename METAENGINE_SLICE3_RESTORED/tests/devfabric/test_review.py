from metaengine.devfabric.models import Verdict, VerificationReceipt
from metaengine.devfabric.review import AIReviewReceipt, ReviewRecommendation, adjudicate_reviews


def verification(verdict):
    return VerificationReceipt.create(
        candidate_hash='candidate-hash', verifier_id='deterministic', verifier_version='1',
        commands=('pytest',), exit_statuses=(0 if verdict is Verdict.PASS else 1,), verdict=verdict,
    )


def test_positive_ai_reviews_cannot_override_deterministic_fail():
    review=AIReviewReceipt.create(candidate_hash='candidate-hash',reviewer_id='critic-a',recommendation=ReviewRecommendation.APPROVE,confidence=1.0,evidence_hashes=('e1',))
    outcome=adjudicate_reviews(verification(Verdict.FAIL),(review,))
    assert outcome.eligible is False
    assert outcome.reason=='DETERMINISTIC_FAIL'


def test_negative_critic_can_block_deterministic_pass():
    review=AIReviewReceipt.create(candidate_hash='candidate-hash',reviewer_id='critic-b',recommendation=ReviewRecommendation.REJECT,confidence=0.8,evidence_hashes=('e2',))
    outcome=adjudicate_reviews(verification(Verdict.PASS),(review,))
    assert outcome.eligible is False
    assert outcome.reason=='REVIEW_REJECT'


def test_review_is_bound_to_candidate_hash():
    review=AIReviewReceipt.create(candidate_hash='other',reviewer_id='critic-c',recommendation=ReviewRecommendation.APPROVE,confidence=0.9)
    outcome=adjudicate_reviews(verification(Verdict.PASS),(review,))
    assert outcome.eligible is False
    assert outcome.reason=='REVIEW_CANDIDATE_MISMATCH'
