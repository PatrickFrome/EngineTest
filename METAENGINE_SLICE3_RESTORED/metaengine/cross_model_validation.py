"""METAENGINE Phase 29 — Cross-Model Validation.

Validates that a mechanism is model-independent: it works across
different model adapters, not just one. This proves the mechanism
is transferable, not model-specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .util import canonical_hash


VALIDATION_VERSION = "METAENGINE-CROSS-MODEL-VALIDATION-1"
INDEPENDENCE_THRESHOLD = 0.2  # max quality delta for model independence


@dataclass(frozen=True)
class ValidationResult:
    """Result of cross-model validation."""
    mechanism_id: str
    model_a_results: dict[str, float]
    model_b_results: dict[str, float]
    quality_delta: float
    model_independent: bool
    validation_hash: str
    truth_effect: str

    def payload(self) -> dict[str, Any]:
        return {
            "validation_version": VALIDATION_VERSION,
            "mechanism_id": self.mechanism_id,
            "model_a_results": self.model_a_results,
            "model_b_results": self.model_b_results,
            "quality_delta": round(self.quality_delta, 6),
            "model_independent": self.model_independent,
            "truth_effect": self.truth_effect,
            "claim_ceiling": "CROSS_MODEL_VALIDATION_IS_EVALUATIVE_NOT_TRUTH",
        }


class CrossModelValidator:
    """Validates mechanism model-independence across different model adapters."""

    def validate(
        self,
        *,
        mechanism_id: str,
        model_a_results: Mapping[str, float],
        model_b_results: Mapping[str, float],
    ) -> ValidationResult:
        """Validate that a mechanism produces similar results across models.

        If quality delta < INDEPENDENCE_THRESHOLD → model_independent=True.
        Otherwise → model-dependent (the mechanism relies on specific model capabilities).
        """
        q_a = float(model_a_results.get("quality", 0.0))
        q_b = float(model_b_results.get("quality", 0.0))
        delta = abs(q_a - q_b)
        independent = delta < INDEPENDENCE_THRESHOLD

        result = ValidationResult(
            mechanism_id=mechanism_id,
            model_a_results=dict(model_a_results),
            model_b_results=dict(model_b_results),
            quality_delta=delta,
            model_independent=independent,
            validation_hash="",
            truth_effect="NONE",
        )
        h = canonical_hash(result.payload())
        return ValidationResult(**{**result.__dict__, "validation_hash": h})
