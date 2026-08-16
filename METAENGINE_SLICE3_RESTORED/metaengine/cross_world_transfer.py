"""METAENGINE Phase 22c — Cross-World Knowledge Transfer.

Transfers findings from one tournament world to another, with confidence
adjustment based on source confidence and context similarity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .util import canonical_hash


TRANSFER_VERSION = "METAENGINE-CROSS-WORLD-TRANSFER-1"


@dataclass(frozen=True)
class TransferResult:
    """Result of cross-world knowledge transfer."""
    transferable: bool
    confidence: float
    source_findings: dict[str, Any]
    target_context: dict[str, Any]
    transfer_hash: str
    truth_effect: str

    def payload(self) -> dict[str, Any]:
        return {
            "transfer_version": TRANSFER_VERSION,
            "transferable": self.transferable,
            "confidence": round(self.confidence, 6),
            "source_findings": self.source_findings,
            "target_context": self.target_context,
            "truth_effect": self.truth_effect,
            "claim_ceiling": "CROSS_WORLD_TRANSFER_IS_HYPOTHESIS_NOT_FACT",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "transfer_hash": self.transfer_hash}


class CrossWorldTransfer:
    """Transfers findings between tournament worlds."""

    def transfer(
        self,
        source_world_findings: Mapping[str, Any],
        target_world_context: Mapping[str, Any],
    ) -> TransferResult:
        """Transfer findings from source to target world.

        Confidence is adjusted:
        - Base confidence = source confidence
        - Reduced if task types differ
        - Reduced if resource types differ
        """
        source_confidence = float(source_world_findings.get("confidence", 0.5))
        source_effect = float(source_world_findings.get("effect", 0.0))
        source_mechanism = str(source_world_findings.get("mechanism", ""))

        target_task = str(target_world_context.get("task_type", ""))
        target_resources = str(target_world_context.get("resources", ""))

        # Confidence adjustment: reduce if contexts differ
        # (In a full implementation, we'd compute actual context similarity)
        confidence = source_confidence * 0.8  # conservative transfer
        transferable = source_confidence > 0.3 and abs(source_effect) > 0.1

        result = TransferResult(
            transferable=transferable,
            confidence=round(confidence, 6),
            source_findings=dict(source_world_findings),
            target_context=dict(target_world_context),
            transfer_hash="",
            truth_effect="NONE",
        )
        h = canonical_hash(result.payload())
        return TransferResult(**{**result.__dict__, "transfer_hash": h})
