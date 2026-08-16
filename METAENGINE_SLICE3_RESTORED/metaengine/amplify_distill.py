"""METAENGINE Phase 52 — Amplify+Distill Cycle (IDA).

Implements Iterated Distillation and Amplification (IDA) for the recursive
improvement loop (Phase 43). Each generation:

  1. AMPLIFY: analyze G(N-1) metrics → generate configuration for G(N)
     - If RLAIF reward is low → increase temperature for more creative reasoning
     - If PBT fitness plateaued → increase exploration_rate
     - If faithfulness is low → add source-grounding emphasis
     - If red team found violations → strengthen relevant invariant weights

  2. DISTILL: extract "essence of improvement" from G(N) campaign
     - Identify which trainers improved most
     - Extract the configuration changes that caused improvement
     - Persist distilled insights for next generation

  3. COMPARE: measure improvement G(N) vs G(N-1)
     - If improved → continue amplifying
     - If not → stop (convergence)

N4: Distillation persistence. Insights are saved to
storage/phase52_amplify_distill/DISTILLATION_HISTORY.json after each distill()
call. This accumulates insights across runs so the system builds a memory of
what worked and what didn't — without promoting any insight to truth.

Constitution compliance:
  - Amplify = configuration adjustment (no code modification)
  - Distill = insight extraction (no truth promotion)
  - All changes are evaluative (truth_effect=NONE)
  - No auto-promotion
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .util import canonical_hash, write_json, load_json


IDA_VERSION = "METAENGINE-AMPLIFY-DISTILL-CYCLE-1"


# ---------------------------------------------------------------------------
# Amplification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AmplificationResult:
    """Result of amplifying G(N-1) → G(N) configuration."""
    generation: int
    config_changes: dict[str, Any]  # what was changed
    rationale: str  # why these changes
    amplified_config: dict[str, Any]  # full config for G(N)
    amplification_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "ida_version": IDA_VERSION,
            "generation": self.generation,
            "config_changes": self.config_changes,
            "rationale": self.rationale,
            "amplified_config": self.amplified_config,
            "truth_effect": "NONE",
            "claim_ceiling": "AMPLIFICATION_IS_CONFIGURATION_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "amplification_hash": self.amplification_hash}


# ---------------------------------------------------------------------------
# Distillation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DistillationResult:
    """Result of distilling G(N) campaign → insights for G(N+1)."""
    generation: int
    improved_trainers: list[str]  # which trainers improved
    key_insights: list[str]  # what caused improvement
    distilled_config: dict[str, Any]  # config to carry forward
    distillation_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "ida_version": IDA_VERSION,
            "generation": self.generation,
            "improved_trainers": self.improved_trainers,
            "key_insights": self.key_insights,
            "distilled_config": self.distilled_config,
            "truth_effect": "NONE",
            "claim_ceiling": "DISTILLATION_IS_INSIGHT_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "distillation_hash": self.distillation_hash}


# ---------------------------------------------------------------------------
# Amplify+Distill Cycle
# ---------------------------------------------------------------------------


class AmplifyDistillCycle:
    """IDA cycle: amplify → distill → compare.

    Usage:
        cycle = AmplifyDistillCycle()
        amplification = cycle.amplify(gen_metrics, previous_config)
        # ... run campaign with amplified_config ...
        distillation = cycle.distill(campaign_result, gen_metrics)
        # ... use distilled_config for next generation ...
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "llm_temperature": 0.4,
        "max_rounds": 4,
        "max_deep_engines": 8,
        "exploration_rate": 0.15,
        "rlaif_weight_provenance": 0.15,
        "rlaif_weight_no_truth": 0.15,
        "redteam_attacks_per_vector": 1,
        "pbt_exploit_fraction": 0.25,
        "es_sigma": 0.3,
        "es_alpha": 0.1,
    }

    # N5: The 7 amplify rules, each with a learned weight.
    # Weights start at 1.0 (neutral) and are updated after each distill based on
    # whether the rules that fired correlated with improvement.
    AMPLIFY_RULE_NAMES = (
        "rlaif_low_increase_temperature",
        "pbt_plateau_increase_exploration",
        "faithfulness_low_increase_provenance",
        "redteam_violations_increase_no_truth",
        "es_not_converged_increase_sigma",
        "marl_foe_low_increase_exploit",
        "transfer_low_increase_max_rounds",
    )

    def __init__(
        self,
        *,
        improvement_threshold: float = 0.01,  # min improvement to continue
        max_config_change: float = 0.3,  # max fractional change per generation
        seed: int = 42,
        persistence_path: str | Path | None = None,  # N4: where to save distillation history
        ml_amplification: bool = False,  # N5: enable ML-based rule weighting
        rule_learning_rate: float = 0.1,  # N5: weight update step size
    ):
        self.improvement_threshold = improvement_threshold
        self.max_config_change = max_config_change
        self.amplifications: list[AmplificationResult] = []
        self.distillations: list[DistillationResult] = []
        # N4: distillation persistence
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._persisted_history: list[dict[str, Any]] = []
        # N4: load existing history on init (so insights accumulate across runs)
        if self.persistence_path is not None:
            self._load_history()
        # N5: ML-based amplification — learned rule weights
        self.ml_amplification = ml_amplification
        self._rule_lr = float(rule_learning_rate)
        self._rule_weights: dict[str, float] = {name: 1.0 for name in self.AMPLIFY_RULE_NAMES}
        # N5: track which rules fired in the most recent amplify() call
        self._last_fired_rules: list[str] = []
        # N5: history of rule weight updates (for inspection/audit)
        self._rule_weight_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Amplify: G(N-1) metrics → G(N) configuration
    # ------------------------------------------------------------------

    def amplify(
        self,
        gen_metrics: dict[str, Any],
        previous_config: dict[str, Any] | None = None,
        generation: int = 0,
    ) -> AmplificationResult:
        """Amplify: analyze metrics → generate improved configuration.

        Args:
            gen_metrics: metrics from G(N-1) campaign (combined_score, rlaif_reward, etc.)
            previous_config: configuration used for G(N-1).
            generation: the generation number being amplified TO.

        Returns:
            AmplificationResult with config changes + rationale.
        """
        config = dict(previous_config or self.DEFAULT_CONFIG)
        changes: dict[str, Any] = {}
        rationales: list[str] = []
        fired_rules: list[str] = []  # N5: track which rules fired

        # N5: helper to get the learned weight for a rule (default 1.0 if disabled)
        def rule_weight(name: str) -> float:
            if not self.ml_amplification:
                return 1.0
            return max(0.1, min(3.0, self._rule_weights.get(name, 1.0)))

        # N5: helper to scale a config change by the rule's weight
        def scale_change(old_val: float, new_val: float, weight: float) -> float:
            """Apply the rule weight to scale the magnitude of the change.

            weight=1.0 → unchanged (default behavior)
            weight=2.0 → double the change magnitude
            weight=0.5 → halve the change magnitude
            """
            delta = new_val - old_val
            scaled_delta = delta * weight
            return old_val + scaled_delta

        # 1. RLAIF reward low → increase temperature (more creative reasoning)
        rlaif_reward = gen_metrics.get("rlaif_reward", 0.5)
        if rlaif_reward < 0.4:
            rule_name = "rlaif_low_increase_temperature"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_temp = config.get("llm_temperature", 0.4)
            base_new_temp = min(2.0, old_temp * 1.2)
            new_temp = min(2.0, scale_change(old_temp, base_new_temp, w))
            config["llm_temperature"] = round(new_temp, 4)
            changes["llm_temperature"] = {"old": old_temp, "new": new_temp, "rule_weight": round(w, 4)}
            rationales.append(f"RLAIF reward {rlaif_reward:.2f} < 0.4 → increased temperature for creative reasoning (rule_weight={w:.2f})")

        # 2. PBT fitness plateaued → increase exploration_rate
        pbt_fitness = gen_metrics.get("pbt_best_fitness", 0.5)
        if pbt_fitness < 0.7:
            rule_name = "pbt_plateau_increase_exploration"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_er = config.get("exploration_rate", 0.15)
            base_new_er = min(0.30, old_er * 1.15)
            new_er = min(0.30, scale_change(old_er, base_new_er, w))
            config["exploration_rate"] = round(new_er, 4)
            changes["exploration_rate"] = {"old": old_er, "new": new_er, "rule_weight": round(w, 4)}
            rationales.append(f"PBT fitness {pbt_fitness:.2f} < 0.7 → increased exploration_rate for diversity (rule_weight={w:.2f})")

        # 3. Faithfulness low → emphasize source-grounding
        faithfulness = gen_metrics.get("faithfulness_mean", 0.5)
        if faithfulness < 0.5:
            rule_name = "faithfulness_low_increase_provenance"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_weight = config.get("rlaif_weight_provenance", 0.15)
            base_new_weight = min(0.30, old_weight * 1.2)
            new_weight = min(0.30, scale_change(old_weight, base_new_weight, w))
            config["rlaif_weight_provenance"] = round(new_weight, 4)
            changes["rlaif_weight_provenance"] = {"old": old_weight, "new": new_weight, "rule_weight": round(w, 4)}
            rationales.append(f"Faithfulness {faithfulness:.2f} < 0.5 → increased provenance weight for source-grounding (rule_weight={w:.2f})")

        # 4. Red team found violations → strengthen no_truth weight
        violation_rate = gen_metrics.get("redteam_violation_rate", 0.0)
        if violation_rate > 0.0:
            rule_name = "redteam_violations_increase_no_truth"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_weight = config.get("rlaif_weight_no_truth", 0.15)
            base_new_weight = min(0.30, old_weight * 1.3)
            new_weight = min(0.30, scale_change(old_weight, base_new_weight, w))
            config["rlaif_weight_no_truth"] = round(new_weight, 4)
            changes["rlaif_weight_no_truth"] = {"old": old_weight, "new": new_weight, "rule_weight": round(w, 4)}
            rationales.append(f"Red team violations {violation_rate:.2f} > 0 → increased no_truth weight for safety (rule_weight={w:.2f})")

        # 5. ES not converged → increase sigma for more exploration
        es_converged = gen_metrics.get("es_converged", False)
        if not es_converged:
            rule_name = "es_not_converged_increase_sigma"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_sigma = config.get("es_sigma", 0.3)
            base_new_sigma = min(0.5, old_sigma * 1.1)
            new_sigma = min(0.5, scale_change(old_sigma, base_new_sigma, w))
            config["es_sigma"] = round(new_sigma, 4)
            changes["es_sigma"] = {"old": old_sigma, "new": new_sigma, "rule_weight": round(w, 4)}
            rationales.append(f"ES not converged → increased sigma for broader search (rule_weight={w:.2f})")

        # 6. MARL foe reward low → increase PBT exploit fraction
        marl_foe = gen_metrics.get("marl_foe_mean", 0.0)
        if marl_foe < 0.05:
            rule_name = "marl_foe_low_increase_exploit"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_ef = config.get("pbt_exploit_fraction", 0.25)
            base_new_ef = min(0.50, old_ef * 1.2)
            new_ef = min(0.50, scale_change(old_ef, base_new_ef, w))
            config["pbt_exploit_fraction"] = round(new_ef, 4)
            changes["pbt_exploit_fraction"] = {"old": old_ef, "new": new_ef, "rule_weight": round(w, 4)}
            rationales.append(f"MARL foe reward {marl_foe:.3f} < 0.05 → increased PBT exploit fraction (rule_weight={w:.2f})")

        # 7. Transfer rate low → increase max_rounds for deeper analysis
        transfer_rate = gen_metrics.get("transfer_rate", 0.0)
        if transfer_rate < 0.3:
            rule_name = "transfer_low_increase_max_rounds"
            fired_rules.append(rule_name)
            w = rule_weight(rule_name)
            old_mr = config.get("max_rounds", 4)
            base_new_mr = min(8, old_mr + 1)
            # For integer fields, scale the delta and round
            mr_delta = (base_new_mr - old_mr) * w
            new_mr = max(1, min(8, old_mr + round(mr_delta)))
            config["max_rounds"] = new_mr
            changes["max_rounds"] = {"old": old_mr, "new": new_mr, "rule_weight": round(w, 4)}
            rationales.append(f"Transfer rate {transfer_rate:.2f} < 0.3 → increased max_rounds for deeper analysis (rule_weight={w:.2f})")

        # N5: remember which rules fired (for the distill() → weight update step)
        self._last_fired_rules = fired_rules

        rationale = "; ".join(rationales) if rationales else "No changes needed — metrics within acceptable ranges"

        result = AmplificationResult(
            generation=generation,
            config_changes=changes,
            rationale=rationale,
            amplified_config=config,
            amplification_hash="",
        )
        h = canonical_hash(result.payload())
        result = AmplificationResult(**{**result.__dict__, "amplification_hash": h})
        self.amplifications.append(result)
        return result

    # ------------------------------------------------------------------
    # Distill: G(N) campaign → insights for G(N+1)
    # ------------------------------------------------------------------

    def distill(
        self,
        campaign_result: dict[str, Any],
        gen_metrics: dict[str, Any],
        previous_metrics: dict[str, Any] | None = None,
        generation: int = 0,
    ) -> DistillationResult:
        """Distill: extract insights from G(N) campaign.

        Args:
            campaign_result: full campaign result with trainer results.
            gen_metrics: metrics for this generation.
            previous_metrics: metrics from G(N-1) for comparison.
            generation: the generation number being distilled FROM.

        Returns:
            DistillationResult with insights + config to carry forward.
        """
        improved_trainers: list[str] = []
        insights: list[str] = []

        # Compare with previous generation
        if previous_metrics:
            for key in ["rlaif_reward", "pbt_best_fitness", "es_best_fitness", "marl_foe_mean", "faithfulness_mean"]:
                prev_val = previous_metrics.get(key, 0.0)
                curr_val = gen_metrics.get(key, 0.0)
                if curr_val > prev_val:
                    improved_trainers.append(key)
                    insights.append(f"{key} improved: {prev_val:.4f} → {curr_val:.4f} (+{curr_val - prev_val:.4f})")
                elif curr_val < prev_val:
                    insights.append(f"{key} decreased: {prev_val:.4f} → {curr_val:.4f} ({curr_val - prev_val:.4f})")

        # Check red team improvements (only if both have violation_rate)
        prev_violations = previous_metrics.get("redteam_violation_rate") if previous_metrics else None
        curr_violations = gen_metrics.get("redteam_violation_rate")
        if prev_violations is not None and curr_violations is not None and curr_violations < prev_violations:
            improved_trainers.append("redteam_safety")
            insights.append(f"Red team violations decreased: {prev_violations:.2f} → {curr_violations:.2f}")

        # Check transfer improvements (only if both have transfer_rate)
        prev_transfer = previous_metrics.get("transfer_rate") if previous_metrics else None
        curr_transfer = gen_metrics.get("transfer_rate")
        if prev_transfer is not None and curr_transfer is not None and curr_transfer > prev_transfer:
            improved_trainers.append("cross_model_transfer")
            insights.append(f"Transfer rate improved: {prev_transfer:.2f} → {curr_transfer:.2f}")

        # Build distilled config: keep settings from amplification
        amplification = self.amplifications[-1] if self.amplifications else None
        distilled_config = amplification.amplified_config if amplification else dict(self.DEFAULT_CONFIG)

        # If no improvements → note convergence
        if not improved_trainers and previous_metrics:
            insights.append("No improvements detected — system may be converging")

        result = DistillationResult(
            generation=generation,
            improved_trainers=improved_trainers,
            key_insights=insights,
            distilled_config=distilled_config,
            distillation_hash="",
        )
        h = canonical_hash(result.payload())
        result = DistillationResult(**{**result.__dict__, "distillation_hash": h})
        self.distillations.append(result)

        # N5: update rule weights based on whether improvement happened.
        # Rules that fired AND correlated with improvement get higher weights.
        # Rules that fired AND correlated with regression get lower weights.
        # Rules that didn't fire are unchanged.
        if self.ml_amplification:
            self._update_rule_weights(gen_metrics, previous_metrics)

        # N4: persist this distillation to the history file (accumulates across runs)
        if self.persistence_path is not None:
            self._persist_distillation(result, gen_metrics, previous_metrics)

        return result

    # ------------------------------------------------------------------
    # N5: ML-based rule weight updates
    # ------------------------------------------------------------------

    def _update_rule_weights(
        self,
        gen_metrics: dict[str, Any],
        previous_metrics: dict[str, Any] | None,
    ) -> None:
        """N5: Update amplify rule weights based on the improvement signal.

        The reward signal is the change in rlaif_reward (or pbt_best_fitness
        as fallback). Rules that fired in the most recent amplify() call are
        credited/blamed for the improvement.

        Update rule (per fired rule):
          - improvement > 0  → weight += lr * improvement (capped at 3.0)
          - improvement < 0  → weight += lr * improvement (capped at 0.1)
          - improvement == 0 → no change (rule fired but had no effect)

        This is a simple policy-gradient-style update where the "policy" is
        the set of rule weights and the "reward" is the metric improvement.
        """
        if previous_metrics is None:
            return  # no baseline → can't compute improvement

        # Compute reward signal: improvement in rlaif_reward (fallback to pbt_best_fitness)
        prev_reward = previous_metrics.get("rlaif_reward", previous_metrics.get("pbt_best_fitness", 0.0))
        curr_reward = gen_metrics.get("rlaif_reward", gen_metrics.get("pbt_best_fitness", 0.0))
        improvement = float(curr_reward) - float(prev_reward)
        # Clip to avoid extreme updates from noisy metrics
        improvement = max(-0.5, min(0.5, improvement))

        fired = list(self._last_fired_rules)
        if not fired:
            return  # no rules fired → nothing to update

        updates: dict[str, dict[str, float]] = {}
        for rule_name in fired:
            old_w = self._rule_weights.get(rule_name, 1.0)
            # SGD-style update: weight += lr * reward
            # Positive reward → increase weight (rule helped)
            # Negative reward → decrease weight (rule hurt)
            new_w = old_w + self._rule_lr * improvement
            # Bound to [0.1, 3.0] for safety
            new_w = max(0.1, min(3.0, new_w))
            self._rule_weights[rule_name] = round(new_w, 6)
            updates[rule_name] = {"old": round(old_w, 6), "new": round(new_w, 6), "delta": round(new_w - old_w, 6)}

        # Record in history for audit
        self._rule_weight_history.append({
            "generation": len(self.amplifications) - 1,
            "improvement": round(improvement, 6),
            "fired_rules": fired,
            "updates": updates,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    def get_rule_weights(self) -> dict[str, float]:
        """N5: Return the current rule weights (for inspection)."""
        return dict(self._rule_weights)

    def get_rule_weight_history(self) -> list[dict[str, Any]]:
        """N5: Return the history of rule weight updates (for audit)."""
        return list(self._rule_weight_history)

    # ------------------------------------------------------------------
    # N4: Distillation persistence
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        """N4: Load distillation history from the persistence file.

        Called on __init__ if persistence_path is set. Insights from previous
        runs are loaded into self._persisted_history so they're available for
        inspection (but NOT used to influence amplification — that would be
        a truth promotion. They're observational only).
        """
        if self.persistence_path is None or not self.persistence_path.is_file():
            self._persisted_history = []
            return
        try:
            data = load_json(self.persistence_path)
            self._persisted_history = data.get("distillations", []) if isinstance(data, dict) else []
        except Exception:
            self._persisted_history = []

    def _persist_distillation(
        self,
        result: DistillationResult,
        gen_metrics: dict[str, Any],
        previous_metrics: dict[str, Any] | None,
    ) -> None:
        """N4: Append a distillation result to the persistence file.

        The file accumulates all distillations across runs, keyed by
        distillation_hash (idempotent — re-saving the same result is a no-op).
        """
        if self.persistence_path is None:
            return
        # Compute improvement delta (if comparable)
        improvement_delta = None
        if previous_metrics is not None:
            prev_reward = previous_metrics.get("rlaif_reward", 0.0)
            curr_reward = gen_metrics.get("rlaif_reward", 0.0)
            improvement_delta = round(curr_reward - prev_reward, 6)

        entry = {
            "distillation_hash": result.distillation_hash,
            "generation": result.generation,
            "improved_trainers": list(result.improved_trainers),
            "key_insights": list(result.key_insights),
            "improvement_delta": improvement_delta,
            "gen_metrics_snapshot": {
                k: float(v) if isinstance(v, (int, float)) else v
                for k, v in gen_metrics.items()
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Idempotent: skip if this distillation_hash already exists
        existing_hashes = {e.get("distillation_hash") for e in self._persisted_history}
        if result.distillation_hash not in existing_hashes:
            self._persisted_history.append(entry)

        # Write atomically (tmp + rename)
        payload = {
            "ida_version": IDA_VERSION,
            "persistence_version": "METAENGINE-DISTILLATION-PERSISTENCE-1",
            "total_distillations": len(self._persisted_history),
            "distillations": self._persisted_history,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "truth_effect": "NONE",
            "claim_ceiling": "DISTILLATION_HISTORY_IS_OBSERVATIONAL_NOT_TRUTH",
            "constitution_compliance": {
                "no_auto_promotion": True,
                "no_code_modification": True,
                "observational_not_authoritative": True,
                "idempotent_append": True,
            },
        }
        write_json(self.persistence_path, payload)

    def get_persisted_history(self) -> list[dict[str, Any]]:
        """N4: Return the distillation history (observations from all runs).

        This is observational only — callers must NOT use it to influence
        amplification decisions (that would be truth promotion). It's for
        inspection, debugging, and audit.
        """
        return list(self._persisted_history)

    def get_persisted_insights(self) -> list[str]:
        """N4: Convenience accessor — flat list of all insight strings across runs."""
        insights: list[str] = []
        for entry in self._persisted_history:
            insights.extend(entry.get("key_insights", []))
        return insights

    # ------------------------------------------------------------------
    # Full IDA cycle
    # ------------------------------------------------------------------

    def run_cycle(
        self,
        gen_metrics: dict[str, Any],
        previous_metrics: dict[str, Any] | None = None,
        previous_config: dict[str, Any] | None = None,
        generation: int = 0,
    ) -> tuple[AmplificationResult, DistillationResult]:
        """Run full IDA cycle: amplify → (campaign would run here) → distill.

        Note: the actual campaign run happens BETWEEN amplify and distill.
        This method does amplify + distill (using the same metrics for demo).

        Returns:
            (AmplificationResult, DistillationResult)
        """
        amplification = self.amplify(gen_metrics, previous_config, generation)
        # In production: run campaign with amplification.amplified_config here
        # Then call distill with the campaign result
        distillation = self.distill(
            campaign_result={"metrics": gen_metrics},  # simulated
            gen_metrics=gen_metrics,
            previous_metrics=previous_metrics,
            generation=generation,
        )
        return amplification, distillation

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return cycle summary."""
        return {
            "ida_version": IDA_VERSION,
            "amplifications_run": len(self.amplifications),
            "distillations_run": len(self.distillations),
            "improvement_threshold": self.improvement_threshold,
            "max_config_change": self.max_config_change,
            "amplifications": [a.payload() for a in self.amplifications],
            "distillations": [d.payload() for d in self.distillations],
            # N4: distillation persistence state
            "persistence": {
                "enabled": self.persistence_path is not None,
                "path": str(self.persistence_path) if self.persistence_path else None,
                "persisted_count": len(self._persisted_history),
            },
            # N5: ML-based amplification state
            "ml_amplification": {
                "enabled": self.ml_amplification,
                "learning_rate": self._rule_lr,
                "rule_weights": self.get_rule_weights(),
                "weight_updates": len(self._rule_weight_history),
                "last_fired_rules": list(self._last_fired_rules),
            },
            "truth_effect": "NONE",
            "claim_ceiling": "IDA_CYCLE_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "amplify_is_configuration": True,  # not code modification
                "distill_is_insight": True,  # not truth promotion
                "no_auto_promotion": True,
                "no_code_modification": True,
                # N4: persistence is observational (doesn't promote insights to truth)
                "persistence_observational": True,
                # N5: rule weights are bounded + observable (don't auto-promote rules)
                "rule_weights_bounded": True,
                "rule_weights_observational": True,
            },
        }
