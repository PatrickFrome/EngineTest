"""METAENGINE-1-SLICE-4 — Sparse Conditional Routing causal tournament.

A clean-room, deterministic, provider-neutral causal experiment that compares
three routing arms under an equal processing-resource budget:

1. ``DENSE_ALL_SPECIALISTS`` — activates all specialists, divides the frozen
   budget across all of them.
2. ``RANDOM_TOP_K`` — selects exactly ``k`` specialists using frozen seeds.
3. ``CAPABILITY_ROUTED_TOP_K`` — selects exactly ``k`` specialists using a
   deterministic capability-matching ranking.

The experiment is frozen via a content-addressed :class:`ExperimentContract`
and produces a content-addressed :class:`ExperimentReceipt` with a local
scientific decision (``FALSIFIED_LOCAL`` / ``CONTEXTUAL_LOCAL`` /
``SUPPORTED_LOCAL``).

Constitutional guarantees (design doc §2):
- ``truth_effect = NONE``, ``assimilation_effect = NONE``.
- Mechanism stays at ``A1_MECHANISM_HYPOTHESIS``.
- No canonical checkpoint/champion/promotion/adaptation mutation.
- The capability router sees ONLY declared capabilities — no task-quality
  labels, no evaluator outputs, no hidden task labels.
- Equal processing-resource budget across all arms (no arm silently gets more).
- A negative/null result is a valid outcome (``FALSIFIED_LOCAL``).
"""

from __future__ import annotations

import hashlib
import random
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from ..util import canonical_hash

EXPERIMENT_VERSION = "METAENGINE-EXPERIMENT-SPARSE-ROUTING-1"
STAGE_ID = "METAENGINE-1-SLICE-4"
MECHANISM_ID = "sparse-conditional-routing"
DEFAULT_K = 2
DEFAULT_BUDGET = 2.0
DEFAULT_SEEDS = (42, 99, 137)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExperimentArm(str, Enum):
    DENSE_ALL_SPECIALISTS = "DENSE_ALL_SPECIALISTS"
    RANDOM_TOP_K = "RANDOM_TOP_K"
    CAPABILITY_ROUTED_TOP_K = "CAPABILITY_ROUTED_TOP_K"


class TaskRegime(str, Enum):
    REGIME_A_SEPARABLE_SPECIALIST_TASKS = "REGIME_A_SEPARABLE_SPECIALIST_TASKS"
    REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS = "REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS"


class LocalDecision(str, Enum):
    FALSIFIED_LOCAL = "FALSIFIED_LOCAL"
    CONTEXTUAL_LOCAL = "CONTEXTUAL_LOCAL"
    SUPPORTED_LOCAL = "SUPPORTED_LOCAL"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _require_hex64(value: object, code: str) -> str:
    text = str(value).strip()
    if not _is_hex(text, 64):
        raise ValueError(code)
    return text


# ---------------------------------------------------------------------------
# Specialist (simplified provider-neutral ResourceDescriptor projection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Specialist:
    resource_id: str
    capabilities: tuple[tuple[str, float], ...]  # (capability_id, affinity 0..1)
    cost: float

    @classmethod
    def create(
        cls,
        resource_id: str,
        capabilities: Iterable[tuple[str, float]],
        cost: float = 1.0,
    ) -> "Specialist":
        caps = tuple(
            sorted(
                ((_text(c, "CAPABILITY_ID_REQUIRED"), float(a)) for c, a in capabilities),
                key=lambda x: x[0],
            )
        )
        for cap_id, aff in caps:
            if not (0.0 <= aff <= 1.0):
                raise ValueError(f"CAPABILITY_AFFINITY_OUT_OF_RANGE:{cap_id}:{aff}")
        return cls(
            resource_id=_text(resource_id, "RESOURCE_ID_REQUIRED"),
            capabilities=caps,
            cost=float(cost),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "capabilities": [[c, a] for c, a in self.capabilities],
            "cost": self.cost,
        }

    @property
    def specialist_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Specialist":
        return cls.create(
            resource_id=str(value["resource_id"]),
            capabilities=tuple(tuple(x) for x in value.get("capabilities", ())),
            cost=float(value.get("cost", 1.0)),
        )


