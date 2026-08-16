"""METAENGINE Phase 37 — Run Real PBT Evolution with RLAIF Fitness.

This script runs a small PBT population (4 members) for 3 generations,
using a hybrid fitness function:
  - For policies that match existing Phase 33 results: use the recorded RLAIF reward
  - For novel policies: use a simulated fitness based on policy hyperparameters

This demonstrates the PBT loop end-to-end:
  1. Initialize population (base policy + 3 mutations)
  2. Evaluate fitness (RLAIF reward where available, simulated otherwise)
  3. Exploit: replace worst with clones of best
  4. Explore: mutate cloned policies
  5. Repeat for 3 generations
  6. Return champion (Pareto frontier)

Constitution preserved:
  - All policies remain SHADOW (never ACTIVE)
  - truth_effect = NONE
  - No auto-promotion
"""

from __future__ import annotations

import json
import sys
import time
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.pbt_trainer import (
    PBTPopulationTrainer,
    PopulationMember,
    PBT_VERSION,
)
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy
from metaengine.util import canonical_hash, write_json


# ---------------------------------------------------------------------------
# Fitness function — hybrid RLAIF + simulated
# ---------------------------------------------------------------------------


def make_hybrid_fitness_fn(recorded_rewards: dict[str, float]):
    """Create a fitness function that uses recorded RLAIF rewards where available,
    and simulates fitness for novel policies.

    The simulation is based on policy hyperparameters:
    - More dialectic operators → slightly higher reward (more perspectives)
    - Higher max_rounds → slightly higher reward but higher cost
    - Higher exploration_rate → higher variance (sometimes good, sometimes bad)
    - Deterministic based on policy hash (so same policy always gets same fitness)
    """
    def fitness_fn(policy: ArchitecturePolicy) -> dict[str, float]:
        policy_hash = policy.policy_hash

        # Check if we have a recorded RLAIF reward for this policy
        if policy_hash in recorded_rewards:
            reward = recorded_rewards[policy_hash]
            return {
                "reward": reward,
                "cost": 1.0,
                "latency": 20.0,
                "task_rewards": {"recorded": reward},
                "task_costs": {"recorded": 1.0},
            }

        # Simulated fitness: deterministic from policy hash + hyperparameters
        h = int(policy_hash[:16], 16)
        # Base fitness from hash (0.3 to 0.8)
        base = 0.3 + (h % 500) / 1000.0
        # Bonus for more operators (up to 0.15)
        op_bonus = min(0.15, len(policy.dialectic_operators) * 0.03)
        # Bonus for max_rounds (up to 0.1, but diminishing)
        round_bonus = min(0.1, policy.max_rounds * 0.015)
        # Exploration rate adds variance
        exploration_factor = 1.0 + (policy.exploration_rate - 0.15) * 0.5

        reward = min(1.0, max(0.0, (base + op_bonus + round_bonus) * exploration_factor))
        cost = 0.5 + policy.max_rounds * 0.1 + len(policy.dialectic_operators) * 0.05
        latency = 5.0 + policy.max_rounds * 3.0 + len(policy.dialectic_operators) * 2.0

        return {
            "reward": round(reward, 4),
            "cost": round(cost, 4),
            "latency": round(latency, 4),
            "task_rewards": {"simulated": round(reward, 4)},
            "task_costs": {"simulated": round(cost, 4)},
        }
    return fitness_fn


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 70)
    print("Phase 37 — PBT Population Trainer (Real Evolution)")
    print("=" * 70)

    out_dir = ROOT / "storage" / "phase37_pbt_evolution"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load recorded RLAIF rewards from Phase 36
    print("\n[1/5] Loading recorded RLAIF rewards from Phase 36...")
    recorded_rewards: dict[str, float] = {}
    # Phase 32 run with engine_16
    rlaif_path = ROOT / "storage" / "phase32_real_llm_run" / "engines" / "engine_16" / "RLAIF_REWARD.json"
    if rlaif_path.is_file():
        rlaif = json.loads(rlaif_path.read_text())
        # The RLAIF reward is for the engine_16 contribution, not a specific policy
        # But we can use it as the "base" fitness for the initial policy
        base_reward = rlaif.get("reward", 0.5)
        print(f"  loaded RLAIF reward for engine_16: {base_reward}")
        # We'll attribute this to the initial policy
        base_policy = initial_policy()
        recorded_rewards[base_policy.policy_hash] = base_reward
        print(f"  attributed to initial policy: {base_policy.policy_hash[:16]}...")
    else:
        base_policy = initial_policy()
        print("  no RLAIF reward found — using simulated fitness only")

    # 2. Initialize PBT trainer
    print("\n[2/5] Initializing PBT population (4 members)...")
    trainer = PBTPopulationTrainer(
        population_size=4,
        exploit_fraction=0.25,
        seed=42,
    )
    population = trainer.initialize(base_policy)
    print(f"  population size: {len(population)}")
    print(f"  seed member: {population.members[0].member_id} (unmutated)")
    for i, m in enumerate(population.members[1:], 1):
        n_mutations = len(m.mutation_history[0]["mutations"]) if m.mutation_history else 0
        print(f"  member {i}: {m.member_id} ({n_mutations} mutations)")
    print(f"  diversity: {population.diversity():.4f}")

    # 3. Run PBT for 3 generations
    print("\n[3/5] Running PBT for 3 generations...")
    fitness_fn = make_hybrid_fitness_fn(recorded_rewards)

    started = time.perf_counter()
    result = trainer.run(fitness_fn, num_generations=3)
    elapsed = time.perf_counter() - started

    print(f"\n  PBT completed in {elapsed:.2f}s")
    print(f"  generations: {result['num_generations']}")

    # 4. Show generation summaries
    print("\n[4/5] Generation summaries:")
    print(f"  {'Gen':>4} | {'Mean Fit':>10} | {'Best Fit':>10} | {'Worst Fit':>10} | {'Diversity':>10}")
    print(f"  {'-'*4} | {'-'*10} | {'-'*10} | {'-'*10} | {'-'*10}")
    for s in result["generation_summaries"]:
        print(f"  {s['generation']:>4} | {s['mean_fitness']:>10.4f} | {s['best_fitness']:>10.4f} | {s['worst_fitness']:>10.4f} | {s['diversity']:>10.4f}")

    # 5. Show champions (Pareto frontier)
    print("\n[5/5] Champions (Pareto frontier):")
    champions = result["champions"]
    print(f"  champion count: {len(champions)}")
    for c in champions:
        print(f"    {c['member_id']}: fitness={c['fitness']:.4f} cost_eff={c['cost_efficiency']:.4f} latency={c['latency']:.4f}")

    # Show final population
    print(f"\n  Final population (diversity={result['final_population']['diversity']:.4f}):")
    for m in result["final_population"]["members"]:
        print(f"    {m['member_id']}: fitness={m['fitness']:.4f} gen={m['generation']} mutations={m['mutation_count']}")

    # 6. Save results
    print(f"\n  Saving to {out_dir}...")
    (out_dir / "PBT_RESULT.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )

    # Manifest
    first_mean = result["generation_summaries"][0]["mean_fitness"]
    last_mean = result["generation_summaries"][-1]["mean_fitness"]
    improvement = last_mean - first_mean

    manifest = {
        "phase": 37,
        "title": "Population-Based Training with RLAIF Fitness",
        "pbt_version": PBT_VERSION,
        "population_size": 4,
        "num_generations": 3,
        "exploit_fraction": 0.25,
        "elapsed_seconds": round(elapsed, 2),
        "fitness_function": "hybrid_rlaif_simulated",
        "recorded_rlaif_rewards_used": len(recorded_rewards),
        "generation_summaries": result["generation_summaries"],
        "champion_count": len(champions),
        "champions": champions,
        "improvement": {
            "first_mean_fitness": first_mean,
            "last_mean_fitness": last_mean,
            "delta": round(improvement, 6),
            "improved": improvement > 0,
        },
        "constitution_compliance": result["constitution_compliance"],
        "claim_ceiling": "PBT_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
        "truth_effect": "NONE",
    }
    (out_dir / "PHASE37_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    print(f"\n{'=' * 70}")
    print(f"Phase 37 COMPLETE. PBT evolution finished.")
    print(f"  Population: 4 members, 3 generations")
    print(f"  First mean fitness: {first_mean:.4f}")
    print(f"  Last mean fitness:  {last_mean:.4f}")
    print(f"  Improvement: {improvement:+.4f} ({'IMPROVED' if improvement > 0 else 'stable/decreased'})")
    print(f"  Champions (Pareto): {len(champions)}")
    print(f"  Diversity preserved: {result['final_population']['diversity']:.4f}")
    print(f"  All policies remain SHADOW: {result['constitution_compliance']['all_policies_remain_shadow']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
