"""METAENGINE Step E — Adaptation pipeline activation.

Bridges orchestrator run output to the adaptation receipt builder (with
D6-G1 guard). After each orchestrator run, this bridge:

1. Converts run metrics (epistemic_coordination, engine results, telemetry)
   into FinalizedEpochMetrics.
2. Calls build_adaptation_receipt() with the metrics.
3. The D6-G1 guard (instrumented in Step 4/Task 31) is automatically called
   inside build_adaptation_receipt — it raises if the receipt status is
   canonical-activation (not shadow-only).

This activates the adaptation subsystem (3938 LOC) for runtime use, closing
the "Adaptation ↔ Orchestrator" integration gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .devfabric.federation.adaptation import (
    AdaptationReceipt,
    FinalizedEpochMetrics,
    build_adaptation_receipt,
    assert_d6_g1_shadow_only,
)
from .devfabric.codec import canonical_digest
from .util import canonical_hash


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdaptationBridgeResult:
    """Result of building an adaptation receipt from an orchestrator run."""
    adaptation_receipt_hash: str
    status: str
    d6_g1_guard_passed: bool
    truth_effect: str
    assimilation_effect: str
    adaptation_input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adaptation_receipt_hash": self.adaptation_receipt_hash,
            "status": self.status,
            "d6_g1_guard_passed": self.d6_g1_guard_passed,
            "truth_effect": self.truth_effect,
            "assimilation_effect": self.assimilation_effect,
            "adaptation_input_hash": self.adaptation_input_hash,
        }


# ---------------------------------------------------------------------------
# Build FinalizedEpochMetrics from orchestrator run
# ---------------------------------------------------------------------------


def build_metrics_from_run(
    run_result: Mapping[str, Any],
    *,
    constitution_hash: str,
) -> FinalizedEpochMetrics:
    """Convert orchestrator run output into FinalizedEpochMetrics.

    The orchestrator produces an epistemic_coordination dict with metrics
    like deep_engine_executions, architecture_mutations, etc. We map these
    to the federation adaptation metrics.
    """
    fusion = run_result.get("fusion", {})
    coord = fusion.get("epistemic_coordination", {})
    policy_hash = coord.get("architecture_policy_hash", "0" * 64)
    telemetry_hash = run_result.get("telemetry_hash", "0" * 64)

    # Build a minimal but valid FinalizedEpochMetrics from run output.
    # The run is a single "epoch" from the adaptation perspective.
    metrics = FinalizedEpochMetrics(
        finalization_hash=telemetry_hash,  # telemetry hash serves as finalization
        recovery_cut_hash=telemetry_hash,  # same (single-run, no multi-epoch cut)
        epoch_id=run_result.get("meta_run_id", "unknown"),
        federation_policy_hash=policy_hash,
        producer_concurrency=coord.get("deep_engine_executions", 0),
        task_count=1,  # one orchestration task per run
        candidate_count=coord.get("deep_engine_executions", 0),
        eligible_candidate_count=len(fusion.get("complete_engines", [])),
        rejected_candidate_count=len(fusion.get("failed_engines", [])),
        stale_candidate_count=0,
        review_count=0,
        review_pass_count=0,
        review_fail_count=0,
        review_inconclusive_count=0,
        conflict_count=0,
        unresolved_conflict_count=0,
        include_count=len(fusion.get("complete_engines", [])),
        exclude_count=len(fusion.get("failed_engines", [])),
        stale_decision_count=0,
        integrated_candidate_count=len(fusion.get("complete_engines", [])),
        participants=(),
        role_observations=(),
    )
    return metrics


# ---------------------------------------------------------------------------
# AdaptationBridge
# ---------------------------------------------------------------------------


class AdaptationBridge:
    """Builds an adaptation receipt from an orchestrator run.

    The D6-G1 guard is automatically called inside build_adaptation_receipt
    (instrumented in Step 4 / Task 31). If the receipt status is canonical-
    activation (not shadow-only), the guard raises before the receipt is
    returned.
    """

    def build_adaptation_from_run(
        self,
        run_result: Mapping[str, Any],
        *,
        constitution_hash: str,
    ) -> AdaptationBridgeResult:
        """Build an AdaptationReceipt from orchestrator run metrics.

        Raises ValueError if the D6-G1 guard fails (should never happen for
        shadow-only receipts, but the guard is the safety net).
        """
        metrics = build_metrics_from_run(run_result, constitution_hash=constitution_hash)

        fusion = run_result.get("fusion", {})
        coord = fusion.get("epistemic_coordination", {})
        policy_hash = coord.get("architecture_policy_hash", "0" * 64)
        telemetry_hash = run_result.get("telemetry_hash", "0" * 64)

        receipt = build_adaptation_receipt(
            metrics_window=(metrics,),
            current_policy_hash=policy_hash,
            current_producer_concurrency=max(2, min(6, coord.get("deep_engine_executions", 4))),
            role_proposals=(),
            telemetry_schema_hash=telemetry_hash,
        )

        # The guard is already called inside build_adaptation_receipt (Step 4).
        # We also call it explicitly here for defense-in-depth.
        assert_d6_g1_shadow_only(receipt)

        return AdaptationBridgeResult(
            adaptation_receipt_hash=receipt.adaptation_receipt_hash,
            status=receipt.status,
            d6_g1_guard_passed=True,  # if we reach here, the guard passed
            truth_effect="NONE",
            assimilation_effect="NONE",
            adaptation_input_hash=receipt.adaptation_input_hash,
        )
