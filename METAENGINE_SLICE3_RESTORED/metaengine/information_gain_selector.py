"""METAENGINE Phase 21 — Information-Gain Experiment Selection.

Selects experiments based on expected information gain, not just expected
performance gain. This optimizes the RATE of learning about the architecture
space, not just the quality of the current best architecture.

Formula: information_gain = expected_gain × uncertainty × novelty / cost
"""

from __future__ import annotations

from typing import Any, Mapping


SELECTOR_VERSION = "METAENGINE-INFORMATION-GAIN-SELECTOR-1"


class InformationGainSelector:
    """Selects experiments by maximizing information gain per unit cost."""

    def select(
        self,
        candidates: list[dict[str, Any]],
        *,
        budget: float,
    ) -> list[dict[str, Any]]:
        """Select experiments that maximize information gain within budget.

        Args:
            candidates: List of dicts with keys: id, expected_gain, uncertainty, novelty, cost.
            budget: Maximum total cost.

        Returns:
            Selected candidates sorted by information gain (descending).
        """
        scored = []
        for c in candidates:
            gain = self._compute_info_gain(
                expected_gain=c.get("expected_gain", 0.5),
                uncertainty=c.get("uncertainty", 0.5),
                novelty=c.get("novelty", 0.5),
                cost=c.get("cost", 1.0),
            )
            scored.append((gain, c))

        # Sort by information gain (descending)
        scored.sort(key=lambda x: -x[0])

        # Greedy selection within budget
        selected: list[dict[str, Any]] = []
        remaining_budget = budget
        for gain, c in scored:
            cost = c.get("cost", 1.0)
            if cost <= remaining_budget:
                selected.append(c)
                remaining_budget -= cost

        return selected

    def _compute_info_gain(
        self,
        *,
        expected_gain: float,
        uncertainty: float,
        novelty: float,
        cost: float,
    ) -> float:
        """Compute information gain: expected_gain × uncertainty × novelty / cost."""
        if cost <= 0:
            return 0.0
        return expected_gain * uncertainty * novelty / cost
