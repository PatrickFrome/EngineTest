"""METAENGINE Phase 4 — Organization Tournament v1.

Runs pairwise comparison of organization policies on a task suite with
Pareto frontier analysis and ablation support. This is the first step
toward falsification-first architecture evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


TOURNAMENT_VERSION = "METAENGINE-ORGANIZATION-TOURNAMENT-1"


class TournamentDimension(str, Enum):
    QUALITY = "quality"
    COST = "cost"
    LATENCY = "latency"
    REPRODUCIBILITY = "reproducibility"
    RESOURCE_EFFICIENCY = "resource_efficiency"


@dataclass(frozen=True)
class PolicyResult:
    """Result of running one policy on one task."""
    policy_id: str
    task_id: str
    quality: float
    cost: float
    latency: float
    reproducibility: float
    resource_efficiency: float

    def payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "task_id": self.task_id,
            "quality": round(self.quality, 6),
            "cost": round(self.cost, 6),
            "latency": round(self.latency, 6),
            "reproducibility": round(self.reproducibility, 6),
            "resource_efficiency": round(self.resource_efficiency, 6),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyResult":
        return cls(
            policy_id=str(value["policy_id"]),
            task_id=str(value["task_id"]),
            quality=float(value["quality"]),
            cost=float(value["cost"]),
            latency=float(value["latency"]),
            reproducibility=float(value["reproducibility"]),
            resource_efficiency=float(value["resource_efficiency"]),
        )


@dataclass(frozen=True)
class PairwiseResult:
    """Result of comparing two policies on one task."""
    task_id: str
    policy_a: str
    policy_b: str
    winner: str  # policy_id or "TIE"
    quality_delta: float
    cost_delta: float
    latency_delta: float

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "policy_a": self.policy_a,
            "policy_b": self.policy_b,
            "winner": self.winner,
            "quality_delta": round(self.quality_delta, 6),
            "cost_delta": round(self.cost_delta, 6),
            "latency_delta": round(self.latency_delta, 6),
        }


@dataclass(frozen=True)
class ParetoEntry:
    """A policy on the Pareto frontier."""
    policy_id: str
    dominated: bool
    metrics: dict[str, float]

    def payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "dominated": self.dominated,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class TournamentResult:
    """Result of a full organization tournament."""
    tournament_version: str
    policy_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    results: tuple[PolicyResult, ...]
    pairwise: tuple[PairwiseResult, ...]
    pareto_frontier: tuple[ParetoEntry, ...]
    dominance: dict[str, list[str]]
    mean_metrics: dict[str, dict[str, float]]
    tournament_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "tournament_version": self.tournament_version,
            "policy_ids": list(self.policy_ids),
            "task_ids": list(self.task_ids),
            "results": [r.payload() for r in self.results],
            "pairwise": [p.payload() for p in self.pairwise],
            "pareto_frontier": [e.payload() for e in self.pareto_frontier],
            "dominance": {k: list(v) for k, v in self.dominance.items()},
            "mean_metrics": self.mean_metrics,
            "truth_effect": "NONE",
            "claim_ceiling": "TOURNAMENT_RESULTS_ARE_EVALUATIVE_NOT_TRUTH",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "tournament_hash": self.tournament_hash}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _dominates(a: PolicyResult, b: PolicyResult) -> bool:
    """Does policy_a dominate policy_b on this task? Higher quality, lower cost/latency."""
    return (a.quality >= b.quality and a.cost <= b.cost and
            a.latency <= b.latency and
            (a.quality > b.quality or a.cost < b.cost or a.latency < b.latency))


def run_tournament(
    results: Iterable[PolicyResult],
    *,
    policy_ids: Iterable[str],
    task_ids: Iterable[str],
) -> TournamentResult:
    """Run a pairwise tournament over policy results.

    For each pair of policies and each task, determines the winner.
    Computes Pareto frontier over mean metrics.
    """
    results_list = tuple(sorted(results, key=lambda r: (r.policy_id, r.task_id)))
    pol_ids = tuple(sorted(set(policy_ids)))
    t_ids = tuple(sorted(set(task_ids)))

    # Pairwise comparison
    pairwise: list[PairwiseResult] = []
    for i, pa in enumerate(pol_ids):
        for pb in pol_ids[i + 1:]:
            for tid in t_ids:
                ra = next((r for r in results_list if r.policy_id == pa and r.task_id == tid), None)
                rb = next((r for r in results_list if r.policy_id == pb and r.task_id == tid), None)
                if ra is None or rb is None:
                    continue
                if _dominates(ra, rb):
                    winner = pa
                elif _dominates(rb, ra):
                    winner = pb
                else:
                    winner = "TIE"
                pairwise.append(PairwiseResult(
                    task_id=tid, policy_a=pa, policy_b=pb, winner=winner,
                    quality_delta=ra.quality - rb.quality,
                    cost_delta=ra.cost - rb.cost,
                    latency_delta=ra.latency - rb.latency,
                ))

    # Mean metrics per policy
    mean_metrics: dict[str, dict[str, float]] = {}
    for pid in pol_ids:
        pr = [r for r in results_list if r.policy_id == pid]
        mean_metrics[pid] = {
            "quality": round(_mean([r.quality for r in pr]), 6),
            "cost": round(_mean([r.cost for r in pr]), 6),
            "latency": round(_mean([r.latency for r in pr]), 6),
            "reproducibility": round(_mean([r.reproducibility for r in pr]), 6),
            "resource_efficiency": round(_mean([r.resource_efficiency for r in pr]), 6),
        }

    # Pareto frontier over mean metrics
    pareto: list[ParetoEntry] = []
    for pid_a in pol_ids:
        ma = mean_metrics[pid_a]
        dominated = False
        for pid_b in pol_ids:
            if pid_a == pid_b:
                continue
            mb = mean_metrics[pid_b]
            if (mb["quality"] >= ma["quality"] and mb["cost"] <= ma["cost"] and
                mb["latency"] <= ma["latency"] and
                (mb["quality"] > ma["quality"] or mb["cost"] < ma["cost"] or mb["latency"] < ma["latency"])):
                dominated = True
                break
        pareto.append(ParetoEntry(policy_id=pid_a, dominated=dominated, metrics=ma))

    # Dominance map: policy → list of policies it dominates
    dominance: dict[str, list[str]] = {pid: [] for pid in pol_ids}
    for p in pairwise:
        if p.winner != "TIE":
            dominance.setdefault(p.winner, []).append(
                p.policy_b if p.winner == p.policy_a else p.policy_a
            )

    result = TournamentResult(
        tournament_version=TOURNAMENT_VERSION,
        policy_ids=pol_ids,
        task_ids=t_ids,
        results=results_list,
        pairwise=tuple(sorted(pairwise, key=lambda p: (p.task_id, p.policy_a, p.policy_b))),
        pareto_frontier=tuple(sorted(pareto, key=lambda e: e.policy_id)),
        dominance=dominance,
        mean_metrics=mean_metrics,
        tournament_hash="",
    )
    h = canonical_hash(result.payload())
    return TournamentResult(**{**result.__dict__, "tournament_hash": h})
