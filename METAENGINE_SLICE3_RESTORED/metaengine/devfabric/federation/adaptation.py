from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from metaengine.devfabric.codec import canonical_digest, to_primitive

from .finalization import EpochFinalization
from .roles import HardRoleGenome, RoleGenome, SoftRoleGenome
from .types import SlotId

ADAPTATION_PROTOCOL_VERSION = "D6.ADAPTATION.1"


@dataclass(frozen=True)
class RationalRate:
    numerator: int
    denominator: int

    @property
    def value(self) -> float:
        return self.numerator / self.denominator


@dataclass(frozen=True)
class RoleObservation:
    slot_id: str
    role_profile_hash: str
    candidate_count: int
    review_count: int

    @property
    def total_count(self) -> int:
        return self.candidate_count + self.review_count


@dataclass(frozen=True)
class FinalizedEpochMetrics:
    finalization_hash: str
    recovery_cut_hash: str
    epoch_id: str
    federation_policy_hash: str
    producer_concurrency: int
    task_count: int
    candidate_count: int
    eligible_candidate_count: int
    rejected_candidate_count: int
    stale_candidate_count: int
    review_count: int
    review_pass_count: int
    review_fail_count: int
    review_inconclusive_count: int
    conflict_count: int
    unresolved_conflict_count: int
    include_count: int
    exclude_count: int
    stale_decision_count: int
    integrated_candidate_count: int
    participants: tuple[tuple[str, str], ...]
    role_observations: tuple[RoleObservation, ...]

    @property
    def conflict_rate(self) -> RationalRate:
        denominator = max(self.candidate_count, 1)
        return RationalRate(min(self.unresolved_conflict_count, denominator), denominator)

    @property
    def verification_pass_rate(self) -> RationalRate:
        return RationalRate(self.review_pass_count, max(self.review_count, 1))

    @property
    def integration_rate(self) -> RationalRate:
        return RationalRate(self.integrated_candidate_count, max(self.candidate_count, 1))

    @property
    def stale_rate(self) -> RationalRate:
        return RationalRate(self.stale_candidate_count, max(self.candidate_count, 1))


def metrics_from_finalization(finalization: EpochFinalization) -> FinalizedEpochMetrics:
    if not isinstance(finalization, EpochFinalization):
        raise ValueError("FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED")
    cut = finalization.recovery_cut
    epoch = cut["epoch"]
    terminal = cut["terminal_snapshot"]["snapshot"]
    reviews = cut["reviews"]
    conflicts = cut["conflicts"]
    decisions = cut["integration_decisions"]
    task_by_hash = {str(row["task_hash"]): row for row in cut["tasks"]}
    attribution: dict[tuple[str, str], list[int]] = {}
    for candidate in cut["candidates"]:
        task = task_by_hash.get(str(candidate.get("task_hash")))
        if task is None:
            raise ValueError("FEDERATION_ADAPTATION_ROLE_ATTRIBUTION_INVALID")
        key = (str(task["owner_slot"]), str(candidate["role_profile_hash"]))
        counts = attribution.setdefault(key, [0, 0])
        counts[0] += 1
    for review in reviews:
        key = (str(review["reviewer_slot"]), str(review["reviewer_role_profile_hash"]))
        counts = attribution.setdefault(key, [0, 0])
        counts[1] += 1

    return FinalizedEpochMetrics(
        finalization_hash=finalization.finalization_hash,
        recovery_cut_hash=finalization.recovery_cut_hash,
        epoch_id=finalization.epoch_id,
        federation_policy_hash=str(epoch["federation_policy_hash"]),
        producer_concurrency=int(epoch["producer_concurrency"]),
        task_count=len(cut["tasks"]),
        candidate_count=len(cut["candidates"]),
        eligible_candidate_count=len(terminal["eligible_candidates"]),
        rejected_candidate_count=len(terminal["rejected_candidates"]),
        stale_candidate_count=len(terminal["stale_candidates"]),
        review_count=len(reviews),
        review_pass_count=sum(str(row.get("verdict")) == "PASS" for row in reviews),
        review_fail_count=sum(str(row.get("verdict")) == "FAIL" for row in reviews),
        review_inconclusive_count=sum(str(row.get("verdict")) == "INCONCLUSIVE" for row in reviews),
        conflict_count=len(conflicts),
        unresolved_conflict_count=sum(not bool(row.get("resolved")) for row in conflicts),
        include_count=sum(str(row.get("decision")) == "INCLUDE" for row in decisions),
        exclude_count=sum(str(row.get("decision")) == "EXCLUDE" for row in decisions),
        stale_decision_count=sum(str(row.get("decision")) == "STALE" for row in decisions),
        integrated_candidate_count=len(terminal["integration_order"]),
        participants=tuple(
            sorted(
                (str(row["slot_id"]), str(row["role_profile_hash"]))
                for row in cut["participant_witnesses"]
            )
        ),
        role_observations=tuple(
            RoleObservation(slot_id=slot, role_profile_hash=profile_hash, candidate_count=counts[0], review_count=counts[1])
            for (slot, profile_hash), counts in sorted(attribution.items())
        ),
    )


