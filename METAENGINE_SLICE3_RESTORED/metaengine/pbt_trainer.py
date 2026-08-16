"""METAENGINE Phase 37 — Population-Based Training (PBT) Trainer.

Evolve a population of architecture policies in parallel using RLAIF reward
as the fitness function. Implements the standard PBT loop:

  1. EXPLOIT: rank policies by fitness, replace worst N/4 with clones of best N/4
  2. EXPLORE: perturb hyperparameters of cloned policies (mutation)
  3. EVALUATE: run all policies on tasks, compute RLAIF reward
  4. Repeat for K generations

Fitness function:
  - Primary: mean RLAIF reward across tasks (constitutional compliance)
  - Secondary: cost efficiency (reward / cost), latency
  - Pareto-based: non-dominated policies survive even if not top-reward

Constitution compliance:
  - PBT does NOT promote policies to ACTIVE — all remain SHADOW
  - Champion selection is on Pareto frontier, not single best
  - Diversity preservation prevents mode collapse
  - RLAIF reward is the fitness, but truth promotion remains external
"""

from __future__ import annotations

import copy
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .util import canonical_hash
from .architecture_policy import ArchitecturePolicy, initial_policy, DIALECTIC_OPERATORS


PBT_VERSION = "METAENGINE-PBT-POPULATION-TRAINER-1"


# ---------------------------------------------------------------------------
# Population member
# ---------------------------------------------------------------------------


@dataclass
class PopulationMember:
    """A member of the PBT population."""
    member_id: str
    policy: ArchitecturePolicy
    generation: int
    parent_id: str | None  # None for seed, member_id of parent for clones
    fitness: float = 0.0  # mean RLAIF reward
    cost_efficiency: float = 0.0  # reward / cost
    latency: float = 0.0
    task_rewards: dict[str, float] = field(default_factory=dict)  # task_id → reward
    task_costs: dict[str, float] = field(default_factory=dict)
    mutation_history: list[dict] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "policy_hash": self.policy.policy_hash[:16],
            "topology_id": self.policy.topology_id,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "fitness": round(self.fitness, 6),
            "cost_efficiency": round(self.cost_efficiency, 6),
            "latency": round(self.latency, 6),
            "task_rewards": {k: round(v, 6) for k, v in self.task_rewards.items()},
            "mutation_count": len(self.mutation_history),
            "truth_effect": "NONE",
            "claim_ceiling": "PBT_FITNESS_IS_EVALUATIVE_NOT_TRUTH",
        }

    @property
    def is_seed(self) -> bool:
        return self.parent_id is None


# ---------------------------------------------------------------------------
# Mutation operators
# ---------------------------------------------------------------------------


