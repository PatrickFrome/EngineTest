from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .util import canonical_hash


PATTERN_SOURCES = [
    {
        "system": "Anthropic Research",
        "pattern": "BREADTH_FIRST_ORCHESTRATOR_WORKERS",
        "integration": "parallel domain workstreams with explicit delegation contracts",
    },
    {
        "system": "Microsoft Magentic-One",
        "pattern": "TASK_LEDGER_PROGRESS_LEDGER_REPLAN",
        "integration": "fact/assumption/unknown separation and stall-triggered replanning",
    },
    {
        "system": "Google AI Co-Scientist",
        "pattern": "GENERATION_REFLECTION_RANKING_EVOLUTION_META_REVIEW",
        "integration": "role-separated candidate evaluation without truth voting",
    },
    {
        "system": "Google DeepMind AlphaEvolve",
        "pattern": "CANDIDATE_ARCHIVE_EVALUATOR_ENSEMBLE",
        "integration": "Pareto archive and deterministic evaluator ensemble",
    },
    {
        "system": "DSPy GEPA",
        "pattern": "TRACE_DRIVEN_REFLECTIVE_POLICY_EVOLUTION",
        "integration": "shadow policy candidates that require an external benchmark",
    },
    {
        "system": "OpenAI Agents SDK",
        "pattern": "TYPED_HANDOFFS_GUARDRAILS_TRACING",
        "integration": "hash-bound handoffs, local guardrails and event receipts",
    },
]


DOMAIN_WORKSTREAMS = {
    "PHILOSOPHICAL_HERMENEUTICS": (
        "Expose rival interpretations and source-resistant questions",
        ["engine_01", "engine_03", "engine_04", "engine_02", "engine_14"],
    ),
    "SEMANTIC_SCOPE": (
        "Test parse, scope, modality, attribution and counterfactual alternatives",
        ["engine_04", "engine_03", "engine_01", "engine_02"],
    ),
    "EVIDENCE_RESEARCH": (
        "Acquire independent evidence and track citation-level provenance",
        ["engine_07", "engine_09", "engine_06", "engine_13", "engine_14"],
    ),
    "GRAPH_RELATIONAL": (
        "Map entities, relations, communities and contradictory paths",
        ["engine_06", "engine_05", "engine_14", "engine_13"],
    ),
    "MEMORY_LONGITUDINAL": (
        "Recover prior states, biographies and temporal contradictions",
        ["engine_05", "engine_06", "engine_12", "engine_03"],
    ),
    "HYPOTHESIS_EXPERIMENT": (
        "Generate falsifiable candidates and discriminating experiments",
        ["engine_15", "engine_16", "engine_07", "engine_04", "engine_02"],
    ),
    "WORKFLOW_ORCHESTRATION": (
        "Decompose execution, expose dependencies and test recovery paths",
        ["engine_08", "engine_10", "engine_11", "engine_12", "engine_16"],
    ),
    "OPTIMIZATION": (
        "Propose measurable policy variants without self-deployment",
        ["engine_16", "engine_11", "engine_12", "engine_15"],
    ),
    "MULTI_PERSPECTIVE": (
        "Preserve dissent and construct independent rival accounts",
        ["engine_14", "engine_04", "engine_07", "engine_02", "engine_03"],
    ),
}


EVALUATOR_WEIGHTS = {
    "verified_source_alignment": 0.30,
    "actual_output_provenance": 0.20,
    "external_outcome": 0.25,
    "measured_cost_efficiency": 0.10,
    "execution_integrity": 0.10,
    "abstention_safety": 0.05,
}


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _hash_record(record: dict, field: str) -> dict:
    result = dict(record)
    result[field] = canonical_hash({k: v for k, v in result.items() if k != field})
    return result


@dataclass(frozen=True)
class FrontierDecision:
    replan_required: bool
    stop_recommended: bool
    reasons: tuple[str, ...]