@dataclass(frozen=True)
class EvidenceSufficiency:
    sufficient: bool
    distinct_finalized_epochs: int
    total_candidates: int
    federation_policy_hash: str | None
    reason: str


@dataclass(frozen=True)
class ConcurrencyDecision:
    status: str
    current: int
    proposed: int
    conflict_numerator: int
    conflict_denominator: int
    evidence_finalization_hashes: tuple[str, ...]
    reason: str


def _normalize_metrics_window(
    metrics_window: tuple[FinalizedEpochMetrics, ...],
) -> tuple[FinalizedEpochMetrics, ...]:
    by_hash: dict[str, FinalizedEpochMetrics] = {}
    for metrics in metrics_window:
        existing = by_hash.get(metrics.finalization_hash)
        if existing is not None and existing != metrics:
            raise ValueError("FEDERATION_ADAPTATION_NONDETERMINISTIC")
        by_hash[metrics.finalization_hash] = metrics
    return tuple(by_hash[key] for key in sorted(by_hash))


def evaluate_concurrency_evidence(
    metrics_window: tuple[FinalizedEpochMetrics, ...],
) -> EvidenceSufficiency:
    normalized = _normalize_metrics_window(metrics_window)
    epoch_ids = {metrics.epoch_id for metrics in normalized}
    total_candidates = sum(metrics.candidate_count for metrics in normalized)
    policies = {metrics.federation_policy_hash for metrics in normalized}
    policy_hash = next(iter(policies)) if len(policies) == 1 else None

    if len(epoch_ids) < 3:
        return EvidenceSufficiency(False, len(epoch_ids), total_candidates, policy_hash, "MIN_FINALIZED_EPOCHS")
    if total_candidates < 6:
        return EvidenceSufficiency(False, len(epoch_ids), total_candidates, policy_hash, "MIN_TOTAL_CANDIDATES")
    if len(policies) != 1:
        return EvidenceSufficiency(False, len(epoch_ids), total_candidates, None, "POLICY_HASH_MISMATCH")
    return EvidenceSufficiency(True, len(epoch_ids), total_candidates, policy_hash, "SUFFICIENT")


def next_producer_concurrency(
    current: int,
    metrics_window: tuple[FinalizedEpochMetrics, ...],
) -> ConcurrencyDecision:
    if not 2 <= int(current) <= 6:
        raise ValueError("FEDERATION_ADAPTATION_CONCURRENCY_OUT_OF_BOUNDS")
    normalized = _normalize_metrics_window(metrics_window)
    evidence_hashes = tuple(metrics.finalization_hash for metrics in normalized)
    sufficiency = evaluate_concurrency_evidence(normalized)
    numerator = sum(metrics.unresolved_conflict_count for metrics in normalized)
    denominator = max(sum(metrics.candidate_count for metrics in normalized), 1)

    if not sufficiency.sufficient:
        return ConcurrencyDecision(
            status="HOLD_INSUFFICIENT_EVIDENCE",
            current=int(current),
            proposed=int(current),
            conflict_numerator=numerator,
            conflict_denominator=denominator,
            evidence_finalization_hashes=evidence_hashes,
            reason=sufficiency.reason,
        )

    if 10 * numerator < denominator:
        proposed = min(int(current) + 1, 6)
        reason = "LOW_CONFLICT_RATE"
    elif 4 * numerator <= denominator:
        proposed = int(current)
        reason = "CONFLICT_BUDGET_HOLD"
    else:
        proposed = max(int(current) - 1, 2)
        reason = "HIGH_CONFLICT_RATE"

    return ConcurrencyDecision(
        status="SHADOW_PROPOSAL_READY",
        current=int(current),
        proposed=proposed,
        conflict_numerator=numerator,
        conflict_denominator=denominator,
        evidence_finalization_hashes=evidence_hashes,
        reason=reason,
    )


