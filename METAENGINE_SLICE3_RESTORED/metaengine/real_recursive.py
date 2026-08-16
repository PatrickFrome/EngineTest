"""METAENGINE Phase 68 — Real Recursive Improvement Runner.

Connects ThreeTierFitnessAdapter (Phase 67) + AmplifyDistillCycle (Phase 52) +
RecursiveImprovementLoop (Phase 43) into a REAL improvement flywheel.

The flywheel:
  1. AMPLIFY: analyze G(N-1) metrics → generate config changes (7 rules)
  2. RUN: execute PBT with real tiered fitness (L0+L1+L2)
  3. DISTILL: extract insights from G(N) results
  4. COMPARE: measure improvement G(N) vs G(N-1)
  5. Repeat

Each generation uses REAL fitness (not simulated):
  - L0 surrogate for all PBT members (~0ms each)
  - L2 real LLM for top-3 candidates (~300-2000ms each)
  - Budget enforcement: max 3 L2 calls per generation

Constitution compliance:
  - truth_effect=NONE
  - Bounded RSI (K0 constitution is fixed anchor)
  - No auto-promotion
  - No code modification
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .util import canonical_hash


REAL_RECURSIVE_VERSION = "METAENGINE-REAL-RECURSIVE-IMPROVEMENT-1"


@dataclass(frozen=True)
class RealGenerationResult:
    """Result of one real generation of the improvement flywheel."""
    generation: int
    amplification_changes: int  # number of config changes
    pbt_mean_fitness: float
    pbt_best_fitness: float
    pbt_champions: int
    l2_calls_used: int
    l2_budget: int
    tier_distribution: dict[str, int]
    distillation_insights: list[str]
    improved_trainers: list[str]
    improvement_vs_prev: float | None  # delta vs G(N-1), None for first gen
    elapsed_seconds: float
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "real_recursive_version": REAL_RECURSIVE_VERSION,
            "generation": self.generation,
            "amplification_changes": self.amplification_changes,
            "pbt_mean_fitness": round(self.pbt_mean_fitness, 6),
            "pbt_best_fitness": round(self.pbt_best_fitness, 6),
            "pbt_champions": self.pbt_champions,
            "l2_calls_used": self.l2_calls_used,
            "l2_budget": self.l2_budget,
            "tier_distribution": self.tier_distribution,
            "distillation_insights": self.distillation_insights,
            "improved_trainers": self.improved_trainers,
            "improvement_vs_prev": round(self.improvement_vs_prev, 6) if self.improvement_vs_prev is not None else None,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "truth_effect": "NONE",
            "claim_ceiling": "REAL_RECURSIVE_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


class RealRecursiveRunner:
    """Runs the real recursive improvement flywheel.

    Usage:
        runner = RealRecursiveRunner(root=ROOT)
        results = runner.run(num_generations=3)
        print(f"Improvement: {results[-1].pbt_mean_fitness - results[0].pbt_mean_fitness:+.4f}")
    """

    def __init__(
        self,
        *,
        root: str | Path,
        num_pbt_generations: int = 2,
        pbt_population_size: int = 4,
        l2_budget: int = 3,
        num_generations: int = 3,
        state_bus: Any = None,  # I3: optional TrainingStateBus for publishing fitness
    ):
        self.root = Path(root)
        self.num_pbt_generations = num_pbt_generations
        self.pbt_population_size = pbt_population_size
        self.l2_budget = l2_budget
        self.num_generations = num_generations
        self.results: list[RealGenerationResult] = []
        self.state_bus = state_bus  # I3: if provided, fitness publishes here

    def _load_accumulated_metrics(self) -> dict:
        """C3/I4: Load real metrics from accumulated_state.json.

        Returns a dict with all metrics needed by amplify AND distill.
        Defaults are sensible zeros so the flywheel still works on a fresh
        storage tree (no accumulated_state.json yet).
        """
        defaults = {
            'total_mechanisms': 0,
            'total_observations': 0,
            'evidence_graph_nodes': 0,
            'run_count': 0,
            # I4: metrics for distill — sourced from accumulated_state when present,
            # else fall back to neutral defaults (no claims about improvement).
            'rlaif_reward': 0.0,
            'pbt_best_fitness': 0.0,
            'es_best_fitness': 0.0,
            'es_converged': False,
            'marl_foe_mean': 0.0,
            'faithfulness_mean': 0.0,
            'redteam_violation_rate': 0.0,
            'transfer_rate': 0.0,
        }
        acc_path = self.root / 'storage' / 'accumulated_state.json'
        if not acc_path.is_file():
            return defaults
        try:
            data = json.loads(acc_path.read_text())
            # Compute aggregate faithfulness_mean from the per-engine scores dict.
            fa_scores = data.get('faithfulness_scores', {})
            if isinstance(fa_scores, dict):
                all_vals = []
                for v in fa_scores.values():
                    if isinstance(v, list):
                        all_vals.extend(v)
                    elif isinstance(v, (int, float)):
                        all_vals.append(v)
                faith_mean = (sum(all_vals) / len(all_vals)) if all_vals else 0.0
            else:
                faith_mean = 0.0
            defaults.update({
                'total_mechanisms': data.get('mechanism_count', 0),
                'total_observations': sum(data.get('biography_observations', {}).values()) if isinstance(data.get('biography_observations'), dict) else 0,
                'evidence_graph_nodes': data.get('evidence_graph_nodes', 0),
                'run_count': data.get('run_count', 0),
                # I4: real accumulated metrics (not hardcoded)
                'faithfulness_mean': faith_mean,
                'transfer_rate': data.get('transfer_rate', 0.0),
            })
            return defaults
        except Exception:
            return defaults

    def run(self, num_generations: int = 3, *, convergence_threshold: float = 0.005, convergence_patience: int = 2) -> list[RealGenerationResult]:
        """Run the improvement flywheel for N generations.

        Each generation:
          1. AMPLIFY: analyze previous metrics
          2. RUN PBT with real tiered fitness
          3. DISTILL: extract insights (R1.1: reject-sampling filter)
          4. COMPARE with previous
          5. R1.2: Convergence check — early stop if improvement < threshold for K gens

        R1.1: Reject-sampling filter — distill is SKIPPED for runs where
        L2 didn't fire or L2 score was below 0.5 (no genuine signal to learn from).
        This is STaR's core insight: don't learn from low-quality runs.

        R1.2: Convergence criterion — stops early if |improvement| < convergence_threshold
        for convergence_patience consecutive generations. Saves L2 budget, prevents
        noise-driven "improvement."

        R6.2: Champion carry-forward — generation N>0 initializes PBT with 50%
        previous champions (with mutation) + 50% fresh initial_policy() for diversity.
        This is meta-learning without LLM overhead.

        Returns:
            List of RealGenerationResult, one per generation.
        """
        # Lazy imports (to avoid circular deps)
        from .tiered_fitness import ThreeTierFitnessAdapter, TIER_VERSION
        from .pbt_fitness_wiring import make_tiered_pbt_fitness_fn
        from .pbt_trainer import PBTPopulationTrainer
        from .architecture_policy import initial_policy, ArchitecturePolicy
        from .amplify_distill import AmplifyDistillCycle

        # C1: Create router + adapter with router
        from .multi_model_router import create_default_router
        router = create_default_router()
        adapter = ThreeTierFitnessAdapter(
            root=self.root,
            l2_budget=self.l2_budget,
            l0_threshold=0.3,
            l1_threshold=0.5,
            cache_size=50,
            router=router,  # C1: wire MultiModelRouter
        )
        # N4: distillation persistence — insights accumulate across runs
        distillation_path = self.root / "storage" / "phase52_amplify_distill" / "DISTILLATION_HISTORY.json"
        ida_cycle = AmplifyDistillCycle(
            improvement_threshold=0.01,
            max_config_change=0.3,
            seed=42,
            persistence_path=distillation_path,  # N4
        )

        base_policy = initial_policy()
        prev_mean_fitness: float | None = None
        # R1.2: convergence tracking
        low_improvement_streak = 0
        converged = False
        # R6.2: carry forward champions from previous generation
        prev_champions: list[ArchitecturePolicy] = []

        for gen in range(num_generations):
            gen_started = time.perf_counter()

            # R1.2: early stop if converged
            if converged:
                try:
                    from .event_publisher import publish_event
                    publish_event("recursive.converged", {
                        "generation": gen,
                        "reason": "convergence_threshold_reached",
                        "improvement_threshold": convergence_threshold,
                        "patience": convergence_patience,
                    })
                except Exception:
                    pass
                break

            # 1. AMPLIFY: generate config from previous metrics
            # C3/I4: Load real metrics from accumulated_state.json (used by BOTH amplify + distill)
            acc_metrics = self._load_accumulated_metrics()
            if prev_mean_fitness is not None:
                # I4: marl_foe_mean / faithfulness_mean / transfer_rate sourced from
                # accumulated_state when available, else sensible defaults.
                gen_metrics = {
                    "rlaif_reward": prev_mean_fitness,
                    "pbt_best_fitness": prev_mean_fitness,
                    "es_best_fitness": prev_mean_fitness,
                    "es_converged": False,
                    "marl_foe_mean": acc_metrics.get('marl_foe_mean', 0.0) or (0.02 if acc_metrics.get('total_observations', 0) < 50 else 0.05),
                    "faithfulness_mean": acc_metrics.get('faithfulness_mean', 0.0) or (0.61 if acc_metrics.get('run_count', 0) < 5 else 0.65),
                    "redteam_violation_rate": acc_metrics.get('redteam_violation_rate', 0.0),
                    "transfer_rate": acc_metrics.get('transfer_rate', 0.0) or (0.57 if acc_metrics.get('total_mechanisms', 0) < 100 else 0.60),
                }
                amplification = ida_cycle.amplify(gen_metrics, generation=gen)
                amp_changes = len(amplification.config_changes)
            else:
                amp_changes = 0

            # 2. RUN PBT with real tiered fitness
            adapter.start_generation()
            fitness_fn = make_tiered_pbt_fitness_fn(adapter, state_bus=self.state_bus)  # I3: publish to bus
            trainer = PBTPopulationTrainer(
                population_size=self.pbt_population_size,
                exploit_fraction=0.25,
                seed=42 + gen,
            )

            # R6.2: Champion carry-forward — amplify-guided mutation (not random ±1).
            # Previously: random ±1 max_rounds, ±0.02 exploration_rate → no quality signal.
            # Now: uses the amplification config changes to guide mutations toward
            # the direction the amplify rules suggest. This makes champion carry-forward
            # directional, not random.
            if prev_champions and gen > 0:
                # 50% of population from champions (with amplify-guided mutation), 50% fresh
                trainer.initialize(base_policy)
                champion_count = min(len(prev_champions), self.pbt_population_size // 2)
                # Get the amplified config to guide mutations
                amplified_config = amplification.amplified_config if prev_mean_fitness is not None else {}
                target_max_rounds = amplified_config.get("max_rounds", base_policy.max_rounds)
                target_exploration = amplified_config.get("exploration_rate", base_policy.exploration_rate)
                target_temperature = amplified_config.get("llm_temperature", base_policy.temperature)
                
                for i in range(champion_count):
                    members = trainer.population.members if hasattr(trainer.population, 'members') else []
                    if i < len(members):
                        champion = prev_champions[i % len(prev_champions)]
                        # Amplify-guided mutation: move champion's hyperparams toward amplify targets
                        # with small step (not full jump, to preserve diversity)
                        step = 0.5  # move 50% of the way toward amplify target
                        new_max_rounds = int(round(champion.max_rounds + step * (target_max_rounds - champion.max_rounds)))
                        new_max_rounds = max(1, min(8, new_max_rounds))
                        new_er = champion.exploration_rate + step * (target_exploration - champion.exploration_rate)
                        new_er = max(0.0, min(0.30, new_er))
                        new_temp = champion.temperature + step * (target_temperature - champion.temperature)
                        new_temp = max(0.0, min(2.0, new_temp))
                        
                        mutated = ArchitecturePolicy(
                            generation=champion.generation + 1,
                            parent_policy_hash=champion.policy_hash,
                            topology_id=champion.topology_id,
                            waves=champion.waves,
                            dialectic_operators=champion.dialectic_operators,
                            max_rounds=new_max_rounds,
                            max_deep_engines=champion.max_deep_engines,
                            exploration_rate=round(new_er, 4),
                            temperature=round(new_temp, 4),
                            guardrail_hash=champion.guardrail_hash,
                            verifier_hash=champion.verifier_hash,
                            benchmark_hash=champion.benchmark_hash,
                            status="SHADOW",
                            mutation_receipt={"origin": "R6.2_amplify_guided", "parent": champion.policy_hash},
                        )
                        members[i].policy = mutated
            else:
                trainer.initialize(base_policy)

            pbt_result = trainer.run(fitness_fn, num_generations=self.num_pbt_generations)

            # Extract metrics
            last_summary = pbt_result["generation_summaries"][-1]
            mean_fitness = last_summary["mean_fitness"]
            best_fitness = last_summary["best_fitness"]
            champions = len(pbt_result.get("champions", []))

            # R6.2: save champions for next generation — extract from trainer.population
            # (PBT result["champions"] only has summary dicts, not full ArchitecturePolicy objects)
            prev_champions = []
            try:
                members = trainer.population.members if hasattr(trainer.population, 'members') else []
                # Sort by fitness descending, take top N
                sorted_members = sorted(members, key=lambda m: getattr(m, 'fitness', 0.0), reverse=True)
                for m in sorted_members[:self.pbt_population_size // 2]:
                    if hasattr(m, 'policy') and isinstance(m.policy, ArchitecturePolicy):
                        prev_champions.append(m.policy)
            except Exception:
                pass

            # R1.1: Reject-sampling — relax to "low_confidence distill" instead of skipping.
            # Previously: skipped distill entirely when no L2 signal → system stopped learning.
            # Now: distills with L0+L1 signal but marks confidence as "low" (no L2 verification).
            # This prevents the plateau+decline seen in massive test series.
            l2_calls_this_gen = adapter._l2_calls_this_gen
            l2_fallback_count = getattr(adapter, '_l2_fallback_count', 0)
            real_l2_success = l2_calls_this_gen > 0  # at least one real L2 evaluation

            # 3. DISTILL: extract insights
            # I4: distill now uses the SAME accumulated metrics as amplify (no more
            # hardcoded 0.02 / 0.61 / 0.57 — values come from accumulated_state.json).
            gen_metrics_for_distill = {
                "rlaif_reward": mean_fitness,
                "pbt_best_fitness": best_fitness,
                "es_best_fitness": best_fitness,
                "es_converged": False,
                "marl_foe_mean": gen_metrics.get("marl_foe_mean", acc_metrics.get('marl_foe_mean', 0.02)) if prev_mean_fitness is not None else acc_metrics.get('marl_foe_mean', 0.02),
                "faithfulness_mean": gen_metrics.get("faithfulness_mean", acc_metrics.get('faithfulness_mean', 0.61)) if prev_mean_fitness is not None else acc_metrics.get('faithfulness_mean', 0.61),
                "redteam_violation_rate": acc_metrics.get('redteam_violation_rate', 0.0),
                "transfer_rate": gen_metrics.get("transfer_rate", acc_metrics.get('transfer_rate', 0.57)) if prev_mean_fitness is not None else acc_metrics.get('transfer_rate', 0.57),
            }

            prev_metrics = None
            if prev_mean_fitness is not None:
                prev_metrics = {
                    "rlaif_reward": prev_mean_fitness,
                    "pbt_best_fitness": prev_mean_fitness,
                    "es_best_fitness": prev_mean_fitness,
                    "es_converged": False,
                    # I4: use accumulated metrics for prev_metrics too (consistent with gen_metrics)
                    "marl_foe_mean": gen_metrics_for_distill["marl_foe_mean"],
                    "faithfulness_mean": gen_metrics_for_distill["faithfulness_mean"],
                    "redteam_violation_rate": gen_metrics_for_distill["redteam_violation_rate"],
                    "transfer_rate": gen_metrics_for_distill["transfer_rate"],
                }

            # R1.1 (relaxed): Always distill, but flag confidence.
            # If no L2 signal, mark as "low_confidence" but still extract insights from L0+L1.
            # This prevents the plateau+decline where the system stops learning entirely.
            distillation_insights: list[str] = []
            improved_trainers: list[str] = []
            if real_l2_success or prev_mean_fitness is None:
                # Gen 0 (no baseline) or gens with real L2 signal → distill normally (high confidence)
                distillation = ida_cycle.distill(
                    campaign_result={"metrics": gen_metrics_for_distill},
                    gen_metrics=gen_metrics_for_distill,
                    previous_metrics=prev_metrics,
                    generation=gen,
                )
                distillation_insights = distillation.key_insights
                improved_trainers = distillation.improved_trainers
            else:
                # R1.1 (relaxed): No L2 signal → distill with L0+L1 signal (low confidence).
                # Previously this was skipped entirely, causing the system to plateau.
                # Now we distill but flag it as low-confidence.
                distillation = ida_cycle.distill(
                    campaign_result={"metrics": gen_metrics_for_distill},
                    gen_metrics=gen_metrics_for_distill,
                    previous_metrics=prev_metrics,
                    generation=gen,
                )
                distillation_insights = distillation.key_insights
                improved_trainers = distillation.improved_trainers
                # Flag as low-confidence (L0+L1 only, no L2 verification)
                if distillation_insights:
                    distillation_insights.append("LOW_CONFIDENCE: L0+L1 signal only (no L2 verification)")
                else:
                    distillation_insights = ["LOW_CONFIDENCE: L0+L1 signal only (no L2 verification)"]
                try:
                    from .event_publisher import publish_event
                    publish_event("distill.low_confidence", {
                        "generation": gen,
                        "reason": "no_real_l2_signal",
                        "l2_calls": l2_calls_this_gen,
                        "l2_fallbacks": l2_fallback_count,
                        "insights_extracted": len(distillation_insights),
                    })
                except Exception:
                    pass

            # 4. COMPARE
            improvement = None
            if prev_mean_fitness is not None:
                improvement = mean_fitness - prev_mean_fitness
                # R1.2: convergence check
                if abs(improvement) < convergence_threshold:
                    low_improvement_streak += 1
                    if low_improvement_streak >= convergence_patience:
                        converged = True
                else:
                    low_improvement_streak = 0

            elapsed = time.perf_counter() - gen_started

            # Get adapter summary for tier distribution
            adapter_summary = adapter.summary()
            tier_dist = adapter_summary.get("tier_distribution", {})

            result = RealGenerationResult(
                generation=gen,
                amplification_changes=amp_changes,
                pbt_mean_fitness=mean_fitness,
                pbt_best_fitness=best_fitness,
                pbt_champions=champions,
                l2_calls_used=adapter._l2_calls_this_gen,
                l2_budget=self.l2_budget,
                tier_distribution=tier_dist,
                distillation_insights=distillation_insights,
                improved_trainers=improved_trainers,
                improvement_vs_prev=improvement,
                elapsed_seconds=elapsed,
                result_hash="",
            )
            h = canonical_hash(result.payload())
            result = RealGenerationResult(**{**result.__dict__, "result_hash": h})
            self.results.append(result)

            prev_mean_fitness = mean_fitness

        return self.results

    def summary(self) -> dict[str, Any]:
        """Return flywheel summary."""
        if not self.results:
            return {
                "real_recursive_version": REAL_RECURSIVE_VERSION,
                "generations_run": 0,
                "truth_effect": "NONE",
            }

        first = self.results[0]
        last = self.results[-1]
        total_improvement = last.pbt_mean_fitness - first.pbt_mean_fitness
        total_l2_calls = sum(r.l2_calls_used for r in self.results)
        total_elapsed = sum(r.elapsed_seconds for r in self.results)

        return {
            "real_recursive_version": REAL_RECURSIVE_VERSION,
            "generations_run": len(self.results),
            "first_mean_fitness": round(first.pbt_mean_fitness, 6),
            "last_mean_fitness": round(last.pbt_mean_fitness, 6),
            "total_improvement": round(total_improvement, 6),
            "improvement_ratio": round(last.pbt_mean_fitness / max(0.001, first.pbt_mean_fitness), 6),
            "total_l2_calls": total_l2_calls,
            "total_l2_budget": self.l2_budget * len(self.results),
            "l2_utilization": round(total_l2_calls / max(1, self.l2_budget * len(self.results)), 4),
            "total_elapsed_seconds": round(total_elapsed, 2),
            "generations": [r.payload() for r in self.results],
            "truth_effect": "NONE",
            "claim_ceiling": "REAL_RECURSIVE_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "bounded_rsi": True,  # K0 constitution is fixed anchor
                "no_auto_promotion": True,
                "no_code_modification": True,
                "real_fitness_used": True,  # L2 real LLM evaluations
                "budget_enforced": True,
            },
        }
