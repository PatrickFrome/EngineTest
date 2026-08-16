"""METAENGINE Phase 22b — Failure Taxonomy.

Classifies engine failures into a taxonomy to enable pattern recognition
and targeted improvement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .util import canonical_hash


FAILURE_TAXONOMY_VERSION = "METAENGINE-FAILURE-TAXONOMY-1"


class FailureClass(str, Enum):
    RESOURCE = "RESOURCE"  # timeout, OOM, rate limit
    REASONING = "REASONING"  # logical error, hallucination, unsupported claim
    ARCHITECTURE = "ARCHITECTURE"  # routing failure, topology mismatch
    EVIDENCE = "EVIDENCE"  # missing source, invalid span, ungrounded claim
    SAFETY = "SAFETY"  # boundary violation, secret leak, mutation without receipt
    UNKNOWN = "UNKNOWN"


_FAILURE_MAP = {
    "timeout": FailureClass.RESOURCE,
    "out_of_memory": FailureClass.RESOURCE,
    "rate_limit": FailureClass.RESOURCE,
    "hallucination": FailureClass.REASONING,
    "logical_error": FailureClass.REASONING,
    "unsupported_claim": FailureClass.REASONING,
    "routing_failure": FailureClass.ARCHITECTURE,
    "topology_mismatch": FailureClass.ARCHITECTURE,
    "missing_source": FailureClass.EVIDENCE,
    "invalid_span": FailureClass.EVIDENCE,
    "ungrounded_claim": FailureClass.EVIDENCE,
    "boundary_violation": FailureClass.SAFETY,
    "secret_leak": FailureClass.SAFETY,
    "mutation_without_receipt": FailureClass.SAFETY,
    "resource_exhaustion": FailureClass.RESOURCE,
}


@dataclass(frozen=True)
class FailureFinding:
    """A classified failure finding."""
    finding_id: str
    failure_type: str
    failure_class: FailureClass
    context: dict[str, Any]
    finding_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "taxonomy_version": FAILURE_TAXONOMY_VERSION,
            "finding_id": self.finding_id,
            "failure_type": self.failure_type,
            "failure_class": self.failure_class.value,
            "context": self.context,
            "truth_effect": "NONE",
            "claim_ceiling": "FAILURE_FINDING_IS_DIAGNOSTIC_NOT_TRUTH",
        }


class FailureTaxonomy:
    """Classifies failures into a taxonomy."""

    def classify(
        self,
        failure_type: str,
        context: Mapping[str, Any],
    ) -> FailureFinding:
        cls = _FAILURE_MAP.get(failure_type, FailureClass.UNKNOWN)
        ctx = dict(context)

        finding = FailureFinding(
            finding_id=f"failure.{failure_type}.{canonical_hash(ctx)[:8]}",
            failure_type=failure_type,
            failure_class=cls,
            context=ctx,
            finding_hash="",
        )
        h = canonical_hash(finding.payload())
        return FailureFinding(**{**finding.__dict__, "finding_hash": h})