@dataclass(frozen=True)
class ShadowRoleGenomeProposal:
    parent_role_profile_hash: str
    proposed_role_profile_hash: str
    hard: HardRoleGenome
    soft: SoftRoleGenome
    status: str
    reason: str


def _validate_soft_change_identities(parent: RoleGenome, changes: Mapping[str, object]) -> None:
    allowed = {
        "capability_weights",
        "preferred_workers",
        "preferred_task_classes",
        "review_pairings",
        "exploration_weight",
        "concurrency_preference",
        "provider_priors",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError("FEDERATION_ADAPTATION_UNKNOWN_SOFT_KEY")

    for field in ("capability_weights", "provider_priors"):
        if field not in changes:
            continue
        raw = changes[field]
        if not isinstance(raw, Mapping):
            raise ValueError("FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS")
        parent_ids = {key for key, _ in getattr(parent.soft, field)}
        if not set(map(str, raw)) <= parent_ids:
            raise ValueError("FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN")

    sequence_fields = ("preferred_workers", "preferred_task_classes")
    for field in sequence_fields:
        if field not in changes:
            continue
        raw = changes[field]
        if isinstance(raw, (str, bytes)):
            raise ValueError("FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS")
        values = tuple(str(value) for value in raw)  # type: ignore[arg-type]
        if not set(values) <= set(getattr(parent.soft, field)):
            raise ValueError("FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN")

    if "review_pairings" in changes:
        raw = changes["review_pairings"]
        if isinstance(raw, (str, bytes)):
            raise ValueError("FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS")
        try:
            values = tuple(value if isinstance(value, SlotId) else SlotId(str(value)) for value in raw)  # type: ignore[arg-type]
        except ValueError as exc:
            raise ValueError("FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN") from exc
        if not set(values) <= set(parent.soft.review_pairings):
            raise ValueError("FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN")


def _role_evidence_counts(
    parent: RoleGenome, evidence_window: tuple[FinalizedEpochMetrics, ...]
) -> tuple[int, int]:
    normalized = _normalize_metrics_window(evidence_window)
    slot_id = parent.hard.slot.value
    profile_hash = parent.profile_hash
    witnessed_epochs = 0
    attributable = 0
    for metrics in normalized:
        if (slot_id, profile_hash) not in metrics.participants:
            continue
        witnessed_epochs += 1
        attributable += sum(
            observation.total_count
            for observation in metrics.role_observations
            if observation.slot_id == slot_id and observation.role_profile_hash == profile_hash
        )
    return witnessed_epochs, attributable


def propose_soft_role_genome(
    *,
    parent: RoleGenome,
    evidence_window: tuple[FinalizedEpochMetrics, ...],
    changes: Mapping[str, object],
) -> ShadowRoleGenomeProposal:
    _validate_soft_change_identities(parent, changes)
    try:
        candidate = parent.with_soft_update(changes)
    except (TypeError, ValueError) as exc:
        raise ValueError("FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS") from exc
    if candidate.hard != parent.hard:
        raise ValueError("FEDERATION_ADAPTATION_HARD_GENOME_IMMUTABLE")

    witnessed_epochs, attributable = _role_evidence_counts(parent, evidence_window)
    if witnessed_epochs < 3:
        return ShadowRoleGenomeProposal(
            parent_role_profile_hash=parent.profile_hash,
            proposed_role_profile_hash=parent.profile_hash,
            hard=parent.hard,
            soft=parent.soft,
            status="HOLD_INSUFFICIENT_EVIDENCE",
            reason="MIN_ROLE_FINALIZED_EPOCHS",
        )
    if attributable < 3:
        return ShadowRoleGenomeProposal(
            parent_role_profile_hash=parent.profile_hash,
            proposed_role_profile_hash=parent.profile_hash,
            hard=parent.hard,
            soft=parent.soft,
            status="HOLD_INSUFFICIENT_EVIDENCE",
            reason="MIN_ROLE_ATTRIBUTABLE_OBSERVATIONS",
        )

    unobserved = set(changes) - {"concurrency_preference"}
    if unobserved:
        return ShadowRoleGenomeProposal(
            parent_role_profile_hash=parent.profile_hash,
            proposed_role_profile_hash=parent.profile_hash,
            hard=parent.hard,
            soft=parent.soft,
            status="HOLD_UNOBSERVED_METRIC",
            reason="UNOBSERVED_SOFT_METRIC",
        )

    return ShadowRoleGenomeProposal(
        parent_role_profile_hash=parent.profile_hash,
        proposed_role_profile_hash=candidate.profile_hash,
        hard=candidate.hard,
        soft=candidate.soft,
        status="SHADOW_PROPOSAL_READY",
        reason="OBSERVABLE_CONCURRENCY_SIGNAL",
    )


@dataclass(frozen=True)
class AdaptationReceipt:
    protocol_version: str
    adaptation_input_hash: str
    adaptation_receipt_hash: str
    evidence_finalization_hashes: tuple[str, ...]
    evidence_recovery_cut_hashes: tuple[str, ...]
    evidence_metrics_hash: str
    current_policy_hash: str
    current_producer_concurrency: int
    concurrency_decision: ConcurrencyDecision
    role_proposals: tuple[ShadowRoleGenomeProposal, ...]
    telemetry_schema_hash: str
    status: str


def _normalized_role_proposals(
    role_proposals: tuple[ShadowRoleGenomeProposal, ...],
) -> tuple[ShadowRoleGenomeProposal, ...]:
    ordered = sorted(
        role_proposals,
        key=lambda proposal: (proposal.parent_role_profile_hash, proposal.proposed_role_profile_hash),
    )
    seen: dict[str, ShadowRoleGenomeProposal] = {}
    for proposal in ordered:
        existing = seen.get(proposal.parent_role_profile_hash)
        if existing is not None and existing != proposal:
            raise ValueError("FEDERATION_ADAPTATION_NONDETERMINISTIC")
        seen[proposal.parent_role_profile_hash] = proposal
    return tuple(seen[key] for key in sorted(seen))


def _adaptation_status(
    concurrency_decision: ConcurrencyDecision,
    role_proposals: tuple[ShadowRoleGenomeProposal, ...],
) -> str:
    ready = concurrency_decision.status == "SHADOW_PROPOSAL_READY" or any(
        proposal.status == "SHADOW_PROPOSAL_READY" for proposal in role_proposals
    )
    if ready:
        return "SHADOW_PROPOSAL_READY"
    if any(proposal.status == "HOLD_UNOBSERVED_METRIC" for proposal in role_proposals):
        return "HOLD_UNOBSERVED_METRIC"
    return "HOLD_INSUFFICIENT_EVIDENCE"


def build_adaptation_receipt(
    *,
    metrics_window: tuple[FinalizedEpochMetrics, ...],
    current_policy_hash: str,
    current_producer_concurrency: int,
    role_proposals: tuple[ShadowRoleGenomeProposal, ...],
    telemetry_schema_hash: str,
) -> AdaptationReceipt:
    normalized_metrics = _normalize_metrics_window(metrics_window)
    normalized_proposals = _normalized_role_proposals(role_proposals)
    concurrency_decision = next_producer_concurrency(current_producer_concurrency, normalized_metrics)
    evidence_finalization_hashes = tuple(metrics.finalization_hash for metrics in normalized_metrics)
    evidence_recovery_cut_hashes = tuple(metrics.recovery_cut_hash for metrics in normalized_metrics)
    evidence_metrics_hash = canonical_digest(tuple(to_primitive(metrics) for metrics in normalized_metrics))
    parent_role_profile_hashes = tuple(
        sorted(proposal.parent_role_profile_hash for proposal in normalized_proposals)
    )
    input_payload = {
        "protocol_version": ADAPTATION_PROTOCOL_VERSION,
        "evidence_finalization_hashes": evidence_finalization_hashes,
        "current_policy_hash": str(current_policy_hash),
        "current_producer_concurrency": int(current_producer_concurrency),
        "parent_role_profile_hashes": parent_role_profile_hashes,
    }
    adaptation_input_hash = canonical_digest(input_payload)
    status = _adaptation_status(concurrency_decision, normalized_proposals)
    receipt_payload = {
        "protocol_version": ADAPTATION_PROTOCOL_VERSION,
        "adaptation_input_hash": adaptation_input_hash,
        "evidence_finalization_hashes": evidence_finalization_hashes,
        "evidence_recovery_cut_hashes": evidence_recovery_cut_hashes,
        "evidence_metrics_hash": evidence_metrics_hash,
        "current_policy_hash": str(current_policy_hash),
        "current_producer_concurrency": int(current_producer_concurrency),
        "concurrency_decision": to_primitive(concurrency_decision),
        "role_proposals": tuple(to_primitive(proposal) for proposal in normalized_proposals),
        "telemetry_schema_hash": str(telemetry_schema_hash),
        "status": status,
    }
    adaptation_receipt_hash = canonical_digest(receipt_payload)
    receipt = AdaptationReceipt(
        protocol_version=ADAPTATION_PROTOCOL_VERSION,
        adaptation_input_hash=adaptation_input_hash,
        adaptation_receipt_hash=adaptation_receipt_hash,
        evidence_finalization_hashes=evidence_finalization_hashes,
        evidence_recovery_cut_hashes=evidence_recovery_cut_hashes,
        evidence_metrics_hash=evidence_metrics_hash,
        current_policy_hash=str(current_policy_hash),
        current_producer_concurrency=int(current_producer_concurrency),
        concurrency_decision=concurrency_decision,
        role_proposals=normalized_proposals,
        telemetry_schema_hash=str(telemetry_schema_hash),
        status=status,
    )
    # Runtime D6-G1 guard: enforce shadow-only at build time. This makes it
    # impossible to create an AdaptationReceipt with a canonical-activation
    # status — the guard raises before the receipt can be returned.
    assert_d6_g1_shadow_only(receipt)
    return receipt


def verify_shadow_receipt(
    receipt: AdaptationReceipt,
    *,
    metrics_window: tuple[FinalizedEpochMetrics, ...],
    current_policy_hash: str,
    current_producer_concurrency: int,
    role_proposals: tuple[ShadowRoleGenomeProposal, ...],
    telemetry_schema_hash: str,
) -> str:
    rebuilt = build_adaptation_receipt(
        metrics_window=metrics_window,
        current_policy_hash=current_policy_hash,
        current_producer_concurrency=current_producer_concurrency,
        role_proposals=role_proposals,
        telemetry_schema_hash=telemetry_schema_hash,
    )
    if receipt != rebuilt:
        raise ValueError("FEDERATION_ADAPTATION_RECEIPT_HASH_MISMATCH")
    # Runtime D6-G1 guard on replay: verify the ORIGINAL receipt (not just the
    # rebuilt one) is also shadow-only. This catches tampered receipts that
    # were stored with a canonical-activation status.
    assert_d6_g1_shadow_only(receipt)
    return "SHADOW_REPLAY_PASS"


# ---------------------------------------------------------------------------
# D6-G1 shadow-only invariant (Boundary: D6-G1 remains shadow-only)
# ---------------------------------------------------------------------------

D6_G1_SHADOW_ONLY_STATUSES = frozenset(
    {
        "SHADOW_PROPOSAL_READY",
        "HOLD_UNOBSERVED_METRIC",
        "HOLD_INSUFFICIENT_EVIDENCE",
    }
)

# Statuses that would indicate canonical activation — FORBIDDEN by the D6-G1
# shadow-only boundary until a separately authorized gate explicitly permits
# promotion. If any adaptation receipt ever carries one of these statuses,
# the D6-G1 boundary has been violated.
D6_G1_FORBIDDEN_CANONICAL_STATUSES = frozenset(
    {
        "ACTIVE",
        "CANONICAL",
        "CANONICAL_ACTIVE",
        "PROMOTED",
        "CANONICAL_PROMOTION_READY",
    }
)


def assert_d6_g1_shadow_only(receipt: AdaptationReceipt) -> None:
    """Assert that a D6-G1 adaptation receipt remains shadow-only.

    D6-G1 is PASS_ADAPTATION_SHADOW_READY: adaptation evidence may be produced
    and shadow proposals may be readied, but NO canonical activation occurs.
    This guard enforces that the receipt status is one of the allowed
    shadow-only statuses and NOT a canonical-activation status.

    Raises ValueError if the receipt status indicates canonical activation
    (Boundary violation) or is an unknown status (defensive).
    """
    status = str(receipt.status)
    if status in D6_G1_FORBIDDEN_CANONICAL_STATUSES:
        raise ValueError(
            f"D6_G1_SHADOW_ONLY_VIOLATION: adaptation receipt status '{status}' "
            "indicates canonical activation, but D6-G1 is shadow-only. "
            "A separately authorized gate is required for any promotion."
        )
    if status not in D6_G1_SHADOW_ONLY_STATUSES:
        raise ValueError(
            f"D6_G1_UNKNOWN_ADAPTATION_STATUS: '{status}' is not a recognized "
            "shadow-only status. Allowed: "
            + ", ".join(sorted(D6_G1_SHADOW_ONLY_STATUSES))
        )
