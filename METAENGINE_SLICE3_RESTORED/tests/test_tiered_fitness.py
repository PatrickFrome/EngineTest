"""Tests for Phase 67 Step 2 — Three-Tier Fitness Adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.tiered_fitness import (
    ThreeTierFitnessAdapter,
    TieredFitnessResult,
    FitnessTier,
    TIER_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    return ThreeTierFitnessAdapter(
        root=ROOT,
        l2_budget=2,
        l0_threshold=0.3,
        l1_threshold=0.5,
        cache_size=10,
    )


@pytest.fixture
def good_theta():
    """Theta that should pass L0 and L1, reaching L2."""
    return {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}


@pytest.fixture
def bad_theta():
    """Theta that should fail L0."""
    return {"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 2.0}


# ---------------------------------------------------------------------------
# Tests: FitnessTier enum
# ---------------------------------------------------------------------------


class TestFitnessTier:
    def test_values(self):
        assert FitnessTier.L0_SURROGATE.value == "L0_SURROGATE"
        assert FitnessTier.L1_CONSTITUTION.value == "L1_CONSTITUTION"
        assert FitnessTier.L2_REAL_LLM.value == "L2_REAL_LLM"


# ---------------------------------------------------------------------------
# Tests: TieredFitnessResult
# ---------------------------------------------------------------------------


class TestResult:
    def test_payload(self):
        r = TieredFitnessResult(
            theta={"x": 1.0}, fitness=0.8, tier=FitnessTier.L2_REAL_LLM,
            l0_score=0.7, l1_score=0.9, l2_score=0.8,
            cached=False, elapsed_ms=5000.0, result_hash="abc",
        )
        p = r.payload()
        assert p["tier_version"] == TIER_VERSION
        assert p["fitness"] == 0.8
        assert p["tier"] == "L2_REAL_LLM"
        assert p["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: L0 Surrogate
# ---------------------------------------------------------------------------


class TestL0Surrogate:
    def test_good_theta_scores_high(self, adapter, good_theta):
        score = adapter._evaluate_l0(good_theta)
        assert score > 0.6

    def test_bad_theta_scores_low(self, adapter, bad_theta):
        score = adapter._evaluate_l0(bad_theta)
        assert score < 0.4

    def test_l0_deterministic(self, adapter, good_theta):
        s1 = adapter._evaluate_l0(good_theta)
        s2 = adapter._evaluate_l0(good_theta)
        assert s1 == s2

    def test_l0_in_range(self, adapter):
        thetas = [
            {"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 2.0},
            {"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.15, "temperature": 0.4},
            {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.30, "temperature": 1.0},
        ]
        for t in thetas:
            score = adapter._evaluate_l0(t)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Tests: L1 Constitution
# ---------------------------------------------------------------------------


class TestL1Constitution:
    def test_valid_theta_scores_high(self, adapter, good_theta):
        score = adapter._evaluate_l1(good_theta)
        assert score >= 0.9

    def test_out_of_bounds_scores_lower(self, adapter):
        score = adapter._evaluate_l1({"max_rounds": 100, "exploration_rate": 1.0, "temperature": 5.0})
        assert score < 0.5

    def test_high_temperature_reduces_score(self, adapter):
        low_temp = adapter._evaluate_l1({"temperature": 0.4, "max_rounds": 4, "exploration_rate": 0.15})
        high_temp = adapter._evaluate_l1({"temperature": 1.8, "max_rounds": 4, "exploration_rate": 0.15})
        assert high_temp < low_temp


# ---------------------------------------------------------------------------
# Tests: L2 Real LLM
# ---------------------------------------------------------------------------


class TestL2RealLLM:
    def test_l2_with_mock_correct(self, adapter, good_theta):
        """Mock LLM returns correct answer (391)."""
        mock_response = {
            "choices": [{"message": {"content": "The answer is 391. This output is generative-only until externally verified."}}]
        }
        # R2.4: Force the math task (17*23=391) so the test is deterministic
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()
            score, fell_back, metadata = adapter._evaluate_l2(good_theta)
        assert score >= 0.7  # R2.1: correct + disclaimer (0.1 + 0.6 + 0.2 = 0.9, or 0.7 if not verified)
        assert fell_back is False  # real L2, not fallback
        assert metadata["correct"] is True

    def test_l2_with_mock_wrong(self, adapter, good_theta):
        mock_response = {
            "choices": [{"message": {"content": "The answer is 400."}}]
        }
        # R2.4: Force the math task (17*23=391) so "400" is wrong
        with patch("metaengine.tiered_fitness.random.choice", return_value=adapter.L2_TASKS[0]), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode()
            score, fell_back, metadata = adapter._evaluate_l2(good_theta)
        assert score <= 0.3  # R2.1: wrong answer → max 0.3 (0.1 base, no disclaimer)
        assert fell_back is False  # real L2, just wrong answer
        assert metadata["correct"] is False

    def test_l2_error_falls_back_to_l0(self, adapter, good_theta):
        with patch("urllib.request.urlopen", side_effect=Exception("bridge down")):
            score, fell_back, metadata = adapter._evaluate_l2(good_theta)
        # Should fall back to L0 score
        l0 = adapter._evaluate_l0(good_theta)
        assert abs(score - l0) < 0.01
        assert fell_back is True  # flagged as fallback


# ---------------------------------------------------------------------------
# Tests: Tiered evaluation
# ---------------------------------------------------------------------------


class TestTieredEvaluation:
    def test_good_theta_reaches_l1(self, adapter, good_theta):
        result = adapter.evaluate(good_theta)
        assert result.tier in [FitnessTier.L1_CONSTITUTION, FitnessTier.L2_REAL_LLM]

    def test_bad_theta_stays_l0(self, adapter, bad_theta):
        result = adapter.evaluate(bad_theta)
        assert result.tier == FitnessTier.L0_SURROGATE

    def test_caching_works(self, adapter, good_theta):
        r1 = adapter.evaluate(good_theta)
        assert r1.cached is False
        r2 = adapter.evaluate(good_theta)
        assert r2.cached is True
        assert r1.result_hash == r2.result_hash

    def test_l2_budget_enforced(self, adapter, good_theta):
        """L2 budget limits real LLM calls."""
        adapter.l2_budget = 1
        adapter.start_generation()

        # First call should use L2
        r1 = adapter.evaluate(good_theta)
        # If bridge is available, this should be L2
        # If not, it will be L1 (acceptable for test)

        # Second call with different theta should NOT use L2 (budget exhausted)
        theta2 = {"max_rounds": 5, "max_deep_engines": 10, "exploration_rate": 0.15, "temperature": 0.4}
        r2 = adapter.evaluate(theta2)
        # Should be L1 (not L2) because budget is exhausted
        assert r2.tier != FitnessTier.L2_REAL_LLM or r2.cached

    def test_start_generation_resets_budget(self, adapter, good_theta):
        adapter.l2_budget = 1
        adapter.start_generation()
        assert adapter._l2_calls_this_gen == 0

    def test_fitness_in_range(self, adapter, good_theta, bad_theta):
        thetas = [good_theta, bad_theta]
        for t in thetas:
            result = adapter.evaluate(t)
            assert 0.0 <= result.fitness <= 1.0

    def test_result_has_hash(self, adapter, good_theta):
        result = adapter.evaluate(good_theta)
        assert result.result_hash != ""

    def test_result_deterministic(self, adapter, good_theta):
        adapter.cache_size = 50  # enable cache
        r1 = adapter.evaluate(good_theta)
        r2 = adapter.evaluate(good_theta)
        # L0 and L1 are deterministic; cached result should match
        assert r1.l0_score == r2.l0_score
        assert r1.l1_score == r2.l1_score


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, adapter):
        s = adapter.summary()
        assert s["tier_version"] == TIER_VERSION
        assert "l2_budget" in s
        assert "tier_distribution" in s
        assert s["truth_effect"] == "NONE"

    def test_summary_constitution(self, adapter):
        s = adapter.summary()
        assert s["constitution_compliance"]["no_truth_promotion"] is True
        assert s["constitution_compliance"]["budget_enforced"] is True

    def test_summary_after_evaluations(self, adapter, good_theta, bad_theta):
        adapter.evaluate(good_theta)
        adapter.evaluate(bad_theta)
        s = adapter.summary()
        assert s["cache_size"] >= 1


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_no_truth_promotion(self, adapter):
        assert not hasattr(adapter, "promote")

    def test_no_code_modification(self, adapter):
        assert not hasattr(adapter, "modify_code")

    def test_all_results_evaluative(self, adapter, good_theta):
        result = adapter.evaluate(good_theta)
        assert result.payload()["truth_effect"] == "NONE"
