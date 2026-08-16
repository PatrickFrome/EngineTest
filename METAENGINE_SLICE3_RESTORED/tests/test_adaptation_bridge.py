"""METAENGINE Step E — Adaptation pipeline activation tests.

Tests that the adaptation receipt builder (with D6-G1 guard) is activated
after an orchestrator run. The adaptation bridge converts orchestrator
run metrics into FinalizedEpochMetrics and builds an AdaptationReceipt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaengine.adaptation_bridge import (
    AdaptationBridge,
    build_metrics_from_run,
    AdaptationBridgeResult,
)


CONSTITUTION_HASH = "1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d"
POLICY_HASH = "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"


@pytest.fixture
def run_result():
    """Simulate an orchestrator run result with epistemic_coordination."""
    return {
        "meta_run_id": "meta23-test-0001",
        "input_hash": "a" * 64,
        "status": "COMPLETE_WITH_REFERENCE_SIMULATIONS",
        "telemetry_hash": "b" * 64,
        "claim_ceiling": "NATIVE_CLAIM_CEILINGS_PRESERVED",
        "fusion": {
            "epistemic_coordination": {
                "architecture_policy_hash": POLICY_HASH,
                "deep_engine_executions": 12,
                "derived_truth_promotion_violations": 0,
                "majority_vote_used": False,
            },
            "complete_engines": ["engine_01", "engine_02"],
            "failed_engines": [],
        },
    }


# ---------------------------------------------------------------------------
# 1. build_metrics_from_run: converts orchestrator output to FinalizedEpochMetrics
# ---------------------------------------------------------------------------


def test_build_metrics_from_run_produces_metrics(run_result):
    """The bridge must convert orchestrator run output to FinalizedEpochMetrics."""
    metrics = build_metrics_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert metrics is not None
    assert metrics.finalization_hash
    assert metrics.federation_policy_hash == POLICY_HASH
    assert metrics.task_count >= 1
    assert metrics.candidate_count >= 0


# ---------------------------------------------------------------------------
# 2. AdaptationBridge builds a receipt from metrics
# ---------------------------------------------------------------------------


def test_bridge_builds_receipt(run_result):
    """The bridge must build an AdaptationReceipt from run metrics."""
    bridge = AdaptationBridge()
    result = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert isinstance(result, AdaptationBridgeResult)
    assert result.adaptation_receipt_hash
    assert result.status  # must have a status (SHADOW_PROPOSAL_READY or HOLD_*)
    assert result.d6_g1_guard_passed is True  # guard must pass for shadow-only


# ---------------------------------------------------------------------------
# 3. D6-G1 guard is called during receipt building
# ---------------------------------------------------------------------------


def test_d6_g1_guard_passed(run_result):
    """The D6-G1 guard must pass (status is shadow-only, not canonical)."""
    bridge = AdaptationBridge()
    result = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert result.d6_g1_guard_passed is True
    assert result.status in ("SHADOW_PROPOSAL_READY", "HOLD_INSUFFICIENT_EVIDENCE", "HOLD_UNOBSERVED_METRIC")


# ---------------------------------------------------------------------------
# 4. Adaptation receipt is content-addressed
# ---------------------------------------------------------------------------


def test_receipt_hash_deterministic(run_result):
    """Same run → same adaptation receipt hash."""
    bridge = AdaptationBridge()
    r1 = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    r2 = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert r1.adaptation_receipt_hash == r2.adaptation_receipt_hash


# ---------------------------------------------------------------------------
# 5. truth_effect and assimilation_effect are NONE
# ---------------------------------------------------------------------------


def test_truth_and_assimilation_none(run_result):
    """The adaptation receipt must have truth_effect=NONE and assimilation_effect=NONE."""
    bridge = AdaptationBridge()
    result = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert result.truth_effect == "NONE"
    assert result.assimilation_effect == "NONE"


# ---------------------------------------------------------------------------
# 6. AdaptationBridgeResult serializes to dict
# ---------------------------------------------------------------------------


def test_result_to_dict(run_result):
    """AdaptationBridgeResult must serialize to dict for persistence."""
    bridge = AdaptationBridge()
    result = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    d = result.to_dict()
    assert "adaptation_receipt_hash" in d
    assert "status" in d
    assert "d6_g1_guard_passed" in d
    assert "truth_effect" in d
    assert "assimilation_effect" in d
    assert d["d6_g1_guard_passed"] is True


# ---------------------------------------------------------------------------
# 7. Full bridge round-trip with real orchestrator run
# ---------------------------------------------------------------------------


def test_bridge_with_real_run():
    """Test with the actual run output from Task 28 (if available)."""
    run_path = Path("/tmp/me_run/META_RUN.json")
    if not run_path.is_file():
        pytest.skip("real run output not available")
    run_result = json.loads(run_path.read_text())
    bridge = AdaptationBridge()
    result = bridge.build_adaptation_from_run(run_result, constitution_hash=CONSTITUTION_HASH)
    assert result.d6_g1_guard_passed is True
    assert result.truth_effect == "NONE"
