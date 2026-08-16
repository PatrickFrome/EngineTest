from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .security import GuardrailReceipt
from .util import canonical_hash


@dataclass(frozen=True)
class OutcomeOracle:
    oracle_id: str
    required_operators: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    minimum_rival_pairs: int = 0
    require_residual_tension: bool = False
    require_source_return: bool = True
    expected_abstention: bool | None = None
    suite: str = "GENERAL"

    def commitment(self) -> str:
        return canonical_hash(
            {
                "oracle_id": self.oracle_id,
                "required_operators": self.required_operators,
                "required_terms": self.required_terms,
                "forbidden_terms": self.forbidden_terms,
                "minimum_rival_pairs": self.minimum_rival_pairs,
                "require_residual_tension": self.require_residual_tension,
                "require_source_return": self.require_source_return,
                "expected_abstention": self.expected_abstention,
                "suite": self.suite,
            }
        )


@dataclass(frozen=True)
class VerifierReport:
    verification_status: str
    metrics: dict[str, float]
    hard_failures: tuple[str, ...]
    observed_outcome: float | None
    promotion_eligible: bool
    source_hash: str
    candidate_hash: str
    oracle_commitment: str | None
    verifier_version: str = "16X-EXTERNAL-OUTCOME-VERIFIER-2.3"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        value = {
            "verifier_version": self.verifier_version,
            "verification_status": self.verification_status,
            "metrics": self.metrics,
            "hard_failures": list(self.hard_failures),
            "observed_outcome": self.observed_outcome,
            "promotion_eligible": self.promotion_eligible,
            "source_hash": self.source_hash,
            "candidate_hash": self.candidate_hash,
            "oracle_commitment": self.oracle_commitment,
            "diagnostics": self.diagnostics,
            "truth_effect": "NONE_WITHOUT_SEPARATE_CLAIM_ARBITRATION",
        }
        value["verifier_hash"] = canonical_hash(value)
        return value