class FrontierControlPlane:
    """Evidence-control overlay for MetaEngine 16X.

    The control plane changes task decomposition, execution ordering and shadow
    policy candidates. It cannot create evidence, promote claims or mutate an
    immutable engine lineage.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.task_ledger: dict = {}
        self.rounds: list[dict] = []
        self.archive: dict[str, dict] = {}
        self.policy_candidates: list[dict] = []
        self._seen_transformation_types: set[str] = set()

    def create_task_ledger(
        self,
        routing: dict,
        disagreements: dict,
        mesh: dict,
        input_hash: str,
        primary_statuses: dict[str, str] | None = None,
    ) -> dict:
        fingerprint = routing["task_fingerprint"]
        active = list(fingerprint.get("active_domains", []))
        workstreams = []
        for ordinal, domain in enumerate(active, 1):
            objective, preferred = DOMAIN_WORKSTREAMS.get(
                domain,
                ("Construct an independent account and expose unresolved assumptions", []),
            )
            workstreams.append(
                {
                    "workstream_id": f"ws-{ordinal:02d}-{domain.lower()}",
                    "domain": domain,
                    "objective": objective,
                    "preferred_engines": preferred,
                    "execution_shape": "BREADTH_FIRST_THEN_EVIDENCE_GATED_DEPTH",
                    "status": "OPEN",
                }
            )
        if not workstreams:
            workstreams.append(
                {
                    "workstream_id": "ws-01-general",
                    "domain": "MULTI_PERSPECTIVE",
                    "objective": DOMAIN_WORKSTREAMS["MULTI_PERSPECTIVE"][0],
                    "preferred_engines": DOMAIN_WORKSTREAMS["MULTI_PERSPECTIVE"][1],
                    "execution_shape": "BREADTH_FIRST_THEN_EVIDENCE_GATED_DEPTH",
                    "status": "OPEN",
                }
            )

        conflicts = disagreements.get("conflicts", [])
        primary_statuses = primary_statuses or {}
        successful_states = {"COMPLETE", "DEGRADED", "REFERENCE_SIMULATION_COMPLETE", "ABSTAIN", "UNRESOLVED"}
        primary_success = sum(status in successful_states for status in primary_statuses.values())
        facts = [
            {
                "statement": f"Observed {primary_success} non-failed primary results from {len(primary_statuses)} reported executions",
                "provenance": ["META_RUN.json", "engines/*/CONTRIBUTION.json"],
            },
            {
                "statement": f"Primary mesh contains {len(mesh.get('research_agenda', []))} agenda items",
                "provenance": ["HYBRID_MESH_PRIMARY.json"],
            },
            {
                "statement": f"Primary disagreement map contains {disagreements.get('conflict_count', 0)} conflicts",
                "provenance": ["DISAGREEMENT_MAP_PRIMARY.json"],
            },
        ]
        assumptions = [
            {
                "statement": "Keyword-derived task domains are routing hypotheses, not semantic facts",
                "status": "REQUIRES_OUTCOME_CALIBRATION",
            },
            {
                "statement": "Expected epistemic gain is a compute-allocation heuristic, not authority",
                "status": "NON_EPISTEMIC_POLICY",
            },
        ]
        unknowns = [
            {
                "unknown_id": f"unknown-{index:03d}",
                "kind": conflict.get("kind", "UNRESOLVED_CONFLICT"),
                "description": str(conflict.get("representative", "material disagreement"))[:500],
                "resolution_gate": "PRIMARY_SOURCE_OR_INDEPENDENT_EVIDENCE",
            }
            for index, conflict in enumerate(conflicts[:24], 1)
        ]
        if not unknowns:
            unknowns.append(
                {
                    "unknown_id": "unknown-001",
                    "kind": "OPEN_WORLD_COMPLETENESS",
                    "description": "No conflict is proof of neither completeness nor correctness",
                    "resolution_gate": "INDEPENDENT_CHALLENGE_AND_EXTERNAL_EVALUATION",
                }
            )

        ledger = {
            "ledger_version": "16X-FRONTIER-TASK-LEDGER-2.3",
            "input_hash": input_hash,
            "goal": "Produce a source-grounded, independently challenged synthesis under an explicit compute budget",
            "active_domains": active,
            "facts": facts,
            "assumptions": assumptions,
            "unknowns": unknowns,
            "workstreams": workstreams,
            "completion_definition": [
                "all material outputs retain provenance",
                "unresolved conflicts remain explicit",
                "derived candidates cannot promote truth",
                "continuation must purchase measurable marginal gain",
                "unverified structural signals cannot update learning state",
            ],
            "claim_ceiling": "TASK_DECOMPOSITION_ORGANIZES_COMPUTE_NOT_TRUTH",
        }
        self.task_ledger = _hash_record(ledger, "task_ledger_hash")
        return self.task_ledger

    def required_engines(
        self,
        round_index: int,
        seen_engines: Iterable[str] = (),
        excluded: Iterable[str] = (),
        limit: int = 4,
    ) -> list[str]:
        seen = set(seen_engines)
        excluded_set = set(excluded)
        required: list[str] = []
        workstreams = self.task_ledger.get("workstreams", [])
        for workstream in workstreams:
            preferred = [
                engine_id
                for engine_id in workstream.get("preferred_engines", [])
                if engine_id not in excluded_set
            ]
            if round_index > 1:
                preferred = [e for e in preferred if e not in seen] + [e for e in preferred if e in seen]
            if preferred and preferred[0] not in required:
                required.append(preferred[0])
            if len(required) >= limit:
                break
        return required

    def _workstream_for_engine(self, engine_id: str) -> dict:
        workstreams = self.task_ledger.get("workstreams", [])
        matches = [w for w in workstreams if engine_id in w.get("preferred_engines", [])]
        if matches:
            return matches[0]
        return {
            "workstream_id": "ws-independent-challenge",
            "domain": "MULTI_PERSPECTIVE",
            "objective": "Construct an independent challenge to the current account",
        }

    def plan_round(
        self,
        round_index: int,
        scheduler_plan: dict,
        architecture: dict,
        input_hash: str,
    ) -> dict:
        handoffs = []
        selection_by_engine = {
            row["engine_id"]: row for row in scheduler_plan.get("selection", [])
        }
        for engine_id in scheduler_plan.get("selected", []):
            workstream = self._workstream_for_engine(engine_id)
            contract = {
                "handoff_version": "16X-TYPED-HANDOFF-2.3",
                "round": round_index,
                "engine_id": engine_id,
                "workstream_id": workstream["workstream_id"],
                "objective": workstream["objective"],
                "input_refs": {
                    "original_source_hash": input_hash,
                    "task_ledger_hash": self.task_ledger.get("task_ledger_hash"),
                    "scheduler_plan_hash": scheduler_plan.get("plan_hash"),
                    "architecture_hash": architecture.get("architecture_hash"),
                },
                "budget_units": selection_by_engine.get(engine_id, {}).get("cost_units", 0),
                "required_output": "TYPED_TRANSFORMATION_OR_EXPLICIT_ABSTENTION",
                "guardrails": [
                    "ORIGINAL_SOURCE_IS_THE_ONLY_PRIMARY_EVIDENCE",
                    "DERIVED_CONTEXT_IS_GENERATIVE_ONLY",
                    "NO_TRUTH_PROMOTION_FROM_RANKING_OR_VOTING",
                    "ABSTENTION_MUST_BE_PRESERVED",
                    "EVERY_MUTATION_REQUIRES_A_RECEIPT",
                    "SELF_UPDATE_CANNOT_MUTATE_VERIFIERS_OR_SAFETY_BOUNDARY",
                ],
            }
            handoffs.append(_hash_record(contract, "handoff_hash"))

        previous = self.rounds[-1] if self.rounds else None
        plan = {
            "round_plan_version": "16X-FRONTIER-ROUND-PLAN-2.3",
            "round": round_index,
            "strategy": "BREADTH_FIRST_ORCHESTRATOR_WORKERS" if round_index == 1 else "EVIDENCE_GATED_ADAPTIVE_DEPTH",
            "replan_from_previous": bool(previous and previous["progress_ledger"]["replan_required"]),
            "selected_topology_id": architecture.get("selected_topology_id"),
            "handoffs": handoffs,
            "evaluator_ensemble": [
                "VERIFIED_SOURCE_ALIGNMENT",
                "ACTUAL_OUTPUT_PROVENANCE",
                "EXTERNAL_OUTCOME",
                "MEASURED_COST_EFFICIENCY",
                "EXECUTION_INTEGRITY",
                "ABSTENTION_SAFETY",
            ],
            "claim_ceiling": "HANDOFFS_AND_EVALUATORS_CONTROL_EXECUTION_NOT_TRUTH",
        }
        return _hash_record(plan, "round_plan_hash")

    @staticmethod
    def pressure_lines(engine_id: str, round_plan: dict) -> list[str]:
        handoff = next(
            (h for h in round_plan.get("handoffs", []) if h.get("engine_id") == engine_id),
            None,
        )
        if not handoff:
            return []
        return [
            f"handoff:{handoff['handoff_hash']}",
            f"workstream:{handoff['workstream_id']}",
            f"objective:{handoff['objective']}",
            "guardrail:derived_context_is_generative_only",
        ]

    def _candidate(self, row: dict) -> dict:
        transformations = row.get("transformations", [])
        types = sorted({t.get("type") for t in transformations if t.get("type")})
        peers = sorted(
            {
                peer
                for transformation in transformations
                for peer in transformation.get("peer_sources", [])
            }
        )
        verifier = row.get("verifier_report") or {}
        verifier_metrics = verifier.get("metrics") or {}
        observed = row.get("observed_outcome")
        externally_verified = row.get("verification_status") == "EXTERNALLY_VERIFIED" and observed is not None
        provenance_score = sum(t.get("provenance") == "ACTUAL_EXECUTOR_OUTPUT" for t in transformations) / max(1, len(transformations))
        actual_usage = row.get("actual_usage") or {}
        wall_seconds = actual_usage.get("wall_seconds")
        measured_efficiency = (float(observed) / max(0.001, float(wall_seconds))) if externally_verified and wall_seconds is not None else 0.0
        evaluator_scores = {
            "verified_source_alignment": _bounded(verifier_metrics.get("source_span_precision", 0.0)),
            "actual_output_provenance": _bounded(provenance_score),
            "external_outcome": _bounded(observed if externally_verified else 0.0),
            "measured_cost_efficiency": _bounded(measured_efficiency),
            "execution_integrity": 1.0 if row.get("status") == "DEEP_COMPLETE" else (0.4 if row.get("status") == "DEEP_REFERENCE_SIMULATION" else 0.0),
            "abstention_safety": 1.0 if not row.get("truth_promotion_allowed", False) else 0.0,
        }
        ensemble_score = _bounded(
            sum(EVALUATOR_WEIGHTS[name] * score for name, score in evaluator_scores.items())
        )
        candidate = {
            "candidate_version": "16X-FRONTIER-CANDIDATE-2.3",
            "engine_id": row["engine_id"],
            "receipt_hash": row.get("receipt_hash"),
            "transformation_types": types,
            "peer_sources": peers,
            "predicted_gain": row.get("predicted_gain"),
            "observed_outcome": observed if externally_verified else None,
            "verification_status": row.get("verification_status", "UNVERIFIED"),
            "actual_usage": actual_usage,
            "evaluator_scores": evaluator_scores,
            "ensemble_score": ensemble_score,
            "truth_effect": "NONE",
            "eligible_for_truth_promotion": False,
        }
        candidate["candidate_id"] = "cand-" + canonical_hash(candidate)[:20]
        return candidate

    @staticmethod
    def _pareto_ids(candidates: list[dict]) -> list[str]:
        dimensions = [
            "verified_source_alignment",
            "actual_output_provenance",
            "external_outcome",
            "measured_cost_efficiency",
            "execution_integrity",
            "abstention_safety",
        ]
        pareto = []
        for candidate in candidates:
            scores = candidate["evaluator_scores"]
            dominated = False
            for rival in candidates:
                if rival is candidate:
                    continue
                rival_scores = rival["evaluator_scores"]
                if all(rival_scores[d] >= scores[d] for d in dimensions) and any(
                    rival_scores[d] > scores[d] for d in dimensions
                ):
                    dominated = True
                    break
            if not dominated:
                pareto.append(candidate["candidate_id"])
        return sorted(pareto)

    @staticmethod
    def _tournament(candidates: list[dict]) -> list[dict]:
        rows = []
        for candidate in candidates:
            wins = losses = ties = 0
            for rival in candidates:
                if rival is candidate:
                    continue
                left = candidate.get("observed_outcome")
                right = rival.get("observed_outcome")
                if left is None or right is None:
                    ties += 1
                    continue
                delta = left - right
                if delta > 0.01:
                    wins += 1
                elif delta < -0.01:
                    losses += 1
                else:
                    ties += 1
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "pairwise_external_outcome_score": wins - losses,
                    "epistemic_authority": False,
                    "unverified_comparisons_are_ties": True,
                }
            )
        return sorted(rows, key=lambda row: (-row["pairwise_external_outcome_score"], row["candidate_id"]))

    def _policy_candidate(
        self,
        round_index: int,
        architecture: dict,
        average_outcome: float | None,
        new_type_count: int,
    ) -> dict | None:
        repeated_topology = bool(
            self.rounds
            and self.rounds[-1]["progress_ledger"].get("selected_topology_id")
            == architecture.get("selected_topology_id")
        )
        mutation = None
        rationale = []
        if average_outcome is None:
            mutation = "REQUIRE_EXTERNAL_OUTCOME_BEFORE_LEARNING"
            rationale.append("no externally verified outcome is available")
        elif repeated_topology and average_outcome < 0.20:
            mutation = "TOPOLOGY_DIVERSITY_FLOOR"
            rationale.append("repeated topology with weak externally observed outcome")
        elif new_type_count == 0:
            mutation = "ROUTER_HIGH_RESOLUTION_TASK_STATE"
            rationale.append("round created no new transformation type")
        elif average_outcome < 0.16:
            mutation = "BREADTH_FIRST_WORKSTREAM_REDECOMPOSITION"
            rationale.append("external verifier observed low average outcome")
        if not mutation:
            return None
        policy = {
            "policy_candidate_version": "16X-SHADOW-POLICY-2.3",
            "round": round_index,
            "mutation": mutation,
            "rationale": rationale,
            "deployment_status": "SHADOW_ONLY",
            "acceptance_gate": "PREREGISTERED_EXTERNAL_BENCHMARK_PLUS_SAFETY_REGRESSION",
            "self_deployment_allowed": False,
            "truth_effect": "NONE",
        }
        policy["policy_candidate_id"] = "policy-" + canonical_hash(policy)[:20]
        return policy

    def evaluate_round(
        self,
        round_index: int,
        round_plan: dict,
        engine_rows: list[dict],
        transformation_metrics: dict,
        depth_decision: dict,
        architecture: dict,
    ) -> dict:
        candidates = [self._candidate(row) for row in engine_rows]
        prior_types = set(self._seen_transformation_types)
        current_types = {
            transformation_type
            for candidate in candidates
            for transformation_type in candidate["transformation_types"]
        }
        new_types = current_types - prior_types
        self._seen_transformation_types.update(current_types)
        for candidate in candidates:
            self.archive[candidate["candidate_id"]] = candidate

        tournament = self._tournament(candidates)
        pareto_ids = self._pareto_ids(candidates)
        verified_outcomes = [c["observed_outcome"] for c in candidates if c.get("observed_outcome") is not None]
        average_outcome = sum(verified_outcomes) / len(verified_outcomes) if verified_outcomes else None
        average_ensemble = sum(c["ensemble_score"] for c in candidates) / max(1, len(candidates))
        reasons = []
        if not new_types:
            reasons.append("NO_NEW_TRANSFORMATION_TYPE")
        if average_outcome is None:
            reasons.append("EXTERNAL_OUTCOME_UNAVAILABLE")
        elif average_outcome < 0.16:
            reasons.append("LOW_EXTERNAL_OUTCOME")
        if depth_decision.get("stop_decision") in {"STOP_RECURSIVE_ECHO", "STOP_MARGINAL_GAIN"}:
            reasons.append(depth_decision["stop_decision"])
        decision = FrontierDecision(
            replan_required=bool(reasons),
            stop_recommended=("STOP_RECURSIVE_ECHO" in reasons or len(reasons) >= 2),
            reasons=tuple(sorted(set(reasons))),
        )
        progress = {
            "progress_ledger_version": "16X-FRONTIER-PROGRESS-2.3",
            "round": round_index,
            "selected_topology_id": architecture.get("selected_topology_id"),
            "candidate_count": len(candidates),
            "pareto_candidate_count": len(pareto_ids),
            "new_transformation_types": sorted(new_types),
            "average_observed_outcome": round(average_outcome, 4) if average_outcome is not None else None,
            "externally_verified_candidate_count": len(verified_outcomes),
            "average_ensemble_score": round(average_ensemble, 4),
            "causal_depth": transformation_metrics.get("causal_depth", 0),
            "replan_required": decision.replan_required,
            "stop_recommended": decision.stop_recommended,
            "reasons": list(decision.reasons),
            "claim_ceiling": "PROGRESS_METRICS_CONTROL_COMPUTE_NOT_TRUTH",
        }
        progress = _hash_record(progress, "progress_ledger_hash")
        policy = self._policy_candidate(
            round_index,
            architecture,
            average_outcome,
            len(new_types),
        )
        if policy:
            self.policy_candidates.append(policy)

        evaluation = {
            "evaluation_version": "16X-EVALUATOR-ENSEMBLE-2.3",
            "round": round_index,
            "candidates": candidates,
            "tournament": tournament,
            "pareto_candidate_ids": pareto_ids,
            "policy_candidate": policy,
            "progress_ledger": progress,
            "invariants": {
                "ranking_is_not_truth": True,
                "evaluator_scores_are_policy_signals": True,
                "policy_candidates_are_shadow_only": True,
                "source_regrounding_remains_mandatory": True,
                "unverified_results_cannot_train_or_promote": True,
            },
        }
        evaluation = _hash_record(evaluation, "evaluation_hash")
        self.rounds.append(evaluation)
        return evaluation

    def artifact(self) -> dict:
        archive = sorted(
            self.archive.values(),
            key=lambda candidate: (-candidate["ensemble_score"], candidate["candidate_id"]),
        )
        artifact = {
            "control_plane_version": "16X-FRONTIER-EVIDENCE-CONTROL-2.3",
            "pattern_sources": PATTERN_SOURCES,
            "task_ledger": self.task_ledger,
            "rounds": self.rounds,
            "candidate_archive": archive,
            "policy_candidates": self.policy_candidates,
            "invariants": {
                "native_lineages_are_immutable": True,
                "candidate_archive_has_no_epistemic_authority": True,
                "automated_evaluation_cannot_promote_truth": True,
                "policy_evolution_requires_external_acceptance": True,
                "typed_handoffs_are_hash_bound": True,
                "stall_can_replan_execution_topology": True,
            },
            "claim_ceiling": "FRONTIER_PATTERNS_IMPROVE_CONTROL_AND_EVALUATION_NOT_EXTERNAL_REASONING_SUPERIORITY",
        }
        return _hash_record(artifact, "control_plane_hash")
