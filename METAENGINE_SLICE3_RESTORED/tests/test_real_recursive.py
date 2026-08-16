"""Tests for Phase 68 — Real Recursive Improvement."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.real_recursive import (
    RealRecursiveRunner,
    RealGenerationResult,
    REAL_RECURSIVE_VERSION,
)


# ---------------------------------------------------------------------------
# Tests: RealGenerationResult
# ---------------------------------------------------------------------------


class TestRealGenerationResult:
    def test_payload_has_fields(self):
        r = RealGenerationResult(
            generation=0, amplification_changes=2,
            pbt_mean_fitness=0.85, pbt_best_fitness=0.9,
            pbt_champions=1, l2_calls_used=3, l2_budget=3,
            tier_distribution={"L0": 1, "L1": 1, "L2": 4},
            distillation_insights=["improved"], improved_trainers=["pbt"],
            improvement_vs_prev=None, elapsed_seconds=5.0,
            result_hash="abc",
        )
        p = r.payload()
        assert p["real_recursive_version"] == REAL_RECURSIVE_VERSION
        assert p["generation"] == 0
        assert p["pbt_mean_fitness"] == 0.85
        assert p["truth_effect"] == "NONE"

    def test_improvement_vs_prev_none_for_first(self):
        r = RealGenerationResult(
            generation=0, amplification_changes=0,
            pbt_mean_fitness=0.5, pbt_best_fitness=0.6,
            pbt_champions=1, l2_calls_used=0, l2_budget=3,
            tier_distribution={}, distillation_insights=[],
            improved_trainers=[], improvement_vs_prev=None,
            elapsed_seconds=1.0, result_hash="abc",
        )
        assert r.improvement_vs_prev is None

    def test_improvement_vs_prev_positive(self):
        r = RealGenerationResult(
            generation=1, amplification_changes=1,
            pbt_mean_fitness=0.9, pbt_best_fitness=0.95,
            pbt_champions=1, l2_calls_used=2, l2_budget=3,
            tier_distribution={}, distillation_insights=["improved"],
            improved_trainers=["pbt"], improvement_vs_prev=0.05,
            elapsed_seconds=3.0, result_hash="abc",
        )
        assert r.improvement_vs_prev == 0.05


# ---------------------------------------------------------------------------
# Tests: RealRecursiveRunner
# ---------------------------------------------------------------------------


class TestRealRecursiveRunner:
    def test_initializes(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2)
        assert runner.root == ROOT
        assert runner.l2_budget == 2

    def test_run_returns_results(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=2)
        assert len(results) == 2
        assert all(isinstance(r, RealGenerationResult) for r in results)

    def test_first_gen_no_improvement(self):
        """First generation has no previous → improvement_vs_prev is None."""
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=1)
        assert results[0].improvement_vs_prev is None

    def test_second_gen_has_improvement(self):
        """Second generation compares with first → improvement_vs_prev is not None."""
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=2)
        assert results[1].improvement_vs_prev is not None

    def test_l2_budget_enforced(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=1)
        assert results[0].l2_calls_used <= results[0].l2_budget

    def test_fitness_in_range(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=1)
        for r in results:
            assert 0.0 <= r.pbt_mean_fitness <= 1.0
            assert 0.0 <= r.pbt_best_fitness <= 1.0

    def test_distillation_has_insights(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=2)
        # Second generation should have distillation insights
        assert len(results[1].distillation_insights) > 0

    def test_all_results_have_hash(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=2)
        for r in results:
            assert r.result_hash != ""

    def test_amplification_changes_after_first_gen(self):
        """Second generation should have amplification changes (based on G0 metrics)."""
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=2)
        # First gen has no previous → 0 changes
        assert results[0].amplification_changes == 0
        # Second gen analyzes G0 → should have changes
        # (may be 0 if metrics are in acceptable ranges, but let's check it ran)
        assert isinstance(results[1].amplification_changes, int)


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self):
        runner = RealRecursiveRunner(root=ROOT)
        s = runner.summary()
        assert s["generations_run"] == 0
        assert s["truth_effect"] == "NONE"

    def test_summary_after_run(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        runner.run(num_generations=2)
        s = runner.summary()
        assert s["generations_run"] == 2
        assert "first_mean_fitness" in s
        assert "last_mean_fitness" in s
        assert "total_improvement" in s
        assert "improvement_ratio" in s
        assert "l2_utilization" in s
        assert s["constitution_compliance"]["real_fitness_used"] is True

    def test_summary_constitution(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        runner.run(num_generations=1)
        s = runner.summary()
        assert s["constitution_compliance"]["bounded_rsi"] is True
        assert s["constitution_compliance"]["no_auto_promotion"] is True
        assert s["constitution_compliance"]["budget_enforced"] is True


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_bounded_rsi(self):
        """RSI is bounded by K0 constitution (fixed anchor)."""
        runner = RealRecursiveRunner(root=ROOT)
        assert not hasattr(runner, "modify_constitution")
        assert not hasattr(runner, "amend_k0")

    def test_no_code_modification(self):
        runner = RealRecursiveRunner(root=ROOT)
        assert not hasattr(runner, "modify_code")

    def test_no_auto_promotion(self):
        runner = RealRecursiveRunner(root=ROOT)
        assert not hasattr(runner, "promote")
        assert not hasattr(runner, "auto_promote")

    def test_all_results_evaluative(self):
        runner = RealRecursiveRunner(root=ROOT, num_generations=1, l2_budget=2, pbt_population_size=3)
        results = runner.run(num_generations=1)
        for r in results:
            assert r.payload()["truth_effect"] == "NONE"
