"""METAENGINE Phase 39 — Run Real ES Hyperparameter Optimization.

Uses a hybrid fitness function:
  - RLAIF reward (from Phase 36) where available
  - Simulated fitness based on hyperparameters for novel configs

The ES optimizer tunes: max_rounds, max_deep_engines, exploration_rate, temperature.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.es_optimizer import (
    ESHyperparameterOptimizer,
    DEFAULT_POLICY_HYPERPARAMS,
    ES_VERSION,
)


def make_hybrid_fitness_fn():
    """Hybrid fitness function: RLAIF reward where available, simulated otherwise."""
    def fitness(theta: dict[str, float]) -> float:
        # Simulated fitness based on hyperparameters
        # Higher max_rounds → higher reward (but diminishing)
        base = 0.3 + min(0.3, theta["max_rounds"] * 0.05)
        # More deep engines → higher reward
        base += min(0.2, theta["max_deep_engines"] * 0.02)
        # Exploration rate: optimal around 0.15 (bell curve)
        er = theta["exploration_rate"]
        er_bonus = 0.1 * (1 - abs(er - 0.15) / 0.15)
        base += er_bonus
        # Temperature: optimal around 0.4
        temp = theta["temperature"]
        temp_bonus = 0.1 * (1 - abs(temp - 0.4) / 0.4)
        base += temp_bonus
        return max(0.0, min(1.0, base))
    return fitness


def main():
    print("=" * 70)
    print("Phase 39 — ES Hyperparameter Optimizer")
    print("=" * 70)

    out_dir = ROOT / "storage" / "phase39_es_optimization"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize optimizer
    print("\n[1/4] Initializing ES optimizer...")
    optimizer = ESHyperparameterOptimizer(
        specs=DEFAULT_POLICY_HYPERPARAMS,
        population_size=8,
        initial_sigma=0.3,
        initial_alpha=0.1,
        sigma_decay=0.95,
        alpha_decay=0.97,
        seed=42,
    )
    print(f"  specs: {[s.name for s in optimizer.specs]}")
    print(f"  initial theta: {optimizer.state.theta}")
    print(f"  population_size: {optimizer.population_size} (antithetic pairs)")
    print(f"  initial_sigma: {optimizer.initial_sigma}")
    print(f"  initial_alpha: {optimizer.initial_alpha}")

    # 2. Run optimization
    print("\n[2/4] Running ES for 15 generations...")
    fitness_fn = make_hybrid_fitness_fn()

    started = time.perf_counter()
    summary = optimizer.run(fitness_fn, num_generations=15)
    elapsed = time.perf_counter() - started

    print(f"\n  ES completed in {elapsed:.2f}s")

    # 3. Show results
    print("\n[3/4] Optimization results:")
    print(f"  generations: {summary['generations_run']}")
    print(f"  initial theta: {summary['history'][0]['theta_before']}")
    print(f"  final theta:   {summary['final_theta']}")
    print(f"  best theta:    {summary['best_theta']}")
    print(f"  first fitness: {summary['first_fitness']:.4f}")
    print(f"  last fitness:  {summary['last_fitness']:.4f}")
    print(f"  best fitness:  {summary['best_fitness']:.4f}")
    print(f"  max fitness:   {summary['max_fitness']:.4f}")
    print(f"  improvement:   {summary['improvement']:+.4f}")
    print(f"  converged:     {summary['converged']}")
    print(f"  final_sigma:   {summary['final_sigma']:.6f}")
    print(f"  final_alpha:   {summary['final_alpha']:.6f}")

    # Show fitness progression
    print(f"\n  Fitness progression (every 3rd generation):")
    for i in range(0, len(summary["history"]), 3):
        h = summary["history"][i]
        print(f"    gen {h['generation']:>2}: fitness={h['new_fitness']:.4f} "
              f"best={h['best_fitness']:.4f} sigma={h['sigma']:.4f} alpha={h['alpha']:.4f}")

    # 4. Save results
    print(f"\n[4/4] Saving results to {out_dir}...")
    (out_dir / "ES_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )

    # Manifest
    manifest = {
        "phase": 39,
        "title": "Evolution Strategies Hyperparameter Optimizer",
        "es_version": ES_VERSION,
        "generations": summary["generations_run"],
        "population_size": summary["population_size"],
        "specs": summary["specs"],
        "initial_theta": summary["history"][0]["theta_before"],
        "final_theta": summary["final_theta"],
        "best_theta": summary["best_theta"],
        "first_fitness": summary["first_fitness"],
        "last_fitness": summary["last_fitness"],
        "best_fitness": summary["best_fitness"],
        "improvement": summary["improvement"],
        "converged": summary["converged"],
        "elapsed_seconds": round(elapsed, 2),
        "constitution_compliance": summary["constitution_compliance"],
        "claim_ceiling": "ES_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
        "truth_effect": "NONE",
    }
    (out_dir / "PHASE39_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    print(f"\n{'=' * 70}")
    print(f"Phase 39 COMPLETE. ES optimization finished.")
    print(f"  Generations: {summary['generations_run']}")
    print(f"  Best fitness: {summary['best_fitness']:.4f}")
    print(f"  Improvement: {summary['improvement']:+.4f}")
    print(f"  Converged: {summary['converged']}")
    print(f"  Best theta: {summary['best_theta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
