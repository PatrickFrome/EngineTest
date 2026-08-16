from __future__ import annotations

from typing import Any

from .util import canonical_hash


class AuditableSynthesizer:
    """Produces an inspectable synthesis while preserving rivals and claim ceilings."""

    @staticmethod
    def synthesize(dialectical_graph: dict[str, Any], arbitration: dict[str, Any], verifier_report: dict[str, Any]) -> dict[str, Any]:
        nodes = dialectical_graph.get("nodes", [])
        by_operator: dict[str, list[dict[str, Any]]] = {}
        for node in nodes:
            by_operator.setdefault(node.get("operator", "UNKNOWN"), []).append(node)
        decisions = arbitration.get("decisions", [])
        supported = [decision for decision in decisions if decision.get("state") in {"PROVISIONALLY_SUPPORTED", "SUPPORTED_BUT_REVIEW_REQUIRED"}]
        unresolved = [decision for decision in decisions if decision.get("state") not in {"PROVISIONALLY_SUPPORTED", "SUPPORTED_BUT_REVIEW_REQUIRED"}]
        result = {
            "synthesis_version": "16X-AUDITABLE-NONLINEAR-SYNTHESIS-2.3",
            "source_readings": by_operator.get("SOURCE_READING", []),
            "rival_readings": by_operator.get("RIVAL_FORK", []),
            "horizon_disclosures": by_operator.get("HORIZON_DISCLOSURE", []),
            "semantic_counterfactuals": by_operator.get("SEMANTIC_COUNTERFACTUAL", []),
            "genealogical_returns": by_operator.get("GENEALOGICAL_RETURN", []),
            "evidence_discriminators": by_operator.get("EVIDENCE_DISCRIMINATOR", []),
            "double_hermeneutics": by_operator.get("DOUBLE_HERMENEUTIC", []),
            "conditional_syntheses": by_operator.get("SUBLATION_WITH_RESIDUE", []),
            "operator_mutations": by_operator.get("OPERATOR_MUTATION", []),
            "source_returns": by_operator.get("SOURCE_RETURN", []),
            "arbitrated_supported_claims": supported,
            "unresolved_claims": unresolved,
            "external_verification_status": verifier_report.get("verification_status"),
            "limitations": [
                "Reference simulations are architectural contracts, not frontier model executors",
                "No externally verified outcome means this synthesis cannot train or promote a policy",
                "Conditional synthesis preserves residual tensions and has no truth authority",
            ],
            "majority_vote_used": False,
            "truth_effect": "NONE_BEYOND_EXISTING_ARBITRATION",
            "claim_ceiling": "AUDITABLE_COORDINATION_OF_READINGS_NOT_AUTOMATIC_TRUTH",
        }
        result["synthesis_hash"] = canonical_hash(result)
        return result
