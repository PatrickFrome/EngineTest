"""METAENGINE Step 2 — Heterogeneous transfer test for sparse-conditional-routing.

Design doc §20: "a heterogeneous transfer test with independently implemented
resources/models under the same mechanism contract."

The transfer test checks whether the sparse-conditional-routing mechanism
TRANSFERS across independently implemented resources, or is local-only. Each
implementation has its OWN routing criterion (not the same affinity function):

- LEXICAL: routes by token overlap (Jaccard similarity)
- SEMANTIC_CLUSTER: routes by cluster membership overlap
- HASH_BASELINE: routes by deterministic hash (content-blind control)

The evaluator uses an independent ground-truth (not any router's criterion).
A mechanism that works only on one implementation is LOCAL; one that works
across implementations TRANSFERS.

Constitutional guarantees:
- truth_effect = NONE, assimilation_effect = NONE
- Mechanism stays at A1 (transfer evidence is necessary but not sufficient
  for advancement; a separately authorized gate is still required)
- Equal processing-resource budget across all arms
- Content-addressed contract + receipt with tamper detection
"""

from __future__ import annotations

import hashlib
import random
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from ..util import canonical_hash

TRANSFER_PROTOCOL_VERSION = "METAENGINE-TRANSFER-TEST-1"
STAGE_ID = "METAENGINE-1-SLICE-4-TRANSFER"
MECHANISM_ID = "sparse-conditional-routing"
DEFAULT_K = 2
DEFAULT_BUDGET = 2.0
DEFAULT_SEEDS = (42, 99, 137)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ImplementationKind(str, Enum):
    LEXICAL = "LEXICAL"
    SEMANTIC_CLUSTER = "SEMANTIC_CLUSTER"
    HASH_BASELINE = "HASH_BASELINE"


class TransferArm(str, Enum):
    DENSE_ALL = "DENSE_ALL"
    RANDOM_TOP_K = "RANDOM_TOP_K"
    ROUTED_TOP_K = "ROUTED_TOP_K"


class TransferRegime(str, Enum):
    REGIME_A_SEPARABLE = "REGIME_A_SEPARABLE"
    REGIME_B_AMBIGUOUS = "REGIME_B_AMBIGUOUS"


class TransferDecision(str, Enum):
    TRANSFERRED = "TRANSFERRED"
    PARTIAL_TRANSFER = "PARTIAL_TRANSFER"
    NOT_TRANSFERRED = "NOT_TRANSFERRED"


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


def _strings(values: Iterable[object], *, code: str) -> tuple[str, ...]:
    return tuple(sorted({_text(v, code) for v in values}))


# ---------------------------------------------------------------------------
# TransferSpecialist (heterogeneous: has implementation-specific data)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferSpecialist:
    resource_id: str
    implementation_kind: ImplementationKind
    # LEXICAL: tokens this specialist handles
    # SEMANTIC_CLUSTER: cluster IDs this specialist covers
    # HASH_BASELINE: hash-seed (content-blind)
    routing_data: tuple[str, ...]
    cost: float

    @classmethod
    def create(
        cls,
        resource_id: str,
        implementation_kind: ImplementationKind | str,
        routing_data: Iterable[str] = (),
        cost: float = 1.0,
    ) -> "TransferSpecialist":
        return cls(
            resource_id=_text(resource_id, "RESOURCE_ID_REQUIRED"),
            implementation_kind=ImplementationKind(implementation_kind),
            routing_data=_strings(routing_data, code="ROUTING_DATA_REQUIRED"),
            cost=float(cost),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "implementation_kind": self.implementation_kind.value,
            "routing_data": list(self.routing_data),
            "cost": self.cost,
        }

    @property
    def specialist_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferSpecialist":
        return cls.create(
            resource_id=str(value["resource_id"]),
            implementation_kind=str(value["implementation_kind"]),
            routing_data=tuple(value.get("routing_data", ())),
            cost=float(value.get("cost", 1.0)),
        )


