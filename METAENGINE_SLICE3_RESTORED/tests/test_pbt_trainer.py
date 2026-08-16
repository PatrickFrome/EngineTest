"""Tests for Phase 37 — PBT Population Trainer."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.pbt_trainer import (
    PBTPopulationTrainer,
    PopulationMember,
    Population,
    PolicyMutator,
    PBT_VERSION,
    make_rlaif_fitness_fn,
)
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_policy():
    return initial_policy()


@pytest.fixture
def mutator():
    return PolicyMutator(seed=42)


@pytest.fixture
def trainer():
    return PBTPopulationTrainer(population_size=4, exploit_fraction=0.25, seed=42)


# ---------------------------------------------------------------------------
# Tests: PolicyMutator
# ---------------------------------------------------------------------------


class TestPolicyMutator:
    """Test the mutation operator."""

    def test_mutate_returns_new_policy(self, mutator, base_policy):
        new_policy, receipt = mutator.mutate(base_policy, "test.m00")
        assert new_policy is not base_policy
        assert new_policy.generation == base_policy.generation + 1
        assert new_policy.parent_policy_hash == base_policy.policy_hash
        assert new_policy.status == "SHADOW"

    def test_mutate_receipt_has_hash(self, mutator, base_policy):
        _, receipt = mutator.mutate(base_policy, "test.m00")
        assert "mutation_hash" in receipt
        assert receipt["mutation_hash"] != ""
        assert receipt["member_id"] == "test.m00"
        assert receipt["mutation_count"] == len(receipt["mutations"])

    def test_mutate_clamps_max_rounds(self, mutator):
        # Create policy with max_rounds at boundary
        pol = ArchitecturePolicy(
            generation=0, parent_policy_hash=None,
            topology_id="TEST", waves=(("engine_01",),),
            dialectic_operators=("SOURCE_READING",),
            max_rounds=8, max_deep_engines=8,  # at upper bound
            exploration_rate=0.30,  # at upper bound
            status="SHADOW",
            mutation_receipt={},
        )
        pol.validate()
        new_policy, _ = mutator.mutate(pol, "test.boundary")
        assert 1 <= new_policy.max_rounds <= 8
        assert 1 <= new_policy.max_deep_engines <= 16
        assert 0.0 <= new_policy.exploration_rate <= 0.30

    def test_mutate_clamps_lower_bounds(self, mutator):
        pol = ArchitecturePolicy(
            generation=0, parent_policy_hash=None,
            topology_id="TEST", waves=(("engine_01",),),
            dialectic_operators=("SOURCE_READING",),
            max_rounds=1, max_deep_engines=1,  # at lower bound
            exploration_rate=0.0,
            status="SHADOW",
            mutation_receipt={},
        )
        pol.validate()
        new_policy, _ = mutator.mutate(pol, "test.lower")
        assert new_policy.max_rounds >= 1
        assert new_policy.max_deep_engines >= 1
        assert new_policy.exploration_rate >= 0.0

    def test_mutate_is_deterministic_with_seed(self, base_policy):
        m1 = PolicyMutator(seed=42)
        m2 = PolicyMutator(seed=42)
        p1, _ = m1.mutate(base_policy, "test")
        p2, _ = m2.mutate(base_policy, "test")
        assert p1.policy_hash == p2.policy_hash


# ---------------------------------------------------------------------------
# Tests: Population
# ---------------------------------------------------------------------------


class TestPopulation:
    """Test the Population container."""

    def test_empty_population(self):
        pop = Population()
        assert len(pop) == 0
        assert pop.mean_fitness() == 0.0
        assert pop.diversity() == 0.0

    def test_add_member(self, base_policy):
        pop = Population()
        m = PopulationMember(member_id="m00", policy=base_policy, generation=0, parent_id=None)
        pop.add(m)
        assert len(pop) == 1

    def test_best_worst_by_fitness(self, base_policy):
        pop = Population()
        for i, fitness in enumerate([0.3, 0.9, 0.5, 0.7]):
            m = PopulationMember(
                member_id=f"m{i}", policy=base_policy, generation=0, parent_id=None,
                fitness=fitness,
            )
            pop.add(m)
        best = pop.best(1)
        worst = pop.worst(1)
        assert best[0].fitness == 0.9
        assert worst[0].fitness == 0.3

    def test_diversity_unique_hashes(self, base_policy, mutator):
        pop = Population()
        # Add base policy
        pop.add(PopulationMember(member_id="m0", policy=base_policy, generation=0, parent_id=None))
        # Add 3 mutations (different hashes)
        for i in range(1, 4):
            p, _ = mutator.mutate(base_policy, f"m{i}")
            pop.add(PopulationMember(member_id=f"m{i}", policy=p, generation=0, parent_id="m0"))
        diversity = pop.diversity()
        assert 0.0 < diversity <= 1.0

    def test_pareto_frontier(self, base_policy):
        pop = Population()
        # Member A: high fitness, high cost
        pop.add(PopulationMember(
            member_id="A", policy=base_policy, generation=0, parent_id=None,
            fitness=0.9, cost_efficiency=0.5, latency=10.0,
        ))
        # Member B: low fitness, low cost
        pop.add(PopulationMember(
            member_id="B", policy=base_policy, generation=0, parent_id=None,
            fitness=0.3, cost_efficiency=2.0, latency=2.0,
        ))
        # Member C: dominated by A (lower fitness, lower cost-eff, higher latency)
        pop.add(PopulationMember(
            member_id="C", policy=base_policy, generation=0, parent_id=None,
            fitness=0.8, cost_efficiency=0.4, latency=12.0,
        ))
        frontier = pop.pareto_frontier()
        frontier_ids = {m.member_id for m in frontier}
        # A and B should be on Pareto frontier; C is dominated by A
        assert "A" in frontier_ids
        assert "B" in frontier_ids
        assert "C" not in frontier_ids

    def test_mean_fitness(self, base_policy):
        pop = Population()
        for f in [0.2, 0.4, 0.6, 0.8]:
            pop.add(PopulationMember(
                member_id=f"m{f}", policy=base_policy, generation=0, parent_id=None,
                fitness=f,
            ))
        assert pop.mean_fitness() == 0.5


# ---------------------------------------------------------------------------
# Tests: PBTPopulationTrainer
# ---------------------------------------------------------------------------


class TestPBTPopulationTrainer:
    """Test the PBT trainer."""

    def test_initialize_creates_population(self, trainer, base_policy):
        pop = trainer.initialize(base_policy)
        assert len(pop) == 4
        assert pop.members[0].is_seed  # first is unmutated
        assert pop.members[0].parent_id is None
        # Rest have parents
        for m in pop.members[1:]:
            assert m.parent_id == "pbt.gen0.m00"

    def test_population_size_validation(self):
        with pytest.raises(ValueError, match="POPULATION_SIZE_MUST_BE_AT_LEAST_2"):
            PBTPopulationTrainer(population_size=1)

    def test_exploit_fraction_validation(self):
        with pytest.raises(ValueError, match="EXPLOIT_FRACTION_MUST_BE_IN"):
            PBTPopulationTrainer(exploit_fraction=0.6)

    def test_evaluate_generation_sets_fitness(self, trainer, base_policy):
        trainer.initialize(base_policy)
        # Mock fitness function
        def mock_fitness(policy):
            return {"reward": 0.7, "cost": 1.0, "latency": 5.0, "task_rewards": {"t1": 0.7}}
        trainer.evaluate_generation(mock_fitness)
        for m in trainer.population:
            assert m.fitness == 0.7
            assert m.cost_efficiency == 0.7  # 0.7 / 1.0
            assert m.latency == 5.0

    def test_exploit_and_explore_replaces_worst(self, trainer, base_policy):
        trainer.initialize(base_policy)
        # Set diverse fitness
        for i, m in enumerate(trainer.population):
            m.fitness = [0.1, 0.2, 0.8, 0.9][i]
        # Population size 4, exploit_fraction 0.25 → replace 1
        receipt = trainer.exploit_and_explore()
        assert receipt["n_replaced"] == 1
        assert receipt["generation"] == 1
        # The worst member (fitness=0.1) should be replaced
        fitnesses = [m.fitness for m in trainer.population]
        assert 0.1 not in fitnesses  # worst was replaced
        # The new member should have generation 1
        new_members = [m for m in trainer.population if m.generation == 1]
        assert len(new_members) == 1

    def test_run_returns_summary(self, trainer, base_policy):
        trainer.initialize(base_policy)
        # Mock fitness function with variation
        call_count = [0]
        def mock_fitness(policy):
            call_count[0] += 1
            # Vary reward by policy hash for diversity
            r = 0.3 + (hash(policy.policy_hash) % 100) / 200.0
            return {"reward": r, "cost": 1.0, "latency": 5.0, "task_rewards": {"t1": r}}
        result = trainer.run(mock_fitness, num_generations=2)
        assert result["pbt_version"] == PBT_VERSION
        assert result["num_generations"] == 2
        assert len(result["generation_summaries"]) >= 2
        assert "champions" in result
        assert "final_population" in result
        assert result["constitution_compliance"]["all_policies_remain_shadow"]

    def test_run_without_initialize_raises(self, trainer):
        with pytest.raises(ValueError, match="POPULATION_NOT_INITIALIZED"):
            trainer.run(lambda p: {"reward": 0.5}, num_generations=1)

    def test_all_policies_remain_shadow(self, trainer, base_policy):
        trainer.initialize(base_policy)
        def mock_fitness(policy):
            return {"reward": 0.5, "cost": 1.0, "latency": 1.0}
        trainer.run(mock_fitness, num_generations=2)
        for m in trainer.population:
            assert m.policy.status == "SHADOW"

    def test_history_accumulates(self, trainer, base_policy):
        trainer.initialize(base_policy)
        def mock_fitness(policy):
            return {"reward": 0.5, "cost": 1.0, "latency": 1.0}
        trainer.run(mock_fitness, num_generations=3)
        # Should have 2 exploit/explore receipts (gen 1 and gen 2)
        assert len(trainer.history) == 2

    def test_fitness_improves_or_stable(self, trainer, base_policy):
        """PBT should not DECREASE mean fitness (exploit replaces worst with best)."""
        trainer.initialize(base_policy)
        # Give each member a fixed fitness based on member_id
        def mock_fitness(policy):
            # Use policy hash to determine fitness (deterministic)
            h = int(policy.policy_hash[:8], 16)
            return {"reward": 0.3 + (h % 70) / 100.0, "cost": 1.0, "latency": 1.0}
        result = trainer.run(mock_fitness, num_generations=3)
        summaries = result["generation_summaries"]
        # Mean fitness should not decrease between first and last generation
        # (exploit replaces worst with best, so mean should improve or stay)
        first_mean = summaries[0]["mean_fitness"]
        last_mean = summaries[-1]["mean_fitness"]
        assert last_mean >= first_mean - 0.01  # allow tiny numerical variance


# ---------------------------------------------------------------------------
# Tests: make_rlaif_fitness_fn
# ---------------------------------------------------------------------------


class TestRLAIFFitnessFunction:
    """Test the RLAIF fitness function factory."""

    def test_fitness_fn_returns_reward(self, base_policy):
        # Mock RLAIF trainer
        mock_trainer = MagicMock()
        mock_reward = MagicMock()
        mock_reward.reward = 0.75
        mock_trainer.evaluate.return_value = mock_reward

        mock_kernel = MagicMock()

        def mock_run_single(policy):
            return {
                "engine_id": "engine_16",
                "contribution": {"canonical": {"response_text": "test"}},
                "cost": 1.0,
                "latency": 5.0,
                "task_id": "sealed-000",
            }

        fitness_fn = make_rlaif_fitness_fn(mock_trainer, mock_kernel, mock_run_single)
        result = fitness_fn(base_policy)
        assert result["reward"] == 0.75
        assert result["cost"] == 1.0
        assert result["latency"] == 5.0
        assert result["task_rewards"]["sealed-000"] == 0.75

    def test_fitness_fn_handles_missing_fields(self, base_policy):
        mock_trainer = MagicMock()
        mock_reward = MagicMock()
        mock_reward.reward = 0.5
        mock_trainer.evaluate.return_value = mock_reward

        mock_kernel = MagicMock()

        def mock_run_single(policy):
            return {}  # empty result

        fitness_fn = make_rlaif_fitness_fn(mock_trainer, mock_kernel, mock_run_single)
        result = fitness_fn(base_policy)
        assert result["reward"] == 0.5
        assert result["cost"] == 1.0  # default
        assert result["latency"] == 0.0  # default


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that PBT preserves constitution."""

    def test_all_members_carry_truth_effect_none(self, trainer, base_policy):
        trainer.initialize(base_policy)
        for m in trainer.population:
            payload = m.payload()
            assert payload["truth_effect"] == "NONE"
            assert payload["claim_ceiling"] == "PBT_FITNESS_IS_EVALUATIVE_NOT_TRUTH"

    def test_population_payload_has_truth_effect_none(self, trainer, base_policy):
        trainer.initialize(base_policy)
        payload = trainer.population.payload()
        assert payload["truth_effect"] == "NONE"
        assert payload["claim_ceiling"] == "PBT_POPULATION_IS_EVALUATIVE_NOT_TRUTH"

    def test_no_member_has_status_active(self, trainer, base_policy):
        trainer.initialize(base_policy)
        def mock_fitness(policy):
            return {"reward": 0.9, "cost": 0.5, "latency": 1.0}
        trainer.run(mock_fitness, num_generations=2)
        for m in trainer.population:
            assert m.policy.status == "SHADOW"  # never ACTIVE
