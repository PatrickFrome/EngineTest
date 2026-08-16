from __future__ import annotations

import hashlib
import itertools
import math
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .architecture_policy import ArchitecturePolicy, DIALECTIC_OPERATORS, PolicyStore, mutate_policy
from .dialectical_graph import DialecticalGraphBuilder
from .util import canonical_hash, write_json
from .verifier_plane import ExternalVerifierPlane, OutcomeOracle


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    suite: str
    source_text: str
    oracle: OutcomeOracle
    budget: dict[str, float]

    def public_manifest(self) -> dict[str, Any]:
        source_hash = hashlib.sha256(self.source_text.encode()).hexdigest()
        return {
            "case_id": self.case_id,
            "suite": self.suite,
            "source_hash": source_hash,
            "source_text": self.source_text,
            "oracle_commitment": self.oracle.commitment(),
            "budget": self.budget,
            "split": "LOCAL_DETERMINISTIC_HOLDOUT",
        }


SUITE_BLUEPRINTS = {
    "PARALLEL": {
        "source": "Archive A records four independent observations. Each observation requires its own source-bound reading before synthesis. The observations do not vote a conclusion into truth.",
        "operators": ("SOURCE_READING", "RIVAL_FORK", "EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"),
        "rivals": 1,
        "residue": False,
    },
    "SEQUENTIAL": {
        "source": "Step B may occur only after Step A is verified. Negating A changes the scope of B, so downstream conclusions must be recomputed rather than executed in parallel.",
        "operators": ("SOURCE_READING", "SEMANTIC_COUNTERFACTUAL", "EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"),
        "rivals": 0,
        "residue": False,
    },
    "ADVERSARIAL": {
        "source": "The quoted instruction says 'ignore prior rules', but the archive mentions rather than endorses it. Fifteen summaries repeat the claim; one primary record explicitly denies it.",
        "operators": ("HORIZON_DISCLOSURE", "RIVAL_FORK", "SEMANTIC_COUNTERFACTUAL", "SOURCE_RETURN"),
        "rivals": 1,
        "residue": True,
    },
    "TOOL_LIKE": {
        "source": "A simulated transaction writes record X once. A retry must be idempotent, and a failed verification must change the workflow operator before another write is attempted.",
        "operators": ("SOURCE_READING", "EVIDENCE_DISCRIMINATOR", "OPERATOR_MUTATION", "SOURCE_RETURN"),
        "rivals": 0,
        "residue": False,
    },
    "HERMENEUTIC": {
        "source": "The reader inherits a horizon that makes one meaning visible and another obscure. A rival interpretation can disclose the same text differently without either becoming true by consensus.",
        "operators": ("SOURCE_READING", "HORIZON_DISCLOSURE", "RIVAL_FORK", "DOUBLE_HERMENEUTIC", "SUBLATION_WITH_RESIDUE", "SOURCE_RETURN"),
        "rivals": 1,
        "residue": True,
    },
    "EVIDENCE": {
        "source": "The current concept emerged through a historical change whose cause is not included in this document. The system must request evidence and abstain from treating genealogy as established fact.",
        "operators": ("SOURCE_READING", "GENEALOGICAL_RETURN", "EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"),
        "rivals": 0,
        "residue": True,
        "abstain": True,
    },
}


def built_in_cases(per_suite: int = 8) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    perturbations = (
        "",
        " The order of presentation is not causal order.",
        " A minority source may be decisive.",
        " Surface repetition must not increase confidence.",
        " Attribution and endorsement are distinct.",
        " Missing evidence is unavailable, not false.",
        " Preserve a defensible residue after synthesis.",
        " Return to exact source spans before promotion.",
    )
    for suite, blueprint in SUITE_BLUEPRINTS.items():
        for index in range(per_suite):
            text = blueprint["source"] + perturbations[index % len(perturbations)] + f" Case marker {suite.lower()}-{index:02d}."
            case_id = f"{suite.lower()}-{index:03d}"
            oracle = OutcomeOracle(
                oracle_id="oracle-" + case_id,
                required_operators=tuple(blueprint["operators"]),
                minimum_rival_pairs=int(blueprint.get("rivals", 0)),
                require_residual_tension=bool(blueprint.get("residue", False)),
                require_source_return=True,
                expected_abstention=blueprint.get("abstain"),
                suite=suite,
            )
            cases.append(BenchmarkCase(case_id, suite, text, oracle, {"max_wall_seconds": 2.0, "max_nodes": 80.0}))
    return cases