# ---------------------------------------------------------------------------
# TransferTask (has independent ground-truth, NOT routing criterion)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferTask:
    task_id: str
    regime: TransferRegime
    required_tokens: tuple[str, ...]  # for LEXICAL router
    required_clusters: tuple[str, ...]  # for SEMANTIC router
    ground_truth: tuple[tuple[str, float], ...]  # INDEPENDENT of all routers

    @classmethod
    def create(
        cls,
        task_id: str,
        regime: TransferRegime | str,
        required_tokens: Iterable[str],
        required_clusters: Iterable[str],
        ground_truth: Iterable[tuple[str, float]],
    ) -> "TransferTask":
        gt = tuple(
            sorted(
                ((_text(s, "GT_SPECIALIST_ID_REQUIRED"), float(q)) for s, q in ground_truth),
                key=lambda x: x[0],
            )
        )
        for sid, q in gt:
            if not (0.0 <= q <= 1.0):
                raise ValueError(f"GT_QUALITY_OUT_OF_RANGE:{sid}:{q}")
        return cls(
            task_id=_text(task_id, "TASK_ID_REQUIRED"),
            regime=TransferRegime(regime),
            required_tokens=_strings(required_tokens, code="TASK_TOKENS_REQUIRED"),
            required_clusters=_strings(required_clusters, code="TASK_CLUSTERS_REQUIRED"),
            ground_truth=gt,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "regime": self.regime.value,
            "required_tokens": list(self.required_tokens),
            "required_clusters": list(self.required_clusters),
            "ground_truth": [[s, q] for s, q in self.ground_truth],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferTask":
        return cls.create(
            task_id=str(value["task_id"]),
            regime=str(value["regime"]),
            required_tokens=tuple(value.get("required_tokens", ())),
            required_clusters=tuple(value.get("required_clusters", ())),
            ground_truth=tuple(tuple(x) for x in value.get("ground_truth", ())),
        )


@dataclass(frozen=True)
class TransferTaskSuite:
    tasks: tuple[TransferTask, ...]

    @classmethod
    def create(cls, tasks: Iterable[TransferTask]) -> "TransferTaskSuite":
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
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferTaskSuite":
        return cls.create(tuple(TransferTask.from_dict(t) for t in value.get("tasks", ())))


# ---------------------------------------------------------------------------
# TransferContract (frozen, content-addressed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferContract:
    transfer_version: str
    stage_id: str
    mechanism_id: str
    mechanism_card_hash: str
    constitution_hash: str
    specialists: tuple[TransferSpecialist, ...]
    task_suite: TransferTaskSuite
    arms: tuple[TransferArm, ...]
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
        specialists: Iterable[TransferSpecialist],
        task_suite: TransferTaskSuite,
        arms: Iterable[TransferArm | str],
        k: int = DEFAULT_K,
        processing_resource_units: float = DEFAULT_BUDGET,
        random_seeds: Iterable[int] = DEFAULT_SEEDS,
    ) -> "TransferContract":
        specs = tuple(sorted(specialists, key=lambda s: s.resource_id))
        if len(specs) < 2:
            raise ValueError("CONTRACT_SPECIALISTS_REQUIRED")
        ordered_arms = tuple(sorted(TransferArm(a) for a in arms))
        seeds = tuple(sorted(int(s) for s in random_seeds))
        if not seeds:
            raise ValueError("CONTRACT_SEEDS_REQUIRED")
        return cls(
            transfer_version=TRANSFER_PROTOCOL_VERSION,
            stage_id=STAGE_ID,
            mechanism_id=MECHANISM_ID,
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
            "transfer_version": self.transfer_version,
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

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferContract":
        contract = cls.create(
            constitution_hash=str(value["constitution_hash"]),
            mechanism_card_hash=str(value["mechanism_card_hash"]),
            specialists=tuple(TransferSpecialist.from_dict(s) for s in value.get("specialists", ())),
            task_suite=TransferTaskSuite.from_dict(value.get("task_suite", {})),
            arms=tuple(value.get("arms", ())),
            k=int(value.get("k", DEFAULT_K)),
            processing_resource_units=float(value.get("processing_resource_units", DEFAULT_BUDGET)),
            random_seeds=tuple(value.get("random_seeds", DEFAULT_SEEDS)),
        )
        claimed = value.get("contract_hash")
        if claimed is not None and str(claimed) != contract.contract_hash:
            raise ValueError("CONTRACT_HASH_MISMATCH")
        return contract


# ---------------------------------------------------------------------------
# Heterogeneous routing functions (each implementation has its OWN criterion)
# ---------------------------------------------------------------------------


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def select_lexical(specialists: Iterable[TransferSpecialist], task: TransferTask, *, k: int) -> tuple[str, ...]:
    """LEXICAL router: select by token overlap (Jaccard similarity).

    This is INDEPENDENT of the SEMANTIC_CLUSTER and HASH_BASELINE criteria.
    """
    task_tokens = frozenset(task.required_tokens)
    scored = sorted(
        specialists,
        key=lambda s: (
            -_jaccard(frozenset(s.routing_data), task_tokens),
            s.resource_id,
        ),
    )
    return tuple(s.resource_id for s in scored[:k])


def select_semantic(specialists: Iterable[TransferSpecialist], task: TransferTask, *, k: int) -> tuple[str, ...]:
    """SEMANTIC_CLUSTER router: select by cluster membership overlap.

    This is INDEPENDENT of the LEXICAL and HASH_BASELINE criteria.
    """
    task_clusters = frozenset(task.required_clusters)
    scored = sorted(
        specialists,
        key=lambda s: (
            -len(frozenset(s.routing_data) & task_clusters),
            s.resource_id,
        ),
    )
    return tuple(s.resource_id for s in scored[:k])


def select_hash_baseline(specialists: Iterable[TransferSpecialist], task: TransferTask, *, k: int) -> tuple[str, ...]:
    """HASH_BASELINE router: content-blind control. Selects by a deterministic
    hash of (specialist_id, task_id), NOT by any task content.

    This is a CONTROL: if sparse routing "works" here, it is an artefact of
    selection size, not routing quality.
    """
    scored = sorted(
        specialists,
        key=lambda s: (
            hashlib.sha256(f"{s.resource_id}:{task.task_id}".encode()).hexdigest(),
            s.resource_id,
        ),
    )
    return tuple(s.resource_id for s in scored[:k])


def select_dense(specialists: Iterable[TransferSpecialist]) -> tuple[str, ...]:
    return tuple(sorted(s.resource_id for s in specialists))


def select_random(specialists: Iterable[TransferSpecialist], *, seed: int, k: int) -> tuple[str, ...]:
    ordered = sorted(specialists, key=lambda s: s.resource_id)
    rng = random.Random(int(seed))
    indices = sorted(rng.sample(range(len(ordered)), k))
    return tuple(ordered[i].resource_id for i in indices)


# ---------------------------------------------------------------------------
# Transfer evaluation (independent ground-truth, NOT any routing criterion)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferTaskResult:
    task_id: str
    regime: TransferRegime
    implementation_kind: ImplementationKind
    arm: TransferArm
    selected_specialists: tuple[str, ...]
    task_quality: float
    active_resource_count: int
    processing_resource_units: float
    reproducibility_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "regime": self.regime.value,
            "implementation_kind": self.implementation_kind.value,
            "arm": self.arm.value,
            "selected_specialists": list(self.selected_specialists),
            "task_quality": round(self.task_quality, 6),
            "active_resource_count": self.active_resource_count,
            "processing_resource_units": self.processing_resource_units,
            "reproducibility_hash": self.reproducibility_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferTaskResult":
        return cls(
            task_id=str(value["task_id"]),
            regime=TransferRegime(str(value["regime"])),
            implementation_kind=ImplementationKind(str(value["implementation_kind"])),
            arm=TransferArm(str(value["arm"])),
            selected_specialists=tuple(value.get("selected_specialists", ())),
            task_quality=float(value["task_quality"]),
            active_resource_count=int(value["active_resource_count"]),
            processing_resource_units=float(value["processing_resource_units"]),
            reproducibility_hash=str(value["reproducibility_hash"]),
        )


def _evaluate_transfer_task(
    contract: TransferContract,
    task: TransferTask,
    impl_kind: ImplementationKind,
    arm: TransferArm,
    selected_ids: tuple[str, ...],
) -> TransferTaskResult:
    """Evaluate using the task's INDEPENDENT ground-truth (not any routing criterion)."""
    spec_map = {s.resource_id: s for s in contract.specialists if s.implementation_kind is impl_kind}
    active = [spec_map[rid] for rid in selected_ids]
    n_active = len(active)
    budget = contract.processing_resource_units
    gt_map = dict(task.ground_truth) if task.ground_truth else {}

    if n_active == 0:
        quality = 0.0
    else:
        per_unit = budget / n_active
        quality = sum(gt_map.get(s.resource_id, 0.0) * per_unit for s in active)

    reproducibility = canonical_hash({
        "contract_hash": contract.contract_hash,
        "task_id": task.task_id,
        "implementation_kind": impl_kind.value,
        "arm": arm.value,
        "selected": list(selected_ids),
    })

    return TransferTaskResult(
        task_id=task.task_id,
        regime=task.regime,
        implementation_kind=impl_kind,
        arm=arm,
        selected_specialists=selected_ids,
        task_quality=quality,
        active_resource_count=n_active,
        processing_resource_units=budget,
        reproducibility_hash=reproducibility,
    )


# ---------------------------------------------------------------------------
# TransferArmResult (aggregate across tasks for one implementation+arm)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferArmResult:
    implementation_kind: ImplementationKind
    arm: TransferArm
    task_results: tuple[TransferTaskResult, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "implementation_kind": self.implementation_kind.value,
            "arm": self.arm.value,
            "task_results": [tr.payload() for tr in self.task_results],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferArmResult":
        return cls(
            implementation_kind=ImplementationKind(str(value["implementation_kind"])),
            arm=TransferArm(str(value["arm"])),
            task_results=tuple(TransferTaskResult.from_dict(tr) for tr in value.get("task_results", ())),
        )

    def mean_quality(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(tr.task_quality for tr in self.task_results) / len(self.task_results)


# ---------------------------------------------------------------------------
# TransferReceipt (content-addressed, with transfer decision)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferReceipt:
    transfer_version: str
    stage_id: str
    mechanism_id: str
    mechanism_card_hash: str
    constitution_hash: str
    contract_hash: str
    task_suite_hash: str
    results: tuple[TransferArmResult, ...]
    transfer_summary: tuple[dict[str, Any], ...]
    transfer_decision: TransferDecision
    truth_effect: str
    assimilation_effect: str
    receipt_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "transfer_version": self.transfer_version,
            "stage_id": self.stage_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_card_hash": self.mechanism_card_hash,
            "constitution_hash": self.constitution_hash,
            "contract_hash": self.contract_hash,
            "task_suite_hash": self.task_suite_hash,
            "results": [r.payload() for r in self.results],
            "transfer_summary": list(self.transfer_summary),
            "transfer_decision": self.transfer_decision.value,
            "truth_effect": self.truth_effect,
            "assimilation_effect": self.assimilation_effect,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferReceipt":
        receipt = cls(
            transfer_version=str(value["transfer_version"]),
            stage_id=str(value["stage_id"]),
            mechanism_id=str(value["mechanism_id"]),
            mechanism_card_hash=str(value["mechanism_card_hash"]),
            constitution_hash=str(value["constitution_hash"]),
            contract_hash=str(value["contract_hash"]),
            task_suite_hash=str(value["task_suite_hash"]),
            results=tuple(TransferArmResult.from_dict(r) for r in value.get("results", ())),
            transfer_summary=tuple(value.get("transfer_summary", ())),
            transfer_decision=TransferDecision(str(value["transfer_decision"])),
            truth_effect=str(value["truth_effect"]),
            assimilation_effect=str(value["assimilation_effect"]),
            receipt_hash=str(value["receipt_hash"]),
        )
        actual = canonical_hash(receipt.payload())
        if actual != receipt.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return receipt


# ---------------------------------------------------------------------------
# Transfer decision logic
# ---------------------------------------------------------------------------

DECISION_MARGIN = 0.05


def _decide_transfer(impl_outcomes: dict[ImplementationKind, bool]) -> TransferDecision:
    """Decide: TRANSFERRED if routed beats dense in ALL implementations,
    PARTIAL_TRANSFER if some, NOT_TRANSFERRED if none."""
    if not impl_outcomes:
        return TransferDecision.NOT_TRANSFERRED
    n_positive = sum(1 for v in impl_outcomes.values() if v)
    n_total = len(impl_outcomes)
    if n_positive == n_total:
        return TransferDecision.TRANSFERRED
    if n_positive == 0:
        return TransferDecision.NOT_TRANSFERRED
    return TransferDecision.PARTIAL_TRANSFER


# ---------------------------------------------------------------------------
# Run transfer test
# ---------------------------------------------------------------------------


def run_transfer_test(contract: TransferContract) -> TransferReceipt:
    """Execute the heterogeneous transfer tournament."""
    tasks = contract.task_suite.tasks
    arms = contract.arms
    impl_kinds = {s.implementation_kind for s in contract.specialists}

    arm_results: list[TransferArmResult] = []
    impl_outcomes: dict[ImplementationKind, bool] = {}

    for impl_kind in sorted(impl_kinds, key=lambda k: k.value):
        impl_specs = tuple(s for s in contract.specialists if s.implementation_kind is impl_kind)
        routed_qualities: list[float] = []
        dense_qualities: list[float] = []
        routed_beats_dense = True

        for arm in arms:
            task_results: list[TransferTaskResult] = []
            for task in tasks:
                if arm is TransferArm.DENSE_ALL:
                    selected = select_dense(impl_specs)
                    tr = _evaluate_transfer_task(contract, task, impl_kind, arm, selected)
                    task_results.append(tr)
                elif arm is TransferArm.RANDOM_TOP_K:
                    seed_results = []
                    for seed in contract.random_seeds:
                        selected = select_random(impl_specs, seed=seed, k=contract.k)
                        sr = _evaluate_transfer_task(contract, task, impl_kind, arm, selected)
                        seed_results.append(sr)
                    mean_q = sum(sr.task_quality for sr in seed_results) / len(seed_results)
                    tr = TransferTaskResult(
                        task_id=task.task_id, regime=task.regime, implementation_kind=impl_kind,
                        arm=arm, selected_specialists=seed_results[0].selected_specialists,
                        task_quality=mean_q, active_resource_count=seed_results[0].active_resource_count,
                        processing_resource_units=seed_results[0].processing_resource_units,
                        reproducibility_hash=canonical_hash([sr.reproducibility_hash for sr in seed_results]),
                    )
                    task_results.append(tr)
                elif arm is TransferArm.ROUTED_TOP_K:
                    if impl_kind is ImplementationKind.LEXICAL:
                        selected = select_lexical(impl_specs, task, k=contract.k)
                    elif impl_kind is ImplementationKind.SEMANTIC_CLUSTER:
                        selected = select_semantic(impl_specs, task, k=contract.k)
                    else:
                        selected = select_hash_baseline(impl_specs, task, k=contract.k)
                    tr = _evaluate_transfer_task(contract, task, impl_kind, arm, selected)
                    task_results.append(tr)

                if arm is TransferArm.ROUTED_TOP_K:
                    routed_qualities.append(tr.task_quality)
                elif arm is TransferArm.DENSE_ALL:
                    dense_qualities.append(tr.task_quality)

            arm_results.append(TransferArmResult(implementation_kind=impl_kind, arm=arm, task_results=tuple(task_results)))

        # Determine if routed beats dense for this implementation
        if routed_qualities and dense_qualities:
            mean_routed = sum(routed_qualities) / len(routed_qualities)
            mean_dense = sum(dense_qualities) / len(dense_qualities)
            routed_beats_dense = mean_routed > mean_dense * (1 + DECISION_MARGIN)
        else:
            routed_beats_dense = False
        impl_outcomes[impl_kind] = routed_beats_dense

    # Build transfer summary
    transfer_summary: list[dict[str, Any]] = []
    for impl_kind in sorted(impl_outcomes.keys(), key=lambda k: k.value):
        impl_arm_results = [r for r in arm_results if r.implementation_kind is impl_kind]
        routed = next((r for r in impl_arm_results if r.arm is TransferArm.ROUTED_TOP_K), None)
        dense = next((r for r in impl_arm_results if r.arm is TransferArm.DENSE_ALL), None)
        transfer_summary.append({
            "implementation_kind": impl_kind.value,
            "routed_better_than_dense": impl_outcomes[impl_kind],
            "mean_quality_routed": round(routed.mean_quality(), 6) if routed else 0.0,
            "mean_quality_dense": round(dense.mean_quality(), 6) if dense else 0.0,
        })

    decision = _decide_transfer(impl_outcomes)

    receipt = TransferReceipt(
        transfer_version=TRANSFER_PROTOCOL_VERSION,
        stage_id=STAGE_ID,
        mechanism_id=MECHANISM_ID,
        mechanism_card_hash=contract.mechanism_card_hash,
        constitution_hash=contract.constitution_hash,
        contract_hash=contract.contract_hash,
        task_suite_hash=contract.task_suite.suite_hash,
        results=tuple(arm_results),
        transfer_summary=tuple(transfer_summary),
        transfer_decision=decision,
        truth_effect="NONE",
        assimilation_effect="NONE",
        receipt_hash="",
    )
    receipt_hash = canonical_hash(receipt.payload())
    return TransferReceipt(**{**receipt.__dict__, "receipt_hash": receipt_hash})


# ---------------------------------------------------------------------------
# Default transfer contract builder
# ---------------------------------------------------------------------------


def build_default_transfer_contract(
    *,
    constitution_hash: str,
    mechanism_card_hash: str,
) -> TransferContract:
    """Build a heterogeneous transfer contract: 3 implementations × 2 specialists each,
    4 tasks (2 per regime), independent ground-truth.

    Design:
    - LEXICAL specialists handle token sets; LEXICAL router uses Jaccard overlap.
    - SEMANTIC_CLUSTER specialists handle cluster IDs; SEMANTIC router uses cluster overlap.
    - HASH_BASELINE specialists are content-blind; HASH router uses deterministic hash.
    - Ground-truth is INDEPENDENT: it does not equal token overlap, cluster overlap, or hash.
    - Regime A: ground-truth aligns with routing (routed should win).
    - Regime B: ground-truth diverges (adversarial — routed may lose).
    """
    specialists = (
        # LEXICAL implementation (4 specialists)
        TransferSpecialist.create("lex.code", ImplementationKind.LEXICAL, ["code", "function", "class", "method"]),
        TransferSpecialist.create("lex.prose", ImplementationKind.LEXICAL, ["prose", "narrative", "story", "text"]),
        TransferSpecialist.create("lex.data", ImplementationKind.LEXICAL, ["data", "schema", "query", "database"]),
        TransferSpecialist.create("lex.logic", ImplementationKind.LEXICAL, ["logic", "proof", "inference", "reasoning"]),
        # SEMANTIC_CLUSTER implementation (4 specialists)
        TransferSpecialist.create("sem.tech", ImplementationKind.SEMANTIC_CLUSTER, ["cluster_technical", "cluster_formal"]),
        TransferSpecialist.create("sem.creative", ImplementationKind.SEMANTIC_CLUSTER, ["cluster_creative", "cluster_informal"]),
        TransferSpecialist.create("sem.analytical", ImplementationKind.SEMANTIC_CLUSTER, ["cluster_analytical", "cluster_formal"]),
        TransferSpecialist.create("sem.expressive", ImplementationKind.SEMANTIC_CLUSTER, ["cluster_expressive", "cluster_informal"]),
        # HASH_BASELINE implementation (4 specialists, content-blind)
        TransferSpecialist.create("hash.a", ImplementationKind.HASH_BASELINE, []),
        TransferSpecialist.create("hash.b", ImplementationKind.HASH_BASELINE, []),
        TransferSpecialist.create("hash.c", ImplementationKind.HASH_BASELINE, []),
        TransferSpecialist.create("hash.d", ImplementationKind.HASH_BASELINE, []),
    )
    task_suite = TransferTaskSuite.create((
        # Regime A (separable): ground-truth aligns with routing — routed should win
        TransferTask.create("task.code_a", TransferRegime.REGIME_A_SEPARABLE,
            required_tokens=["code", "function"],
            required_clusters=["cluster_technical"],
            ground_truth=[("lex.code", 0.90), ("lex.prose", 0.10), ("lex.data", 0.20), ("lex.logic", 0.15),
                          ("sem.tech", 0.85), ("sem.creative", 0.10), ("sem.analytical", 0.30), ("sem.expressive", 0.05),
                          ("hash.a", 0.40), ("hash.b", 0.30), ("hash.c", 0.35), ("hash.d", 0.25)]),
        TransferTask.create("task.prose_a", TransferRegime.REGIME_A_SEPARABLE,
            required_tokens=["prose", "narrative"],
            required_clusters=["cluster_creative"],
            ground_truth=[("lex.prose", 0.90), ("lex.code", 0.10), ("lex.data", 0.05), ("lex.logic", 0.15),
                          ("sem.creative", 0.85), ("sem.tech", 0.10), ("sem.analytical", 0.15), ("sem.expressive", 0.30),
                          ("hash.a", 0.35), ("hash.b", 0.30), ("hash.c", 0.40), ("hash.d", 0.20)]),
        # Regime B (ambiguous/adversarial): ground-truth DIVERGES from routing
        TransferTask.create("task.mixed_b", TransferRegime.REGIME_B_AMBIGUOUS,
            required_tokens=["code", "prose"],
            required_clusters=["cluster_technical", "cluster_creative"],
            ground_truth=[("lex.code", 0.20), ("lex.prose", 0.20), ("lex.data", 0.70), ("lex.logic", 0.15),
                          ("sem.tech", 0.20), ("sem.creative", 0.20), ("sem.analytical", 0.65), ("sem.expressive", 0.10),
                          ("hash.a", 0.60), ("hash.b", 0.50), ("hash.c", 0.55), ("hash.d", 0.45)]),
        TransferTask.create("task.inverted_b", TransferRegime.REGIME_B_AMBIGUOUS,
            required_tokens=["function"],
            required_clusters=["cluster_formal"],
            ground_truth=[("lex.code", 0.15), ("lex.prose", 0.75), ("lex.data", 0.10), ("lex.logic", 0.20),
                          ("sem.tech", 0.10), ("sem.creative", 0.65), ("sem.analytical", 0.15), ("sem.expressive", 0.70),
                          ("hash.a", 0.50), ("hash.b", 0.45), ("hash.c", 0.40), ("hash.d", 0.55)]),
    ))
    return TransferContract.create(
        constitution_hash=constitution_hash,
        mechanism_card_hash=mechanism_card_hash,
        specialists=specialists,
        task_suite=task_suite,
        arms=(TransferArm.DENSE_ALL, TransferArm.RANDOM_TOP_K, TransferArm.ROUTED_TOP_K),
        k=DEFAULT_K,
        processing_resource_units=DEFAULT_BUDGET,
        random_seeds=DEFAULT_SEEDS,
    )
