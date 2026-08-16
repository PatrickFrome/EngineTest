"""METAENGINE Phase 67 Step 3 — PBT Fitness Wiring.

Thin adapter that connects ThreeTierFitnessAdapter to PBTPopulationTrainer.

PBT expects: fitness_fn(ArchitecturePolicy) → dict with 'reward', 'cost', 'latency'
Tiered adapter: evaluate(theta) → TieredFitnessResult with .fitness, .tier, .elapsed_ms

This module bridges the two:
  1. Extract theta from ArchitecturePolicy (max_rounds, max_deep_engines, etc.)
  2. Call ThreeTierFitnessAdapter.evaluate(theta)
  3. Convert TieredFitnessResult → PBT-compatible dict

Constitution compliance:
  - Adapter is read-only (no mutation of policy or constitution)
  - truth_effect=NONE propagated
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .architecture_policy import ArchitecturePolicy
from .tiered_fitness import ThreeTierFitnessAdapter, TieredFitnessResult


def make_tiered_pbt_fitness_fn(
    adapter: ThreeTierFitnessAdapter,
    *,
    state_bus: Optional[Any] = None,  # I3: optional TrainingStateBus for publishing
) -> Callable[[ArchitecturePolicy], dict[str, float]]:
    """Create a PBT-compatible fitness function from a ThreeTierFitnessAdapter.

    Usage:
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=3)
        fitness_fn = make_tiered_pbt_fitness_fn(adapter)
        trainer = PBTPopulationTrainer(population_size=4)
        trainer.initialize(base_policy)
        trainer.run(fitness_fn, num_generations=3)

    I3: If state_bus (TrainingStateBus) is provided, each evaluation result is
    published to the bus so other trainers (ES, real_recursive) can subscribe.

    Args:
        adapter: ThreeTierFitnessAdapter instance.
        state_bus: optional TrainingStateBus to publish fitness results to.

    Returns:
        fitness_fn: callable(ArchitecturePolicy) → dict with 'reward', 'cost', 'latency'
    """
    def fitness_fn(policy: ArchitecturePolicy) -> dict[str, float]:
        # 1. Extract theta from policy (I1: temperature now comes from policy, not hardcoded)
        theta = {
            "max_rounds": float(policy.max_rounds),
            "max_deep_engines": float(policy.max_deep_engines),
            "exploration_rate": float(policy.exploration_rate),
            "temperature": float(getattr(policy, "temperature", 0.4)),  # I1: from policy
        }

        # 2. Evaluate via tiered adapter
        result = adapter.evaluate(theta)

        # I3: Publish to state bus if provided (best known so far, monotonic)
        if state_bus is not None:
            try:
                prev_best = getattr(state_bus, "tiered_fitness_best", 0.0)
                best_fitness = max(prev_best, result.fitness)
                adapter_summary = adapter.summary()
                state_bus.publish_tiered_fitness(
                    best_fitness=best_fitness,
                    mean_fitness=result.fitness,  # last result as running mean proxy
                    generation=adapter._generation,
                    l2_calls=adapter._l2_calls_this_gen,
                    tier_distribution=adapter_summary.get("tier_distribution", {}),
                    last_theta=dict(theta),
                )
            except Exception:
                # Publishing must never break evaluation (defensive)
                pass

        # 3. Convert to PBT-compatible dict
        return {
            "reward": result.fitness,
            "cost": 1.0,  # normalized cost (tiered adapter doesn't track cost)
            "latency": result.elapsed_ms / 1000.0,  # convert ms → seconds
            "task_rewards": {f"tier_{result.tier.value}": result.fitness},
            "task_costs": {f"tier_{result.tier.value}": 1.0},
            # Extra metadata for debugging
            "tier": result.tier.value,
            "l0_score": result.l0_score,
            "l1_score": result.l1_score,
            "l2_score": result.l2_score,
            "cached": result.cached,
        }

    return fitness_fn


def make_tiered_es_fitness_fn(
    adapter: ThreeTierFitnessAdapter,
) -> Callable[[dict[str, float]], float]:
    """Create an ES-compatible fitness function from a ThreeTierFitnessAdapter.

    Usage:
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=3)
        fitness_fn = make_tiered_es_fitness_fn(adapter)
        optimizer = ESHyperparameterOptimizer()
        optimizer.run(fitness_fn, num_generations=10)

    Args:
        adapter: ThreeTierFitnessAdapter instance.

    Returns:
        fitness_fn: callable(theta: dict) → float (0-1)
    """
    def fitness_fn(theta: dict[str, float]) -> float:
        result = adapter.evaluate(theta)
        return result.fitness

    return fitness_fn


def create_default_adapter(
    root: str,
    *,
    l2_budget: int = 3,
) -> ThreeTierFitnessAdapter:
    """Create a default ThreeTierFitnessAdapter with sensible defaults.

    Args:
        root: MetaEngine root directory.
        l2_budget: max real LLM evaluations per generation.

    Returns:
        Configured ThreeTierFitnessAdapter.
    """
    return ThreeTierFitnessAdapter(
        root=root,
        l2_budget=l2_budget,
        l0_threshold=0.3,
        l1_threshold=0.5,
        cache_size=50,
    )