class ExternalVerifierPlane:
    """Objective verifier boundary.

    When no oracle is supplied, it validates integrity and provenance but deliberately emits no
    positive learning signal. Structural richness is diagnostic and cannot promote a policy.
    """

    def evaluate(
        self,
        source_text: str,
        candidate: dict[str, Any],
        oracle: OutcomeOracle | None = None,
        guardrail_receipt: GuardrailReceipt | dict[str, Any] | None = None,
        actual_cost: dict[str, Any] | None = None,
    ) -> VerifierReport:
        source_hash = hashlib.sha256(source_text.encode()).hexdigest()
        candidate_hash = canonical_hash(candidate)
        nodes = candidate.get("nodes") or candidate.get("transformations") or []
        operators = {
            node.get("operator") or node.get("type")
            for node in nodes
            if node.get("operator") or node.get("type")
        }
        failures: list[str] = []
        span_total = span_valid = 0
        for node in nodes:
            if node.get("truth_effect") not in (None, "NONE"):
                failures.append("DERIVED_TRUTH_EFFECT")
            if node.get("provenance") == "STATIC_TYPE_MAP":
                failures.append("SYNTHETIC_TRANSFORMATION_PROVENANCE")
            for span in node.get("source_spans", []):
                span_total += 1
                start, end = int(span.get("start", -1)), int(span.get("end", -1))
                if 0 <= start <= end <= len(source_text):
                    text = source_text[start:end]
                    valid_hash = hashlib.sha256(text.encode()).hexdigest() == span.get("text_hash")
                    valid_source = span.get("source_id") in {source_hash, candidate.get("source_id")}
                    if valid_hash and valid_source:
                        span_valid += 1
                    else:
                        failures.append("SOURCE_SPAN_HASH_OR_ID_MISMATCH")
                else:
                    failures.append("SOURCE_SPAN_BOUNDS_INVALID")
        receipt = guardrail_receipt.as_dict() if isinstance(guardrail_receipt, GuardrailReceipt) else (guardrail_receipt or {})
        if receipt and not all(receipt.get(key) for key in ("contract_verified", "objective_acknowledged", "guardrails_applied")):
            failures.append("GUARDRAIL_CONTRACT_NOT_ENFORCED")
        span_precision = span_valid / max(1, span_total)
        source_bound_operators = {"SOURCE_READING", "RIVAL_FORK", "SEMANTIC_COUNTERFACTUAL", "EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"}
        nodes_requiring_source = sum((node.get("operator") or node.get("type")) in source_bound_operators for node in nodes)
        # Hermeneutic/meta-analytic nodes are allowed to expose assumptions without pretending to
        # be quotations. Coverage is measured only over operators whose contract requires spans.
        source_coverage = min(1.0, span_valid / max(1, nodes_requiring_source))
        actual_cost = actual_cost or {}
        cost = float(actual_cost.get("wall_seconds", 0.0) or 0.0)

        metrics: dict[str, float] = {
            "source_span_precision": round(span_precision, 6),
            "source_bound_coverage": round(source_coverage, 6),
            "execution_integrity": 0.0 if failures else 1.0,
            "hard_safety": 0.0 if failures else 1.0,
            "wall_seconds": round(cost, 6),
        }
        if oracle is None:
            return VerifierReport(
                "INSUFFICIENT_EXTERNAL_EVIDENCE",
                metrics,
                tuple(sorted(set(failures))),
                None,
                False,
                source_hash,
                candidate_hash,
                None,
                diagnostics={"operators_observed": sorted(x for x in operators if x), "structural_metrics_excluded_from_learning": True},
            )

        required = set(oracle.required_operators)
        operator_recall = len(required & operators) / max(1, len(required))
        body = " ".join(str(node.get("proposition", "")) for node in nodes).lower()
        term_recall = sum(term.lower() in body for term in oracle.required_terms) / max(1, len(oracle.required_terms)) if oracle.required_terms else 1.0
        forbidden_hits = sum(term.lower() in body for term in oracle.forbidden_terms)
        if forbidden_hits:
            failures.append("FORBIDDEN_OR_INJECTED_CONTENT_ACCEPTED")
        rival_pairs = len({node.get("rival_id") for node in nodes if node.get("rival_id")})
        rival_score = min(1.0, rival_pairs / max(1, oracle.minimum_rival_pairs)) if oracle.minimum_rival_pairs else 1.0
        residue_score = 1.0 if (not oracle.require_residual_tension or any(node.get("residual_tensions") for node in nodes)) else 0.0
        return_score = 1.0 if (not oracle.require_source_return or "SOURCE_RETURN" in operators) else 0.0
        expected_abstention = oracle.expected_abstention
        has_abstention = any(node.get("abstention_reason") for node in nodes)
        abstention_score = 1.0 if expected_abstention is None or has_abstention == expected_abstention else 0.0
        metrics.update(
            {
                "required_operator_recall": round(operator_recall, 6),
                "required_term_recall": round(term_recall, 6),
                "rival_preservation": round(rival_score, 6),
                "residual_tension_preservation": residue_score,
                "source_return": return_score,
                "abstention_calibration": abstention_score,
                "forbidden_content_avoidance": 0.0 if forbidden_hits else 1.0,
            }
        )
        outcome = (
            0.28 * operator_recall
            + 0.18 * span_precision
            + 0.12 * source_coverage
            + 0.10 * term_recall
            + 0.10 * rival_score
            + 0.08 * residue_score
            + 0.08 * return_score
            + 0.06 * abstention_score
        )
        if failures:
            outcome *= 0.25
        outcome = round(max(0.0, min(1.0, outcome)), 6)
        return VerifierReport(
            "EXTERNALLY_VERIFIED" if not failures else "EXTERNAL_VERIFICATION_FAILED",
            metrics,
            tuple(sorted(set(failures))),
            outcome,
            not failures,
            source_hash,
            candidate_hash,
            oracle.commitment(),
            diagnostics={"suite": oracle.suite, "operators_observed": sorted(x for x in operators if x), "actual_cost": actual_cost},
        )