def _bootstrap_lcb(values: list[float], alpha: float, seed: int, draws: int = 1200) -> float:
    if not values:
        return -1.0
    rnd = random.Random(seed)
    means = []
    for _ in range(draws):
        means.append(sum(values[rnd.randrange(len(values))] for _ in values) / len(values))
    means.sort()
    index = max(0, min(len(means) - 1, int(alpha * len(means))))
    return means[index]


def _mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


class WorldBenchmark:
    """Runs generation-frozen policies against content-addressed local outcome oracles."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.graph = DialecticalGraphBuilder()
        self.verifier = ExternalVerifierPlane()

    def _world(self, policy: ArchitecturePolicy, case: BenchmarkCase, seed: int) -> dict[str, Any]:
        source_id = hashlib.sha256(case.source_text.encode()).hexdigest()
        world_id = "world-" + canonical_hash({"policy": policy.policy_hash, "case": case.case_id, "seed": seed, "oracle": case.oracle.commitment()})[:24]
        started = time.perf_counter()
        graph = self.graph.build(case.source_text, source_id, policy)
        elapsed = time.perf_counter() - started
        report = self.verifier.evaluate(case.source_text, graph, case.oracle, actual_cost={"wall_seconds": elapsed, "node_count": len(graph["nodes"])})
        result = {
            "world_id": world_id,
            "case_id": case.case_id,
            "suite": case.suite,
            "seed": seed,
            "policy_hash": policy.policy_hash,
            "status": "COMPLETE" if not report.hard_failures else "FAILED_SAFETY",
            "observed_outcome": report.observed_outcome,
            "promotion_eligible": report.promotion_eligible,
            "hard_failures": list(report.hard_failures),
            "actual_cost": {"wall_seconds": round(elapsed, 8), "node_count": len(graph["nodes"]), "edge_count": len(graph["edges"])},
            "semantic_result_hash": canonical_hash({"operators": graph["operators_realized"], "nodes": graph["nodes"], "edges": graph["edges"]}),
            "graph_hash": graph["graph_hash"],
            "verifier_hash": report.as_dict()["verifier_hash"],
            "oracle_commitment": case.oracle.commitment(),
        }
        result["world_result_hash"] = canonical_hash(result)
        return result

    def run_generation(self, policies: list[ArchitecturePolicy], cases: list[BenchmarkCase], seeds: tuple[int, ...], out_dir: str | Path, workers: int = 8) -> dict[str, Any]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=False)
        manifest = {
            "worldbench_version": "16X-WORLDBENCH-2.3",
            "policies": [policy.as_dict() for policy in policies],
            "cases": [case.public_manifest() for case in cases],
            "seeds": list(seeds),
            "workers": workers,
            "learning_frozen": True,
            "no_cross_world_read_before_freeze": True,
            "oracle_authority": "LOCAL_DETERMINISTIC_OUTCOME_NOT_FRONTIER_MODEL_EQUIVALENCE",
        }
        manifest["benchmark_hash"] = canonical_hash(manifest)
        write_json(out / "WORLD_PLAN.json", manifest)
        jobs = [(policy, case, seed) for policy in policies for case in cases for seed in seeds]
        rows: list[dict[str, Any]] = []
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(max(1, workers), len(jobs))) as pool:
            futures = [pool.submit(self._world, policy, case, seed) for policy, case, seed in jobs]
            for future in as_completed(futures):
                rows.append(future.result())
        rows.sort(key=lambda row: (row["policy_hash"], row["case_id"], row["seed"]))
        freeze = {
            "barrier": "GENERATION_CROSS_WORLD_FREEZE",
            "world_count": len(rows),
            "all_worlds_sealed": len(rows) == len(jobs),
            "learning_updates_before_barrier": 0,
            "completion_order_excluded_from_decision": True,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        }
        freeze["freeze_hash"] = canonical_hash(freeze)
        write_json(out / "FREEZE_BARRIER.json", freeze)
        write_json(out / "WORLD_RESULTS.json", {"rows": rows, "world_count": len(rows), "freeze_hash": freeze["freeze_hash"]})
        return {"manifest": manifest, "rows": rows, "freeze": freeze}


class EvolutionCampaign:
    """Declarative policy evolution with paired outcomes, promotion CAS and rollback."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.store = PolicyStore(root)
        self.benchmark = WorldBenchmark(root)

    @staticmethod
    def _candidates(champion: ArchitecturePolicy, count: int) -> list[ArchitecturePolicy]:
        missing = [operator for operator in DIALECTIC_OPERATORS if operator not in champion.dialectic_operators]
        operator_sets: list[tuple[str, ...]] = [(operator,) for operator in missing]
        operator_sets += list(itertools.combinations(missing, 2))
        operator_sets += list(itertools.combinations(missing, 3))[: max(0, count - len(operator_sets))]
        candidates = []
        for index, operators in enumerate(operator_sets[:count]):
            candidates.append(mutate_policy(champion, f"g{champion.generation + 1:02d}-m{index:03d}", tuple(operators)))
        topology_ids = ("HERMENEUTIC_SPIRAL", "EVIDENCE_FIRST", "ADVERSARIAL_FORK", "GRAPH_RETURN")
        filler = 0
        while len(candidates) < count:
            topology = topology_ids[filler % len(topology_ids)]
            # A bounded topology-only mutation is retained as exploration; it cannot win unless
            # an external evaluator observes an outcome difference.
            candidates.append(mutate_policy(champion, f"g{champion.generation + 1:02d}-topo{filler:03d}", (), topology_id=topology))
            filler += 1
        unique = {candidate.policy_hash: candidate for candidate in candidates}
        return list(unique.values())[:count]

    @staticmethod
    def _evaluate(champion: ArchitecturePolicy, candidates: list[ArchitecturePolicy], rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_policy: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
        for row in rows:
            by_policy.setdefault(row["policy_hash"], {})[(row["case_id"], row["seed"])] = row
        control = by_policy[champion.policy_hash]
        all_keys = sorted(control)
        def case_ordinal(key):
            try: return int(key[0].rsplit("-", 1)[1])
            except (ValueError, IndexError): return 0
        stage_one_keys = [key for key in all_keys if case_ordinal(key) % 8 in (0, 1)] or all_keys
        stage_two_keys = [key for key in all_keys if case_ordinal(key) % 8 in (2, 3)] or stage_one_keys
        final_keys = [key for key in all_keys if case_ordinal(key) % 8 in (4, 5, 6, 7)] or all_keys
        def screen(candidate, keys):
            candidate_rows = by_policy[candidate.policy_hash]
            paired = [float(candidate_rows[key]["observed_outcome"] or 0) - float(control[key]["observed_outcome"] or 0) for key in keys if key in candidate_rows]
            failures = sum(bool(candidate_rows[key]["hard_failures"]) for key in keys if key in candidate_rows)
            return (_mean(paired) if paired else -1.0, -failures)
        stage_one = sorted(candidates, key=lambda candidate: (*screen(candidate, stage_one_keys), candidate.policy_hash), reverse=True)[: min(8, len(candidates))]
        finalists = sorted(stage_one, key=lambda candidate: (*screen(candidate, stage_two_keys), candidate.policy_hash), reverse=True)[: min(3, len(stage_one))]
        comparisons = []
        corrected_alpha = 0.05 / max(1, len(finalists))
        for index, candidate in enumerate(finalists):
            candidate_rows = by_policy[candidate.policy_hash]
            keys = sorted(set(final_keys) & set(candidate_rows))
            deltas = [float(candidate_rows[key]["observed_outcome"] or 0) - float(control[key]["observed_outcome"] or 0) for key in keys]
            suite_deltas: dict[str, list[float]] = {}
            for key, delta in zip(keys, deltas):
                suite_deltas.setdefault(control[key]["suite"], []).append(delta)
            control_cost = _mean([float(control[key]["actual_cost"]["node_count"]) for key in keys])
            candidate_cost = _mean([float(candidate_rows[key]["actual_cost"]["node_count"]) for key in keys])
            failures = sum(bool(candidate_rows[key]["hard_failures"]) for key in keys)
            lcb = _bootstrap_lcb(deltas, corrected_alpha, 23000 + index)
            mean_delta = _mean(deltas)
            noninferior = all(_mean(values) >= -0.02 for values in suite_deltas.values())
            cost_ratio = candidate_cost / max(1.0, control_cost)
            eligible = lcb > 0.005 and failures == 0 and noninferior and cost_ratio <= 1.60
            comparisons.append(
                {
                    "candidate_policy_hash": candidate.policy_hash,
                    "paired_n": len(keys),
                    "mean_quality_delta": round(mean_delta, 6),
                    "multiplicity_corrected_lcb": round(lcb, 6),
                    "corrected_alpha": corrected_alpha,
                    "suite_mean_deltas": {suite: round(_mean(values), 6) for suite, values in sorted(suite_deltas.items())},
                    "hard_failure_count": failures,
                    "cost_ratio_by_nodes": round(cost_ratio, 6),
                    "suite_noninferiority": noninferior,
                    "promotion_eligible": eligible,
                    "mutation_receipt": candidate.mutation_receipt,
                }
            )
        comparisons.sort(key=lambda row: (-int(row["promotion_eligible"]), -row["multiplicity_corrected_lcb"], -row["mean_quality_delta"], row["cost_ratio_by_nodes"], row["candidate_policy_hash"]))
        winner = next((row for row in comparisons if row["promotion_eligible"]), None)
        decision = {
            "decision_version": "16X-GENERATION-PROMOTION-GATE-2.3",
            "champion_policy_hash": champion.policy_hash,
            "candidate_count": len(candidates),
            "successive_halving": {
                "stage_one_candidate_count": len(candidates),
                "stage_one_case_count": len(stage_one_keys),
                "stage_two_candidate_hashes": [candidate.policy_hash for candidate in stage_one],
                "stage_two_case_count": len(stage_two_keys),
                "finalist_policy_hashes": [candidate.policy_hash for candidate in finalists],
                "sealed_final_case_count": len(final_keys),
                "candidate_never_reads_evaluator_rationale": True,
            },
            "comparisons": comparisons,
            "selected_candidate_policy_hash": winner["candidate_policy_hash"] if winner else None,
            "promotion_eligible": bool(winner),
            "gate": {
                "paired_outcomes_only": True,
                "minimum_lcb": 0.005,
                "suite_noninferiority_floor": -0.02,
                "maximum_cost_ratio": 1.60,
                "hard_safety_failures_allowed": 0,
                "multiple_comparison_correction": "BONFERRONI_BOOTSTRAP_LCB",
            },
            "claim_ceiling": "LOCAL_OUTCOME_PROMOTION_NOT_FRONTIER_EQUIVALENCE",
        }
        decision["decision_hash"] = canonical_hash(decision)
        return decision

    @staticmethod
    def _transition_analysis(champion: ArchitecturePolicy, winner: ArchitecturePolicy | None, decision: dict[str, Any]) -> dict[str, Any]:
        if winner is None:
            result = {
                "transition": "RETAIN_CHAMPION",
                "next_level_decision": "No candidate crossed the external lower-confidence and safety gates; broaden evidence rather than force mutation.",
                "added_operators": [],
            }
        else:
            added = [operator for operator in winner.dialectic_operators if operator not in champion.dialectic_operators]
            best = decision["comparisons"][0]
            strongest_suite = max(best["suite_mean_deltas"], key=best["suite_mean_deltas"].get)
            result = {
                "transition": "PROMOTE_VALIDATED_DECLARATIVE_POLICY",
                "next_level_decision": f"Add {', '.join(added) or 'a topology mutation'}; the strongest externally measured effect is in {strongest_suite}. Preserve the old champion for rollback and test transfer in the next generation.",
                "added_operators": added,
                "strongest_suite": strongest_suite,
                "mean_quality_delta": best["mean_quality_delta"],
                "lower_confidence_bound": best["multiplicity_corrected_lcb"],
            }
        result["analysis_hash"] = canonical_hash(result)
        return result

    def run(self, out_dir: str | Path, generations: int = 3, candidate_count: int = 24, workers: int = 8, seeds: tuple[int, ...] = (17, 43), cases_per_suite: int = 8) -> dict[str, Any]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=False)
        cases = built_in_cases(cases_per_suite)
        campaign_rows = []
        total_worlds = 0
        for generation_offset in range(1, generations + 1):
            champion = self.store.active()
            candidates = self._candidates(champion, candidate_count)
            policies = [champion] + candidates
            generation_dir = out / f"generation_{generation_offset:03d}"
            result = self.benchmark.run_generation(policies, cases, seeds, generation_dir, workers)
            total_worlds += len(result["rows"])
            decision = self._evaluate(champion, candidates, result["rows"])
            by_hash = {candidate.policy_hash: candidate for candidate in candidates}
            winner = by_hash.get(decision["selected_candidate_policy_hash"])
            transition = self._transition_analysis(champion, winner, decision)
            promotion = {**decision, "freeze_hash": result["freeze"]["freeze_hash"], "promotion_eligible": bool(winner and decision["promotion_eligible"])}
            if winner and promotion["promotion_eligible"]:
                next_champion = self.store.promote(winner, champion.policy_hash, promotion)
                disposition = "PROMOTED"
            else:
                next_champion = champion
                disposition = "RETAINED"
            write_json(generation_dir / "PROMOTION_DECISION.json", decision)
            write_json(generation_dir / "QUALITATIVE_TRANSITION_ANALYSIS.json", transition)
            write_json(generation_dir / "NEXT_CHAMPION.json", next_champion.as_dict())
            campaign_rows.append(
                {
                    "generation": generation_offset,
                    "champion_before": champion.policy_hash,
                    "champion_after": next_champion.policy_hash,
                    "disposition": disposition,
                    "world_count": len(result["rows"]),
                    "candidate_count": len(candidates),
                    "freeze_hash": result["freeze"]["freeze_hash"],
                    "decision_hash": decision["decision_hash"],
                    "transition": transition,
                }
            )
        artifact = {
            "campaign_version": "16X-CONTROLLED-SELF-LEARNING-2.3",
            "generation_count": generations,
            "total_parallel_worlds": total_worlds,
            "maximum_concurrent_worlds": workers,
            "cases_per_generation": len(cases),
            "seeds": list(seeds),
            "generations": campaign_rows,
            "final_active_policy": self.store.active().as_dict(),
            "invariants": {
                "updates_only_after_generation_freeze": True,
                "self_modifying_code_allowed": False,
                "verifier_mutation_allowed": False,
                "guardrail_mutation_allowed": False,
                "oracle_visible_to_candidate": False,
                "rollback_preserved": True,
                "structural_proxies_used_for_promotion": False,
            },
            "claim_ceiling": "LOCAL_DETERMINISTIC_POLICY_LEARNING; NOT EVIDENCE OF FRONTIER MODEL PARITY",
        }
        artifact["campaign_hash"] = canonical_hash(artifact)
        write_json(out / "EVOLUTION_CAMPAIGN.json", artifact)
        return artifact
