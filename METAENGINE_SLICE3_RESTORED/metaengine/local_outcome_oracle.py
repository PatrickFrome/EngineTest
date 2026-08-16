"""METAENGINE Phase 2 — Local Outcome Oracle for closing the self-learning loop.

The self-learning loop is currently OPEN: biographies.update() has a gate
ONLY_EXTERNALLY_VERIFIED_OUTCOMES_UPDATE_BIOGRAPHIES, and the verifier returns
INSUFFICIENT_EXTERNAL_EVIDENCE because there is no oracle.

This module provides a LocalOutcomeOracle — a deterministic oracle that:
1. Validates source-grounded span integrity (spans point to real source text)
2. Returns VERIFIED_LOCAL (not VERIFIED — local only, not frontier)
3. Is clearly labelled LOCAL_DETERMINISTIC_OUTCOME_NOT_FRONTIER_MODEL_EQUIVALENCE
4. Allows biographies.update() to accept the outcome and update scheduler priors

This closes the learning loop: run → verified outcome → biography update →
updated priors → better scheduling on next run.

Constitutional boundary: LOCAL_DETERMINISTIC_OUTCOME is NOT scientific truth.
It is a deterministic verification that source spans are valid — the minimum
evidence needed for the engine to learn from its own deterministic runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from .util import canonical_hash
from .devfabric.codec import canonical_digest


ORACLE_VERSION = "METAENGINE-LOCAL-OUTCOME-ORACLE-1"
ORACLE_AUTHORITY = "LOCAL_DETERMINISTIC_OUTCOME_NOT_FRONTIER_MODEL_EQUIVALENCE"


@dataclass(frozen=True)
class LocalOutcomeOracle:
    """A deterministic local oracle for self-learning loop closure.

    Validates that dialectical graph nodes have source-grounded spans
    pointing to real source text. If spans are valid, returns VERIFIED_LOCAL.
    If spans are missing or invalid, returns INSUFFICIENT_LOCAL_EVIDENCE.

    This is NOT an external model — it is a deterministic check that the
    engine's output is grounded in the source text.
    """

    oracle_id: str = "local-outcome-oracle"
    source_text_hash: str = ""

    @classmethod
    def create(cls, source_text: str) -> "LocalOutcomeOracle":
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        return cls(
            oracle_id=f"local-oracle-{source_hash[:16]}",
            source_text_hash=source_hash,
        )

    def commitment(self) -> str:
        return canonical_hash({
            "oracle_id": self.oracle_id,
            "oracle_version": ORACLE_VERSION,
            "source_text_hash": self.source_text_hash,
            "authority": ORACLE_AUTHORITY,
        })

    def evaluate(
        self,
        source_text: str,
        dialectical_graph: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Evaluate the dialectical graph against the source text.

        Returns a verification result that the verifier can use as an oracle
        outcome, allowing biographies to update.
        """
        nodes = dialectical_graph.get("nodes", [])
        total_spans = 0
        valid_spans = 0
        nodes_with_spans = 0

        for node in nodes:
            spans = node.get("source_spans", [])
            if spans:
                nodes_with_spans += 1
            for span in spans:
                total_spans += 1
                start = span.get("start", -1)
                end = span.get("end", -1)
                if 0 <= start <= end <= len(source_text):
                    text = source_text[start:end]
                    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if span.get("text_hash") == expected_hash:
                        valid_spans += 1

        # Deterministic outcome: if >50% of spans are valid, VERIFIED_LOCAL
        if total_spans > 0 and valid_spans / total_spans >= 0.5:
            status = "VERIFIED_LOCAL"
            observed_outcome = {
                "quality_proxy": round(valid_spans / max(1, total_spans), 4),
                "span_coverage": round(nodes_with_spans / max(1, len(nodes)), 4),
                "source_grounding": "MAJORITY_VALID",
            }
        elif total_spans > 0:
            status = "INSUFFICIENT_LOCAL_EVIDENCE"
            observed_outcome = {
                "quality_proxy": round(valid_spans / max(1, total_spans), 4),
                "span_coverage": round(nodes_with_spans / max(1, len(nodes)), 4),
                "source_grounding": "MINORITY_VALID",
            }
        else:
            status = "NO_SOURCE_SPANS"
            observed_outcome = None

        return {
            "verification_status": status,
            "oracle_commitment": self.commitment(),
            "oracle_authority": ORACLE_AUTHORITY,
            "observed_outcome": observed_outcome,
            "total_spans": total_spans,
            "valid_spans": valid_spans,
            "nodes_with_spans": nodes_with_spans,
            "total_nodes": len(nodes),
            "promotion_eligible": False,  # local oracle never authorizes promotion
        }
