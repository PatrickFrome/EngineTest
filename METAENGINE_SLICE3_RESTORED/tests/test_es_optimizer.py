"""Tests for Phase 39 — ES Hyperparameter Optimizer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.es_optimizer import (
    ESHyperparameterOptimizer,
    HyperparameterSpec,
    ESState,
    DEFAULT_POLICY_HYPERPARAMS,
    ES_VERSION,
    make_policy_fitness_fn,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def specs():
    return DEFAULT_POLICY_HYPERPARAMS


@pytest.fixture
def optimizer():
    return ESHyperparameterOptimizer(
        population_size=4,
        initial_sigma=0.2,
        initial_alpha=0.1,
        seed=42,
    )


@pytest.fixture
def quadratic_optimizer():
    """Optimizer with 1 param, fitness = -(x-5)^2 + 10 (optimum at x=5)."""
    spec = (HyperparameterSpec("x", 0.0, 10.0, 2.0, is_integer=False),)
    return ESHyperparameterOptimizer(
        specs=spec,
        population_size=4,
        initial_sigma=0.5,
        initial_alpha=0.5,
        seed=42,
    )


# ---------------------------------------------------------------------------
# Tests: HyperparameterSpec
# ---------------------------------------------------------------------------


class TestHyperparameterSpec:
    def test_clamp_within_range(self):
        spec = HyperparameterSpec("test", 0.0, 1.0, 0.5)
        assert spec.clamp(0.3) == 0.3
        assert spec.clamp(0.7) == 0.7

    def test_clamp_below_min(self):
        spec = HyperparameterSpec("test", 0.0, 1.0, 0.5)
        assert spec.clamp(-0.5) == 0.0

    def test_clamp_above_max(self):
        spec = HyperparameterSpec("test", 0.0, 1.0, 0.5)
        assert spec.clamp(1.5) == 1.0

    def test_clamp_integer_rounds(self):
        spec = HyperparameterSpec("test", 1, 10, 5, is_integer=True)
        assert spec.clamp(3.7) == 4
        assert spec.clamp(3.2) == 3

    def test_payload_has_fields(self):
        spec = HyperparameterSpec("test", 0.0, 1.0, 0.5, is_integer=False)
        p = spec.payload()
        assert p["name"] == "test"
        assert p["min"] == 0.0
        assert p["max"] == 1.0
        assert p["initial"] == 0.5
        assert p["is_integer"] is False


# ---------------------------------------------------------------------------
# Tests: ESState
# ---------------------------------------------------------------------------


class TestESState:
    def test_initial_state(self):
        state = ESState(
            theta={"x": 0.5},
            sigma=0.3,
            alpha=0.1,
        )
        assert state.generation == 0
        assert state.best_fitness == 0.0
        assert state.history == []

    def test_payload_has_truth_effect_none(self):
        state = ESState(theta={"x": 0.5}, sigma=0.3, alpha=0.1)
        p = state.payload()
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "ES_STATE_IS_OPTIMIZATION_NOT_TRUTH"


# ---------------------------------------------------------------------------
# Tests: ESHyperparameterOptimizer
# ---------------------------------------------------------------------------


class TestESOptimizer:
    def test_initialize_with_default_specs(self, optimizer):
        assert "max_rounds" in optimizer.state.theta
        assert "max_deep_engines" in optimizer.state.theta
        assert "exploration_rate" in optimizer.state.theta
        assert "temperature" in optimizer.state.theta

    def test_population_size_validation(self):
        with pytest.raises(ValueError, match="POPULATION_SIZE_MUST_BE_AT_LEAST_2"):
            ESHyperparameterOptimizer(population_size=1)

    def test_sigma_decay_validation(self):
        with pytest.raises(ValueError, match="SIGMA_DECAY_MUST_BE_IN"):
            ESHyperparameterOptimizer(sigma_decay=1.5)

    def test_sample_noise_returns_dict(self, optimizer):
        noise = optimizer._sample_noise()
        assert set(noise.keys()) == {s.name for s in optimizer.specs}

    def test_perturb_theta_clamps(self, optimizer):
        theta = optimizer.state.theta
        noise = {s.name: 1000.0 for s in optimizer.specs}  # huge noise
        perturbed = optimizer._perturb_theta(theta, noise, direction=+1)
        for spec in optimizer.specs:
            assert spec.min_value <= perturbed[spec.name] <= spec.max_value

    def test_perturb_theta_antithetic(self, optimizer):
        theta = optimizer.state.theta
        noise = {s.name: 0.5 for s in optimizer.specs}
        plus = optimizer._perturb_theta(theta, noise, direction=+1)
        minus = optimizer._perturb_theta(theta, noise, direction=-1)
        for spec in optimizer.specs:
            # Antithetic: plus should be above theta, minus below (if not clamped)
            assert plus[spec.name] >= minus[spec.name]

    def test_step_returns_record(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        record = optimizer.step(mock_fitness)
        assert "generation" in record
        assert "mean_fitness" in record
        assert "new_fitness" in record
        assert "record_hash" in record
        assert record["truth_effect"] == "NONE"

    def test_step_increments_generation(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        optimizer.step(mock_fitness)
        optimizer.step(mock_fitness)
        assert optimizer.state.generation == 2

    def test_step_decays_sigma(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        initial_sigma = optimizer.state.sigma
        optimizer.step(mock_fitness)
        assert optimizer.state.sigma < initial_sigma  # decayed

    def test_step_decays_alpha(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        initial_alpha = optimizer.state.alpha
        optimizer.step(mock_fitness)
        assert optimizer.state.alpha < initial_alpha  # decayed

    def test_step_tracks_best(self, optimizer):
        call_count = [0]
        def mock_fitness(theta):
            call_count[0] += 1
            # Vary fitness based on max_rounds (higher = better)
            return 0.3 + theta["max_rounds"] * 0.05
        optimizer.step(mock_fitness)
        assert optimizer.state.best_fitness > 0
        assert optimizer.state.best_theta != {}

    def test_step_improvement_flag(self, optimizer):
        call_count = [0]
        def mock_fitness(theta):
            call_count[0] += 1
            # First call returns low, subsequent return higher
            if call_count[0] <= 8:
                return 0.3
            return 0.8
        record = optimizer.step(mock_fitness)
        # new_fitness evaluated last → 0.8, should improve
        assert "improved" in record

    def test_run_returns_summary(self, optimizer):
        def mock_fitness(theta):
            return 0.5 + theta["max_rounds"] * 0.01
        summary = optimizer.run(mock_fitness, num_generations=3)
        assert summary["es_version"] == ES_VERSION
        assert summary["generations_run"] == 3
        assert "best_theta" in summary
        assert "best_fitness" in summary
        assert "constitution_compliance" in summary

    def test_run_without_steps_returns_empty(self):
        opt = ESHyperparameterOptimizer()
        summary = opt.summary()
        assert summary["generations_run"] == 0
        assert summary["truth_effect"] == "NONE"

    def test_history_accumulates(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        optimizer.run(mock_fitness, num_generations=5)
        assert len(optimizer.state.history) == 5

    def test_convergence_detected(self, optimizer):
        def constant_fitness(theta):
            return 0.5
        optimizer.run(constant_fitness, num_generations=5)
        summary = optimizer.summary()
        # Constant fitness → should converge (max - min < 0.01 in last 3)
        assert summary["converged"] is True

    def test_no_convergence_with_improving_fitness(self, optimizer):
        gen = [0]
        def increasing_fitness(theta):
            gen[0] += 1
            return 0.1 + gen[0] * 0.1  # always increasing
        optimizer.run(increasing_fitness, num_generations=5)
        summary = optimizer.summary()
        assert summary["converged"] is False


# ---------------------------------------------------------------------------
# Tests: Quadratic optimization (sanity check)
# ---------------------------------------------------------------------------


class TestQuadraticOptimization:
    """ES should find the optimum of a simple quadratic function."""

    def test_finds_optimum_of_quadratic(self, quadratic_optimizer):
        """fitness = -(x-5)^2 + 10, optimum at x=5."""
        def fitness(theta):
            x = theta["x"]
            return -((x - 5) ** 2) + 10
        quadratic_optimizer.run(fitness, num_generations=15)
        summary = quadratic_optimizer.summary()
        # Best theta should be close to 5
        assert abs(summary["best_theta"]["x"] - 5.0) < 2.0  # within 2 of optimum
        # Best fitness should be close to 10 (optimum)
        assert summary["best_fitness"] > 7.0  # at least 70% of optimum

    def test_fitness_improves_over_generations(self, quadratic_optimizer):
        def fitness(theta):
            x = theta["x"]
            return -((x - 5) ** 2) + 10
        # Initial fitness
        initial = fitness({"x": 2.0})
        quadratic_optimizer.run(fitness, num_generations=10)
        summary = quadratic_optimizer.summary()
        assert summary["best_fitness"] > initial


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_summary_has_constitution_compliance(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        optimizer.run(mock_fitness, num_generations=2)
        summary = optimizer.summary()
        assert summary["constitution_compliance"]["no_code_modification"] is True
        assert summary["constitution_compliance"]["all_policies_remain_shadow"] is True
        assert summary["constitution_compliance"]["no_auto_promotion"] is True

    def test_all_records_have_truth_effect_none(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        optimizer.run(mock_fitness, num_generations=3)
        for record in optimizer.state.history:
            assert record["truth_effect"] == "NONE"

    def test_summary_claim_ceiling(self, optimizer):
        def mock_fitness(theta):
            return 0.5
        optimizer.run(mock_fitness, num_generations=1)
        summary = optimizer.summary()
        assert summary["claim_ceiling"] == "ES_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"
        assert summary["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_same_result(self):
        def fitness(theta):
            return theta["max_rounds"] * 0.1
        opt1 = ESHyperparameterOptimizer(seed=42)
        opt2 = ESHyperparameterOptimizer(seed=42)
        opt1.run(fitness, num_generations=3)
        opt2.run(fitness, num_generations=3)
        assert opt1.state.theta == opt2.state.theta
        assert opt1.state.best_fitness == opt2.state.best_fitness
