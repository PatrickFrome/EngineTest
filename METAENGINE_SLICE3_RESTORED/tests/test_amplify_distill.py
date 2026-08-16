"""Tests for Phase 52 — Amplify+Distill Cycle (IDA)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.amplify_distill import (
    AmplifyDistillCycle,
    AmplificationResult,
    DistillationResult,
    IDA_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cycle():
    return AmplifyDistillCycle(improvement_threshold=0.01, max_config_change=0.3, seed=42)


@pytest.fixture
def low_metrics():
    """Metrics that should trigger amplification changes."""
    return {
        "rlaif_reward": 0.3,  # < 0.4 → increase temperature
        "pbt_best_fitness": 0.5,  # < 0.7 → increase exploration_rate
        "faithfulness_mean": 0.3,  # < 0.5 → increase provenance weight
        "redteam_violation_rate": 0.2,  # > 0 → increase no_truth weight
        "es_converged": False,  # → increase sigma
        "marl_foe_mean": 0.01,  # < 0.05 → increase exploit fraction
        "transfer_rate": 0.1,  # < 0.3 → increase max_rounds
    }


@pytest.fixture
def good_metrics():
    """Metrics that should NOT trigger amplification changes."""
    return {
        "rlaif_reward": 0.6,
        "pbt_best_fitness": 0.85,
        "faithfulness_mean": 0.7,
        "redteam_violation_rate": 0.0,
        "es_converged": True,
        "marl_foe_mean": 0.1,
        "transfer_rate": 0.5,
    }


# ---------------------------------------------------------------------------
# Tests: AmplificationResult
# ---------------------------------------------------------------------------


class TestAmplificationResult:
    def test_payload_has_required_fields(self):
        r = AmplificationResult(
            generation=1,
            config_changes={"temperature": {"old": 0.4, "new": 0.48}},
            rationale="test",
            amplified_config={"temperature": 0.48},
            amplification_hash="abc",
        )
        p = r.payload()
        assert p["ida_version"] == IDA_VERSION
        assert p["generation"] == 1
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = AmplificationResult(
            generation=0, config_changes={}, rationale="",
            amplified_config={}, amplification_hash="abc123",
        )
        d = r.as_dict()
        assert d["amplification_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: DistillationResult
# ---------------------------------------------------------------------------


class TestDistillationResult:
    def test_payload_has_required_fields(self):
        r = DistillationResult(
            generation=1,
            improved_trainers=["rlaif"],
            key_insights=["RLAIF improved"],
            distilled_config={"temperature": 0.4},
            distillation_hash="abc",
        )
        p = r.payload()
        assert p["ida_version"] == IDA_VERSION
        assert "rlaif" in p["improved_trainers"]
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = DistillationResult(
            generation=0, improved_trainers=[], key_insights=[],
            distilled_config={}, distillation_hash="abc123",
        )
        d = r.as_dict()
        assert d["distillation_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Amplify
# ---------------------------------------------------------------------------


class TestAmplify:
    def test_amplify_returns_result(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics, generation=1)
        assert isinstance(result, AmplificationResult)
        assert result.generation == 1
        assert result.amplification_hash != ""

    def test_amplify_low_rlaif_increases_temperature(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "llm_temperature" in result.config_changes
        old = result.config_changes["llm_temperature"]["old"]
        new = result.config_changes["llm_temperature"]["new"]
        assert new > old  # increased

    def test_amplify_low_pbt_increases_exploration(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "exploration_rate" in result.config_changes
        assert result.config_changes["exploration_rate"]["new"] > result.config_changes["exploration_rate"]["old"]

    def test_amplify_low_faithfulness_increases_provenance(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "rlaif_weight_provenance" in result.config_changes

    def test_amplify_violations_increase_no_truth_weight(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "rlaif_weight_no_truth" in result.config_changes

    def test_amplify_es_not_converged_increases_sigma(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "es_sigma" in result.config_changes

    def test_amplify_low_marl_increases_exploit_fraction(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "pbt_exploit_fraction" in result.config_changes

    def test_amplify_low_transfer_increases_rounds(self, cycle, low_metrics):
        result = cycle.amplify(low_metrics)
        assert "max_rounds" in result.config_changes

    def test_amplify_good_metrics_no_changes(self, cycle, good_metrics):
        result = cycle.amplify(good_metrics)
        assert len(result.config_changes) == 0
        assert "No changes" in result.rationale

    def test_amplify_uses_previous_config(self, cycle):
        prev_config = {"llm_temperature": 0.8, "max_rounds": 6, "transfer_rate": 0.5}
        result = cycle.amplify(
            {"rlaif_reward": 0.3, "transfer_rate": 0.5},  # triggers temperature change only
            previous_config=prev_config,
        )
        # Should start from previous config
        assert result.amplified_config["max_rounds"] == 6

    def test_amplify_clamps_temperature(self, cycle):
        """Temperature should not exceed 2.0."""
        result = cycle.amplify(
            {"rlaif_reward": 0.1},
            previous_config={"llm_temperature": 1.9},
        )
        assert result.amplified_config["llm_temperature"] <= 2.0

    def test_amplify_clamps_exploration_rate(self, cycle):
        """Exploration rate should not exceed 0.30."""
        result = cycle.amplify(
            {"pbt_best_fitness": 0.1},
            previous_config={"exploration_rate": 0.28},
        )
        assert result.amplified_config["exploration_rate"] <= 0.30

    def test_amplify_added_to_history(self, cycle, low_metrics):
        cycle.amplify(low_metrics)
        assert len(cycle.amplifications) == 1

    def test_amplify_deterministic(self, cycle, low_metrics):
        r1 = cycle.amplify(low_metrics)
        cycle.amplifications.clear()
        r2 = cycle.amplify(low_metrics)
        assert r1.amplification_hash == r2.amplification_hash


# ---------------------------------------------------------------------------
# Tests: Distill
# ---------------------------------------------------------------------------


class TestDistill:
    def test_distill_returns_result(self, cycle, good_metrics):
        result = cycle.distill(
            campaign_result={"metrics": good_metrics},
            gen_metrics=good_metrics,
            generation=0,
        )
        assert isinstance(result, DistillationResult)
        assert result.distillation_hash != ""

    def test_distill_detects_improvements(self, cycle):
        prev = {"rlaif_reward": 0.3, "pbt_best_fitness": 0.5}
        curr = {"rlaif_reward": 0.5, "pbt_best_fitness": 0.7}
        result = cycle.distill(
            campaign_result={},
            gen_metrics=curr,
            previous_metrics=prev,
        )
        assert "rlaif_reward" in result.improved_trainers
        assert "pbt_best_fitness" in result.improved_trainers

    def test_distill_detects_decreases(self, cycle):
        prev = {"rlaif_reward": 0.7}
        curr = {"rlaif_reward": 0.3}
        result = cycle.distill(
            campaign_result={},
            gen_metrics=curr,
            previous_metrics=prev,
        )
        assert any("decreased" in insight for insight in result.key_insights)

    def test_distill_no_previous_no_comparison(self, cycle, good_metrics):
        """First generation has no previous → no comparison."""
        result = cycle.distill(
            campaign_result={},
            gen_metrics=good_metrics,
            previous_metrics=None,
        )
        assert len(result.improved_trainers) == 0

    def test_distill_convergence_detected(self, cycle):
        """No improvements → convergence note."""
        prev = {"rlaif_reward": 0.5}
        curr = {"rlaif_reward": 0.5}  # same
        result = cycle.distill(
            campaign_result={},
            gen_metrics=curr,
            previous_metrics=prev,
        )
        assert any("converging" in insight.lower() for insight in result.key_insights)

    def test_distill_added_to_history(self, cycle, good_metrics):
        cycle.distill(campaign_result={}, gen_metrics=good_metrics)
        assert len(cycle.distillations) == 1


# ---------------------------------------------------------------------------
# Tests: Full IDA cycle
# ---------------------------------------------------------------------------


class TestFullCycle:
    def test_run_cycle_returns_both(self, cycle, low_metrics):
        amplification, distillation = cycle.run_cycle(
            gen_metrics=low_metrics,
            previous_config=None,
            generation=0,
        )
        assert isinstance(amplification, AmplificationResult)
        assert isinstance(distillation, DistillationResult)

    def test_run_cycle_with_previous(self, cycle, low_metrics, good_metrics):
        """Amplify from G0 (low) → distill comparing G1 (good) vs G0 (low)."""
        amplification, distillation = cycle.run_cycle(
            gen_metrics=good_metrics,
            previous_metrics=low_metrics,
            previous_config=cycle.DEFAULT_CONFIG,
            generation=1,
        )
        assert amplification.generation == 1
        assert len(distillation.improved_trainers) > 0  # good > low → improvements


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self, cycle):
        s = cycle.summary()
        assert s["amplifications_run"] == 0
        assert s["distillations_run"] == 0
        assert s["truth_effect"] == "NONE"

    def test_summary_after_cycles(self, cycle, low_metrics, good_metrics):
        cycle.run_cycle(low_metrics, generation=0)
        cycle.run_cycle(good_metrics, previous_metrics=low_metrics, generation=1)
        s = cycle.summary()
        assert s["amplifications_run"] == 2
        assert s["distillations_run"] == 2
        assert len(s["amplifications"]) == 2
        assert len(s["distillations"]) == 2

    def test_summary_constitution_compliance(self, cycle, low_metrics):
        cycle.amplify(low_metrics)
        s = cycle.summary()
        assert s["constitution_compliance"]["amplify_is_configuration"] is True
        assert s["constitution_compliance"]["distill_is_insight"] is True
        assert s["constitution_compliance"]["no_code_modification"] is True


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_amplify_is_configuration_not_code(self, cycle, low_metrics):
        """Amplification changes configuration, not code."""
        result = cycle.amplify(low_metrics)
        # Config changes are parameter adjustments, not code modifications
        for key in result.config_changes:
            assert key in [
                "llm_temperature", "exploration_rate", "rlaif_weight_provenance",
                "rlaif_weight_no_truth", "es_sigma", "pbt_exploit_fraction", "max_rounds",
            ]

    def test_distill_is_insight_not_truth(self, cycle, good_metrics):
        """Distillation produces insights, not truth claims."""
        result = cycle.distill(
            campaign_result={},
            gen_metrics=good_metrics,
            generation=0,
        )
        assert result.payload()["truth_effect"] == "NONE"
        assert "INSIGHT" in result.payload()["claim_ceiling"]

    def test_no_auto_promotion(self, cycle):
        assert not hasattr(cycle, "promote")
        assert not hasattr(cycle, "auto_promote")

    def test_no_code_modification(self, cycle):
        assert not hasattr(cycle, "modify_code")
        assert not hasattr(cycle, "execute_code")
