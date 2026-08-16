from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import Verdict

from .contracts import FederatedCandidateReceipt, FederatedReviewReceipt, FederatedTaskEnvelope
from .types import ConflictClass


@dataclass(frozen=True)
class ConflictEdge:
    conflict_class: ConflictClass
    left: str
    right: str
    evidence: tuple[str, ...] = ()

    @property
    def conflict_hash(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ConflictGraph:
    conflicts: tuple[ConflictEdge, ...]
    ordering_edges: tuple[tuple[str, str], ...]

    @property
    def graph_hash(self) -> str:
        return canonical_digest(self)


def _edge(kind: ConflictClass, left: str, right: str, evidence: Iterable[str] = ()) -> ConflictEdge:
    a, b = sorted((str(left), str(right)))
    return ConflictEdge(kind, a, b, tuple(sorted(set(str(v) for v in evidence))))


def detect_candidate_conflicts(
    tasks: Iterable[FederatedTaskEnvelope],
    candidates: Iterable[FederatedCandidateReceipt],
    *,
    reviews: Iterable[FederatedReviewReceipt] = (),
) -> ConflictGraph:
    task_list = tuple(sorted(tasks, key=lambda item: item.task_hash))
    candidate_list = tuple(sorted(candidates, key=lambda item: item.candidate_hash))
    task_by_hash = {task.task_hash: task for task in task_list}
    task_id_to_hash = {task.task_id: task.task_hash for task in task_list}
    task_id_to_hash.update({task.base_task.task_id: task.task_hash for task in task_list})

    ordering: set[tuple[str, str]] = set()
    for task in task_list:
        for dependency_id in task.dependency_task_ids:
            dependency_hash = task_id_to_hash.get(dependency_id)
            if dependency_hash is not None and dependency_hash != task.task_hash:
                ordering.add((dependency_hash, task.task_hash))

    conflict_set: set[ConflictEdge] = set()
    for left_candidate, right_candidate in combinations(candidate_list, 2):
        if left_candidate.task_hash == right_candidate.task_hash:
            continue
        left_task = task_by_hash.get(left_candidate.task_hash)
        right_task = task_by_hash.get(right_candidate.task_hash)
        if left_task is None or right_task is None:
            continue
        if set(left_task.write_set) & set(right_task.write_set):
            conflict_set.add(
                _edge(
                    ConflictClass.PATH_WRITE_CONFLICT,
                    left_candidate.candidate_hash,
                    right_candidate.candidate_hash,
                    set(left_task.write_set) & set(right_task.write_set),
                )
            )
        if set(left_task.interface_set) & set(right_task.interface_set):
            conflict_set.add(
                _edge(
                    ConflictClass.INTERFACE_CONTRACT_CONFLICT,
                    left_candidate.candidate_hash,
                    right_candidate.candidate_hash,
                    set(left_task.interface_set) & set(right_task.interface_set),
                )
            )
        dependency_declared = (
            (left_task.task_hash, right_task.task_hash) in ordering
            or (right_task.task_hash, left_task.task_hash) in ordering
        )
        if left_task.base_checkpoint_id != right_task.base_checkpoint_id and not dependency_declared:
            conflict_set.add(
                _edge(
                    ConflictClass.STALE_BASE_CONFLICT,
                    left_candidate.candidate_hash,
                    right_candidate.candidate_hash,
                    (left_task.base_checkpoint_id, right_task.base_checkpoint_id),
                )
            )

    reviews_by_candidate: dict[str, list[FederatedReviewReceipt]] = {}
    for review in reviews:
        reviews_by_candidate.setdefault(review.candidate_hash, []).append(review)

    for candidate in candidate_list:
        task = task_by_hash.get(candidate.task_hash)
        if task is None or not task.review_slots:
            continue
        candidate_reviews = reviews_by_candidate.get(candidate.candidate_hash, [])
        for required_slot in task.review_slots:
            matching = [review for review in candidate_reviews if review.reviewer_slot is required_slot]
            if not matching or not any(review.verdict is Verdict.PASS for review in matching):
                conflict_set.add(
                    _edge(
                        ConflictClass.VERIFICATION_CONFLICT,
                        candidate.candidate_hash,
                        f"review:{required_slot.value}",
                        tuple(review.review_hash for review in matching),
                    )
                )

    conflicts = tuple(
        sorted(conflict_set, key=lambda edge: (edge.conflict_class.value, edge.left, edge.right, edge.evidence))
    )
    return ConflictGraph(conflicts=conflicts, ordering_edges=tuple(sorted(ordering)))