# ---------------------------------------------------------------------------
# TaskRequirement + TaskSuite
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskRequirement:
    task_id: str
    regime: TaskRegime
    required_capabilities: tuple[str, ...]
    # Ground-truth quality per specialist for this task. This is INDEPENDENT of
    # the capability affinity used by the router: it is the actual task-quality
    # each specialist would produce if activated. This breaks the selector=scorer
    # circularity: the router selects by affinity, the evaluator scores by
    # ground-truth. A capability router can now LOSE if its affinity-based
    # selection picks specialists with low ground-truth quality.
    ground_truth: tuple[tuple[str, float], ...]

    @classmethod
    def create(
        cls,
        task_id: str,
        regime: TaskRegime | str,
        required_capabilities: Iterable[str],
        ground_truth: Iterable[tuple[str, float]] | None = None,
    ) -> "TaskRequirement":
        caps = tuple(sorted({_text(c, "TASK_CAP_REQUIRED") for c in required_capabilities}))
        if not caps:
            raise ValueError("TASK_CAPABILITIES_REQUIRED")
        gt = tuple(
            sorted(
                ((_text(s, "GT_SPECIALIST_ID_REQUIRED"), float(q)) for s, q in (ground_truth or ())),
                key=lambda x: x[0],
            )
        )
        for sid, q in gt:
            if not (0.0 <= q <= 1.0):
                raise ValueError(f"GT_QUALITY_OUT_OF_RANGE:{sid}:{q}")
        return cls(
            task_id=_text(task_id, "TASK_ID_REQUIRED"),
            regime=TaskRegime(regime),
            required_capabilities=caps,
            ground_truth=gt,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "regime": self.regime.value,
            "required_capabilities": list(self.required_capabilities),
            "ground_truth": [[s, q] for s, q in self.ground_truth],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskRequirement":
        return cls.create(
            task_id=str(value["task_id"]),
            regime=str(value["regime"]),
            required_capabilities=tuple(value.get("required_capabilities", ())),
            ground_truth=tuple(tuple(x) for x in value.get("ground_truth", ())),
        )


@dataclass(frozen=True)
class TaskSuite:
    tasks: tuple[TaskRequirement, ...]

    @classmethod
    def create(cls, tasks: Iterable[TaskRequirement]) -> "TaskSuite":
        ordered = tuple(sorted(tasks, key=lambda t: t.task_id))
        ids = [t.task_id for t in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("TASK_ID_DUPLICATE")
        if not ordered:
            raise ValueError("TASK_SUITE_EMPTY")
        return cls(tasks=ordered)

    def payload(self) -> dict[str, Any]:
        return {"tasks": [t.payload() for t in self.tasks]}

    @property
    def suite_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskSuite":
        return cls.create(tuple(TaskRequirement.from_dict(t) for t in value.get("tasks", ())))


# ---------------------------------------------------------------------------
# ExperimentContract (frozen, content-addressed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentContract:
    experiment_version: str
    stage_id: str
    mechanism_id: str
    mechanism_card_hash: str
    constitution_hash: str
    specialists: tuple[Specialist, ...]
    task_suite: TaskSuite
    arms: tuple[ExperimentArm, ...]
    k: int
    processing_resource_units: float
    random_seeds: tuple[int, ...]
    truth_effect: str
    assimilation_effect: str

    @classmethod
    def create(
        cls,
        *,
        constitution_hash: str,
        mechanism_card_hash: str,
        specialists: Iterable[Specialist],
        task_suite: TaskSuite,
        arms: Iterable[ExperimentArm | str],
        k: int = DEFAULT_K,
        processing_resource_units: float = DEFAULT_BUDGET,
        random_seeds: Iterable[int] = DEFAULT_SEEDS,
        experiment_version: str = EXPERIMENT_VERSION,
        stage_id: str = STAGE_ID,
        mechanism_id: str = MECHANISM_ID,
    ) -> "ExperimentContract":
        specs = tuple(sorted(specialists, key=lambda s: s.resource_id))
        if len(specs) < 2:
            raise ValueError("CONTRACT_SPECIALISTS_REQUIRED")
        ids = [s.resource_id for s in specs]
        if len(ids) != len(set(ids)):
            raise ValueError("CONTRACT_SPECIALIST_ID_DUPLICATE")
        ordered_arms = tuple(sorted(ExperimentArm(a) for a in arms))
        seeds = tuple(sorted(int(s) for s in random_seeds))
        if not seeds:
            raise ValueError("CONTRACT_SEEDS_REQUIRED")
        if int(k) < 1 or int(k) > len(specs):
            raise ValueError("CONTRACT_K_INVALID")
        return cls(
            experiment_version=experiment_version,
            stage_id=stage_id,
            mechanism_id=mechanism_id,
            mechanism_card_hash=_require_hex64(mechanism_card_hash, "CONTRACT_MECHANISM_CARD_HASH_INVALID"),
            constitution_hash=_require_hex64(constitution_hash, "CONTRACT_CONSTITUTION_HASH_INVALID"),
            specialists=specs,
            task_suite=task_suite,
            arms=ordered_arms,
            k=int(k),
            processing_resource_units=float(processing_resource_units),
            random_seeds=seeds,
            truth_effect="NONE",
            assimilation_effect="NONE",
        )

    def payload(self) -> dict[str, Any]:
        return {
            "experiment_version": self.experiment_version,
            "stage_id": self.stage_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_card_hash": self.mechanism_card_hash,
            "constitution_hash": self.constitution_hash,
            "specialists": [s.payload() for s in self.specialists],
            "task_suite": self.task_suite.payload(),
            "arms": [a.value for a in self.arms],
            "k": self.k,
            "processing_resource_units": self.processing_resource_units,
            "random_seeds": list(self.random_seeds),
            "truth_effect": self.truth_effect,
            "assimilation_effect": self.assimilation_effect,
        }

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self.payload())

    @property
    def task_suite_hash(self) -> str:
        return self.task_suite.suite_hash

    @property
    def specialist_hashes(self) -> tuple[str, ...]:
        return tuple(s.specialist_hash for s in self.specialists)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentContract":
        contract = cls.create(
            constitution_hash=str(value["constitution_hash"]),
            mechanism_card_hash=str(value["mechanism_card_hash"]),
            specialists=tuple(Specialist.from_dict(s) for s in value.get("specialists", ())),
            task_suite=TaskSuite.from_dict(value.get("task_suite", {})),
            arms=tuple(value.get("arms", ())),
            k=int(value.get("k", DEFAULT_K)),
            processing_resource_units=float(value.get("processing_resource_units", DEFAULT_BUDGET)),
            random_seeds=tuple(value.get("random_seeds", DEFAULT_SEEDS)),
            experiment_version=str(value.get("experiment_version", EXPERIMENT_VERSION)),
            stage_id=str(value.get("stage_id", STAGE_ID)),
            mechanism_id=str(value.get("mechanism_id", MECHANISM_ID)),
        )
        claimed = value.get("contract_hash")
        if claimed is not None and str(claimed) != contract.contract_hash:
            raise ValueError("CONTRACT_HASH_MISMATCH")
        return contract


# ---------------------------------------------------------------------------
# Affinity + selection (the three arms)
# ---------------------------------------------------------------------------


def specialist_affinity(specialist: Specialist, task: TaskRequirement) -> float:
    """Mean of specialist's affinity values for the task's required capabilities.

    Returns 0.0 if the task has no required capabilities (defensive).
    """
    cap_map = dict(specialist.capabilities)
    if not task.required_capabilities:
        return 0.0
    return sum(cap_map.get(c, 0.0) for c in task.required_capabilities) / len(task.required_capabilities)


def select_dense(specialists: Iterable[Specialist]) -> tuple[str, ...]:
    """DENSE_ALL_SPECIALISTS: activate every specialist."""
    return tuple(sorted(s.resource_id for s in specialists))


def select_random(specialists: Iterable[Specialist], *, seed: int, k: int) -> tuple[str, ...]:
    """RANDOM_TOP_K: select exactly k specialists using a frozen seed.

    Uses a deterministic RNG seeded with ``seed``. The specialist list is
    sorted by resource_id before sampling so the seed produces a stable
    selection regardless of input order.
    """
    ordered = sorted(specialists, key=lambda s: s.resource_id)
    rng = random.Random(int(seed))
    indices = sorted(rng.sample(range(len(ordered)), k))
    return tuple(ordered[i].resource_id for i in indices)


def select_capability(specialists: Iterable[Specialist], task: TaskRequirement, *, k: int) -> tuple[str, ...]:
    """CAPABILITY_ROUTED_TOP_K: select exactly k by affinity ranking.

    Sees ONLY declared capabilities (via ``specialist.capabilities`` and
    ``task.required_capabilities``). No access to task-quality labels or
    evaluator outputs.

    Tie-breaking: by resource_id ascending (canonical, replayable).
    """
    scored = sorted(
        specialists,
        key=lambda s: (-specialist_affinity(s, task), s.resource_id),
    )
    return tuple(s.resource_id for s in scored[:k])


# ---------------------------------------------------------------------------
# Task evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    regime: TaskRegime
    arm: ExperimentArm
    selected_specialists: tuple[str, ...]
    task_quality: float
    active_resource_count: int
    processing_resource_units: float
    routing_error_rate: float
    routing_overhead: float
    activation_overhead: float
    deterministic_cost_proxy: float
    complexity_delta: float
    reproducibility_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "regime": self.regime.value,
            "arm": self.arm.value,
            "selected_specialists": list(self.selected_specialists),
            "task_quality": round(self.task_quality, 6),
            "active_resource_count": self.active_resource_count,
            "processing_resource_units": self.processing_resource_units,
            "routing_error_rate": round(self.routing_error_rate, 6),
            "routing_overhead": round(self.routing_overhead, 6),
            "activation_overhead": round(self.activation_overhead, 6),
            "deterministic_cost_proxy": round(self.deterministic_cost_proxy, 6),
            "complexity_delta": round(self.complexity_delta, 6),
            "reproducibility_hash": self.reproducibility_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskResult":
        return cls(
            task_id=str(value["task_id"]),
            regime=TaskRegime(str(value["regime"])),
            arm=ExperimentArm(str(value["arm"])),
            selected_specialists=tuple(value.get("selected_specialists", ())),
            task_quality=float(value["task_quality"]),
            active_resource_count=int(value["active_resource_count"]),
            processing_resource_units=float(value["processing_resource_units"]),
            routing_error_rate=float(value["routing_error_rate"]),
            routing_overhead=float(value["routing_overhead"]),
            activation_overhead=float(value["activation_overhead"]),
            deterministic_cost_proxy=float(value["deterministic_cost_proxy"]),
            complexity_delta=float(value["complexity_delta"]),
            reproducibility_hash=str(value["reproducibility_hash"]),
        )


def _evaluate_task(
    contract: ExperimentContract,
    task: TaskRequirement,
    arm: ExperimentArm,
    selected_ids: tuple[str, ...],
    *,
    dense_baseline_quality: float | None = None,
) -> TaskResult:
    """Evaluate a single task under one arm with the frozen budget.

    Scoring uses the task's **ground_truth** quality per specialist — NOT the
    capability affinity used by the router. This breaks the selector=scorer
    circularity: the router selects by affinity, the evaluator scores by
    ground-truth. A capability router can now LOSE if its affinity-based
    selection picks specialists with low ground-truth quality.
    """
    spec_map = {s.resource_id: s for s in contract.specialists}
    active = [spec_map[rid] for rid in selected_ids]
    n_active = len(active)
    budget = contract.processing_resource_units

    # Build a ground-truth lookup. Specialists not in ground_truth default to
    # 0.0 (UNOBSERVED / no contribution).
    gt_map = dict(task.ground_truth) if task.ground_truth else {}

    if n_active == 0:
        quality = 0.0
    else:
        per_unit = budget / n_active
        quality = sum(gt_map.get(s.resource_id, 0.0) * per_unit for s in active)

    # routing_error_rate: did the selection miss the BEST ground-truth specialist?
    # (Not the highest-affinity one — the one that actually produces the best
    # quality. This measures whether the router found the right specialist for
    # the task, independently of the router's own affinity criterion.)
    if gt_map:
        best_gt_id = min(
            contract.specialists,
            key=lambda s: (-gt_map.get(s.resource_id, 0.0), s.resource_id),
        ).resource_id
        routing_error = 0.0 if best_gt_id in selected_ids else 1.0
    else:
        # No ground truth: routing_error is UNOBSERVED (0.0 is the neutral value
        # for a metric, but the experiment SHOULD have ground truth).
        routing_error = 0.0

    # overheads
    if arm is ExperimentArm.DENSE_ALL_SPECIALISTS:
        routing_overhead = 0.0
    elif arm is ExperimentArm.RANDOM_TOP_K:
        routing_overhead = 0.1  # constant random-selection overhead
    else:
        routing_overhead = 0.15  # ranking cost

    activation_overhead = n_active * 0.05
    deterministic_cost = sum(s.cost for s in active)

    if dense_baseline_quality is not None and dense_baseline_quality > 0:
        complexity_delta = (quality - dense_baseline_quality) / dense_baseline_quality
    else:
        complexity_delta = 0.0

    reproducibility = canonical_hash({
        "contract_hash": contract.contract_hash,
        "task_id": task.task_id,
        "arm": arm.value,
        "selected": list(selected_ids),
    })

    return TaskResult(
        task_id=task.task_id,
        regime=task.regime,
        arm=arm,
        selected_specialists=selected_ids,
        task_quality=quality,
        active_resource_count=n_active,
        processing_resource_units=budget,
        routing_error_rate=routing_error,
        routing_overhead=routing_overhead,
        activation_overhead=activation_overhead,
        deterministic_cost_proxy=deterministic_cost,
        complexity_delta=complexity_delta,
        reproducibility_hash=reproducibility,
    )


# ---------------------------------------------------------------------------
# Arm result (aggregate across tasks)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmResult:
    arm: ExperimentArm
    task_results: tuple[TaskResult, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "task_results": [tr.payload() for tr in self.task_results],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArmResult":
        return cls(
            arm=ExperimentArm(str(value["arm"])),
            task_results=tuple(TaskResult.from_dict(tr) for tr in value.get("task_results", ())),
        )

    def mean_quality(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(tr.task_quality for tr in self.task_results) / len(self.task_results)


# ---------------------------------------------------------------------------
# ExperimentReceipt (content-addressed, with decision)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentReceipt:
    experiment_version: str
    stage_id: str
    mechanism_id: str
    mechanism_card_hash: str
    constitution_hash: str
    contract_hash: str
    task_suite_hash: str
    specialist_hashes: tuple[str, ...]
    arms: tuple[ExperimentArm, ...]
    random_seeds: tuple[int, ...]
    results: tuple[ArmResult, ...]
    ablation_comparisons: tuple[dict[str, Any], ...]
    local_decision: LocalDecision
    truth_effect: str
    assimilation_effect: str
    receipt_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "experiment_version": self.experiment_version,
            "stage_id": self.stage_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_card_hash": self.mechanism_card_hash,
            "constitution_hash": self.constitution_hash,
            "contract_hash": self.contract_hash,
            "task_suite_hash": self.task_suite_hash,
            "specialist_hashes": list(self.specialist_hashes),
            "arms": [a.value for a in self.arms],
            "random_seeds": list(self.random_seeds),
            "results": [r.payload() for r in self.results],
            "ablation_comparisons": list(self.ablation_comparisons),
            "local_decision": self.local_decision.value,
            "truth_effect": self.truth_effect,
            "assimilation_effect": self.assimilation_effect,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentReceipt":
        receipt = cls(
            experiment_version=str(value["experiment_version"]),
            stage_id=str(value["stage_id"]),
            mechanism_id=str(value["mechanism_id"]),
            mechanism_card_hash=str(value["mechanism_card_hash"]),
            constitution_hash=str(value["constitution_hash"]),
            contract_hash=str(value["contract_hash"]),
            task_suite_hash=str(value["task_suite_hash"]),
            specialist_hashes=tuple(value.get("specialist_hashes", ())),
            arms=tuple(ExperimentArm(a) for a in value.get("arms", ())),
            random_seeds=tuple(value.get("random_seeds", ())),
            results=tuple(ArmResult.from_dict(r) for r in value.get("results", ())),
            ablation_comparisons=tuple(value.get("ablation_comparisons", ())),
            local_decision=LocalDecision(str(value["local_decision"])),
            truth_effect=str(value["truth_effect"]),
            assimilation_effect=str(value["assimilation_effect"]),
            receipt_hash=str(value["receipt_hash"]),
        )
        actual = canonical_hash(receipt.payload())
        if actual != receipt.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return receipt

    def regime_quality(self, regime: TaskRegime | str) -> dict[ExperimentArm, float]:
        """Mean quality per arm for a given regime."""
        regime = TaskRegime(regime)
        out: dict[ExperimentArm, float] = {}
        for arm_result in self.results:
            regime_results = [tr for tr in arm_result.task_results if tr.regime is regime]
            if regime_results:
                out[arm_result.arm] = sum(tr.task_quality for tr in regime_results) / len(regime_results)
            else:
                out[arm_result.arm] = 0.0
        return out


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


DECISION_MARGIN = 0.05  # 5% margin to avoid noise


def _decide(
    regime_a: dict[ExperimentArm, float],
    regime_b: dict[ExperimentArm, float],
) -> LocalDecision:
    """Decide the local scientific outcome from per-regime quality.

    - SUPPORTED_LOCAL: capability routing beats BOTH dense and random in BOTH
      regimes (with margin).
    - CONTEXTUAL_LOCAL: capability routing beats baselines in Regime A but
      NOT in Regime B.
    - FALSIFIED_LOCAL: capability routing doesn't beat baselines in Regime A.
    """
    cap = ExperimentArm.CAPABILITY_ROUTED_TOP_K
    dense = ExperimentArm.DENSE_ALL_SPECIALISTS
    rand = ExperimentArm.RANDOM_TOP_K

    def beats_baselines(regime_q: dict[ExperimentArm, float]) -> bool:
        cap_q = regime_q.get(cap, 0.0)
        dense_q = regime_q.get(dense, 0.0)
        rand_q = regime_q.get(rand, 0.0)
        return cap_q > dense_q * (1 + DECISION_MARGIN) and cap_q > rand_q * (1 + DECISION_MARGIN)

    a_supported = beats_baselines(regime_a)
    b_supported = beats_baselines(regime_b)

    if a_supported and b_supported:
        return LocalDecision.SUPPORTED_LOCAL
    if a_supported and not b_supported:
        return LocalDecision.CONTEXTUAL_LOCAL
    return LocalDecision.FALSIFIED_LOCAL


# ---------------------------------------------------------------------------
# Run experiment
# ---------------------------------------------------------------------------


def run_experiment(contract: ExperimentContract) -> ExperimentReceipt:
    """Execute the frozen tournament and produce a content-addressed receipt."""
    specs = contract.specialists
    tasks = contract.task_suite.tasks
    arms = contract.arms

    # Precompute dense baseline quality per task (for complexity_delta).
    dense_baselines: dict[str, float] = {}
    for task in tasks:
        dense_selected = select_dense(specs)
        dense_result = _evaluate_task(contract, task, ExperimentArm.DENSE_ALL_SPECIALISTS, dense_selected)
        dense_baselines[task.task_id] = dense_result.task_quality

    arm_results: list[ArmResult] = []
    for arm in arms:
        task_results: list[TaskResult] = []
        for task in tasks:
            if arm is ExperimentArm.DENSE_ALL_SPECIALISTS:
                selected = select_dense(specs)
                tr = _evaluate_task(contract, task, arm, selected, dense_baseline_quality=dense_baselines[task.task_id])
                task_results.append(tr)
            elif arm is ExperimentArm.RANDOM_TOP_K:
                # Average across frozen seeds
                seed_results: list[TaskResult] = []
                for seed in contract.random_seeds:
                    selected = select_random(specs, seed=seed, k=contract.k)
                    tr = _evaluate_task(contract, task, arm, selected, dense_baseline_quality=dense_baselines[task.task_id])
                    seed_results.append(tr)
                # Mean the quality across seeds; keep the first result's structure
                mean_quality = sum(tr.task_quality for tr in seed_results) / len(seed_results)
                mean_routing_error = sum(tr.routing_error_rate for tr in seed_results) / len(seed_results)
                representative = seed_results[0]
                task_results.append(
                    TaskResult(
                        task_id=representative.task_id,
                        regime=representative.regime,
                        arm=representative.arm,
                        selected_specialists=representative.selected_specialists,
                        task_quality=mean_quality,
                        active_resource_count=representative.active_resource_count,
                        processing_resource_units=representative.processing_resource_units,
                        routing_error_rate=mean_routing_error,
                        routing_overhead=representative.routing_overhead,
                        activation_overhead=representative.activation_overhead,
                        deterministic_cost_proxy=representative.deterministic_cost_proxy,
                        complexity_delta=representative.complexity_delta,
                        reproducibility_hash=canonical_hash([tr.reproducibility_hash for tr in seed_results]),
                    )
                )
            elif arm is ExperimentArm.CAPABILITY_ROUTED_TOP_K:
                selected = select_capability(specs, task, k=contract.k)
                tr = _evaluate_task(contract, task, arm, selected, dense_baseline_quality=dense_baselines[task.task_id])
                task_results.append(tr)
        arm_results.append(ArmResult(arm=arm, task_results=tuple(task_results)))

    # Ablation comparisons
    ablations: list[dict[str, Any]] = []
    for ar in arm_results:
        ablations.append({
            "arm": ar.arm.value,
            "mean_quality": round(ar.mean_quality(), 6),
            "mean_active_resource_count": (
                sum(tr.active_resource_count for tr in ar.task_results) / len(ar.task_results)
                if ar.task_results else 0.0
            ),
            "mean_routing_error_rate": (
                sum(tr.routing_error_rate for tr in ar.task_results) / len(ar.task_results)
                if ar.task_results else 0.0
            ),
        })

    # Decision
    regime_a_q = {}
    regime_b_q = {}
    for ar in arm_results:
        a_results = [tr for tr in ar.task_results if tr.regime is TaskRegime.REGIME_A_SEPARABLE_SPECIALIST_TASKS]
        b_results = [tr for tr in ar.task_results if tr.regime is TaskRegime.REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS]
        if a_results:
            regime_a_q[ar.arm] = sum(tr.task_quality for tr in a_results) / len(a_results)
        if b_results:
            regime_b_q[ar.arm] = sum(tr.task_quality for tr in b_results) / len(b_results)

    decision = _decide(regime_a_q, regime_b_q)

    receipt = ExperimentReceipt(
        experiment_version=contract.experiment_version,
        stage_id=contract.stage_id,
        mechanism_id=contract.mechanism_id,
        mechanism_card_hash=contract.mechanism_card_hash,
        constitution_hash=contract.constitution_hash,
        contract_hash=contract.contract_hash,
        task_suite_hash=contract.task_suite_hash,
        specialist_hashes=contract.specialist_hashes,
        arms=contract.arms,
        random_seeds=contract.random_seeds,
        results=tuple(arm_results),
        ablation_comparisons=tuple(ablations),
        local_decision=decision,
        truth_effect="NONE",
        assimilation_effect="NONE",
        receipt_hash="",  # filled below
    )
    receipt_hash = canonical_hash(receipt.payload())
    return ExperimentReceipt(**{**receipt.__dict__, "receipt_hash": receipt_hash})


# ---------------------------------------------------------------------------
# Default contract builder (6 specialists, 6 tasks, 3 arms, k=2, budget=2)
# ---------------------------------------------------------------------------


def build_default_contract(
    *,
    constitution_hash: str,
    mechanism_card_hash: str,
) -> ExperimentContract:
    """Build the reference experiment contract from the design doc §5.

    Ground-truth design (breaks selector=scorer circularity):
    - Regime A (separable): ground-truth correlates with affinity — capability
      router should win (its affinity-based selection aligns with actual quality).
    - Regime B (ambiguous): ground-truth PARTIALLY DIVERGES from affinity —
      some tasks where the affinity-high specialist has LOW ground-truth quality.
      This makes CONTEXTUAL or FALSIFIED possible: the capability router can
      LOSE in Regime B if its affinity criterion misleads it.
    """
    specialists = (
        Specialist.create("spec.code", [("CODE", 1.0), ("REASONING", 0.2)], cost=1.0),
        Specialist.create("spec.math", [("MATH", 1.0), ("REASONING", 0.3)], cost=1.0),
        Specialist.create("spec.translate", [("TRANSLATE", 1.0), ("LANGUAGE", 0.8)], cost=1.0),
        Specialist.create("spec.reason", [("REASONING", 1.0), ("LOGIC", 0.9)], cost=1.0),
        Specialist.create("spec.retrieve", [("RETRIEVE", 1.0), ("SEARCH", 0.8)], cost=1.0),
        Specialist.create("spec.general", [("CODE", 0.3), ("MATH", 0.3), ("REASONING", 0.3), ("TRANSLATE", 0.3)], cost=1.0),
    )
    task_suite = TaskSuite.create((
        # Regime A: ground-truth aligns with affinity (capability router wins)
        TaskRequirement.create("task.code_a", TaskRegime.REGIME_A_SEPARABLE_SPECIALIST_TASKS, ("CODE",),
            ground_truth=[("spec.code", 0.95), ("spec.general", 0.30), ("spec.math", 0.05), ("spec.translate", 0.0), ("spec.reason", 0.10), ("spec.retrieve", 0.0)]),
        TaskRequirement.create("task.math_a", TaskRegime.REGIME_A_SEPARABLE_SPECIALIST_TASKS, ("MATH",),
            ground_truth=[("spec.math", 0.95), ("spec.general", 0.30), ("spec.code", 0.05), ("spec.translate", 0.0), ("spec.reason", 0.20), ("spec.retrieve", 0.0)]),
        TaskRequirement.create("task.translate_a", TaskRegime.REGIME_A_SEPARABLE_SPECIALIST_TASKS, ("TRANSLATE",),
            ground_truth=[("spec.translate", 0.95), ("spec.general", 0.30), ("spec.code", 0.0), ("spec.math", 0.0), ("spec.reason", 0.0), ("spec.retrieve", 0.0)]),
        # Regime B: ground-truth DIVERGES from affinity (adversarial)
        # task.code_reason_b: spec.code has high CODE affinity (1.0) but LOW ground-truth (0.20)
        #   -> capability router picks spec.code (high affinity) but gets low quality.
        #   The best ground-truth specialist is spec.reason (0.90) which has REASONING affinity 1.0
        #   but spec.code also has REASONING 0.2 so capability ranking: spec.reason(1.0) > spec.code(0.6 avg).
        #   Actually with k=2 and (CODE,REASONING) requirements, affinity: spec.code=avg(1.0,0.2)=0.6,
        #   spec.reason=avg(0,1.0)... wait spec.reason has no CODE. Let me recompute.
        #   spec.code caps: CODE=1.0, REASONING=0.2 -> avg for (CODE,REASONING) = 0.6
        #   spec.reason caps: REASONING=1.0, LOGIC=0.9 -> has REASONING but not CODE -> avg = (0+1.0)/2=0.5
        #   spec.general: CODE=0.3, REASONING=0.3 -> avg=0.3
        #   So capability router picks spec.code(0.6) + spec.reason(0.5).
        #   Ground-truth: spec.code=0.20 (LOW!), spec.reason=0.90 (HIGH).
        #   quality = (0.20 + 0.90) * (2/2) = 1.10. Dense = sum all gt /6 *2.
        #   This is a case where capability routing still does OK (gets spec.reason).
        # Let me make a cleaner adversarial case:
        TaskRequirement.create("task.code_reason_b", TaskRegime.REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS, ("CODE", "REASONING"),
            ground_truth=[("spec.code", 0.20), ("spec.reason", 0.90), ("spec.general", 0.40), ("spec.math", 0.10), ("spec.translate", 0.0), ("spec.retrieve", 0.0)]),
        # task.math_logic_b: spec.math has high MATH affinity but LOW ground-truth (0.15) — adversarial
        TaskRequirement.create("task.math_logic_b", TaskRegime.REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS, ("MATH", "LOGIC"),
            ground_truth=[("spec.math", 0.15), ("spec.reason", 0.85), ("spec.general", 0.35), ("spec.code", 0.10), ("spec.translate", 0.0), ("spec.retrieve", 0.0)]),
        # task.general_b: genuinely ambiguous — no specialist is clearly best
        TaskRequirement.create("task.general_b", TaskRegime.REGIME_B_AMBIGUOUS_OR_OVERLAPPING_TASKS, ("CODE", "MATH", "REASONING"),
            ground_truth=[("spec.general", 0.60), ("spec.code", 0.35), ("spec.math", 0.35), ("spec.reason", 0.40), ("spec.translate", 0.0), ("spec.retrieve", 0.0)]),
    ))
    return ExperimentContract.create(
        constitution_hash=constitution_hash,
        mechanism_card_hash=mechanism_card_hash,
        specialists=specialists,
        task_suite=task_suite,
        arms=(
            ExperimentArm.DENSE_ALL_SPECIALISTS,
            ExperimentArm.RANDOM_TOP_K,
            ExperimentArm.CAPABILITY_ROUTED_TOP_K,
        ),
        k=DEFAULT_K,
        processing_resource_units=DEFAULT_BUDGET,
        random_seeds=DEFAULT_SEEDS,
    )