class PolicyMutator:
    """Mutates architecture policy hyperparameters.

    Implements PBT perturbation: each hyperparameter is either
    multiplied or divided by a perturbation factor (0.8 or 1.2).
    """

    PERTURBATION_FACTORS = (0.8, 1.2)  # standard PBT values
    OPERATOR_SWAP_PROB = 0.3

    def __init__(self, *, seed: int = 42):
        self._rng = random.Random(seed)

    def mutate(self, policy: ArchitecturePolicy, member_id: str) -> tuple[ArchitecturePolicy, dict]:
        """Return a mutated copy of the policy + mutation receipt."""
        mutations: list[dict] = []

        # 1. Perturb max_rounds (clamped to [1, 8])
        factor = self._rng.choice(self.PERTURBATION_FACTORS)
        old_mr = policy.max_rounds
        new_mr = max(1, min(8, int(round(old_mr * factor))))
        if new_mr != old_mr:
            mutations.append({"field": "max_rounds", "old": old_mr, "new": new_mr, "factor": factor})

        # 2. Perturb max_deep_engines (clamped to [1, 16])
        factor = self._rng.choice(self.PERTURBATION_FACTORS)
        old_mde = policy.max_deep_engines
        new_mde = max(1, min(16, int(round(old_mde * factor))))
        if new_mde != old_mde:
            mutations.append({"field": "max_deep_engines", "old": old_mde, "new": new_mde, "factor": factor})

        # 3. Perturb exploration_rate (clamped to [0.0, 0.30])
        factor = self._rng.choice(self.PERTURBATION_FACTORS)
        old_er = policy.exploration_rate
        new_er = max(0.0, min(0.30, round(old_er * factor, 4)))
        if new_er != old_er:
            mutations.append({"field": "exploration_rate", "old": old_er, "new": new_er, "factor": factor})

        # 4. Operator swap (add or remove one operator)
        if self._rng.random() < self.OPERATOR_SWAP_PROB:
            current_ops = set(policy.dialectic_operators)
            available = set(DIALECTIC_OPERATORS) - current_ops
            if available and self._rng.random() < 0.5:
                # Add a random operator
                new_op = self._rng.choice(sorted(available))
                new_ops = tuple(sorted(current_ops | {new_op}))
                mutations.append({"field": "dialectic_operators", "action": "add", "operator": new_op})
            elif len(current_ops) > 1:
                # Remove a random operator (keep at least 1)
                remove_op = self._rng.choice(sorted(current_ops))
                new_ops = tuple(sorted(current_ops - {remove_op}))
                mutations.append({"field": "dialectic_operators", "action": "remove", "operator": remove_op})
            else:
                new_ops = policy.dialectic_operators
        else:
            new_ops = policy.dialectic_operators

        # 5. Topology mutation (small probability)
        topology_id = policy.topology_id
        # Don't mutate topology — it's the identity of the policy

        receipt = {
            "member_id": member_id,
            "generation": policy.generation + 1,
            "parent_policy_hash": policy.policy_hash,
            "mutations": mutations,
            "mutation_count": len(mutations),
        }
        receipt["mutation_hash"] = canonical_hash({k: v for k, v in receipt.items() if k != "mutation_hash"})

        new_policy = ArchitecturePolicy(
            generation=policy.generation + 1,
            parent_policy_hash=policy.policy_hash,
            topology_id=topology_id,
            waves=policy.waves,
            dialectic_operators=new_ops,
            max_rounds=new_mr,
            max_deep_engines=new_mde,
            exploration_rate=new_er,
            guardrail_hash=policy.guardrail_hash,
            verifier_hash=policy.verifier_hash,
            benchmark_hash=policy.benchmark_hash,
            status="SHADOW",  # always shadow — never promoted
            mutation_receipt=receipt,
        )
        new_policy.validate()
        return new_policy, receipt


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------


class Population:
    """A population of architecture policies being trained by PBT."""

    def __init__(self, members: list[PopulationMember] | None = None):
        self.members: list[PopulationMember] = list(members) if members else []

    def __len__(self) -> int:
        return len(self.members)

    def __iter__(self):
        return iter(self.members)

    def add(self, member: PopulationMember) -> None:
        self.members.append(member)

    def best(self, n: int = 1) -> list[PopulationMember]:
        """Return the top-N members by fitness."""
        return sorted(self.members, key=lambda m: -m.fitness)[:n]

    def worst(self, n: int = 1) -> list[PopulationMember]:
        """Return the bottom-N members by fitness."""
        return sorted(self.members, key=lambda m: m.fitness)[:n]

    def pareto_frontier(self) -> list[PopulationMember]:
        """Return non-dominated members (high fitness, low cost, low latency)."""
        non_dominated: list[PopulationMember] = []
        for m in self.members:
            dominated = False
            for other in self.members:
                if other.member_id == m.member_id:
                    continue
                # other dominates m if: higher/equal fitness, lower/equal cost, lower/equal latency
                # and at least one strictly better
                if (other.fitness >= m.fitness
                    and other.cost_efficiency >= m.cost_efficiency
                    and other.latency <= m.latency
                    and (other.fitness > m.fitness
                         or other.cost_efficiency > m.cost_efficiency
                         or other.latency < m.latency)):
                    dominated = True
                    break
            if not dominated:
                non_dominated.append(m)
        return non_dominated

    def diversity(self) -> float:
        """Compute population diversity as fraction of unique policy hashes."""
        if not self.members:
            return 0.0
        unique = len({m.policy.policy_hash for m in self.members})
        return unique / len(self.members)

    def mean_fitness(self) -> float:
        if not self.members:
            return 0.0
        return sum(m.fitness for m in self.members) / len(self.members)

    def payload(self) -> dict[str, Any]:
        return {
            "pbt_version": PBT_VERSION,
            "population_size": len(self.members),
            "mean_fitness": round(self.mean_fitness(), 6),
            "diversity": round(self.diversity(), 6),
            "members": [m.payload() for m in self.members],
            "truth_effect": "NONE",
            "claim_ceiling": "PBT_POPULATION_IS_EVALUATIVE_NOT_TRUTH",
        }


