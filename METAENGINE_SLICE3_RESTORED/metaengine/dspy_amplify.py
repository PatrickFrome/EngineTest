"""Step 9: DSPy-powered automatic prompt optimization for amplification.

Replaces the 7 hand-coded amplify rules in amplify_distill.py with a DSPy
teleprompter that learns which configuration changes improve fitness.

Architecture:
  1. DSPy Signature: defines input (metrics) → output (config changes)
  2. DSPy Module: uses LLM to generate config change suggestions
  3. Teleprompter: BootstrapFewShot learns from (metrics, config, fitness) triples
  4. Compiled module: optimized prompt that produces better config changes

The existing 7 rules remain as fallback when DSPy is unavailable or when
insufficient training data exists (< 5 examples).

Constitution compliance:
  - DSPy module is transparent (doesn't modify constitution)
  - All suggestions are evaluative (truth_effect=NONE)
  - No auto-promotion (suggestions require external validation)
  - No code modification (config changes only)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Step 9: DSPy imports (graceful degradation)
try:
    import dspy
    from dspy.teleprompt import BootstrapFewShot
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False


DSPY_AMPLIFY_VERSION = "METAENGINE-DSPY-AMPLIFY-1"


# ---------------------------------------------------------------------------
# DSPy Signature: metrics → config_changes
# ---------------------------------------------------------------------------

if DSPY_AVAILABLE:
    class AmplifySignature(dspy.Signature):
        """Given training metrics, suggest configuration changes to improve fitness."""
        metrics = dspy.InputField(desc="Training metrics: rlaif_reward, pbt_fitness, faithfulness, etc.")
        config_changes = dspy.OutputField(desc="JSON dict of config changes with rationale")

    class AmplifyModule(dspy.Module):
        """DSPy module that generates config change suggestions from metrics."""
        def __init__(self):
            super().__init__()
            self.generate = dspy.ChainOfThought(AmplifySignature)

        def forward(self, metrics: str):
            return self.generate(metrics=metrics)


@dataclass
class DSPyAmplifyResult:
    """Result of DSPy-powered amplification."""
    config_changes: dict[str, Any]
    rationale: str
    using_dspy: bool  # True if DSPy generated, False if fallback to rules
    training_examples: int  # number of examples used for compilation


class DSPyAmplifier:
    """DSPy-powered automatic amplification.

    Usage:
        amp = DSPyAmplifier()
        # Add training examples (metrics, config, fitness)
        amp.add_example(metrics, config_changes, fitness_score)
        # Compile (trains the teleprompter)
        amp.compile()
        # Generate config changes from new metrics
        result = amp.amplify(metrics)
        print(result.config_changes)

    Falls back to heuristic rules when:
      - DSPy not installed
      - < 5 training examples
      - Compilation fails
    """

    MIN_EXAMPLES_FOR_COMPILE = 5
    MAX_EXAMPLES = 100

    # Heuristic fallback (same as amplify_distill.py DEFAULT_CONFIG)
    HEURISTIC_RULES = {
        "rlaif_low_increase_temperature": {
            "condition": lambda m: m.get("rlaif_reward", 0.5) < 0.4,
            "change": lambda c: {"llm_temperature": round(min(2.0, c.get("llm_temperature", 0.4) * 1.2), 4)},
        },
        "pbt_plateau_increase_exploration": {
            "condition": lambda m: m.get("pbt_best_fitness", 0.5) < 0.7,
            "change": lambda c: {"exploration_rate": round(min(0.30, c.get("exploration_rate", 0.15) * 1.15), 4)},
        },
        "faithfulness_low_increase_provenance": {
            "condition": lambda m: m.get("faithfulness_mean", 0.5) < 0.5,
            "change": lambda c: {"rlaif_weight_provenance": round(min(0.30, c.get("rlaif_weight_provenance", 0.15) * 1.2), 4)},
        },
        "redteam_violations_increase_no_truth": {
            "condition": lambda m: m.get("redteam_violation_rate", 0.0) > 0.0,
            "change": lambda c: {"rlaif_weight_no_truth": round(min(0.30, c.get("rlaif_weight_no_truth", 0.15) * 1.3), 4)},
        },
        "es_not_converged_increase_sigma": {
            "condition": lambda m: not m.get("es_converged", False),
            "change": lambda c: {"es_sigma": round(min(0.5, c.get("es_sigma", 0.3) * 1.1), 4)},
        },
        "marl_foe_low_increase_exploit": {
            "condition": lambda m: m.get("marl_foe_mean", 0.0) < 0.05,
            "change": lambda c: {"pbt_exploit_fraction": round(min(0.50, c.get("pbt_exploit_fraction", 0.25) * 1.2), 4)},
        },
        "transfer_low_increase_max_rounds": {
            "condition": lambda m: m.get("transfer_rate", 0.0) < 0.3,
            "change": lambda c: {"max_rounds": min(8, c.get("max_rounds", 4) + 1)},
        },
    }

    def __init__(self, *, use_dspy: bool = True):
        self.use_dspy = use_dspy and DSPY_AVAILABLE
        self._examples: list[dict[str, Any]] = []  # (metrics, config, fitness)
        self._compiled_module: Any = None
        self._compile_count: int = 0
        self._last_compile_time_ms: float = 0.0

    def add_example(
        self,
        metrics: dict[str, Any],
        config_changes: dict[str, Any],
        fitness: float,
    ) -> None:
        """Add a training example for the teleprompter.

        Args:
            metrics: training metrics from a generation.
            config_changes: config changes that were applied.
            fitness: resulting fitness score (higher = better).
        """
        self._examples.append({
            "metrics": dict(metrics),
            "config_changes": dict(config_changes),
            "fitness": float(fitness),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        if len(self._examples) > self.MAX_EXAMPLES:
            self._examples = self._examples[-self.MAX_EXAMPLES:]
        # Invalidate compiled module
        self._compiled_module = None

    def compile(self) -> bool:
        """Compile the DSPy teleprompter from collected examples.

        Returns True if compilation succeeded.
        """
        if not self.use_dspy or len(self._examples) < self.MIN_EXAMPLES_FOR_COMPILE:
            return False

        try:
            started = time.perf_counter()

            # Sort examples by fitness (best first for BootstrapFewShot)
            sorted_examples = sorted(self._examples, key=lambda x: x["fitness"], reverse=True)

            # Create training set
            trainset = []
            for ex in sorted_examples[:20]:  # Use top 20 examples
                metrics_str = json.dumps(ex["metrics"], default=str)
                changes_str = json.dumps(ex["config_changes"], default=str)
                trainset.append(dspy.Example(
                    metrics=metrics_str,
                    config_changes=changes_str,
                ).with_inputs("metrics"))

            # Define a simple metric: prefer examples with higher fitness
            def amplify_metric(example, prediction, trace=None):
                # Simple metric: does the prediction match the expected changes?
                expected = example.config_changes
                predicted = prediction.config_changes if hasattr(prediction, 'config_changes') else ""
                # Simple overlap metric
                try:
                    pred_dict = json.loads(predicted) if isinstance(predicted, str) else predicted
                    overlap = len(set(pred_dict.keys()) & set(expected.keys()))
                    return overlap / max(1, len(expected))
                except Exception:
                    return 0.0

            # Compile with BootstrapFewShot
            teleprompter = BootstrapFewShot(metric=amplify_metric, max_bootstrapped_demos=3, max_labeled_demos=5)
            self._compiled_module = teleprompter.compile(AmplifyModule(), trainset=trainset)
            self._compile_count += 1
            self._last_compile_time_ms = (time.perf_counter() - started) * 1000
            return True
        except Exception:
            self._compiled_module = None
            return False

    def amplify(
        self,
        metrics: dict[str, Any],
        current_config: dict[str, Any] | None = None,
    ) -> DSPyAmplifyResult:
        """Generate config changes from metrics.

        Uses DSPy compiled module when available, falls back to heuristic rules.
        """
        config = dict(current_config or {})
        n_examples = len(self._examples)

        # Try DSPy first
        if self.use_dspy and self._compiled_module is not None:
            try:
                metrics_str = json.dumps(metrics, default=str)
                prediction = self._compiled_module(metrics=metrics_str)
                changes_text = prediction.config_changes if hasattr(prediction, 'config_changes') else ""

                # Parse the predicted changes
                try:
                    changes = json.loads(changes_text) if isinstance(changes_text, str) else changes_text
                    if isinstance(changes, dict) and changes:
                        return DSPyAmplifyResult(
                            config_changes=changes,
                            rationale=f"DSPy-generated (compiled with {n_examples} examples)",
                            using_dspy=True,
                            training_examples=n_examples,
                        )
                except (json.JSONDecodeError, TypeError):
                    pass  # Fall through to heuristic
            except Exception:
                pass  # Fall through to heuristic

        # Heuristic fallback (same as existing 7 rules)
        changes: dict[str, Any] = {}
        rationales: list[str] = []

        for rule_name, rule in self.HEURISTIC_RULES.items():
            try:
                if rule["condition"](metrics):
                    change = rule["change"](config)
                    changes.update(change)
                    rationales.append(f"{rule_name}: applied {change}")
            except Exception:
                pass

        rationale = "; ".join(rationales) if rationales else "No changes needed — metrics within acceptable ranges"

        return DSPyAmplifyResult(
            config_changes=changes,
            rationale=rationale,
            using_dspy=False,
            training_examples=n_examples,
        )

    def state(self) -> dict[str, Any]:
        """Return amplifier state for inspection."""
        return {
            "dspy_amplify_version": DSPY_AMPLIFY_VERSION,
            "dspy_available": DSPY_AVAILABLE,
            "use_dspy": self.use_dspy,
            "compiled": self._compiled_module is not None,
            "example_count": len(self._examples),
            "compile_count": self._compile_count,
            "last_compile_time_ms": round(self._last_compile_time_ms, 2),
            "min_examples_for_compile": self.MIN_EXAMPLES_FOR_COMPILE,
            "heuristic_rules": len(self.HEURISTIC_RULES),
            "truth_effect": "NONE",
        }
