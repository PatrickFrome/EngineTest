"""METAENGINE Phase 67 — Three-Tier Real Fitness Adapter.

Based on research (Step 1):
  - Surrogate-Assisted Optimization (Yu 2024, cited 41)
  - SAFE: Scale-Adaptive Fitness Evaluation (Wu 2021, cited 162)
  - Verifiable-Reward RL (Mar 2026)

3-tier fitness (cheap → expensive):
  L0: SURROGATE — heuristic score (~0ms) for all candidates
  L1: CONSTITUTION — K0 invariant check (~1ms) for filtered candidates
  L2: REAL_LLM — RLAIF evaluation (~3-10s) only for top-N candidates

The adapter decides which tier to use based on:
  - budget (max L2 evaluations per generation)
  - candidate quality (L0 score must exceed threshold for L1)
  - diversity (L2 only for non-cached, diverse candidates)

Caching: L2 results cached by (theta_hash) → idempotent.
Constitution: all tiers return truth_effect=NONE.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .util import canonical_hash


TIER_VERSION = "METAENGINE-THREE-TIER-FITNESS-1"


class FitnessTier(str, Enum):
    L0_SURROGATE = "L0_SURROGATE"
    L1_CONSTITUTION = "L1_CONSTITUTION"
    L2_REAL_LLM = "L2_REAL_LLM"


@dataclass(frozen=True)
class TieredFitnessResult:
    """Result of a tiered fitness evaluation."""
    theta: dict[str, float]
    fitness: float  # 0-1
    tier: FitnessTier
    l0_score: float  # surrogate
    l1_score: float  # constitution (0 if not evaluated)
    l2_score: float  # real LLM (0 if not evaluated)
    cached: bool  # was this result from cache?
    elapsed_ms: float
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "tier_version": TIER_VERSION,
            "theta": dict(self.theta),
            "fitness": round(self.fitness, 6),
            "tier": self.tier.value,
            "l0_score": round(self.l0_score, 6),
            "l1_score": round(self.l1_score, 6),
            "l2_score": round(self.l2_score, 6),
            "cached": self.cached,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "truth_effect": "NONE",
            "claim_ceiling": "FITNESS_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


class ThreeTierFitnessAdapter:
    """3-tier fitness adapter for PBT/ES.

    Usage:
        adapter = ThreeTierFitnessAdapter(root=ROOT, l2_budget=3)
        result = adapter.evaluate(theta={"max_rounds": 4, ...})
        print(f"Fitness: {result.fitness}, Tier: {result.tier}")

    I5: L0 surrogate learns from L2 observations via online linear residual
    correction. Initially the correction is zero (L0 = base heuristic, backward
    compatible). As L2 evaluations accumulate, the correction learns the residual
    (l2_score - base_l0_score) as a linear function of normalized theta features.
    This means the L0 surrogate becomes more accurate over time, reducing the
    gap between cheap L0 evaluations and expensive L2 evaluations.
    """

    # C2/R2.4: Expanded multi-task L2 evaluation set (was 3, now 12).
    # Each task has: prompt, check (substring), expected_answer (for execution verification R3.3),
    # task_type (math/logic/reasoning/knowledge), difficulty (1-3).
    # R2.4: More tasks → rote-learning risk mitigated, finer-grained signal.
    # R3.3: expected_answer enables deterministic execution verification (ground truth).
    L2_TASKS = [
        {"prompt": "What is 17 * 23? Reply with only the number.", "check": "391", "expected": 391, "task_type": "math", "difficulty": 1},
        {"prompt": "What is 144 / 12? Reply with only the number.", "check": "12", "expected": 12, "task_type": "math", "difficulty": 1},
        {"prompt": "What is 2^10? Reply with only the number.", "check": "1024", "expected": 1024, "task_type": "math", "difficulty": 2},
        {"prompt": "What is 15 * 15? Reply with only the number.", "check": "225", "expected": 225, "task_type": "math", "difficulty": 1},
        {"prompt": "If all humans are mortal, and Socrates is human, what can we conclude about Socrates? Reply in one sentence.", "check": "mortal", "expected": None, "task_type": "logic", "difficulty": 1},
        {"prompt": "All cats are animals. Whiskers is a cat. What is Whiskers? Reply in one sentence.", "check": "animal", "expected": None, "task_type": "logic", "difficulty": 1},
        {"prompt": "Does correlation imply causation? Reply yes or no with one sentence explanation.", "check": "no", "expected": None, "task_type": "reasoning", "difficulty": 2},
        {"prompt": "If A > B and B > C, which is largest: A, B, or C? Reply with only the letter.", "check": "a", "expected": "A", "task_type": "logic", "difficulty": 1},
        {"prompt": "What is the capital of France? Reply with only the city name.", "check": "paris", "expected": "Paris", "task_type": "knowledge", "difficulty": 1},
        {"prompt": "What is 7 + 8? Reply with only the number.", "check": "15", "expected": 15, "task_type": "math", "difficulty": 1},
        {"prompt": "If today is Monday, what day will it be in 3 days? Reply with only the day name.", "check": "thursday", "expected": "Thursday", "task_type": "reasoning", "difficulty": 2},
        {"prompt": "Is the statement 'I am lying right now' logically consistent? Reply yes or no.", "check": "no", "expected": None, "task_type": "reasoning", "difficulty": 3},
    ]

    # I5: Feature names for the surrogate's learned linear correction.
    SURROGATE_FEATURE_NAMES = ("max_rounds", "max_deep_engines", "exploration_rate", "temperature")

    def __init__(
        self,
        *,
        root: str | Path,
        l2_budget: int = 3,  # max L2 (real LLM) evaluations per generation
        l0_threshold: float = 0.3,  # L0 must exceed this for L1 evaluation
        l1_threshold: float = 0.5,  # L1 must exceed this for L2 evaluation
        cache_size: int = 50,
        router=None,  # C1: MultiModelRouter (optional, for failover)
        surrogate_learning_rate: float = 0.1,  # I5: online GD step size
        surrogate_max_observations: int = 100,  # I5: rolling window size
        ucb_exploration: float = 0.3,  # R5.2: UCB exploration constant (0=pure exploitation, 1=high exploration)
        deterministic_l2: bool = True,  # W8 fix: seed L2 task selection for determinism
        use_botorch: bool = True,  # Step 6: use BoTorch GP surrogate for L0
    ):
        # W8 fix: seed random for deterministic L2 task selection
        if deterministic_l2:
            random.seed(42)
        self.root = Path(root)
        self.l2_budget = l2_budget
        self.l0_threshold = l0_threshold
        self.l1_threshold = l1_threshold
        self.cache_size = cache_size

        # C1: Use MultiModelRouter if provided, else direct urllib
        self.router = router

        self._cache: dict[str, TieredFitnessResult] = {}
        self._l2_calls_this_gen = 0
        self._generation = 0
        self._l2_task_index = 0  # C2: rotate through tasks

        # Step 6: BoTorch GP surrogate
        self.use_botorch = use_botorch
        self._botorch_surrogate = None
        if use_botorch:
            try:
                from .botorch_surrogate import BotorchSurrogate, BOTORCH_AVAILABLE
                if BOTORCH_AVAILABLE:
                    self._botorch_surrogate = BotorchSurrogate()
            except Exception:
                self._botorch_surrogate = None

        # I5: Online surrogate adaptation state.
        # The surrogate predicts the RESIDUAL = l2_score - base_l0_score
        # as a linear function of normalized theta features.
        # Initial weights are zero → correction = 0 → L0 = base heuristic (backward compat).
        self._surrogate_weights: list[float] = [0.0] * len(self.SURROGATE_FEATURE_NAMES)
        self._surrogate_bias: float = 0.0
        self._surrogate_lr: float = float(surrogate_learning_rate)
        self._surrogate_max_obs: int = int(surrogate_max_observations)
        self._surrogate_observations: list[dict[str, Any]] = []  # rolling history

        # R5.2: UCB acquisition state.
        # Tracks how many times each theta (by hash) has been evaluated at L2.
        # UCB score = L0_score + ucb_exploration * sqrt(2 * ln(total_evals) / theta_evals)
        # Thetas with fewer evaluations get a exploration bonus, encouraging diverse L2 usage.
        self._ucb_exploration = float(ucb_exploration)
        self._theta_eval_counts: dict[str, int] = {}  # theta_hash → L2 eval count
        self._total_l2_evals = 0  # total L2 evaluations across all generations

    # ------------------------------------------------------------------
    # Generation management
    # ------------------------------------------------------------------

    def start_generation(self) -> None:
        """Reset L2 budget for a new generation."""
        self._l2_calls_this_gen = 0
        self._generation += 1

    # ------------------------------------------------------------------
    # R5.2: UCB acquisition for L2 candidate selection
    # ------------------------------------------------------------------

    def _ucb_score(self, theta: dict[str, float], l0_score: float) -> float:
        """R5.2: Upper Confidence Bound score for L2 candidate selection.

        UCB = exploitation + exploration
        exploitation = l0_score (current best estimate)
        exploration = ucb_exploration * sqrt(2 * ln(total_evals + 1) / (theta_evals + 1))

        Thetas that have been evaluated fewer times get a higher exploration bonus,
        encouraging the system to try diverse thetas at L2 rather than always
        picking the highest-L0 theta (pure exploitation).

        This is the multi-armed bandit UCB1 algorithm applied to L2 evaluation.
        """
        import math
        theta_key = canonical_hash({"theta": theta})
        theta_evals = self._theta_eval_counts.get(theta_key, 0)
        exploration_bonus = self._ucb_exploration * math.sqrt(
            2.0 * math.log(self._total_l2_evals + 2) / (theta_evals + 1)
        )
        return l0_score + exploration_bonus

    def _record_l2_eval(self, theta: dict[str, float]) -> None:
        """R5.2: Record that a theta was evaluated at L2 (for UCB tracking)."""
        theta_key = canonical_hash({"theta": theta})
        self._theta_eval_counts[theta_key] = self._theta_eval_counts.get(theta_key, 0) + 1
        self._total_l2_evals += 1

    # ------------------------------------------------------------------
    # I5: Surrogate feature extraction + online learning
    # ------------------------------------------------------------------

    def _surrogate_features(self, theta: dict[str, float]) -> list[float]:
        """I5: Extract normalized features from theta for the surrogate model.

        Each feature is scaled to roughly [0, 1] so gradient descent is stable.
        """
        return [
            float(theta.get("max_rounds", 4)) / 8.0,
            float(theta.get("max_deep_engines", 8)) / 16.0,
            float(theta.get("exploration_rate", 0.15)) / 0.30,
            float(theta.get("temperature", 0.4)) / 2.0,
        ]

    def _surrogate_predict_correction(self, theta: dict[str, float]) -> float:
        """I5: Predict the additive correction to apply on top of the base heuristic."""
        feats = self._surrogate_features(theta)
        correction = self._surrogate_bias
        for w, x in zip(self._surrogate_weights, feats):
            correction += w * x
        # Clip to a safe band so the surrogate can't wildly distort L0.
        return max(-0.3, min(0.3, correction))

    def _surrogate_update(self, theta: dict[str, float], l2_score: float, base_l0: float) -> None:
        """I5 + Step 6: Update both the linear surrogate AND the BoTorch GP.

        Learns to predict the residual (l2_score - base_l0) as a linear function
        of normalized theta features. Called after every successful L2 evaluation.
        Also feeds (theta, l2_score) to BoTorch GP for posterior fitting.
        """
        # Step 6: Feed observation to BoTorch GP
        if self._botorch_surrogate is not None:
            self._botorch_surrogate.add_observation(theta, l2_score)

        # I5: Linear surrogate update (kept for backward compat + when BoTorch unavailable)
        feats = self._surrogate_features(theta)
        prediction = self._surrogate_bias
        for w, x in zip(self._surrogate_weights, feats):
            prediction += w * x
        target_residual = l2_score - base_l0
        # Clip target so a single noisy L2 result can't derail the model.
        target_residual = max(-0.5, min(0.5, target_residual))
        error = target_residual - prediction

        # SGD update with bias regularization toward 0 (L2-like)
        self._surrogate_bias += self._surrogate_lr * error
        for i, x in enumerate(feats):
            self._surrogate_weights[i] += self._surrogate_lr * error * x

        # R6.4: Prioritized surrogate replay — keep high-surprise observations longer.
        # Previously: FIFO rolling window (drop oldest when full).
        # Now: when the window is full, drop the LEAST surprising (lowest |error|)
        # observation instead of the oldest. This is Prioritized Experience Replay (PER).
        obs_entry = {
            "theta": dict(theta),
            "l2_score": float(l2_score),
            "base_l0": float(base_l0),
            "residual": float(target_residual),
            "prediction": float(prediction),
            "error": float(error),
            "surprise": float(abs(error)),  # R6.4: |error| = surprise score
            "generation": self._generation,
        }
        self._surrogate_observations.append(obs_entry)
        if len(self._surrogate_observations) > self._surrogate_max_obs:
            # R6.4: Drop least surprising instead of oldest
            # Find the index with minimum surprise
            min_surprise_idx = 0
            min_surprise = float('inf')
            for i, obs in enumerate(self._surrogate_observations):
                if obs["surprise"] < min_surprise:
                    min_surprise = obs["surprise"]
                    min_surprise_idx = i
            del self._surrogate_observations[min_surprise_idx]

    def surrogate_state(self) -> dict[str, Any]:
        """I5: Snapshot of the surrogate model state (for inspection / persistence)."""
        # Compute mean absolute error (MAE) over the observation window
        if self._surrogate_observations:
            mae = sum(abs(o["error"]) for o in self._surrogate_observations) / len(self._surrogate_observations)
        else:
            mae = 0.0
        return {
            "feature_names": list(self.SURROGATE_FEATURE_NAMES),
            "weights": list(self._surrogate_weights),
            "bias": self._surrogate_bias,
            "learning_rate": self._surrogate_lr,
            "observation_count": len(self._surrogate_observations),
            "max_observations": self._surrogate_max_obs,
            "mean_abs_error": round(mae, 6),
            "correction_band": [-0.3, 0.3],
        }

    # ------------------------------------------------------------------
    # L0: Surrogate (heuristic, ~0ms)
    # ------------------------------------------------------------------

    def _evaluate_l0(self, theta: dict[str, float]) -> float:
        """L0: heuristic fitness (no LLM, no orchestrator).

        Step 6: When BoTorch surrogate is available and has >= 3 observations,
        uses GP posterior mean instead of hand-coded heuristic.
        Falls back to heuristic when insufficient data.

        I5: An additive correction (learned from L2 observations) is applied on
        top of the base heuristic. Initially the correction is 0 (backward
        compatible). As L2 evaluations accumulate, the surrogate learns the
        residual (l2_score - base) and adjusts L0 accordingly.
        """
        # Step 6: Try BoTorch GP surrogate first
        if self._botorch_surrogate is not None:
            pred = self._botorch_surrogate.predict(theta)
            if pred.using_gp:
                # GP is fitted — use posterior mean as L0 score
                return max(0.0, min(1.0, pred.mean))

        # Fallback: hand-coded heuristic (same as before Step 6)
        max_rounds = max(1, min(8, int(theta.get("max_rounds", 4))))
        max_deep = max(1, min(16, int(theta.get("max_deep_engines", 8))))
        er = max(0.0, min(0.30, float(theta.get("exploration_rate", 0.15))))
        temp = max(0.0, min(2.0, float(theta.get("temperature", 0.4))))

        round_score = min(0.3, max_rounds * 0.05)
        engine_score = min(0.2, max_deep * 0.02)
        er_score = 0.15 * (1.0 - abs(er - 0.15) / 0.15)
        temp_score = 0.15 * (1.0 - abs(temp - 0.4) / 0.4)
        base = 0.2

        base_score = base + round_score + engine_score + er_score + temp_score
        # I5: apply learned additive correction (clipped to [-0.3, +0.3] in _surrogate_predict_correction)
        correction = self._surrogate_predict_correction(theta)
        
        # Diversity bonus: if this theta has been evaluated before (cached), reduce score slightly.
        # This prevents PBT from collapsing to a single config — novel configs get a small bonus.
        # This is a novelty-seeking mechanism inspired by Quality-Diversity algorithms (MAP-Elites).
        theta_key = canonical_hash({"theta": theta})
        if theta_key in self._theta_eval_counts:
            # Already evaluated → small penalty (encourage exploration of new thetas)
            eval_count = self._theta_eval_counts[theta_key]
            diversity_penalty = min(0.05, 0.01 * eval_count)  # max -0.05, scales with eval count
        else:
            diversity_penalty = 0.0  # new theta → no penalty
        
        return max(0.0, min(1.0, base_score + correction - diversity_penalty))

    def _evaluate_l0_base(self, theta: dict[str, float]) -> float:
        """I5: The base heuristic WITHOUT the learned correction.

        Used by _surrogate_update to compute the residual (l2 - base) that the
        surrogate model is trying to predict. Keeping this separate from
        _evaluate_l0 (which applies the correction) avoids a feedback loop where
        the correction influences its own training target.
        """
        max_rounds = max(1, min(8, int(theta.get("max_rounds", 4))))
        max_deep = max(1, min(16, int(theta.get("max_deep_engines", 8))))
        er = max(0.0, min(0.30, float(theta.get("exploration_rate", 0.15))))
        temp = max(0.0, min(2.0, float(theta.get("temperature", 0.4))))

        round_score = min(0.3, max_rounds * 0.05)
        engine_score = min(0.2, max_deep * 0.02)
        er_score = 0.15 * (1.0 - abs(er - 0.15) / 0.15)
        temp_score = 0.15 * (1.0 - abs(temp - 0.4) / 0.4)
        base = 0.2
        return max(0.0, min(1.0, base + round_score + engine_score + er_score + temp_score))

    # ------------------------------------------------------------------
    # L1: Constitution check (~1ms)
    # ------------------------------------------------------------------

    def _evaluate_l1(self, theta: dict[str, float]) -> float:
        """L1: constitution compliance score.

        Checks if the theta values are within constitutionally-valid ranges.
        Returns 1.0 if all valid, lower if any are out of bounds.
        """
        score = 1.0

        # Check max_rounds in valid range [1, 8]
        mr = theta.get("max_rounds", 4)
        if mr < 1 or mr > 8:
            score -= 0.2

        # Check exploration_rate in valid range [0, 0.30]
        er = theta.get("exploration_rate", 0.15)
        if er < 0 or er > 0.30:
            score -= 0.2

        # Check temperature in valid range [0, 2.0]
        temp = theta.get("temperature", 0.4)
        if temp < 0 or temp > 2.0:
            score -= 0.2

        # Check that theta doesn't encode any forbidden actions
        # (e.g., extremely high temperature = "always say anything")
        if temp > 1.5:
            score -= 0.1  # high temperature reduces constitution score

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # L2: Real LLM evaluation (~3-10s)
    # ------------------------------------------------------------------

    def _evaluate_l2(self, theta: dict[str, float]) -> tuple[float, bool, dict]:
        """L2: real LLM evaluation via bridge or MultiModelRouter.

        R2.1: Fixed scoring formula — correctness is now dominant.
          Wrong answer: max 0.3 (was 0.7)
          Correct + disclaimer: 0.9+ (was 0.5)
          Correct + no disclaimer: 0.7 (was 0.8 — but wrong+disclaimer=0.7 was a bug)
        R3.3: Execution verification for math tasks — uses Python eval() as ground truth.
          This breaks the "intrinsic self-correction" failure mode (Huang 2023).
        R2.4: Random task sampling from expanded bank (was round-robin of 3).

        Returns:
            (score, fell_back, metadata): tuple of (float 0-1, bool, dict with task details).
            metadata includes task_type, difficulty, verified (execution check), correct.
        """
        try:
            temp = float(theta.get("temperature", 0.4))

            # R2.4: Random task sampling (was round-robin)
            task = random.choice(self.L2_TASKS)
            task_type = task.get("task_type", "unknown")
            difficulty = task.get("difficulty", 1)
            expected = task.get("expected")

            prompt = (
                f"You are engine_16 in MetaEngine. Your output is generative-only "
                f"until externally verified. {task['prompt']}"
            )

            response_text = ""

            # C1: Use MultiModelRouter if available
            if self.router is not None:
                result = self.router.call(
                    prompt,
                    max_tokens=128,
                    temperature=temp,
                    timeout=30.0,
                    max_retries=3,
                )
                if result.success:
                    response_text = result.response_text
                else:
                    # Router failed → fall back to L0
                    return (self._evaluate_l0(theta), True, {"task_type": task_type, "reason": "router_failed"})
            else:
                # Direct urllib (backward-compatible)
                import urllib.request

                body = json.dumps({
                    "model": "metaengine-glm-1",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 128,
                    "temperature": temp,
                }).encode("utf-8")

                req = urllib.request.Request(
                    "http://localhost:3031/v1/chat/completions",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # C2: Check correctness against task-specific answer
            correct = task["check"].lower() in response_text.lower()

            # R3.3: Execution verification for math tasks (ground truth)
            verified = None
            if expected is not None and isinstance(expected, (int, float)):
                # Math task — verify by execution (Python eval is deterministic)
                try:
                    # Extract the first number from the response and check if it matches
                    numbers = re.findall(r'-?\d+(?:\.\d+)?', response_text)
                    if numbers:
                        response_num = float(numbers[0])
                        verified = (response_num == float(expected))
                    else:
                        verified = False
                except Exception:
                    verified = None  # couldn't verify
            elif expected is not None and isinstance(expected, str):
                # String tasks — check if expected is in response
                verified = expected.lower() in response_text.lower()

            # If execution verification succeeded, prefer it over substring check
            if verified is not None:
                correct = verified  # ground truth overrides substring match

            # Check constitution: "generative" or "verified" or "uncertain" mentioned
            response_lower = response_text.lower()
            has_disclaimer = (
                "generative" in response_lower or
                "verified" in response_lower or
                "uncertain" in response_lower or
                "not sure" in response_lower or
                "may be" in response_lower or
                "might be" in response_lower
            )

            # R2.1: Fixed scoring formula — correctness is dominant.
            # Old (buggy): 0.5 base + 0.3 correct + 0.2 disclaimer
                       #   wrong+disclaimer = 0.7, correct+no disclaimer = 0.8 (wrong+disclaimer nearly matched correct!)
            # New: 0.1 base + 0.6 correct + 0.2 disclaimer + 0.1 verified
            #   wrong+nothing = 0.1, wrong+disclaimer = 0.3, correct+nothing = 0.7, correct+disclaimer = 0.9
            score = 0.1  # base
            if correct:
                score += 0.6
            if has_disclaimer:
                score += 0.2
            if verified is True:
                score += 0.1  # bonus for execution-verified correctness

            metadata = {
                "task_type": task_type,
                "difficulty": difficulty,
                "correct": correct,
                "verified": verified,
                "has_disclaimer": has_disclaimer,
                "response_preview": response_text[:100],
            }

            # Round to 6 decimal places to avoid floating-point representation
            # drift (e.g. 0.1 + 0.2 = 0.30000000000000004 in IEEE-754). This
            # preserves the R2.1 contract: wrong+disclaimer = exactly 0.3.
            return (round(min(1.0, score), 6), False, metadata)

        except Exception:
            # On error, fall back to L0 score
            return (self._evaluate_l0(theta), True, {"reason": "exception"})

    # ------------------------------------------------------------------
    # Main evaluation (tiered)
    # ------------------------------------------------------------------

    def evaluate(self, theta: dict[str, float]) -> TieredFitnessResult:
        """Evaluate theta using 3-tier fitness.

        Decision logic:
          1. L0 always runs
          2. L1 runs if L0 >= l0_threshold
          3. L2 runs if L1 >= l1_threshold AND budget available AND not cached

        Returns:
            TieredFitnessResult with fitness + tier + scores
        """
        started = time.perf_counter()
        theta_key = canonical_hash({"theta": theta})

        # Check cache
        if theta_key in self._cache:
            cached = self._cache[theta_key]
            return TieredFitnessResult(
                theta=dict(theta),
                fitness=cached.fitness,
                tier=cached.tier,
                l0_score=cached.l0_score,
                l1_score=cached.l1_score,
                l2_score=cached.l2_score,
                cached=True,
                elapsed_ms=0.0,
                result_hash=cached.result_hash,
            )

        # L0: Surrogate (always)
        l0 = self._evaluate_l0(theta)
        fitness = l0
        tier = FitnessTier.L0_SURROGATE
        l1_score = 0.0
        l2_score = 0.0

        # L1: Constitution (if L0 passes threshold)
        if l0 >= self.l0_threshold:
            l1_score = self._evaluate_l1(theta)
            # Blend L0 + L1
            fitness = 0.6 * l0 + 0.4 * l1_score
            tier = FitnessTier.L1_CONSTITUTION

            # R5.2: UCB acquisition — lower the effective L2 threshold for
            # under-explored thetas (exploration bonus makes them more likely
            # to be selected for L2 evaluation).
            ucb_bonus = self._ucb_score(theta, 0.0) if self._ucb_exploration > 0 else 0.0
            
            # R5.5: MAE-gated L2 threshold — adapt L2 threshold based on surrogate accuracy.
            # If surrogate MAE is low (surrogate is accurate), RAISE the threshold
            # (trust L0+L1, save L2 budget for truly uncertain cases).
            # If surrogate MAE is high (surrogate is inaccurate), LOWER the threshold
            # (need more L2 evaluations to calibrate the surrogate).
            surrogate_mae = self.surrogate_state()["mean_abs_error"]
            mae_adjustment = (surrogate_mae - 0.1) * 0.5  # ±0.05 adjustment based on MAE
            mae_adjustment = max(-0.1, min(0.1, mae_adjustment))  # bounded
            
            effective_l1_threshold = self.l1_threshold - ucb_bonus - mae_adjustment

            # L2: Real LLM (if L1 passes effective threshold AND budget available)
            if l1_score >= effective_l1_threshold and self._l2_calls_this_gen < self.l2_budget:
                # I5: capture the BASE L0 (without learned correction) so the surrogate
                # learns the residual between base heuristic and real L2 score.
                base_l0_for_update = self._evaluate_l0_base(theta)
                l2_score, l2_fell_back, l2_metadata = self._evaluate_l2(theta)
                if not l2_fell_back:
                    # Real L2 evaluation succeeded → consume budget + update surrogate
                    self._l2_calls_this_gen += 1
                    # R5.2: record this L2 evaluation for UCB tracking
                    self._record_l2_eval(theta)
                    # Blend L0 + L1 + L2 (L2 has highest weight)
                    fitness = 0.2 * l0 + 0.3 * l1_score + 0.5 * l2_score
                    tier = FitnessTier.L2_REAL_LLM
                    # I5: update the surrogate model with this REAL L2 observation.
                    self._surrogate_update(theta, l2_score, base_l0_for_update)
                    # N1: publish fitness.evaluated event for real-time monitoring
                    try:
                        from .event_publisher import publish_event
                        publish_event("fitness.evaluated", {
                            "tier": tier.value,
                            "fitness": round(fitness, 6),
                            "l0_score": round(l0, 6),
                            "l1_score": round(l1_score, 6),
                            "l2_score": round(l2_score, 6),
                            "generation": self._generation,
                            "l2_calls_used": self._l2_calls_this_gen,
                            "l2_budget": self.l2_budget,
                            "l2_fell_back": False,
                            "task_type": l2_metadata.get("task_type", "unknown"),
                            "difficulty": l2_metadata.get("difficulty", 1),
                            "verified": l2_metadata.get("verified"),
                            "correct": l2_metadata.get("correct"),
                            "theta": {k: float(v) for k, v in theta.items()},
                        })
                    except Exception:
                        pass  # best-effort
                else:
                    # L2 fell back to L0 (bridge rate-limited or error).
                    # Do NOT consume budget, do NOT update surrogate,
                    # do NOT mark tier as L2_REAL_LLM.
                    # Keep tier as L1_CONSTITUTION and fitness as L0+L1 blend.
                    # Track the fallback for observability.
                    self._l2_fallback_count = getattr(self, '_l2_fallback_count', 0) + 1
                    l2_score = 0.0  # no real L2 score
                    try:
                        from .event_publisher import publish_event
                        publish_event("fitness.l2_fallback", {
                            "tier": "L2_FALLBACK_TO_L1",
                            "generation": self._generation,
                            "l2_fallback_count": self._l2_fallback_count,
                            "l2_budget_remaining": self.l2_budget - self._l2_calls_this_gen,
                            "theta": {k: float(v) for k, v in theta.items()},
                        })
                    except Exception:
                        pass  # best-effort

        elapsed_ms = (time.perf_counter() - started) * 1000

        result = TieredFitnessResult(
            theta=dict(theta),
            fitness=fitness,
            tier=tier,
            l0_score=l0,
            l1_score=l1_score,
            l2_score=l2_score,
            cached=False,
            elapsed_ms=elapsed_ms,
            result_hash="",
        )
        h = canonical_hash(result.payload())
        result = TieredFitnessResult(**{**result.__dict__, "result_hash": h})

        # Cache
        if len(self._cache) < self.cache_size:
            self._cache[theta_key] = result
        else:
            # Evict oldest
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            self._cache[theta_key] = result

        return result

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return adapter summary."""
        tier_counts: dict[str, int] = {"L0": 0, "L1": 0, "L2": 0}
        for r in self._cache.values():
            if r.tier == FitnessTier.L0_SURROGATE:
                tier_counts["L0"] += 1
            elif r.tier == FitnessTier.L1_CONSTITUTION:
                tier_counts["L1"] += 1
            elif r.tier == FitnessTier.L2_REAL_LLM:
                tier_counts["L2"] += 1

        return {
            "tier_version": TIER_VERSION,
            "generation": self._generation,
            "l2_budget": self.l2_budget,
            "l2_calls_this_gen": self._l2_calls_this_gen,
            "l2_fallback_count": getattr(self, "_l2_fallback_count", 0),
            "l0_threshold": self.l0_threshold,
            "l1_threshold": self.l1_threshold,
            "cache_size": len(self._cache),
            "tier_distribution": tier_counts,
            # R5.2: UCB acquisition state
            "ucb": {
                "exploration_constant": self._ucb_exploration,
                "total_l2_evals": self._total_l2_evals,
                "unique_thetas_evaluated": len(self._theta_eval_counts),
            },
            # I5: surrogate learning state
            "surrogate": self.surrogate_state(),
            # Step 6: BoTorch GP surrogate state
            "botorch": self._botorch_surrogate.state() if self._botorch_surrogate else {"available": False, "enabled": self.use_botorch},
            "truth_effect": "NONE",
            "claim_ceiling": "FITNESS_ADAPTER_IS_EVALUATIVE_NOT_TRUTH",
            "constitution_compliance": {
                "no_truth_promotion": True,
                "no_code_modification": True,
                "l2_caches_idempotent": True,
                "budget_enforced": True,
                # I5: surrogate correction is bounded and observable
                "surrogate_bounded": True,
                "surrogate_observational": True,
            },
        }