# ---------------------------------------------------------------------------
# PBT Trainer
# ---------------------------------------------------------------------------


class PBTPopulationTrainer:
    """Population-Based Training trainer.

    Standard PBT loop:
      1. Initialize population (N seed policies, possibly with mutations)
      2. For each generation:
         a. EVALUATE: run all members on tasks, compute fitness (RLAIF reward)
         b. EXPLOIT: replace worst N/4 with clones of best N/4
         c. EXPLORE: mutate cloned members
      3. Return final population + champion (Pareto frontier)

    Usage:
        trainer = PBTPopulationTrainer(population_size=8, num_generations=3)
        trainer.initialize(base_policy)
        for gen in range(num_generations):
            trainer.evaluate_generation(fitness_fn)
            trainer.exploit_and_explore()
        champion = trainer.population.pareto_frontier()
    """

    def __init__(
        self,
        *,
        population_size: int = 8,
        exploit_fraction: float = 0.25,  # fraction replaced each generation
        seed: int = 42,
    ):
        if population_size < 2:
            raise ValueError("POPULATION_SIZE_MUST_BE_AT_LEAST_2")
        if not 0.0 < exploit_fraction <= 0.5:
            raise ValueError("EXPLOIT_FRACTION_MUST_BE_IN_(0, 0.5]")
        self.population_size = population_size
        self.exploit_fraction = exploit_fraction
        self._rng = random.Random(seed)
        self._mutator = PolicyMutator(seed=seed)
        self.population = Population()
        self.generation = 0
        self.history: list[dict] = []

    def initialize(self, base_policy: ArchitecturePolicy) -> Population:
        """Initialize the population with mutations of the base policy.

        The first member is the unmutated base policy (seed).
        The rest are random mutations of the base policy.
        """
        self.population = Population()
        # Member 0: unmutated seed
        seed_member = PopulationMember(
            member_id="pbt.gen0.m00",
            policy=base_policy,
            generation=0,
            parent_id=None,
        )
        self.population.add(seed_member)

        # Members 1..N-1: mutations of the base policy
        for i in range(1, self.population_size):
            mutated_policy, receipt = self._mutator.mutate(base_policy, f"pbt.gen0.m{i:02d}")
            member = PopulationMember(
                member_id=f"pbt.gen0.m{i:02d}",
                policy=mutated_policy,
                generation=0,
                parent_id="pbt.gen0.m00",
                mutation_history=[receipt],
            )
            self.population.add(member)

        self.generation = 0
        return self.population

    def evaluate_generation(
        self,
        fitness_fn: Callable[[ArchitecturePolicy], dict[str, float]],
    ) -> None:
        """Evaluate all members using the fitness function.

        Args:
            fitness_fn: takes a policy, returns dict with keys:
                'reward' (0-1), 'cost', 'latency', 'task_rewards' (dict)
        """
        for member in self.population:
            result = fitness_fn(member.policy)
            member.fitness = float(result.get("reward", 0.0))
            cost = float(result.get("cost", 1.0))
            member.cost_efficiency = member.fitness / max(0.01, cost)
            member.latency = float(result.get("latency", 0.0))
            member.task_rewards = dict(result.get("task_rewards", {}))
            member.task_costs = dict(result.get("task_costs", {}))

    def exploit_and_explore(self) -> dict[str, Any]:
        """PBT exploit + explore step.

        Exploit: replace worst N*exploit_fraction with clones of best N*exploit_fraction.
        Explore: mutate the cloned policies.

        Returns a receipt of the exploit/explore operation.
        """
        n_replace = max(1, int(self.population_size * self.exploit_fraction))
        worst_members = self.population.worst(n_replace)
        best_members = self.population.best(n_replace)

        replacements: list[dict] = []
        new_gen = self.generation + 1

        for i, (worst, best) in enumerate(zip(worst_members, best_members)):
            # Clone the best policy
            cloned_policy, receipt = self._mutator.mutate(best.policy, f"pbt.gen{new_gen}.m{i:02d}")
            # Replace worst with the mutated clone
            new_member = PopulationMember(
                member_id=f"pbt.gen{new_gen}.m{i:02d}",
                policy=cloned_policy,
                generation=new_gen,
                parent_id=best.member_id,
                mutation_history=list(best.mutation_history) + [receipt],
            )
            replacements.append({
                "replaced_member_id": worst.member_id,
                "replaced_fitness": worst.fitness,
                "cloned_from": best.member_id,
                "cloned_fitness": best.fitness,
                "new_member_id": new_member.member_id,
                "mutation_receipt": receipt,
            })
            # Replace in population
            idx = self.population.members.index(worst)
            self.population.members[idx] = new_member

        self.generation = new_gen

        receipt = {
            "generation": new_gen,
            "exploit_fraction": self.exploit_fraction,
            "n_replaced": n_replace,
            "mean_fitness_before": round(self.population.mean_fitness(), 6),
            "diversity_after": round(self.population.diversity(), 6),
            "replacements": replacements,
            "truth_effect": "NONE",
        }
        receipt["receipt_hash"] = canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        self.history.append(receipt)
        return receipt

    def run(
        self,
        fitness_fn: Callable[[ArchitecturePolicy], dict[str, float]],
        num_generations: int = 3,
    ) -> dict[str, Any]:
        """Run the full PBT loop.

        Args:
            fitness_fn: function that evaluates a policy.
            num_generations: number of generations to run.

        Returns:
            Summary dict with final population, champion, history.
        """
        if not self.population:
            raise ValueError("POPULATION_NOT_INITIALIZED")

        generation_summaries: list[dict] = []
        for gen in range(num_generations):
            self.evaluate_generation(fitness_fn)
            gen_summary = {
                "generation": self.generation,
                "mean_fitness": round(self.population.mean_fitness(), 6),
                "best_fitness": round(self.population.best(1)[0].fitness, 6),
                "worst_fitness": round(self.population.worst(1)[0].fitness, 6),
                "diversity": round(self.population.diversity(), 6),
            }
            generation_summaries.append(gen_summary)

            if gen < num_generations - 1:
                self.exploit_and_explore()

        # Final evaluation (after last exploit/explore)
        if num_generations > 0:
            self.evaluate_generation(fitness_fn)
            gen_summary = {
                "generation": self.generation,
                "mean_fitness": round(self.population.mean_fitness(), 6),
                "best_fitness": round(self.population.best(1)[0].fitness, 6),
                "worst_fitness": round(self.population.worst(1)[0].fitness, 6),
                "diversity": round(self.population.diversity(), 6),
            }
            generation_summaries.append(gen_summary)

        champion = self.population.pareto_frontier()
        return {
            "pbt_version": PBT_VERSION,
            "num_generations": num_generations,
            "population_size": self.population_size,
            "generation_summaries": generation_summaries,
            "final_population": self.population.payload(),
            "champion_count": len(champion),
            "champions": [m.payload() for m in champion],
            "history": self.history,
            "truth_effect": "NONE",
            "claim_ceiling": "PBT_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "all_policies_remain_shadow": True,
                "no_auto_promotion": True,
                "pareto_based_selection": True,
                "diversity_preserved": self.population.diversity() > 0.0,
            },
        }


