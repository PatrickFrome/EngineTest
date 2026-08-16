"""METAENGINE Phase 19 — Task-Conditional Policy Selection.

Selects organization policies based on task features (complexity, uncertainty,
context length). This enables online adaptation: different tasks get different
organizations, not a single global policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .util import canonical_hash


SELECTOR_VERSION = "METAENGINE-TASK-CONDITIONAL-SELECTOR-1"


@dataclass(frozen=True)
class PolicySelection:
    """Result of task-conditional policy selection."""
    selected_policy: str
    confidence: float
    rationale: str
    task_features: dict[str, float]
    selection_hash: str
    truth_effect: str

    def payload(self) -> dict[str, Any]:
        return {
            "selector_version": SELECTOR_VERSION,
            "selected_policy": self.selected_policy,
            "confidence": round(self.confidence, 6),
            "rationale": self.rationale,
            "task_features": self.task_features,
            "truth_effect": self.truth_effect,
            "claim_ceiling": "POLICY_SELECTION_IS_HEURISTIC_NOT_TRUTH",
        }


class TaskConditionalSelector:
    """Selects organization policies based on task features.

    Rules (deterministic, evidence-bound):
    - High uncertainty → MODEL_PLUS_VERIFIER (verification needed)
    - Low complexity → SINGLE_MODEL (simplest sufficient)
    - High complexity + low uncertainty → FEDERATION (parallel capacity)
    - Default: highest biography prior
    """

    def __init__(self):
        self._experience: dict[str, list[float]] = {}  # policy → list of actual qualities

    def select(
        self,
        *,
        task_features: Mapping[str, float],
        available_policies: list[str],
        biography_priors: Mapping[str, float],
    ) -> PolicySelection:
        complexity = task_features.get("complexity", 0.5)
        uncertainty = task_features.get("uncertainty", 0.5)

        selected = None
        rationale = ""
        confidence = 0.5

        # Rule 1: high uncertainty → verifier
        # Fix 6: Use OrganizationType enum values (RESOURCE_PLUS_VERIFIER, not MODEL_PLUS_VERIFIER)
        if uncertainty > 0.7 and "RESOURCE_PLUS_VERIFIER" in available_policies:
            selected = "RESOURCE_PLUS_VERIFIER"
            rationale = f"High uncertainty ({uncertainty:.2f}) → verifier needed"
            confidence = 0.8

        # Rule 2: low complexity → simplest
        elif complexity < 0.3 and "ONE_RESOURCE" in available_policies:
            selected = "ONE_RESOURCE"
            rationale = f"Low complexity ({complexity:.2f}) → simplest sufficient"
            confidence = 0.85

        # Rule 3: high complexity + low uncertainty → federation
        elif complexity > 0.7 and uncertainty < 0.3 and "HIERARCHICAL_FEDERATION" in available_policies:
            selected = "HIERARCHICAL_FEDERATION"
            rationale = f"High complexity ({complexity:.2f}) + low uncertainty ({uncertainty:.2f}) → parallel capacity"
            confidence = 0.7

        # Default: highest biography prior + experience
        if selected is None or selected not in available_policies:
            # Use biography priors + experience
            best_score = -1.0
            for p in available_policies:
                bio = biography_priors.get(p, 0.5)
                exp = sum(self._experience.get(p, [0.5])) / max(1, len(self._experience.get(p, [0.5])))
                score = 0.5 * bio + 0.5 * exp
                if score > best_score:
                    best_score = score
                    selected = p
            rationale = f"Best combined score (biography + experience): {best_score:.2f}"
            confidence = best_score

        result = PolicySelection(
            selected_policy=selected,
            confidence=round(confidence, 6),
            rationale=rationale,
            task_features=dict(task_features),
            selection_hash="",
            truth_effect="NONE",
        )
        h = canonical_hash(result.payload())
        return PolicySelection(**{**result.__dict__, "selection_hash": h})

    def update(self, policy: str, *, actual_quality: float, task_features: Mapping[str, float]):
        """Update experience with actual outcome."""
        if policy not in self._experience:
            self._experience[policy] = []
        self._experience[policy].append(actual_quality)
