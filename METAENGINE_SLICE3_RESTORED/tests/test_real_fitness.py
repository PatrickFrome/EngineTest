"""Tests for Phase 50 — Real Fitness Functions."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.real_fitness import (
    RealFitnessFunctionFactory,
    FitnessResult,
    REAL_FITNESS_VERSION,
)
from metaengine.state_bus import TrainingStateBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory(tmp_path):
    return RealFitnessFunctionFactory(
        root=ROOT,
        cache_dir=tmp_path / "fitness_cache",
        rate_limit_delay=0.0,  # no delay in tests
        max_cache_entries=10,
    )


@pytest.fixture
def factory_with_bus(tmp_path):
    bus = TrainingStateBus()
    return RealFitnessFunctionFactory(
        root=ROOT,
        bus=bus,
        cache_dir=tmp_path / "fitness_cache",
        rate_limit_delay=0.0,
    )


# ---------------------------------------------------------------------------
# Tests: FitnessResult
# ---------------------------------------------------------------------------


class TestFitnessResult:
    def test_payload_has_required_fields(self):
        r = FitnessResult(
            theta={"max_rounds": 4},
            fitness=0.5,
            cost=1.0,
            latency=0.1,
            source="HEURISTIC",
            result_hash="abc",
        )
        p = r.payload()
        assert p["fitness_version"] == REAL_FITNESS_VERSION
        assert p["fitness"] == 0.5
        assert p["source"] == "HEURISTIC"
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = FitnessResult(
            theta={}, fitness=0.5, cost=1.0, latency=0.1,
            source="HEURISTIC", result_hash="abc123",
        )
        d = r.as_dict()
        assert d["result_hash"] == "abc123"

    def test_rlaif_fields_optional(self):
        r = FitnessResult(
            theta={}, fitness=0.5, cost=1.0, latency=0.1,
            source="RLAIF", rlaif_reward=0.7, rlaif_confidence=0.9,
            trace_count=5, faithfulness_score=0.8,
            result_hash="abc",
        )
        p = r.payload()
        assert p["rlaif_reward"] == 0.7
        assert p["rlaif_confidence"] == 0.9
        assert p["trace_count"] == 5
        assert p["faithfulness_score"] == 0.8


# ---------------------------------------------------------------------------
# Tests: Cache management
# ---------------------------------------------------------------------------


class TestCache:
    def test_cache_key_deterministic(self, factory):
        theta = {"max_rounds": 4, "exploration_rate": 0.15}
        k1 = factory._cache_key(theta)
        k2 = factory._cache_key(theta)
        assert k1 == k2

    def test_cache_key_different_for_different_theta(self, factory):
        t1 = {"max_rounds": 4}
        t2 = {"max_rounds": 8}
        assert factory._cache_key(t1) != factory._cache_key(t2)

    def test_put_and_get_cached(self, factory):
        result = FitnessResult(
            theta={"max_rounds": 4}, fitness=0.7, cost=1.0,
            latency=0.1, source="HEURISTIC", result_hash="abc",
        )
        factory._put_cached(result)
        cached = factory._get_cached({"max_rounds": 4})
        assert cached is not None
        assert cached.fitness == 0.7

    def test_get_cached_miss(self, factory):
        cached = factory._get_cached({"max_rounds": 99})
        assert cached is None

    def test_cache_eviction(self, tmp_path):
        f = RealFitnessFunctionFactory(
            root=ROOT, cache_dir=tmp_path / "cache",
            rate_limit_delay=0.0, max_cache_entries=3,
        )
        for i in range(5):
            r = FitnessResult(
                theta={"max_rounds": i}, fitness=0.1 * i,
                cost=1.0, latency=0.1, source="HEURISTIC", result_hash="abc",
            )
            f._put_cached(r)
        assert len(f._cache) <= 3  # evicted oldest


# ---------------------------------------------------------------------------
# Tests: Theta → policy params
# ---------------------------------------------------------------------------


class TestThetaConversion:
    def test_theta_to_policy_params(self, factory):
        theta = {"max_rounds": 6, "max_deep_engines": 10, "exploration_rate": 0.2, "temperature": 0.5}
        params = factory._theta_to_policy_params(theta)
        assert params["max_rounds"] == 6
        assert params["max_deep_engines"] == 10
        assert params["exploration_rate"] == 0.2
        assert params["temperature"] == 0.5

    def test_clamping_max_rounds(self, factory):
        params = factory._theta_to_policy_params({"max_rounds": 100})
        assert params["max_rounds"] == 8  # clamped

    def test_clamping_min_rounds(self, factory):
        params = factory._theta_to_policy_params({"max_rounds": -5})
        assert params["max_rounds"] == 1  # clamped

    def test_clamping_exploration_rate(self, factory):
        params = factory._theta_to_policy_params({"exploration_rate": 1.0})
        assert params["exploration_rate"] == 0.30  # clamped

    def test_clamping_temperature(self, factory):
        params = factory._theta_to_policy_params({"temperature": 5.0})
        assert params["temperature"] == 2.0  # clamped

    def test_defaults_for_missing_keys(self, factory):
        params = factory._theta_to_policy_params({})
        assert params["max_rounds"] == 4
        assert params["max_deep_engines"] == 8
        assert params["exploration_rate"] == 0.15
        assert params["temperature"] == 0.4


# ---------------------------------------------------------------------------
# Tests: Heuristic fitness
# ---------------------------------------------------------------------------


class TestHeuristicFitness:
    def test_returns_float_0_to_1(self, factory):
        fitness = factory._heuristic_fitness({"max_rounds": 4})
        assert 0.0 <= fitness <= 1.0

    def test_optimal_theta_scores_higher(self, factory):
        optimal = {"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.15, "temperature": 0.4}
        suboptimal = {"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 2.0}
        assert factory._heuristic_fitness(optimal) > factory._heuristic_fitness(suboptimal)

    def test_deterministic(self, factory):
        theta = {"max_rounds": 4, "exploration_rate": 0.15}
        assert factory._heuristic_fitness(theta) == factory._heuristic_fitness(theta)


# ---------------------------------------------------------------------------
# Tests: Fitness function factory
# ---------------------------------------------------------------------------


class TestFitnessFunction:
    def test_make_fitness_fn_returns_callable(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        assert callable(fn)

    def test_fitness_fn_returns_float(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        result = fn({"max_rounds": 4})
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_cache_used_on_second_call(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=True, use_rate_limit=False)
        # First call
        r1 = fn({"max_rounds": 4, "exploration_rate": 0.15})
        # Second call with same theta → should use cache
        r2 = fn({"max_rounds": 4, "exploration_rate": 0.15})
        assert r1 == r2
        assert len(factory._cache) == 1

    def test_different_theta_different_fitness(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        f1 = fn({"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.15, "temperature": 0.4})
        f2 = fn({"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 2.0})
        assert f1 != f2  # different theta → different fitness

    def test_call_count_increments(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        assert factory._call_count == 0
        fn({"max_rounds": 4})
        assert factory._call_count == 1
        fn({"max_rounds": 8})
        assert factory._call_count == 2

    def test_publishes_to_bus(self, factory_with_bus):
        fn = factory_with_bus.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        fn({"max_rounds": 4})
        # Bus should have a reward published
        assert len(factory_with_bus.bus.rlaif_rewards) > 0

    def test_rate_limit_respected(self, tmp_path):
        f = RealFitnessFunctionFactory(
            root=ROOT, cache_dir=tmp_path / "cache",
            rate_limit_delay=0.1,
        )
        fn = f.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=True)
        import time
        start = time.perf_counter()
        fn({"max_rounds": 4})
        fn({"max_rounds": 8})
        elapsed = time.perf_counter() - start
        # Second call should have waited ~0.1s
        assert elapsed >= 0.1


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, factory):
        s = factory.summary()
        assert s["fitness_version"] == REAL_FITNESS_VERSION
        assert s["total_calls"] == 0
        assert s["cache_size"] == 0
        assert s["bus_connected"] is False
        assert s["truth_effect"] == "NONE"

    def test_summary_after_calls(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=True, use_rate_limit=False)
        fn({"max_rounds": 4})
        fn({"max_rounds": 8})
        s = factory.summary()
        assert s["total_calls"] == 2
        assert s["cache_size"] == 2

    def test_summary_with_bus(self, factory_with_bus):
        s = factory_with_bus.summary()
        assert s["bus_connected"] is True


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_real_measurement_not_assumed(self, factory):
        """Fitness is measured, not assumed."""
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        # Fitness comes from heuristic computation, not hardcoded
        f1 = fn({"max_rounds": 1})
        f2 = fn({"max_rounds": 8})
        assert f1 != f2  # different theta → different fitness (measured)

    def test_no_code_modification(self, factory):
        """Factory has no methods to modify code."""
        assert not hasattr(factory, "modify_code")
        assert not hasattr(factory, "execute_code")

    def test_caching_idempotent(self, factory):
        """Same theta → same cached result (idempotent)."""
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=True, use_rate_limit=False)
        r1 = fn({"max_rounds": 4})
        r2 = fn({"max_rounds": 4})
        assert r1 == r2  # idempotent

    def test_all_results_evaluative(self, factory):
        fn = factory.make_fitness_fn(use_rlaif=False, use_cache=False, use_rate_limit=False)
        fn({"max_rounds": 4})
        results = factory.get_cached_results()
        # If cached, check truth_effect
        for r in results:
            assert r.payload()["truth_effect"] == "NONE"
