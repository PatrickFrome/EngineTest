#!/usr/bin/env python3
"""Generate deterministic release-evidence smoke fixtures for portable tests.

The test_schemas.py tests validate that smoke artifacts conform to their JSON
schemas. The original release-evidence/ directory was non-portable (listed in
KNOWN_LOSSES as intentional non-portable state). This script generates minimal
deterministic fixtures that satisfy the schemas, making the test suite portable.

These are NOT real campaign outputs — they are deterministic fixtures that
exercise the schema validation. Each fixture is clearly labelled as a fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "release-evidence"


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# 2.0 smoke: META_RUN.json
# ---------------------------------------------------------------------------

def gen_2_0_smoke():
    meta_run = {
        "meta_run_id": "fixture-meta-run-2.0",
        "engine_version": "2.0.0-alpha.1",
        "input_hash": "fixture-input-hash-0000000000000000000000000000000000000000000000000000000000",
        "status": "COMPLETE",
        "barrier": "PRIMARY_INTERWEAVE",
        "engine_states": {"engine_01": {"status": "COMPLETE", "role": "PRIMARY"}},
        "fusion": {"fusion_version": "16X-FUSION-1"},
        "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES",
        "routing_plan_hash": "fixture-routing-hash-000000000000000000000000000000000000000000000000000000000",
        "coordination": {"barrier": "PRIMARY_INTERWEAVE"},
        "fixture_note": "DETERMINISTIC_FIXTURE_NOT_REAL_CAMPAIGN_OUTPUT",
    }
    _write(EVIDENCE / "2.0" / "smoke" / "META_RUN.json", meta_run)


# ---------------------------------------------------------------------------
# 2.1 smoke: META_RUN, ROUTING_PLAN, SELF_ORGANIZING_ECOLOGY, TRANSFORMATION_GRAPH,
#            SELF_ORGANIZING_METRICS, EPISTEMIC_SAFETY_2.0
# ---------------------------------------------------------------------------

def gen_2_1_smoke():
    smoke = EVIDENCE / "2.1" / "smoke"
    _write(smoke / "META_RUN.json", {
        "meta_run_id": "fixture-meta-run-2.1",
        "engine_version": "2.1.0-alpha.1",
        "input_hash": "fixture-input-hash-0000000000000000000000000000000000000000000000000000000000",
        "status": "COMPLETE",
        "barrier": "SELF_ORGANIZING_SPARSE_DEEP_EXECUTION",
        "engine_states": {"engine_01": {"status": "COMPLETE", "role": "PRIMARY"}},
        "fusion": {"fusion_version": "16X-FUSION-2.1"},
        "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES",
        "routing_plan_hash": "fixture-routing-hash-000000000000000000000000000000000000000000000000000000000",
        "coordination": {"barrier": "SELF_ORGANIZING_SPARSE_DEEP_EXECUTION"},
        "fixture_note": "DETERMINISTIC_FIXTURE_NOT_REAL_CAMPAIGN_OUTPUT",
    })
    _write(smoke / "ROUTING_PLAN.json", {
        "routing_version": "16X-ROUTING-2.1",
        "mode": "SPARSE_DEEP",
        "all_16_scheduled": True,
        "task_fingerprint": "fixture-fingerprint-000000000000000000000000000000000000000000000000000000",
        "assignments": [{"engine_id": "engine_01", "scheduled": True, "role": "PRIMARY", "expected_gain": 0.5}],
        "role_counts": {"PRIMARY": 16},
        "plan_hash": "fixture-plan-hash-0000000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "SELF_ORGANIZING_ECOLOGY.json", {
        "ecology_version": "16X-ECOLOGY-2.1",
        "scheduler_rounds": 4,
        "architecture_history": ["HERMENEUTIC_SPIRAL"],
        "selected_topology_id": "HERMENEUTIC_SPIRAL",
        "coalitions": [],
        "stop_reason": "MARGINAL_GAIN_EXHAUSTED",
        "depth_budget": {"max_deep_engines": 8, "max_rounds": 4},
        "cache": {"hit_rate": 0.0},
        "disagreement_reorganizations": 0,
        "architecture_mutations": 0,
        "truth_promotion_allowed_from_ecology": False,
        "claim_ceiling": "ECOLOGY_ORGANIZES_COMPUTATION_NOT_TRUTH",
        "ecology_hash": "fixture-ecology-hash-0000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "TRANSFORMATION_GRAPH.json", {
        "graph_version": "16X-TRANSFORMATION-GRAPH-2.0",
        "nodes": [{"node_id": "fixture-node-1", "node_type": "PRIMARY", "label": "fixture"}],
        "edges": [],
        "metrics": {"node_count": 1, "edge_count": 0, "transformation_types": [], "type_diversity": 0.0, "causal_depth": 0, "source_reground_count": 0, "peer_pairs": [], "unresolved_tensions": 0, "cycle_pressure": 0, "topology_mutation_edges": 0},
        "claim_ceiling": "TRANSFORMATION_GRAPH_IS_DIAGNOSTIC_NOT_TRUTH",
        "graph_hash": "fixture-graph-hash-0000000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "SELF_ORGANIZING_METRICS.json", {
        "evaluation_version": "16X-SELF-ORGANIZING-METRICS-2.0",
        "hermeneutic_nonlinearity_proxy": 0.5,
        "epistemic_nonlinearity_proxy": 0.5,
        "depth_proxy": 0.5,
        "performance": {"wall_seconds": 1.0},
        "safety": {"derived_truth_promotion_violations": 0},
        "claim_ceiling": "METRICS_ARE_DIAGNOSTIC_NOT_TRUTH",
        "evaluation_hash": "fixture-metrics-hash-0000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "EPISTEMIC_SAFETY_2.0.json", {
        "claim_node_delta_vs_primary": 0.0,
        "native_position_delta_vs_primary": 0.0,
        "derived_truth_promotion_violations": 0,
        "majority_vote_used": False,
        "all_16_primary_scheduled": True,
        "deep_execution_is_sparse": True,
    })


def gen_2_1_parallel():
    e = EVIDENCE / "2.1"
    _write(e / "PARALLEL_SMOKE_EXPERIMENT_PLAN.json", {
        "fabric_version": "16X-PARALLEL-EXPERIMENTAL-ECOLOGY-2.1",
        "case_count": 1,
        "world_workers": 1,
        "inner_workers": 1,
        "cases": [{"case_id": "fixture-case-1", "source_text": "fixture"}],
        "biography_policy": "FROZEN_BASELINE",
        "default_cache_policy": "NO_CACHE",
        "compile_hash": "fixture-compile-hash-000000000000000000000000000000000000000000000000000000",
    })
    _write(e / "PARALLEL_SMOKE_FREEZE_BARRIER.json", {
        "barrier": "CROSS_WORLD_FREEZE_BARRIER",
        "all_worlds_completed": True,
        "completed": 1,
        "failed": 0,
        "elapsed_s": 1.0,
        "no_cross_world_read_before_freeze": True,
        "freeze_hash": "fixture-freeze-hash-0000000000000000000000000000000000000000000000000000000",
    })


# ---------------------------------------------------------------------------
# 2.2 smoke: META_RUN, SELF_ORGANIZING_ECOLOGY, FRONTIER_CONTROL_PLANE
# ---------------------------------------------------------------------------

def gen_2_2_smoke():
    smoke = EVIDENCE / "2.2" / "smoke"
    _write(smoke / "META_RUN.json", {
        "meta_run_id": "fixture-meta-run-2.2",
        "engine_version": "2.2.0-alpha.1",
        "input_hash": "fixture-input-hash-0000000000000000000000000000000000000000000000000000000000",
        "status": "COMPLETE",
        "barrier": "FRONTIER_TASK_LEDGER",
        "engine_states": {"engine_01": {"status": "COMPLETE", "role": "PRIMARY"}},
        "fusion": {"fusion_version": "16X-FUSION-2.2"},
        "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES",
        "routing_plan_hash": "fixture-routing-hash-000000000000000000000000000000000000000000000000000000000",
        "coordination": {"barrier": "FRONTIER_TASK_LEDGER"},
        "fixture_note": "DETERMINISTIC_FIXTURE_NOT_REAL_CAMPAIGN_OUTPUT",
    })
    _write(smoke / "SELF_ORGANIZING_ECOLOGY.json", {
        "ecology_version": "16X-ECOLOGY-2.2",
        "scheduler_rounds": 4, "architecture_history": ["HERMENEUTIC_SPIRAL"], "selected_topology_id": "HERMENEUTIC_SPIRAL",
        "coalitions": [], "stop_reason": "MARGINAL_GAIN_EXHAUSTED", "depth_budget": {"max_deep_engines": 8, "max_rounds": 4},
        "cache": {"hit_rate": 0.0}, "disagreement_reorganizations": 0, "architecture_mutations": 0,
        "truth_promotion_allowed_from_ecology": False, "claim_ceiling": "ECOLOGY_ORGANIZES_COMPUTATION_NOT_TRUTH",
        "ecology_hash": "fixture-ecology-hash-0000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "FRONTIER_CONTROL_PLANE.json", {
        "control_plane_version": "16X-FRONTIER-EVIDENCE-CONTROL-2.2",
        "pattern_sources": [], "task_ledger": {"tasks": []}, "rounds": [],
        "candidate_archive": [], "policy_candidates": [],
        "invariants": {"derived_candidates_cannot_promote_truth": True},
        "claim_ceiling": "FRONTIER_CANDIDATES_ARE_SHADOW_ONLY",
        "control_plane_hash": "fixture-fcp-hash-0000000000000000000000000000000000000000000000000000000000",
    })


# ---------------------------------------------------------------------------
# 2.3 smoke + final_smoke + campaign
# ---------------------------------------------------------------------------

def _active_policy():
    return {
        "policy_version": "16X-DECLARATIVE-ARCHITECTURE-POLICY-2.3",
        "generation": 2,
        "parent_policy_hash": "5f2b57eda164a8f8a27baaed17a8b712985a05d34d2b643586663056e129e27c",
        "topology_id": "HERMENEUTIC_SPIRAL",
        "waves": [["engine_01","engine_03","engine_04","engine_07"],["engine_02","engine_06","engine_14","engine_15"],["engine_05","engine_08","engine_09","engine_10"],["engine_11","engine_12","engine_13","engine_16"]],
        "dialectic_operators": ["SOURCE_READING","RIVAL_FORK","EVIDENCE_DISCRIMINATOR","SOURCE_RETURN","HORIZON_DISCLOSURE","SEMANTIC_COUNTERFACTUAL","GENEALOGICAL_RETURN","DOUBLE_HERMENEUTIC","SUBLATION_WITH_RESIDUE","OPERATOR_MUTATION"],
        "engine_architecture_mix": {f"engine_{i:02d}": ["SOURCE_READING"] for i in range(1,17)},
        "max_rounds": 4, "max_deep_engines": 8, "exploration_rate": 0.15,
        "guardrail_hash": "7ca26b082e1c4dc1de5f3d098f957d0330a5b9f2cf70da12160a672c01a2eb38",
        "verifier_hash": "EXTERNAL_VERIFIER_PINNED_BY_CAMPAIGN",
        "benchmark_hash": "SEALED_BY_CAMPAIGN",
        "status": "ACTIVE",
        "mutation_receipt": {"mutation_id": "fixture"},
        "self_modifying_code_allowed": False,
        "truth_effect": "NONE",
        "policy_hash": "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
    }


def _dialectical_graph():
    return {
        "graph_version": "16X-TYPED-DIALECTICAL-GRAPH-2.3",
        "source_id": "fixture-source",
        "policy_hash": "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        "nodes": [{"operator": "SOURCE_READING", "proposition": "fixture", "source_spans": []}],
        "edges": [],
        "metrics": {"node_count": 1, "edge_count": 0},
        "graph_hash": "fixture-dg-hash-00000000000000000000000000000000000000000000000000000000000",
    }


def gen_2_3_smoke():
    smoke = EVIDENCE / "2.3" / "smoke"
    _write(smoke / "ACTIVE_ARCHITECTURE_POLICY.json", _active_policy())
    _write(smoke / "DIALECTICAL_GRAPH.json", _dialectical_graph())
    _write(smoke / "DIALECTICAL_GRAPH_VERIFICATION.json", {
        "verifier_version": "16X-EXTERNAL-OUTCOME-VERIFIER-2.3",
        "verification_status": "INSUFFICIENT_EXTERNAL_EVIDENCE",
        "metrics": {},
        "hard_failures": [],
        "observed_outcome": None,
        "promotion_eligible": False,
        "candidate_hash": "fixture-candidate-hash-0000000000000000000000000000000000000000000000000000",
        "verifier_hash": "fixture-verifier-hash-0000000000000000000000000000000000000000000000000000000",
    })
    _write(smoke / "TELEMETRY.json", {
        "telemetry_version": "16X-RUN-TELEMETRY-2.3",
        "run_id": "fixture-run-2.3",
        "wall_seconds": 1.0,
        "events": [],
        "telemetry_hash": "fixture-telemetry-hash-0000000000000000000000000000000000000000000000000000",
    })


def gen_2_3_final_smoke():
    final = EVIDENCE / "2.3" / "final_smoke"
    _write(final / "ACTIVE_ARCHITECTURE_POLICY.json", _active_policy())
    _write(final / "DIALECTICAL_GRAPH.json", _dialectical_graph())
    # For replicate_run test: needs a minimal run structure
    _write(final / "META_RUN.json", {
        "meta_run_id": "fixture-final-smoke-2.3",
        "engine_version": "2.3.0-alpha.1",
        "input_hash": "fixture-input-hash-0000000000000000000000000000000000000000000000000000000000",
        "status": "COMPLETE",
        "barrier": "PERSIST_AND_CHECKPOINT",
        "engine_states": {},
        "fusion": {},
        "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES",
        "routing_plan_hash": "fixture-routing-hash-000000000000000000000000000000000000000000000000000000000",
        "coordination": {},
        "fixture_note": "DETERMINISTIC_FIXTURE_FOR_REPLICATE_RUN_TEST",
    })


def gen_2_3_campaign():
    campaign = EVIDENCE / "2.3" / "outcome_gated_evolution_campaign"
    _write(campaign / "EVOLUTION_CAMPAIGN.json", {
        "campaign_version": "16X-CONTROLLED-SELF-LEARNING-2.3",
        "generation_count": 1,
        "total_parallel_worlds": 1,
        "maximum_concurrent_worlds": 1,
        "generations": [{"generation_index": 1, "world_count": 1, "learning_updates_before_barrier": 0}],
        "final_active_policy": _active_policy(),
        "invariants": {"structural_proxies_used_for_promotion": False},
        "campaign_hash": "fixture-campaign-hash-0000000000000000000000000000000000000000000000000000",
    })


def main():
    gen_2_0_smoke()
    gen_2_1_smoke()
    gen_2_1_parallel()
    gen_2_2_smoke()
    gen_2_3_smoke()
    gen_2_3_final_smoke()
    gen_2_3_campaign()
    print("FIXTURES_GENERATED")
    # Count
    files = list(EVIDENCE.rglob("*.json"))
    print(f"files: {len(files)}")
    for f in sorted(files):
        print(f"  {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
