"""METAENGINE Phase 15 — Causal Attribution Engine.

Determines WHY an architecture won, not just THAT it won.
Uses ablation results to build causal findings: "mechanism M is responsible
for effect E of size S with confidence C."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .util import canonical_hash


CAUSAL_VERSION = "METAENGINE-CAUSAL-ATTRIBUTION-1"


@dataclass(frozen=True)
class CausalFinding:
    """A causal finding: component X causes effect Y of size Z."""
    finding_id: str
    winner_policy: str
    loser_policy: str
    component: str
    effect_size: float
    confidence: float
    finding_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "causal_version": CAUSAL_VERSION,
            "finding_id": self.finding_id,
            "winner_policy": self.winner_policy,
            "loser_policy": self.loser_policy,
            "component": self.component,
            "effect_size": round(self.effect_size, 6),
            "confidence": round(self.confidence, 6),
            "truth_effect": "NONE",
            "claim_ceiling": "CAUSAL_FINDING_IS_LOCAL_NOT_UNIVERSAL",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "finding_hash": self.finding_hash}


class CausalAttributionEngine:
    """Attributes causal effects from ablation results."""

    def attribute(
        self,
        *,
        winner_policy: str,
        loser_policy: str,
        ablated_component: str,
        quality_with: float,
        quality_without: float,
    ) -> CausalFinding:
        """Attribute the quality difference to the ablated component.

        effect_size = quality_with - quality_without
        confidence = min(1.0, |effect_size| / max(0.01, quality_with))
        """
        effect = quality_with - quality_without
        confidence = min(1.0, abs(effect) / max(0.01, quality_with)) if quality_with > 0 else 0.0

        finding = CausalFinding(
            finding_id=f"causal.{ablated_component}.{winner_policy[:8]}",
            winner_policy=winner_policy,
            loser_policy=loser_policy,
            component=ablated_component,
            effect_size=round(effect, 6),
            confidence=round(confidence, 6),
            finding_hash="",
        )
        h = canonical_hash(finding.payload())
        return CausalFinding(**{**finding.__dict__, "finding_hash": h})
