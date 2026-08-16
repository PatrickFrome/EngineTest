"""Tests for Phase 67 Step 3 — PBT/ES Fitness Wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.pbt_fitness_wiring import (
    make_tiered_pbt_fitness_fn,
    make_tiered_es_fitness_fn,
    create_default_adapter,
)
from metaengine.tiered_fitness import ThreeTierFitnessAdapter, FitnessTier
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy
from metaengine.pbt_trainer import PBTPopulationTrainer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    return ThreeTierFitnessAdapter(
        root=ROOT, l2_budget=3, l0_threshold=0.3, l1_threshold=0.5, cache_size=10,
    )


@pytest.fixture
def base_policy():
    return initial_policy()


# ---------------------------------------------------------------------------
# Tests: PBT fitness wiring
# ---------------------------------------------------------------------------


class TestPBTFitnessWiring:
    def test_pbt_fitness_fn_returns_dict(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        result = fn(base_policy)
        assert isinstance(result, dict)
        assert "reward" in result
        assert "cost" in result
        assert "latency" in result

    def test_pbt_fitness_returns_float_reward(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        result = fn(base_policy)
        assert isinstance(result["reward"], float)
        assert 0.0 <= result["reward"] <= 1.0

    def test_pbt_fitness_includes_tier_metadata(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        result = fn(base_policy)
        assert "tier" in result
        assert result["tier"] in [t.value for t in FitnessTier]

    def test_pbt_fitness_includes_l0_l1_l2_scores(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        result = fn(base_policy)
        assert "l0_score" in result
        assert "l1_score" in result
        assert "l2_score" in result

    def test_pbt_fitness_includes_cached_flag(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        result = fn(base_policy)
        assert "cached" in result
        assert isinstance(result["cached"], bool)

    def test_pbt_fitness_deterministic_for_same_policy(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        r1 = fn(base_policy)
        r2 = fn(base_policy)
        assert r1["reward"] == r2["reward"]  # same policy → same result (cached)

    def test_pbt_fitness_different_for_different_policies(self, adapter):
        fn = make_tiered_pbt_fitness_fn(adapter)
        base = initial_policy()
        # Create a different policy with different max_rounds
        different = ArchitecturePolicy(
            generation=base.generation + 1, parent_policy_hash=base.policy_hash,
            topology_id=base.topology_id, waves=base.waves,
            dialectic_operators=base.dialectic_operators,
            max_rounds=8, max_deep_engines=16,  # different
            exploration_rate=0.15,
            guardrail_hash=base.guardrail_hash, verifier_hash=base.verifier_hash,
            benchmark_hash=base.benchmark_hash, status="SHADOW",
            mutation_receipt={"origin": "test"},
        )
        different.validate()
        r1 = fn(base)
        r2 = fn(different)
        assert r1["reward"] != r2["reward"]  # different policy → different fitness


# ---------------------------------------------------------------------------
# Tests: ES fitness wiring
# ---------------------------------------------------------------------------


class TestESFitnessWiring:
    def test_es_fitness_fn_returns_float(self, adapter):
        fn = make_tiered_es_fitness_fn(adapter)
        result = fn({"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4})
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_es_fitness_deterministic(self, adapter):
        fn = make_tiered_es_fitness_fn(adapter)
        theta = {"max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15, "temperature": 0.4}
        r1 = fn(theta)
        r2 = fn(theta)
        assert r1 == r2  # cached

    def test_es_fitness_different_for_different_theta(self, adapter):
        fn = make_tiered_es_fitness_fn(adapter)
        good = fn({"max_rounds": 8, "max_deep_engines": 16, "exploration_rate": 0.15, "temperature": 0.4})
        bad = fn({"max_rounds": 1, "max_deep_engines": 1, "exploration_rate": 0.0, "temperature": 2.0})
        assert good != bad


# ---------------------------------------------------------------------------
# Tests: Integration with PBT trainer
# ---------------------------------------------------------------------------


class TestPBTIntegration:
    def test_pbt_trainer_with_tiered_fitness(self, adapter, base_policy):
        """Run PBT with tiered fitness — verify it completes."""
        fn = make_tiered_pbt_fitness_fn(adapter)
        trainer = PBTPopulationTrainer(population_size=4, exploit_fraction=0.25, seed=42)
        trainer.initialize(base_policy)

        # Run 2 generations
        adapter.start_generation()
        result = trainer.run(fn, num_generations=2)

        assert result["num_generations"] == 2
        assert "champions" in result
        assert len(result["champions"]) > 0

    def test_pbt_fitness_improves_or_stable(self, adapter, base_policy):
        """PBT should not DECREASE fitness (exploit replaces worst with best)."""
        fn = make_tiered_pbt_fitness_fn(adapter)
        trainer = PBTPopulationTrainer(population_size=4, exploit_fraction=0.25, seed=42)
        trainer.initialize(base_policy)

        adapter.start_generation()
        result = trainer.run(fn, num_generations=3)

        summaries = result["generation_summaries"]
        first_mean = summaries[0]["mean_fitness"]
        last_mean = summaries[-1]["mean_fitness"]
        # Allow tiny numerical variance, but should not decrease significantly
        assert last_mean >= first_mean - 0.01

    def test_pbt_all_members_have_fitness(self, adapter, base_policy):
        """After evaluation, all members should have fitness > 0."""
        fn = make_tiered_pbt_fitness_fn(adapter)
        trainer = PBTPopulationTrainer(population_size=4, seed=42)
        trainer.initialize(base_policy)
        trainer.evaluate_generation(fn)

        for member in trainer.population:
            assert member.fitness > 0.0


# ---------------------------------------------------------------------------
# Tests: create_default_adapter
# ---------------------------------------------------------------------------


class TestCreateDefaultAdapter:
    def test_creates_adapter(self):
        adapter = create_default_adapter(str(ROOT))
        assert isinstance(adapter, ThreeTierFitnessAdapter)
        assert adapter.l2_budget == 3
        assert adapter.l0_threshold == 0.3
        assert adapter.l1_threshold == 0.5

    def test_custom_l2_budget(self):
        adapter = create_default_adapter(str(ROOT), l2_budget=5)
        assert adapter.l2_budget == 5


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_wiring_doesnt_modify_policy(self, adapter, base_policy):
        """Wiring should not modify the policy object."""
        original_hash = base_policy.policy_hash
        fn = make_tiered_pbt_fitness_fn(adapter)
        fn(base_policy)
        assert base_policy.policy_hash == original_hash  # unchanged

    def test_all_results_evaluative(self, adapter, base_policy):
        fn = make_tiered_pbt_fitness_fn(adapter)
        # The underlying TieredFitnessResult carries truth_effect=NONE
        # The wiring preserves this
        result = adapter.evaluate({
            "max_rounds": 4, "max_deep_engines": 8,
            "exploration_rate": 0.15, "temperature": 0.4,
        })
        assert result.payload()["truth_effect"] == "NONE"

    def test_no_code_modification(self):
        assert not hasattr(make_tiered_pbt_fitness_fn, "modify_code")
