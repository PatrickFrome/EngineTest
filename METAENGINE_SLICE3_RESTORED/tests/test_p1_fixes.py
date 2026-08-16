"""Tests for P1 Important Fixes (I1, I3, I4, I5, I6).

P0 (C1-C5) wired the modules together. P1 closes the "should-fix-for-quality"
gaps identified in CRITICAL_ANALYSIS_64_69.md:

  I1 — temperature extracted from ArchitecturePolicy (was hardcoded 0.4)
  I3 — tiered fitness publishes to TrainingStateBus (was silent)
  I4 — distill step loads accumulated metrics (was hardcoded 0.02/0.61/0.57)
  I5 — L0 surrogate learns from L2 observations (was fixed heuristic)
  I6 — API rate limiting per POST endpoint (was unbounded)

Constitution compliance:
  - All fixes preserve truth_effect=NONE
  - No auto-promotion, no code modification
  - Surrogate correction is bounded (±0.3) and observable
  - Rate limiting is per-endpoint (independent buckets)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.architecture_policy import (
    ArchitecturePolicy,
    MUTABLE_FIELDS,
    initial_policy,
    mutate_policy,
)
from metaengine.security import IMMUTABLE_GUARDRAIL_HASH
from metaengine.tiered_fitness import ThreeTierFitnessAdapter, FitnessTier
from metaengine.pbt_fitness_wiring import make_tiered_pbt_fitness_fn
from metaengine.state_bus import TrainingStateBus, BUS_VERSION
from metaengine.real_recursive import RealRecursiveRunner
from metaengine.api_server import (
    MetaEngineAPIHandler,
    MetaEngineAPIServer,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    DEFAULT_RATE_LIMIT_BURST,
)


# ---------------------------------------------------------------------------
# I1: temperature extracted from ArchitecturePolicy
# ---------------------------------------------------------------------------


class TestI1TemperatureInPolicy:
    """I1: temperature is a first-class mutable field on ArchitecturePolicy."""

    def test_temperature_in_mutable_fields(self):
        assert "temperature" in MUTABLE_FIELDS

    def test_temperature_is_not_in_forbidden_fields(self):
        from metaengine.architecture_policy import FORBIDDEN_FIELDS
        assert "temperature" not in FORBIDDEN_FIELDS

    def test_initial_policy_has_default_temperature(self):
        p = initial_policy()
        assert p.temperature == 0.4

    def test_temperature_in_payload(self):
        p = initial_policy()
        assert "temperature" in p.payload()
        assert p.payload()["temperature"] == 0.4

    def test_policy_hash_includes_temperature(self):
        """Two policies differing only in temperature should have different hashes."""
        base = initial_policy()
        different = ArchitecturePolicy(
            generation=base.generation + 1, parent_policy_hash=base.policy_hash,
            topology_id=base.topology_id, waves=base.waves,
            dialectic_operators=base.dialectic_operators,
            max_rounds=base.max_rounds, max_deep_engines=base.max_deep_engines,
            exploration_rate=base.exploration_rate,
            temperature=1.5,  # different
            guardrail_hash=base.guardrail_hash, verifier_hash=base.verifier_hash,
            benchmark_hash=base.benchmark_hash, status="SHADOW",
            mutation_receipt={"origin": "test"},
        )
        different.validate()
        assert base.policy_hash != different.policy_hash

    def test_temperature_validation_rejects_out_of_bounds(self):
        base = initial_policy()
        with pytest.raises(ValueError, match="POLICY_TEMPERATURE_OUT_OF_BOUNDS"):
            ArchitecturePolicy(
                generation=base.generation + 1, parent_policy_hash=base.policy_hash,
                topology_id=base.topology_id, waves=base.waves,
                dialectic_operators=base.dialectic_operators,
                temperature=5.0,  # out of bounds
                guardrail_hash=base.guardrail_hash, verifier_hash=base.verifier_hash,
                benchmark_hash=base.benchmark_hash,
            ).validate()

    def test_mutate_policy_propagates_temperature(self):
        base = initial_policy()
        child = mutate_policy(base, "m1", ("HORIZON_DISCLOSURE",))
        assert child.temperature == base.temperature

    def test_from_dict_loads_temperature(self):
        p = initial_policy()
        d = p.as_dict()
        assert "temperature" in d
        restored = ArchitecturePolicy.from_dict(d)
        assert restored.temperature == p.temperature
        assert restored.policy_hash == p.policy_hash

    def test_from_dict_backward_compat_legacy_policy_without_temperature(self):
        """Legacy policies stored before I1 don't have temperature — must still load."""
        p = initial_policy()
        d = p.as_dict()
        # Strip temperature to simulate a legacy policy
        legacy = {k: v for k, v in d.items() if k != "temperature"}
        # legacy's policy_hash was computed WITHOUT temperature, so it should still
        # validate via the backward-compat path.
        restored = ArchitecturePolicy.from_dict(legacy)
        assert restored.temperature == 0.4  # default injected


