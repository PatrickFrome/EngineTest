"""METAENGINE Phase 4 — Organization Tournament tests."""

from __future__ import annotations

import pytest

from metaengine.organization_tournament import (
    PolicyResult,
    PairwiseResult,
    ParetoEntry,
    TournamentResult,
    TournamentDimension,
    run_tournament,
    TOURNAMENT_VERSION,
)


def _result(pid, tid, q, c, l):
    return PolicyResult(policy_id=pid, task_id=tid, quality=q, cost=c, latency=l, reproducibility=1.0, resource_efficiency=0.5)


# ---------------------------------------------------------------------------
# Basic tournament
# ---------------------------------------------------------------------------


def test_tournament_two_policies_one_task():
    results = [
        _result("P0", "T0", 0.8, 1.0, 0.5),
        _result("P1", "T0", 0.9, 1.0, 0.5),
    ]
    t = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
    assert len(t.pairwise) == 1
    assert t.pairwise[0].winner == "P1"  # higher quality, same cost/latency


def test_tournament_tie():
    results = [
        _result("P0", "T0", 0.8, 1.0, 0.5),
        _result("P1", "T0", 0.8, 1.0, 0.5),
    ]
    t = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
    assert t.pairwise[0].winner == "TIE"


def test_pareto_frontier():
    results = [
        _result("P0", "T0", 0.8, 1.0, 0.5),  # good quality, high cost
        _result("P1", "T0", 0.7, 0.5, 0.3),  # lower quality, lower cost
        _result("P2", "T0", 0.6, 1.2, 0.6),  # dominated by both
    ]
    t = run_tournament(results, policy_ids=["P0", "P1", "P2"], task_ids=["T0"])
    frontier = [e for e in t.pareto_frontier if not e.dominated]
    frontier_ids = {e.policy_id for e in frontier}
    assert "P0" in frontier_ids
    assert "P1" in frontier_ids
    assert "P2" not in frontier_ids  # dominated


def test_dominance_map():
    results = [
        _result("P0", "T0", 0.9, 0.5, 0.3),
        _result("P1", "T0", 0.7, 1.0, 0.5),
    ]
    t = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
    assert "P1" in t.dominance.get("P0", [])


# ---------------------------------------------------------------------------
# Hash + tamper detection
# ---------------------------------------------------------------------------


def test_tournament_hash_deterministic():
    results = [_result("P0", "T0", 0.8, 1.0, 0.5), _result("P1", "T0", 0.9, 1.0, 0.5)]
    t1 = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
    t2 = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0"])
    assert t1.tournament_hash == t2.tournament_hash


def test_tournament_truth_effect_none():
    results = [_result("P0", "T0", 0.8, 1.0, 0.5)]
    t = run_tournament(results, policy_ids=["P0"], task_ids=["T0"])
    assert t.payload()["truth_effect"] == "NONE"
    assert t.payload()["claim_ceiling"] == "TOURNAMENT_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"


# ---------------------------------------------------------------------------
# Multi-task
# ---------------------------------------------------------------------------


def test_multi_task_tournament():
    results = [
        _result("P0", "T0", 0.9, 0.5, 0.3),
        _result("P0", "T1", 0.6, 0.8, 0.4),
        _result("P1", "T0", 0.7, 1.0, 0.5),
        _result("P1", "T1", 0.8, 0.3, 0.2),
    ]
    t = run_tournament(results, policy_ids=["P0", "P1"], task_ids=["T0", "T1"])
    assert len(t.pairwise) == 2  # one per task
    assert len(t.mean_metrics) == 2
    # P0 wins T0, P1 wins T1 → both on Pareto
    frontier = [e for e in t.pareto_frontier if not e.dominated]
    assert len(frontier) == 2
