from pathlib import Path

from metaengine.frontier_control_plane import FrontierControlPlane


ROOT = Path(__file__).resolve().parents[1]


def routing():
    return {
        "task_fingerprint": {
            "active_domains": ["EVIDENCE_RESEARCH", "HYPOTHESIS_EXPERIMENT"],
            "complexity": 0.6,
        }
    }


def disagreement():
    return {
        "conflict_count": 1,
        "conflicts": [{"kind": "SOURCE_CONFLICT", "representative": "A versus B"}],
    }


def mesh():
    return {"research_agenda": [{"seed_kind": "EVIDENCE", "seed_text": "verify A"}]}


def scheduler():
    selection = [
        {"engine_id": "engine_07", "cost_units": 0.85, "expected_gain": 0.7},
        {"engine_id": "engine_15", "cost_units": 0.85, "expected_gain": 0.6},
    ]
    return {
        "selected": [row["engine_id"] for row in selection],
        "selection": selection,
        "plan_hash": "scheduler-hash",
    }


def architecture(topology="EVIDENCE_FIRST"):
    return {
        "selected_topology_id": topology,
        "architecture_hash": f"architecture-{topology}",
    }


def row(engine_id, realized_gain=0.4, transformation_type="EVIDENCE_REQUEST"):
    return {
        "engine_id": engine_id,
        "status": "DEEP_COMPLETE",
        "receipt_hash": f"receipt-{engine_id}",
        "transformations": [
            {
                "type": transformation_type,
                "peer_sources": ["engine_03", "engine_04"],
            }
        ],
        "realized_gain": realized_gain,
        "cost_units": 0.85,
        "source_reground_required": True,
        "truth_promotion_allowed": False,
    }


def test_task_ledger_separates_facts_assumptions_and_unknowns():
    control = FrontierControlPlane(ROOT)
    ledger = control.create_task_ledger(routing(), disagreement(), mesh(), "input-hash")
    assert ledger["facts"] and ledger["assumptions"] and ledger["unknowns"]
    assert ledger["task_ledger_hash"]
    assert all(w["execution_shape"].startswith("BREADTH_FIRST") for w in ledger["workstreams"])


def test_round_plan_emits_typed_guarded_handoffs():
    control = FrontierControlPlane(ROOT)
    control.create_task_ledger(routing(), disagreement(), mesh(), "input-hash")
    plan = control.plan_round(1, scheduler(), architecture(), "input-hash")
    assert len(plan["handoffs"]) == 2
    assert all(h["handoff_hash"] for h in plan["handoffs"])
    assert all("NO_TRUTH_PROMOTION_FROM_RANKING_OR_VOTING" in h["guardrails"] for h in plan["handoffs"])


def test_candidate_ranking_is_non_authoritative_and_pareto_preserving():
    control = FrontierControlPlane(ROOT)
    control.create_task_ledger(routing(), disagreement(), mesh(), "input-hash")
    plan = control.plan_round(1, scheduler(), architecture(), "input-hash")
    result = control.evaluate_round(
        1,
        plan,
        [row("engine_07"), row("engine_15", transformation_type="HYPOTHESIS")],
        {"causal_depth": 3},
        {"stop_decision": "CONTINUE"},
        architecture(),
    )
    assert result["pareto_candidate_ids"]
    assert all(not item["epistemic_authority"] for item in result["tournament"])
    assert all(not item["eligible_for_truth_promotion"] for item in result["candidates"])


def test_stall_creates_shadow_policy_not_self_deployment():
    control = FrontierControlPlane(ROOT)
    control.create_task_ledger(routing(), disagreement(), mesh(), "input-hash")
    first = control.plan_round(1, scheduler(), architecture(), "input-hash")
    control.evaluate_round(
        1,
        first,
        [row("engine_07", 0.08, "EVIDENCE_REQUEST")],
        {"causal_depth": 2},
        {"stop_decision": "STOP_MARGINAL_GAIN"},
        architecture(),
    )
    second = control.plan_round(2, scheduler(), architecture(), "input-hash")
    result = control.evaluate_round(
        2,
        second,
        [row("engine_07", 0.05, "EVIDENCE_REQUEST")],
        {"causal_depth": 2},
        {"stop_decision": "STOP_RECURSIVE_ECHO"},
        architecture(),
    )
    policy = result["policy_candidate"]
    assert policy and policy["deployment_status"] == "SHADOW_ONLY"
    assert not policy["self_deployment_allowed"]
    assert result["progress_ledger"]["replan_required"]


def test_frontier_required_engines_are_domain_diverse():
    control = FrontierControlPlane(ROOT)
    control.create_task_ledger(routing(), disagreement(), mesh(), "input-hash")
    required = control.required_engines(1)
    assert required == ["engine_07", "engine_15"]