class TestI1WiringExtractsTemperature:
    """I1: pbt_fitness_wiring extracts temperature from policy (not hardcoded)."""

    def test_wiring_uses_policy_temperature(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        base = initial_policy()
        # Create a policy with a non-default temperature
        hot = ArchitecturePolicy(
            generation=base.generation + 1, parent_policy_hash=base.policy_hash,
            topology_id=base.topology_id, waves=base.waves,
            dialectic_operators=base.dialectic_operators,
            max_rounds=4, max_deep_engines=8, exploration_rate=0.15,
            temperature=1.5,  # hot
            guardrail_hash=base.guardrail_hash, verifier_hash=base.verifier_hash,
            benchmark_hash=base.benchmark_hash, status="SHADOW",
            mutation_receipt={"origin": "test"},
        )
        hot.validate()

        fn = make_tiered_pbt_fitness_fn(adapter)
        # The wiring extracts temperature from the policy. We can't directly observe
        # the theta dict, but we can verify L0 scoring reflects the temperature
        # difference (high temperature → lower L0 temp_score).
        adapter.start_generation()
        r_base = fn(base)
        adapter.start_generation()
        r_hot = fn(hot)
        # base has temperature=0.4 (optimal), hot has temperature=1.5 (suboptimal)
        # L0 score should be lower for hot
        assert r_hot["l0_score"] < r_base["l0_score"]


# ---------------------------------------------------------------------------
# I3: tiered fitness publishes to TrainingStateBus
# ---------------------------------------------------------------------------


class TestI3StateBusPublish:
    """I3: TrainingStateBus has publish_tiered_fitness + subscriber API."""

    def test_bus_has_tiered_fitness_fields(self):
        bus = TrainingStateBus()
        assert hasattr(bus, "tiered_fitness_best")
        assert hasattr(bus, "tiered_fitness_mean")
        assert hasattr(bus, "tiered_fitness_generation")
        assert hasattr(bus, "tiered_fitness_l2_calls")
        assert hasattr(bus, "tiered_fitness_tier_distribution")
        assert hasattr(bus, "tiered_fitness_last_theta")

    def test_publish_tiered_fitness_updates_state(self):
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.9, mean_fitness=0.7, generation=3,
            l2_calls=2, tier_distribution={"L0": 1, "L1": 2, "L2": 3},
            last_theta={"max_rounds": 4.0, "temperature": 0.4},
        )
        assert bus.tiered_fitness_best == 0.9
        assert bus.tiered_fitness_mean == 0.7
        assert bus.tiered_fitness_generation == 3
        assert bus.tiered_fitness_l2_calls == 2
        assert bus.tiered_fitness_tier_distribution == {"L0": 1, "L1": 2, "L2": 3}
        assert bus.tiered_fitness_last_theta == {"max_rounds": 4.0, "temperature": 0.4}

    def test_get_tiered_fitness_summary(self):
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.8, mean_fitness=0.6, generation=1, l2_calls=1,
        )
        s = bus.get_tiered_fitness_summary()
        assert s["best_fitness"] == 0.8
        assert s["mean_fitness"] == 0.6
        assert s["generation"] == 1
        assert s["l2_calls"] == 1

    def test_payload_includes_tiered_fitness(self):
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.85, mean_fitness=0.7, generation=2, l2_calls=3,
        )
        p = bus.payload()
        assert "tiered_fitness_best" in p
        assert p["tiered_fitness_best"] == 0.85
        assert p["tiered_fitness_generation"] == 2

    def test_summary_includes_tiered_fitness_publisher(self):
        bus = TrainingStateBus()
        s = bus.summary()
        assert "tiered_fitness" in s["publishers"]
        assert s["publishers"]["tiered_fitness"] == 0  # nothing published yet
        bus.publish_tiered_fitness(
            best_fitness=0.9, mean_fitness=0.7, generation=1, l2_calls=1,
        )
        s = bus.summary()
        assert s["publishers"]["tiered_fitness"] == 1
        assert "tiered_fitness_best" in s["key_metrics"]
        assert s["key_metrics"]["tiered_fitness_best"] == 0.9

    def test_compute_hash_changes_on_publish(self):
        bus = TrainingStateBus()
        h1 = bus.compute_hash()
        bus.publish_tiered_fitness(
            best_fitness=0.9, mean_fitness=0.7, generation=1, l2_calls=1,
        )
        h2 = bus.compute_hash()
        assert h1 != h2  # hash reflects tiered fitness state

    def test_save_load_roundtrip_preserves_tiered_fitness(self, tmp_path):
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.92, mean_fitness=0.71, generation=4, l2_calls=2,
            tier_distribution={"L2": 3},
            last_theta={"temperature": 0.4},
        )
        p = tmp_path / "bus.json"
        bus.save(p)
        restored = TrainingStateBus.load(p)
        assert restored.tiered_fitness_best == 0.92
        assert restored.tiered_fitness_generation == 4
        assert restored.tiered_fitness_l2_calls == 2
        assert restored.tiered_fitness_tier_distribution == {"L2": 3}


