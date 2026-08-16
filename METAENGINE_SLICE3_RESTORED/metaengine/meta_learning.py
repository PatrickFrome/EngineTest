"""METAENGINE Phase 30 — Meta-Learning (learning to learn).

Compares experiment selection strategies to determine which approach
to experiment selection is most efficient. This is "learning to learn":
the engine optimizes its own research process, not just its architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .util import canonical_hash


META_LEARNING_VERSION = "METAENGINE-META-LEARNING-1"


@dataclass(frozen=True)
class StrategyRecord:
    """Record of an experiment selection strategy's performance."""
    strategy_id: str
    experiments_run: int
    correct_predictions: int
    compute_cost: float

    @property
    def accuracy(self) -> float:
        return self.correct_predictions / max(1, self.experiments_run)

    @property
    def efficiency(self) -> float:
        """Accuracy per unit compute cost."""
        return self.accuracy / max(0.01, self.compute_cost)


@dataclass(frozen=True)
class MetaLearningResult:
    """Result of comparing experiment selection strategies."""
    best_strategy: str
    improvement_ratio: float
    strategies: dict[str, dict[str, float]]
    result_hash: str
    truth_effect: str

    def payload(self) -> dict[str, Any]:
        return {
            "meta_learning_version": META_LEARNING_VERSION,
            "best_strategy": self.best_strategy,
            "improvement_ratio": round(self.improvement_ratio, 6),
            "strategies": self.strategies,
            "truth_effect": self.truth_effect,
            "claim_ceiling": "META_LEARNING_IS_EVALUATIVE_NOT_TRUTH",
        }


class MetaLearner:
    """Compares experiment selection strategies to optimize the research process."""

    def __init__(self):
        self._strategies: dict[str, StrategyRecord] = {}

    def record_strategy(
        self,
        strategy_id: str,
        experiments_run: int,
        correct_predictions: int,
        compute_cost: float,
    ) -> None:
        """Record the performance of an experiment selection strategy."""
        self._strategies[strategy_id] = StrategyRecord(
            strategy_id=strategy_id,
            experiments_run=experiments_run,
            correct_predictions=correct_predictions,
            compute_cost=compute_cost,
        )

    def compare_strategies(self) -> MetaLearningResult:
        """Compare all recorded strategies and determine the best."""
        if not self._strategies:
            result = MetaLearningResult(
                best_strategy="none",
                improvement_ratio=0.0,
                strategies={},
                result_hash="",
                truth_effect="NONE",
            )
            return MetaLearningResult(**{**result.__dict__, "result_hash": canonical_hash(result.payload())})

        # Rank by efficiency (accuracy / cost)
        ranked = sorted(self._strategies.values(), key=lambda s: -s.efficiency)
        best = ranked[0]
        worst = ranked[-1]

        improvement = best.efficiency / max(0.01, worst.efficiency) if worst.efficiency > 0 else 1.0

        strategies = {
            s.strategy_id: {
                "accuracy": round(s.accuracy, 6),
                "efficiency": round(s.efficiency, 6),
                "experiments": s.experiments_run,
                "correct": s.correct_predictions,
                "cost": s.compute_cost,
            }
            for s in ranked
        }

        result = MetaLearningResult(
            best_strategy=best.strategy_id,
            improvement_ratio=improvement,
            strategies=strategies,
            result_hash="",
            truth_effect="NONE",
        )
        h = canonical_hash(result.payload())
        return MetaLearningResult(**{**result.__dict__, "result_hash": h})
