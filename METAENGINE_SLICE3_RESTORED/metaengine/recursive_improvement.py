"""METAENGINE Phase 16 — Recursive Self-Improvement Measurement.

Compares researcher generations (G0 vs G1) to measure whether the engine
actually improves at finding good architectures over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .util import canonical_hash


RECURSIVE_VERSION = "METAENGINE-RECURSIVE-IMPROVEMENT-1"


@dataclass(frozen=True)
class GenerationResult:
    """Result of comparing two researcher generations."""
    g0_accuracy: float  # correct predictions / total experiments
    g1_accuracy: float
    g0_experiments: int
    g1_experiments: int
    g1_better: bool
    improvement_ratio: float
    efficiency_improved: bool
    experiment_reduction: int  # how many fewer experiments G1 needed
    result_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "recursive_version": RECURSIVE_VERSION,
            "g0_accuracy": round(self.g0_accuracy, 6),
            "g1_accuracy": round(self.g1_accuracy, 6),
            "g0_experiments": self.g0_experiments,
            "g1_experiments": self.g1_experiments,
            "g1_better": self.g1_better,
            "improvement_ratio": round(self.improvement_ratio, 6),
            "efficiency_improved": self.efficiency_improved,
            "experiment_reduction": self.experiment_reduction,
            "truth_effect": "NONE",
            "claim_ceiling": "GENERATION_COMPARISON_IS_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "result_hash": self.result_hash}


class GenerationComparator:
    """Compares two researcher generations to measure recursive improvement."""

    def compare(
        self,
        *,
        g0_experiments: int,
        g0_correct_predictions: int,
        g1_experiments: int,
        g1_correct_predictions: int,
    ) -> GenerationResult:
        """Compare G0 and G1 researcher generations.

        Metrics:
        - accuracy = correct / total
        - g1_better = G1 accuracy > G0 accuracy
        - improvement_ratio = G1_accuracy / G0_accuracy
        - efficiency_improved = G1 uses fewer experiments AND higher accuracy
        - experiment_reduction = G0_experiments - G1_experiments (positive = G1 more efficient)
        """
        g0_acc = g0_correct_predictions / max(1, g0_experiments)
        g1_acc = g1_correct_predictions / max(1, g1_experiments)
        g1_better = g1_acc > g0_acc
        improvement = g1_acc / max(0.01, g0_acc)
        exp_reduction = g0_experiments - g1_experiments
        efficiency = g1_better and exp_reduction > 0

        result = GenerationResult(
            g0_accuracy=g0_acc,
            g1_accuracy=g1_acc,
            g0_experiments=g0_experiments,
            g1_experiments=g1_experiments,
            g1_better=g1_better,
            improvement_ratio=improvement,
            efficiency_improved=efficiency,
            experiment_reduction=exp_reduction,
            result_hash="",
        )
        h = canonical_hash(result.payload())
        return GenerationResult(**{**result.__dict__, "result_hash": h})
