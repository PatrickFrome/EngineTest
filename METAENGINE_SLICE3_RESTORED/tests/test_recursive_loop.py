"""Tests for Phase 43 — Recursive Self-Improvement Loop."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.recursive_loop import (
    RecursiveImprovementLoop,
    GenerationMetrics,
    ImprovementComparison,
    RECURSIVE_LOOP_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_campaign_result(
    rlaif=0.5, pbt=0.7, es=0.8, marl=0.3, az=5, rt=0
):
    """Create a mock campaign result with given metrics."""
    return {
        "shared_state_summary": {
            "rlaif_reward": rlaif,
            "pbt_best_fitness": pbt,
            "es_best_fitness": es,
            "marl_foe_mean_reward": marl,
            "alphazero_mechanisms_extracted": az,
            "redteam_total_violations": rt,
        }
    }


@pytest.fixture
def loop():
    return RecursiveImprovementLoop(convergence_threshold=0.01, max_generations=5)


# ---------------------------------------------------------------------------
# Tests: GenerationMetrics
# ---------------------------------------------------------------------------


class TestGenerationMetrics:
    """Test the GenerationMetrics dataclass."""

    def test_payload_has_required_fields(self):
        m = GenerationMetrics(
            generation=0,
            rlaif_reward=0.5,
            pbt_best_fitness=0.7,
            es_best_fitness=0.8,
            marl_foe_mean_reward=0.3,
            alphazero_mechanisms=5,
            redteam_violations=0,
            combined_score=0.65,
            metrics_hash="abc",
        )
        p = m.payload()
        assert p["generation"] == 0
        assert p["combined_score"] == 0.65
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        m = GenerationMetrics(
            generation=0,
            rlaif_reward=0.5,
            pbt_best_fitness=0.7,
            es_best_fitness=0.8,
            marl_foe_mean_reward=0.3,
            alphazero_mechanisms=5,
            redteam_violations=0,
            combined_score=0.65,
            metrics_hash="abc123",
        )
        d = m.as_dict()
        assert d["metrics_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: ImprovementComparison
# ---------------------------------------------------------------------------


class TestImprovementComparison:
    """Test the ImprovementComparison dataclass."""

    def test_payload_has_required_fields(self):
        m_a = GenerationMetrics(
            generation=0, rlaif_reward=0.5, pbt_best_fitness=0.7,
            es_best_fitness=0.8, marl_foe_mean_reward=0.3,
            alphazero_mechanisms=5, redteam_violations=0,
            combined_score=0.6,
        )
        m_b = GenerationMetrics(
            generation=1, rlaif_reward=0.6, pbt_best_fitness=0.8,
            es_best_fitness=0.85, marl_foe_mean_reward=0.4,
            alphazero_mechanisms=6, redteam_violations=0,
            combined_score=0.7,
        )
        comp = ImprovementComparison(
            generation_a=0, generation_b=1,
            metrics_a=m_a, metrics_b=m_b,
            improvement_ratio=0.7 / 0.6,
            improved=True,
            delta_scores={"combined_score": 0.1},
            comparison_hash="abc",
        )
        p = comp.payload()
        assert p["generation_a"] == 0
        assert p["generation_b"] == 1
        assert p["improved"] is True
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "IMPROVEMENT_COMPARISON_IS_EVALUATIVE_NOT_TRUTH"


# ---------------------------------------------------------------------------
# Tests: RecursiveImprovementLoop
# ---------------------------------------------------------------------------


class TestRecursiveImprovementLoop:
    """Test the recursive improvement loop."""

    def test_initializes_empty(self, loop):
        assert loop.generations == []
        assert loop.comparisons == []
        assert loop.converged is False

    def test_run_generation_extracts_metrics(self, loop):
        result = make_campaign_result(rlaif=0.6, pbt=0.8)
        metrics = loop.run_generation(result)
        assert metrics.generation == 0
        assert metrics.rlaif_reward == 0.6
        assert metrics.pbt_best_fitness == 0.8
        assert metrics.combined_score > 0
        assert metrics.metrics_hash != ""

    def test_run_generation_no_campaign_fn_raises(self):
        loop = RecursiveImprovementLoop(campaign_fn=None)
        with pytest.raises(ValueError, match="NO_CAMPAIGN_FUNCTION_PROVIDED"):
            loop.run_generation()

    def test_run_generation_uses_campaign_fn(self):
        call_count = [0]
        def mock_campaign():
            call_count[0] += 1
            return make_campaign_result(rlaif=0.5 + call_count[0] * 0.1)
        loop = RecursiveImprovementLoop(campaign_fn=mock_campaign)
        loop.run_generation()
        assert call_count[0] == 1

    def test_compare_first_generation_no_comparison(self, loop):
        loop.run_generation(make_campaign_result())
        assert len(loop.comparisons) == 0  # first gen has no previous

    def test_compare_second_generation_creates_comparison(self, loop):
        loop.run_generation(make_campaign_result(rlaif=0.5))
        loop.run_generation(make_campaign_result(rlaif=0.6))
        assert len(loop.comparisons) == 1
        comp = loop.comparisons[0]
        assert comp.generation_a == 0
        assert comp.generation_b == 1
        assert comp.improved is True  # 0.6 > 0.5

    def test_improvement_ratio_computed(self, loop):
        loop.run_generation(make_campaign_result(rlaif=0.5, pbt=0.7, es=0.8))
        loop.run_generation(make_campaign_result(rlaif=0.6, pbt=0.8, es=0.9))
        comp = loop.comparisons[0]
        assert comp.improvement_ratio > 1.0

    def test_no_improvement_detected(self, loop):
        loop.run_generation(make_campaign_result(rlaif=0.8, pbt=0.9, es=0.9))
        loop.run_generation(make_campaign_result(rlaif=0.5, pbt=0.6, es=0.7))
        comp = loop.comparisons[0]
        assert comp.improved is False
        assert comp.improvement_ratio < 1.0

    def test_delta_scores_computed(self, loop):
        loop.run_generation(make_campaign_result(rlaif=0.5, pbt=0.7))
        loop.run_generation(make_campaign_result(rlaif=0.6, pbt=0.8))
        comp = loop.comparisons[0]
        assert comp.delta_scores["rlaif_reward"] == pytest.approx(0.1, abs=0.001)
        assert comp.delta_scores["pbt_best_fitness"] == pytest.approx(0.1, abs=0.001)

    def test_convergence_detected(self, loop):
        # First gen: high score
        loop.run_generation(make_campaign_result(rlaif=0.9, pbt=0.9, es=0.9))
        # Second gen: barely different (within threshold)
        loop.run_generation(make_campaign_result(rlaif=0.9, pbt=0.9, es=0.91))
        # Should converge if improvement < 1%
        comp = loop.comparisons[-1]
        if comp.improvement_ratio < 1.0 + loop.convergence_threshold:
            assert loop.converged is True

    def test_no_convergence_with_significant_improvement(self, loop):
        loop.run_generation(make_campaign_result(rlaif=0.3, pbt=0.3, es=0.3))
        loop.run_generation(make_campaign_result(rlaif=0.9, pbt=0.9, es=0.9))
        assert loop.converged is False

    def test_run_multiple_generations(self, loop):
        results = [
            make_campaign_result(rlaif=0.3),
            make_campaign_result(rlaif=0.5),
            make_campaign_result(rlaif=0.7),
        ]
        summary = loop.run(campaign_results=results)
        assert summary["generations_run"] == 3
        assert len(loop.comparisons) == 2  # 3 gens → 2 comparisons

    def test_run_stops_on_convergence(self):
        loop = RecursiveImprovementLoop(convergence_threshold=0.5, max_generations=5)
        results = [
            make_campaign_result(rlaif=0.5),
            make_campaign_result(rlaif=0.51),  # barely improved
            make_campaign_result(rlaif=0.52),
        ]
        loop.run(campaign_results=results)
        # Should have converged early (improvement < threshold)
        assert loop.converged is True

    def test_combined_score_weights(self):
        loop = RecursiveImprovementLoop(
            score_weights={
                "rlaif_reward": 1.0,
                "pbt_best_fitness": 0.0,
                "es_best_fitness": 0.0,
                "marl_foe_mean_reward": 0.0,
                "alphazero_mechanisms": 0.0,
                "redteam_safety": 0.0,
            }
        )
        loop.run_generation(make_campaign_result(rlaif=0.8))
        # Combined score should equal rlaif_reward (weight=1.0, others=0)
        assert loop.generations[0].combined_score == pytest.approx(0.8, abs=0.01)

    def test_redteam_safety_in_score(self, loop):
        # 0 violations → safety = 1.0 (good)
        loop.run_generation(make_campaign_result(rt=0))
        score_safe = loop.generations[0].combined_score
        # 5 violations → safety = 0.5 (worse)
        loop2 = RecursiveImprovementLoop()
        loop2.run_generation(make_campaign_result(rt=5))
        score_unsafe = loop2.generations[0].combined_score
        assert score_safe > score_unsafe

    def test_alphazero_mechanisms_normalized(self, loop):
        # 10 mechanisms → normalized = 1.0 (max)
        loop.run_generation(make_campaign_result(az=10))
        # 5 mechanisms → normalized = 0.5
        loop2 = RecursiveImprovementLoop()
        loop2.run_generation(make_campaign_result(az=5))
        assert loop.generations[0].combined_score > loop2.generations[0].combined_score


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    """Test the summary function."""

    def test_empty_summary(self, loop):
        summary = loop.summary()
        assert summary["generations_run"] == 0
        assert summary["truth_effect"] == "NONE"

    def test_summary_after_generations(self, loop):
        results = [
            make_campaign_result(rlaif=0.5, pbt=0.7, es=0.8),
            make_campaign_result(rlaif=0.6, pbt=0.8, es=0.9),
        ]
        loop.run(campaign_results=results)
        summary = loop.summary()
        assert summary["generations_run"] == 2
        assert "first_combined_score" in summary
        assert "last_combined_score" in summary
        assert "total_improvement" in summary
        assert "total_improvement_ratio" in summary
        assert summary["total_improvement_ratio"] > 1.0

    def test_summary_constitution_compliance(self, loop):
        loop.run_generation(make_campaign_result())
        summary = loop.summary()
        assert summary["constitution_compliance"]["all_generations_shadow"] is True
        assert summary["constitution_compliance"]["no_auto_promotion"] is True
        assert summary["constitution_compliance"]["improvement_measured_not_assumed"] is True
        assert summary["constitution_compliance"]["no_code_modification"] is True

    def test_summary_claim_ceiling(self, loop):
        loop.run_generation(make_campaign_result())
        summary = loop.summary()
        assert summary["claim_ceiling"] == "RECURSIVE_LOOP_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"
        assert summary["truth_effect"] == "NONE"

    def test_summary_includes_generations(self, loop):
        loop.run(campaign_results=[make_campaign_result(), make_campaign_result()])
        summary = loop.summary()
        assert len(summary["generations"]) == 2
        assert len(summary["comparisons"]) == 1


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_metrics_same_hash(self):
        loop1 = RecursiveImprovementLoop()
        loop2 = RecursiveImprovementLoop()
        result = make_campaign_result(rlaif=0.5, pbt=0.7, es=0.8)
        m1 = loop1.run_generation(result)
        m2 = loop2.run_generation(result)
        assert m1.metrics_hash == m2.metrics_hash

    def test_same_comparison_same_hash(self):
        loop1 = RecursiveImprovementLoop()
        loop2 = RecursiveImprovementLoop()
        r1 = make_campaign_result(rlaif=0.5)
        r2 = make_campaign_result(rlaif=0.6)
        loop1.run_generation(r1)
        loop1.run_generation(r2)
        loop2.run_generation(r1)
        loop2.run_generation(r2)
        assert loop1.comparisons[0].comparison_hash == loop2.comparisons[0].comparison_hash


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that recursive loop preserves constitution."""

    def test_all_generations_are_shadow(self, loop):
        loop.run(campaign_results=[make_campaign_result(), make_campaign_result()])
        summary = loop.summary()
        assert summary["constitution_compliance"]["all_generations_shadow"] is True

    def test_no_auto_promotion(self, loop):
        loop.run_generation(make_campaign_result())
        summary = loop.summary()
        assert summary["constitution_compliance"]["no_auto_promotion"] is True

    def test_improvement_measured_not_assumed(self, loop):
        loop.run(campaign_results=[
            make_campaign_result(rlaif=0.5),
            make_campaign_result(rlaif=0.6),
        ])
        summary = loop.summary()
        assert summary["constitution_compliance"]["improvement_measured_not_assumed"] is True
        # Improvement ratio is computed from actual metrics, not assumed
        assert summary["total_improvement_ratio"] != 1.0

    def test_no_code_modification(self, loop):
        loop.run_generation(make_campaign_result())
        summary = loop.summary()
        assert summary["constitution_compliance"]["no_code_modification"] is True
