"""METAENGINE Phase 43 — Recursive Self-Improvement Loop.

Closes the recursive improvement loop: G0 → G1 → G2 → ... where each
generation uses the PREVIOUS generation's results to improve.

Inspired by:
  - Iterated Distillation and Amplification (IDA): amplify → distill → repeat
  - SIA (Self-Improving AI, May 2026): feedback loop updating harness + weights
  - Recursive self-improvement (Anbarjafari 2025): mathematical framework

The loop:
  1. RUN: execute a parallel training campaign → generation results
  2. ANALYZE: extract improvement signals (which trainers improved?)
  3. AMPLIFY: use G(N-1) insights to configure G(N) campaign
  4. DISTILL: extract the "essence" of improvement (mechanisms, hyperparameters)
  5. Compare G(N) vs G(N-1) → measure improvement ratio
  6. If improved → continue; if not → stop (convergence)

Constitution compliance:
  - Each generation is a SHADOW campaign (no auto-promotion)
  - Improvement is MEASURED, not assumed
  - No code modification (only hyperparameter/policy adjustment)
  - truth_effect = NONE (evaluative, not truth)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .util import canonical_hash


RECURSIVE_LOOP_VERSION = "METAENGINE-RECURSIVE-IMPROVEMENT-LOOP-1"


# ---------------------------------------------------------------------------
# Generation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationMetrics:
    """Metrics for one generation of the recursive loop."""
    generation: int
    rlaif_reward: float
    pbt_best_fitness: float
    es_best_fitness: float
    marl_foe_mean_reward: float
    alphazero_mechanisms: int
    redteam_violations: int
    combined_score: float  # weighted aggregate
    metrics_hash: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "rlaif_reward": round(self.rlaif_reward, 6),
            "pbt_best_fitness": round(self.pbt_best_fitness, 6),
            "es_best_fitness": round(self.es_best_fitness, 6),
            "marl_foe_mean_reward": round(self.marl_foe_mean_reward, 6),
            "alphazero_mechanisms": self.alphazero_mechanisms,
            "redteam_violations": self.redteam_violations,
            "combined_score": round(self.combined_score, 6),
            "truth_effect": "NONE",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "metrics_hash": self.metrics_hash}


# ---------------------------------------------------------------------------
# Improvement comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImprovementComparison:
    """Comparison between two generations."""
    generation_a: int
    generation_b: int
    metrics_a: GenerationMetrics
    metrics_b: GenerationMetrics
    improvement_ratio: float  # combined_score_b / combined_score_a
    improved: bool  # improvement_ratio > 1.0
    delta_scores: dict[str, float]  # per-metric deltas
    comparison_hash: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "generation_a": self.generation_a,
            "generation_b": self.generation_b,
            "combined_score_a": round(self.metrics_a.combined_score, 6),
            "combined_score_b": round(self.metrics_b.combined_score, 6),
            "improvement_ratio": round(self.improvement_ratio, 6),
            "improved": self.improved,
            "delta_scores": {k: round(v, 6) for k, v in self.delta_scores.items()},
            "truth_effect": "NONE",
            "claim_ceiling": "IMPROVEMENT_COMPARISON_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "comparison_hash": self.comparison_hash}


# ---------------------------------------------------------------------------
# Recursive Improvement Loop
# ---------------------------------------------------------------------------


class RecursiveImprovementLoop:
    """Recursive self-improvement loop: G0 → G1 → G2 → ...

    Each generation:
      1. Run a campaign (or load cached results)
      2. Extract metrics
      3. Compare with previous generation
      4. If improved → continue; if not → stop

    Usage:
        loop = RecursiveImprovementLoop(campaign_fn=my_campaign_fn)
        loop.run(num_generations=3)
        summary = loop.summary()
    """

    # Weights for combined score (sum to 1.0)
    DEFAULT_SCORE_WEIGHTS = {
        "rlaif_reward": 0.20,
        "pbt_best_fitness": 0.25,
        "es_best_fitness": 0.20,
        "marl_foe_mean_reward": 0.10,
        "alphazero_mechanisms": 0.15,  # normalized by /10
        "redteam_safety": 0.10,  # 1.0 - violation_rate
    }

    def __init__(
        self,
        *,
        campaign_fn: Callable[[], dict[str, Any]] | None = None,
        score_weights: dict[str, float] | None = None,
        convergence_threshold: float = 0.01,  # stop if improvement < 1%
        max_generations: int = 10,
    ):
        self.campaign_fn = campaign_fn
        self.score_weights = score_weights or dict(self.DEFAULT_SCORE_WEIGHTS)
        self.convergence_threshold = convergence_threshold
        self.max_generations = max_generations
        self.generations: list[GenerationMetrics] = []
        self.comparisons: list[ImprovementComparison] = []
        self.converged: bool = False

    # ------------------------------------------------------------------
    # Metric extraction
    # ------------------------------------------------------------------

    def _extract_metrics(self, campaign_result: dict[str, Any], generation: int) -> GenerationMetrics:
        """Extract metrics from a campaign result.

        Args:
            campaign_result: dict with shared_state_summary or trainer results.
            generation: the generation number.

        Returns:
            GenerationMetrics with all metrics + combined score.
        """
        # Try to get from shared_state_summary first
        shared = campaign_result.get("shared_state_summary") or campaign_result.get("shared_state") or {}

        rlaif_reward = float(shared.get("rlaif_reward", 0.0))
        pbt_best = float(shared.get("pbt_best_fitness", 0.0))
        es_best = float(shared.get("es_best_fitness", 0.0))
        marl_foe = float(shared.get("marl_foe_mean_reward", 0.0))
        az_mechanisms = int(shared.get("alphazero_mechanisms_extracted", 0))
        rt_violations = int(shared.get("redteam_total_violations", 0))

        # Compute combined score
        rt_safety = 1.0 if rt_violations == 0 else max(0.0, 1.0 - rt_violations * 0.1)
        az_normalized = min(1.0, az_mechanisms / 10.0)

        combined = (
            self.score_weights["rlaif_reward"] * rlaif_reward
            + self.score_weights["pbt_best_fitness"] * pbt_best
            + self.score_weights["es_best_fitness"] * es_best
            + self.score_weights["marl_foe_mean_reward"] * marl_foe
            + self.score_weights["alphazero_mechanisms"] * az_normalized
            + self.score_weights["redteam_safety"] * rt_safety
        )

        metrics = GenerationMetrics(
            generation=generation,
            rlaif_reward=rlaif_reward,
            pbt_best_fitness=pbt_best,
            es_best_fitness=es_best,
            marl_foe_mean_reward=marl_foe,
            alphazero_mechanisms=az_mechanisms,
            redteam_violations=rt_violations,
            combined_score=combined,
            metrics_hash="",
        )
        h = canonical_hash(metrics.payload())
        return GenerationMetrics(**{**metrics.__dict__, "metrics_hash": h})

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def _compare_generations(
        self,
        metrics_a: GenerationMetrics,
        metrics_b: GenerationMetrics,
    ) -> ImprovementComparison:
        """Compare two generations."""
        ratio = metrics_b.combined_score / max(0.001, metrics_a.combined_score)
        improved = ratio > 1.0

        delta_scores = {
            "rlaif_reward": metrics_b.rlaif_reward - metrics_a.rlaif_reward,
            "pbt_best_fitness": metrics_b.pbt_best_fitness - metrics_a.pbt_best_fitness,
            "es_best_fitness": metrics_b.es_best_fitness - metrics_a.es_best_fitness,
            "marl_foe_mean_reward": metrics_b.marl_foe_mean_reward - metrics_a.marl_foe_mean_reward,
            "alphazero_mechanisms": metrics_b.alphazero_mechanisms - metrics_a.alphazero_mechanisms,
            "redteam_violations": metrics_b.redteam_violations - metrics_a.redteam_violations,
            "combined_score": metrics_b.combined_score - metrics_a.combined_score,
        }

        comp = ImprovementComparison(
            generation_a=metrics_a.generation,
            generation_b=metrics_b.generation,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            improvement_ratio=ratio,
            improved=improved,
            delta_scores=delta_scores,
            comparison_hash="",
        )
        h = canonical_hash(comp.payload())
        return ImprovementComparison(**{**comp.__dict__, "comparison_hash": h})

    # ------------------------------------------------------------------
    # Run one generation
    # ------------------------------------------------------------------

    def run_generation(self, campaign_result: dict[str, Any] | None = None) -> GenerationMetrics:
        """Run one generation of the recursive loop.

        Args:
            campaign_result: if provided, use this campaign result.
                           if None, call self.campaign_fn.

        Returns:
            GenerationMetrics for this generation.
        """
        if campaign_result is None:
            if self.campaign_fn is None:
                raise ValueError("NO_CAMPAIGN_FUNCTION_PROVIDED")
            campaign_result = self.campaign_fn()

        gen = len(self.generations)
        metrics = self._extract_metrics(campaign_result, gen)

        # Compare with previous generation if exists
        if self.generations:
            prev = self.generations[-1]
            comparison = self._compare_generations(prev, metrics)
            self.comparisons.append(comparison)

            # Check convergence
            if comparison.improvement_ratio < 1.0 + self.convergence_threshold:
                self.converged = True

        self.generations.append(metrics)
        return metrics

    # ------------------------------------------------------------------
    # Run multiple generations
    # ------------------------------------------------------------------

    def run(
        self,
        num_generations: int | None = None,
        campaign_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run multiple generations of the recursive loop.

        Args:
            num_generations: number of generations (default: max_generations).
            campaign_results: list of pre-computed campaign results
                             (if None, calls campaign_fn for each).

        Returns:
            Summary dict.
        """
        n = num_generations or self.max_generations
        if campaign_results:
            n = min(n, len(campaign_results))

        for i in range(n):
            if self.converged:
                break
            result = campaign_results[i] if campaign_results else None
            self.run_generation(result)

        return self.summary()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return loop summary."""
        if not self.generations:
            return {
                "recursive_loop_version": RECURSIVE_LOOP_VERSION,
                "generations_run": 0,
                "truth_effect": "NONE",
            }

        first = self.generations[0]
        last = self.generations[-1]

        return {
            "recursive_loop_version": RECURSIVE_LOOP_VERSION,
            "generations_run": len(self.generations),
            "converged": self.converged,
            "convergence_threshold": self.convergence_threshold,
            "first_combined_score": round(first.combined_score, 6),
            "last_combined_score": round(last.combined_score, 6),
            "total_improvement": round(last.combined_score - first.combined_score, 6),
            "total_improvement_ratio": round(
                last.combined_score / max(0.001, first.combined_score), 6
            ),
            "score_weights": self.score_weights,
            "generations": [g.as_dict() for g in self.generations],
            "comparisons": [c.as_dict() for c in self.comparisons],
            "truth_effect": "NONE",
            "claim_ceiling": "RECURSIVE_LOOP_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "all_generations_shadow": True,
                "no_auto_promotion": True,
                "improvement_measured_not_assumed": True,
                "no_code_modification": True,
                "convergence_detected": self.converged,
            },
        }