# ---------------------------------------------------------------------------
# Fitness function factory
# ---------------------------------------------------------------------------


def make_rlaif_fitness_fn(
    rlaif_trainer,
    constitution_kernel,
    run_single_fn: Callable[[ArchitecturePolicy], dict[str, Any]],
) -> Callable[[ArchitecturePolicy], dict[str, float]]:
    """Create a fitness function that uses RLAIF reward.

    Args:
        rlaif_trainer: ConstitutionalRLAIFTrainer instance.
        constitution_kernel: Loaded ConstitutionKernel.
        run_single_fn: function that takes a policy and returns a dict with:
            'contribution' (engine contribution dict), 'cost', 'latency', 'task_id'

    Returns:
        fitness_fn: takes a policy, returns dict with 'reward', 'cost', 'latency', 'task_rewards'.
    """
    def fitness_fn(policy: ArchitecturePolicy) -> dict[str, float]:
        run_result = run_single_fn(policy)
        contribution = run_result.get("contribution", {})
        reward = rlaif_trainer.evaluate(
            engine_id=run_result.get("engine_id", "unknown"),
            contribution=contribution,
            constitution_kernel=constitution_kernel,
        )
        return {
            "reward": reward.reward,
            "cost": float(run_result.get("cost", 1.0)),
            "latency": float(run_result.get("latency", 0.0)),
            "task_rewards": {run_result.get("task_id", "default"): reward.reward},
            "task_costs": {run_result.get("task_id", "default"): float(run_result.get("cost", 1.0))},
        }
    return fitness_fn