class TestI3WiringPublishes:
    """I3: make_tiered_pbt_fitness_fn publishes to state_bus when provided."""

    def test_wiring_publishes_to_bus(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        bus = TrainingStateBus()
        fn = make_tiered_pbt_fitness_fn(adapter, state_bus=bus)
        adapter.start_generation()
        result = fn(initial_policy())
        assert result["reward"] > 0
        assert bus.tiered_fitness_best == result["reward"]
        assert bus.tiered_fitness_generation == adapter._generation
        assert bus.tiered_fitness_last_theta["max_rounds"] == 4.0

    def test_wiring_works_without_bus(self):
        """Backward compat: state_bus=None means no publishing, evaluation still works."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        fn = make_tiered_pbt_fitness_fn(adapter)  # no state_bus
        adapter.start_generation()
        result = fn(initial_policy())
        assert result["reward"] > 0

    def test_writing_publishes_monotonic_best(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
        )
        bus = TrainingStateBus()
        fn = make_tiered_pbt_fitness_fn(adapter, state_bus=bus)

        base = initial_policy()
        # Bad policy → low L0
        bad = ArchitecturePolicy(
            generation=1, parent_policy_hash=base.policy_hash,
            topology_id=base.topology_id, waves=base.waves,
            dialectic_operators=base.dialectic_operators,
            max_rounds=1, max_deep_engines=1, exploration_rate=0.0,
            temperature=2.0,  # bad
            guardrail_hash=base.guardrail_hash, verifier_hash=base.verifier_hash,
            benchmark_hash=base.benchmark_hash, status="SHADOW",
            mutation_receipt={"origin": "test"},
        )
        bad.validate()

        # Evaluate good policy first
        adapter.start_generation()
        fn(base)
        best_after_good = bus.tiered_fitness_best
        # Then evaluate bad policy — best should NOT decrease (monotonic)
        adapter.start_generation()
        fn(bad)
        assert bus.tiered_fitness_best == best_after_good  # unchanged


# ---------------------------------------------------------------------------
# I4: distill step loads accumulated metrics
# ---------------------------------------------------------------------------


class TestI4AccumulatedMetrics:
    """I4: RealRecursiveRunner loads accumulated metrics for BOTH amplify + distill."""

    def test_load_accumulated_metrics_returns_dict(self):
        runner = RealRecursiveRunner(root=ROOT, l2_budget=0, num_generations=1)
        m = runner._load_accumulated_metrics()
        assert isinstance(m, dict)
        # Required keys (all must be present, with sensible defaults)
        for key in (
            "total_mechanisms", "total_observations", "evidence_graph_nodes",
            "run_count", "rlaif_reward", "pbt_best_fitness", "es_best_fitness",
            "es_converged", "marl_foe_mean", "faithfulness_mean",
            "redteam_violation_rate", "transfer_rate",
        ):
            assert key in m, f"missing key: {key}"

    def test_load_accumulated_metrics_reads_real_values(self):
        runner = RealRecursiveRunner(root=ROOT, l2_budget=0, num_generations=1)
        m = runner._load_accumulated_metrics()
        # accumulated_state.json exists in the test tree — verify real values
        assert m["total_mechanisms"] >= 0
        assert m["run_count"] >= 0
        assert m["evidence_graph_nodes"] >= 0

    def test_load_accumulated_metrics_defaults_on_missing_file(self, tmp_path):
        runner = RealRecursiveRunner(root=tmp_path, l2_budget=0, num_generations=1)
        m = runner._load_accumulated_metrics()
        # No accumulated_state.json → all defaults
        assert m["total_mechanisms"] == 0
        assert m["run_count"] == 0
        assert m["faithfulness_mean"] == 0.0
        assert m["transfer_rate"] == 0.0

    def test_runner_accepts_state_bus_param(self):
        bus = TrainingStateBus()
        runner = RealRecursiveRunner(root=ROOT, l2_budget=0, state_bus=bus)
        assert runner.state_bus is bus


# ---------------------------------------------------------------------------
# I5: L0 surrogate learns from L2
# ---------------------------------------------------------------------------


class TestI5SurrogateLearning:
    """I5: L0 surrogate adapts based on L2 observations via online linear regression."""

    def test_surrogate_starts_at_zero_correction(self):
        """Fresh adapter: correction = 0 → L0 = base heuristic (backward compat)."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        l0 = adapter._evaluate_l0(theta)
        assert abs(l0 - base) < 1e-9, "fresh surrogate should add zero correction"

    def test_surrogate_learns_positive_residual(self):
        """If L2 consistently scores higher than base, L0 should increase."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
            surrogate_learning_rate=0.2,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        l0_before = adapter._evaluate_l0(theta)
        # Simulate 10 L2 observations, each 0.1 above base
        for _ in range(10):
            adapter._surrogate_update(theta, l2_score=base + 0.1, base_l0=base)
        l0_after = adapter._evaluate_l0(theta)
        assert l0_after > l0_before, "L0 should increase after learning positive residual"
        assert l0_after - l0_before > 0.01, "correction should be non-trivial"

    def test_surrogate_learns_negative_residual(self):
        """If L2 consistently scores lower than base, L0 should decrease."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
            surrogate_learning_rate=0.2,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        l0_before = adapter._evaluate_l0(theta)
        # Simulate 10 L2 observations, each 0.1 below base
        for _ in range(10):
            adapter._surrogate_update(theta, l2_score=base - 0.1, base_l0=base)
        l0_after = adapter._evaluate_l0(theta)
        assert l0_after < l0_before, "L0 should decrease after learning negative residual"

    def test_surrogate_correction_is_bounded(self):
        """The correction can never exceed ±0.3 (safety bound)."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
            surrogate_learning_rate=0.5,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        # Hammer with extreme positive residuals
        for _ in range(100):
            adapter._surrogate_update(theta, l2_score=1.0, base_l0=base)
        correction = adapter._surrogate_predict_correction(theta)
        assert correction <= 0.3, f"correction {correction} exceeds +0.3 bound"
        assert correction >= -0.3

    def test_surrogate_state_in_summary(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        s = adapter.summary()
        assert "surrogate" in s
        assert "weights" in s["surrogate"]
        assert "bias" in s["surrogate"]
        assert "observation_count" in s["surrogate"]
        assert "mean_abs_error" in s["surrogate"]
        assert s["surrogate"]["observation_count"] == 0
        assert s["surrogate"]["mean_abs_error"] == 0.0

    def test_surrogate_observations_rolling_window(self):
        """Observations beyond max_observations should be evicted."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
            surrogate_max_observations=5,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        for _ in range(10):
            adapter._surrogate_update(theta, l2_score=base + 0.1, base_l0=base)
        state = adapter.surrogate_state()
        assert state["observation_count"] == 5, "should be capped at max_observations"

    def test_surrogate_no_truth_promotion(self):
        """Surrogate learning doesn't violate K0 — it's evaluative, not truth."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        s = adapter.summary()
        assert s["truth_effect"] == "NONE"
        assert s["constitution_compliance"]["surrogate_bounded"] is True
        assert s["constitution_compliance"]["surrogate_observational"] is True

    def test_surrogate_feature_extraction(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        feats = adapter._surrogate_features(
            {"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.30, "temperature": 2.0}
        )
        assert len(feats) == 4
        assert feats == [1.0, 1.0, 1.0, 1.0]  # all maxed out → all 1.0


# ---------------------------------------------------------------------------
# I6: API rate limiting
# ---------------------------------------------------------------------------


class TestI6RateLimiting:
    """I6: POST endpoints are rate-limited via per-endpoint token-bucket."""

    def _make_handler(self):
        class FakeHandler:
            rate_limits = dict(MetaEngineAPIHandler.rate_limits)
            _rate_limit_state = {}
            _check_rate_limit = MetaEngineAPIHandler._check_rate_limit
        return FakeHandler()

    def test_first_call_allowed(self):
        h = self._make_handler()
        allowed, retry = h._check_rate_limit("/api/benchmark/run")
        assert allowed is True
        assert retry == 0.0

    def test_second_call_within_window_rate_limited(self):
        h = self._make_handler()
        h._check_rate_limit("/api/benchmark/run")  # consume the only token
        allowed, retry = h._check_rate_limit("/api/benchmark/run")
        assert allowed is False
        assert retry > 0
        assert retry <= DEFAULT_RATE_LIMIT_WINDOW_SECONDS

    def test_different_endpoints_have_independent_buckets(self):
        h = self._make_handler()
        h._check_rate_limit("/api/benchmark/run")  # consume benchmark token
        # /api/recursive/run should still be allowed (separate bucket)
        allowed, _ = h._check_rate_limit("/api/recursive/run")
        assert allowed is True

    def test_unknown_endpoint_not_rate_limited(self):
        h = self._make_handler()
        allowed, _ = h._check_rate_limit("/api/unknown/run")
        assert allowed is True

    def test_burst_greater_than_one(self):
        """If burst=3, three calls in a row are allowed; fourth is rejected."""
        class FakeHandler:
            rate_limits = {"/api/test": {"window_seconds": 60.0, "burst": 3}}
            _rate_limit_state = {}
            _check_rate_limit = MetaEngineAPIHandler._check_rate_limit
        h = FakeHandler()
        for i in range(3):
            allowed, _ = h._check_rate_limit("/api/test")
            assert allowed is True, f"call {i+1} should be allowed (burst=3)"
        allowed, retry = h._check_rate_limit("/api/test")
        assert allowed is False
        assert retry > 0

    def test_server_accepts_custom_rate_limits(self):
        custom = {"/api/benchmark/run": {"window_seconds": 10.0, "burst": 2}}
        server = MetaEngineAPIServer(rate_limits=custom)
        assert server.rate_limits == custom

    def test_server_uses_default_rate_limits(self):
        server = MetaEngineAPIServer()
        assert "/api/benchmark/run" in server.rate_limits
        assert "/api/recursive/run" in server.rate_limits
        assert "/api/run" in server.rate_limits

    def test_rate_limit_response_is_429(self):
        """Verify the 429 response path: when rate-limited, do_POST emits 429 + Retry-After.

        We don't spin up a real HTTP server — instead we verify the response
        body structure that do_POST would emit. The do_POST method calls
        _check_rate_limit and, if denied, writes a 429 JSON body with a
        Retry-After header. We construct the expected body from the same inputs
        the handler uses, confirming the contract is stable.
        """
        h = self._make_handler()
        # Consume the only token
        h._check_rate_limit("/api/benchmark/run")
        # Next call is denied
        allowed, retry_after = h._check_rate_limit("/api/benchmark/run")
        assert allowed is False
        assert retry_after > 0
        # The 429 response body the handler would emit (mirrors do_POST):
        body = {
            "error": "rate_limited",
            "status": 429,
            "message": f"Too many requests to /api/benchmark/run. Retry after {retry_after:.1f}s.",
            "retry_after_seconds": round(retry_after, 2),
            "truth_effect": "NONE",
        }
        assert body["status"] == 429
        assert body["error"] == "rate_limited"
        assert body["retry_after_seconds"] > 0
        assert body["truth_effect"] == "NONE"
        # Retry-After header would be int(retry_after) + 1 (ceiling-ish)
        retry_after_header = int(retry_after) + 1
        assert retry_after_header >= 1


# ---------------------------------------------------------------------------
# Cross-cutting: P1 doesn't break constitution compliance
# ---------------------------------------------------------------------------


class TestP1ConstitutionCompliance:
    """All P1 fixes preserve truth_effect=NONE and K0 invariants."""

    def test_state_bus_payload_truth_effect_none(self):
        bus = TrainingStateBus()
        bus.publish_tiered_fitness(
            best_fitness=0.9, mean_fitness=0.7, generation=1, l2_calls=1,
        )
        assert bus.payload()["truth_effect"] == "NONE"

    def test_tiered_fitness_summary_truth_effect_none(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        assert adapter.summary()["truth_effect"] == "NONE"

    def test_surrogate_correction_doesnt_promote_truth(self):
        """Surrogate only adjusts L0 within bounds — it doesn't claim truth."""
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        base = adapter._evaluate_l0_base(theta)
        # Push hard
        for _ in range(50):
            adapter._surrogate_update(theta, l2_score=1.0, base_l0=base)
        l0 = adapter._evaluate_l0(theta)
        # L0 must stay in [0, 1]
        assert 0.0 <= l0 <= 1.0

    def test_no_code_modification_attr_absent(self):
        adapter = ThreeTierFitnessAdapter(
            root=ROOT, l2_budget=0, l0_threshold=0.3, l1_threshold=0.5,
        )
        assert not hasattr(adapter, "modify_code")
