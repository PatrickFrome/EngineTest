from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from typing import Iterable

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope, Verdict

from .conflicts import ConflictEdge, ConflictGraph, detect_candidate_conflicts
from .contracts import FederatedCandidateReceipt, FederatedReviewReceipt, FederatedTaskEnvelope
from .finalization import (
    FINALIZATION_PROTOCOL_VERSION,
    EpochFinalization,
    normalize_recovery_cut,
    recovery_cut_hash,
    snapshot_payload_from_cut,
)
from .store import FederationStore
from .types import CandidateEligibility, ConflictClass, IntegrationMode, SlotId


@dataclass(frozen=True)
class SynchronizationSnapshot:
    epoch_id: str
    base_checkpoint_id: str
    policy_hash: str
    catalog_hash: str
    eligible_candidates: tuple[str, ...]
    rejected_candidates: tuple[str, ...]
    stale_candidates: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    integration_order: tuple[str, ...]
    required_verification_hashes: tuple[str, ...]

    @property
    def snapshot_hash(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class CollectedFederation:
    tasks: tuple[FederatedTaskEnvelope, ...]
    candidates: tuple[FederatedCandidateReceipt, ...]
    reviews: tuple[FederatedReviewReceipt, ...]


def _decode_task(payload_json: str) -> FederatedTaskEnvelope:
    data = json.loads(payload_json)
    base = data["base_task"]
    base_task = TaskEnvelope(
        task_id=base["task_id"], task_hash=base["task_hash"], source_checkpoint_id=base["source_checkpoint_id"],
        source_tree_hash=base["source_tree_hash"], objective=base["objective"],
        acceptance_tests=tuple(base["acceptance_tests"]), allowed_paths=tuple(base["allowed_paths"]),
        forbidden_paths=tuple(base["forbidden_paths"]), capabilities_required=tuple(base["capabilities_required"]),
        risk_class=RiskClass(base["risk_class"]), privacy_class=PrivacyClass(base["privacy_class"]),
        zero_spend=bool(base["zero_spend"]),
    )
    return FederatedTaskEnvelope(
        base_task=base_task, epoch_id=data["epoch_id"], task_version=int(data["task_version"]),
        owner_slot=SlotId(data["owner_slot"]), lease_generation=int(data["lease_generation"]),
        role_profile_hash=data["role_profile_hash"], base_checkpoint_id=data["base_checkpoint_id"],
        dependency_task_ids=tuple(data["dependency_task_ids"]), read_set=tuple(data["read_set"]),
        write_set=tuple(data["write_set"]), interface_set=tuple(data["interface_set"]),
        integration_mode=IntegrationMode(data["integration_mode"]),
        review_slots=tuple(SlotId(v) for v in data["review_slots"]), blind_group_id=data.get("blind_group_id"),
    )


def _decode_candidate(payload_json: str) -> FederatedCandidateReceipt:
    data = json.loads(payload_json)
    return FederatedCandidateReceipt(
        base_candidate_hash=data["base_candidate_hash"], task_hash=data["task_hash"], epoch_id=data["epoch_id"],
        task_version=int(data["task_version"]), slot_id=SlotId(data["slot_id"]), session_id=data["session_id"],
        lease_generation=int(data["lease_generation"]), role_profile_hash=data["role_profile_hash"],
        base_checkpoint_id=data["base_checkpoint_id"], patch_digest=data["patch_digest"],
        changed_paths=tuple(data["changed_paths"]), interface_changes=tuple(data["interface_changes"]),
        verification_hashes=tuple(data["verification_hashes"]), claims=tuple(data["claims"]), risks=tuple(data["risks"]),
        dependency_observations=tuple(data["dependency_observations"]), summary=data["summary"],
    )


def _decode_review(payload_json: str) -> FederatedReviewReceipt:
    data = json.loads(payload_json)
    return FederatedReviewReceipt(
        candidate_hash=data["candidate_hash"], reviewer_slot=SlotId(data["reviewer_slot"]),
        session_id=data["session_id"], lease_generation=int(data["lease_generation"]),
        reviewer_role_profile_hash=data["reviewer_role_profile_hash"],
        verification_hashes=tuple(data["verification_hashes"]), verdict=Verdict(data["verdict"]),
    )


def build_recovery_cut(store: FederationStore, epoch_id: str, final_snapshot_hash: str) -> dict[str, object]:
    epoch = store.get_epoch(epoch_id)
    if epoch is None:
        raise KeyError(epoch_id)
    snapshot_row = store.snapshot_row(final_snapshot_hash)
    if snapshot_row is None or snapshot_row["epoch_id"] != epoch_id:
        raise ValueError("FEDERATION_FINAL_SNAPSHOT_INVALID")
    snapshot_payload = json.loads(snapshot_row["payload_json"])
    if canonical_digest(snapshot_payload) != final_snapshot_hash:
        raise ValueError("FEDERATION_FINAL_SNAPSHOT_INVALID")

    tasks: list[dict[str, object]] = []
    task_privacy: dict[str, str] = {}
    for row in store.list_task_rows(epoch_id):
        data = json.loads(row["payload_json"])
        base = data["base_task"]
        task_hash = str(row["task_hash"])
        privacy_class = str(base["privacy_class"])
        task_privacy[task_hash] = privacy_class
        tasks.append(
            {
                "task_hash": task_hash,
                "base_task_id": str(base["task_id"]),
                "task_version": int(data["task_version"]),
                "owner_slot": str(data["owner_slot"]),
                "lease_generation": int(data["lease_generation"]),
                "role_profile_hash": str(data["role_profile_hash"]),
                "dependency_task_ids": list(data["dependency_task_ids"]),
                "write_set": list(data["write_set"]),
                "interface_set": list(data["interface_set"]),
                "risk_class": str(base["risk_class"]),
                "privacy_class": privacy_class,
                "review_slots": list(data["review_slots"]),
            }
        )

    assignments = [
        {
            "assignment_id": str(row["assignment_id"]),
            "task_hash": str(row["task_hash"]),
            "session_id": str(row["session_id"]),
            "lease_generation": int(row["lease_generation"]),
            "assignment_state": str(row["assignment_state"]),
        }
        for row in store.list_assignment_rows(epoch_id)
    ]

    candidates: list[dict[str, object]] = []
    for row in store.list_candidate_rows(epoch_id):
        data = json.loads(row["payload_json"])
        candidates.append(
            {
                "candidate_hash": str(row["candidate_hash"]),
                "task_hash": str(row["task_hash"]),
                "task_version": int(data["task_version"]),
                "session_id": str(row["session_id"]),
                "lease_generation": int(row["lease_generation"]),
                "role_profile_hash": str(data["role_profile_hash"]),
                "eligibility": str(row["eligibility"]),
                "verification_hashes": list(data["verification_hashes"]),
                "changed_paths": list(data["changed_paths"]),
                "interface_changes": list(data["interface_changes"]),
                "claims": list(data["claims"]),
                "risks": list(data["risks"]),
                "dependency_observations": list(data["dependency_observations"]),
                "summary": str(data["summary"]),
                "privacy_class": task_privacy.get(str(row["task_hash"]), "P1"),
            }
        )

    reviews: list[dict[str, object]] = []
    candidate_task = {str(row["candidate_hash"]): str(row["task_hash"]) for row in candidates}
    for row in store.list_review_rows_for_epoch(epoch_id):
        data = json.loads(row["payload_json"])
        reviews.append(
            {
                "review_hash": str(row["review_hash"]),
                "candidate_hash": str(row["candidate_hash"]),
                "reviewer_slot": str(row["reviewer_slot"]),
                "session_id": str(row["session_id"]),
                "lease_generation": int(row["lease_generation"]),
                "reviewer_role_profile_hash": str(data["reviewer_role_profile_hash"]),
                "verdict": str(row["verdict"]),
                "verification_hashes": list(data["verification_hashes"]),
                "privacy_class": task_privacy.get(candidate_task.get(str(row["candidate_hash"]), ""), "P1"),
            }
        )

    conflicts: list[dict[str, object]] = []
    for row in store.list_conflict_rows(epoch_id):
        conflicts.append(
            {
                "conflict_hash": str(row["conflict_hash"]),
                "conflict_class": str(row["conflict_class"]),
                "left_ref": str(row["left_ref"]),
                "right_ref": str(row["right_ref"]),
                "resolved": False,
            }
        )

    decisions = [
        {
            "decision_hash": str(row["decision_hash"]),
            "candidate_hash": row["candidate_hash"],
            "decision": str(row["decision"]),
            "reason": str(row["reason"]),
        }
        for row in store.list_integration_decision_rows(epoch_id)
    ]
    witnesses = [
        {
            "slot_id": str(row["slot_id"]),
            "session_id": str(row["session_id"]),
            "lease_generation": int(row["lease_generation"]),
            "role_profile_hash": str(row["role_profile_hash"]),
            "revoked": bool(row["revoked"]),
            "released_at": row["released_at"],
        }
        for row in store.list_session_rows(epoch_id)
    ]

    cut = {
        "cut_version": FINALIZATION_PROTOCOL_VERSION,
        "epoch": {
            "epoch_id": epoch_id,
            "base_checkpoint_id": str(epoch["base_checkpoint_id"]),
            "base_payload_root": str(epoch.get("base_payload_root", "")),
            "federation_policy_hash": str(epoch["policy_hash"]),
            "role_catalog_hash": str(epoch["catalog_hash"]),
            "producer_concurrency": int(epoch.get("producer_concurrency", 0)),
        },
        "tasks": tasks,
        "assignments": assignments,
        "candidates": candidates,
        "reviews": reviews,
        "conflicts": conflicts,
        "integration_decisions": decisions,
        "participant_witnesses": witnesses,
        "terminal_snapshot": {"snapshot_hash": final_snapshot_hash, "snapshot": snapshot_payload},
    }
    normalized = normalize_recovery_cut(cut)
    if canonical_digest(snapshot_payload_from_cut(normalized)) != final_snapshot_hash:
        raise ValueError("FEDERATION_FINALIZATION_CUT_SNAPSHOT_MISMATCH")
    return normalized


def recover_from_cut(finalization: EpochFinalization) -> SynchronizationSnapshot:
    if finalization.protocol_version != FINALIZATION_PROTOCOL_VERSION:
        raise ValueError("FEDERATION_FINALIZATION_VERSION_UNSUPPORTED")
    try:
        actual_cut_hash = recovery_cut_hash(finalization.recovery_cut)
    except ValueError as exc:
        if str(exc) == "FEDERATION_FINALIZATION_VERSION_UNSUPPORTED":
            raise
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR") from exc
    if actual_cut_hash != finalization.recovery_cut_hash:
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")

    normalized = normalize_recovery_cut(finalization.recovery_cut)
    terminal = normalized["terminal_snapshot"]
    if str(terminal.get("snapshot_hash")) != finalization.final_snapshot_hash:
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")
    terminal_payload = terminal.get("snapshot")
    if not isinstance(terminal_payload, dict) or canonical_digest(terminal_payload) != finalization.final_snapshot_hash:
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")

    payload = snapshot_payload_from_cut(normalized)
    snapshot = SynchronizationSnapshot(
        epoch_id=str(payload["epoch_id"]),
        base_checkpoint_id=str(payload["base_checkpoint_id"]),
        policy_hash=str(payload["policy_hash"]),
        catalog_hash=str(payload["catalog_hash"]),
        eligible_candidates=tuple(payload["eligible_candidates"]),
        rejected_candidates=tuple(payload["rejected_candidates"]),
        stale_candidates=tuple(payload["stale_candidates"]),
        conflict_refs=tuple(payload["conflict_refs"]),
        integration_order=tuple(payload["integration_order"]),
        required_verification_hashes=tuple(payload["required_verification_hashes"]),
    )
    if snapshot.snapshot_hash != finalization.final_snapshot_hash:
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")
    return snapshot


class Synchronizer:
    """Disposable C0 projection over the federation ledger."""

    def __init__(self, store: FederationStore) -> None:
        self.store = store

    def collect(self, epoch_id: str) -> CollectedFederation:
        tasks = tuple(_decode_task(row["payload_json"]) for row in self.store.list_task_rows(epoch_id))
        candidate_rows = self.store.list_candidate_rows(epoch_id)
        candidates = tuple(_decode_candidate(row["payload_json"]) for row in candidate_rows)
        reviews: list[FederatedReviewReceipt] = []
        for candidate in candidates:
            reviews.extend(_decode_review(row["payload_json"]) for row in self.store.list_review_rows(candidate.candidate_hash))
        return CollectedFederation(
            tasks=tuple(sorted(tasks, key=lambda item: item.task_hash)),
            candidates=tuple(sorted(candidates, key=lambda item: item.candidate_hash)),
            reviews=tuple(sorted(reviews, key=lambda item: item.review_hash)),
        )

    def _candidate_base_eligibility(
        self, candidate: FederatedCandidateReceipt, task_by_hash: dict[str, FederatedTaskEnvelope]
    ) -> CandidateEligibility:
        task = task_by_hash.get(candidate.task_hash)
        if task is None:
            return CandidateEligibility.REJECTED
        if task.task_version != candidate.task_version:
            return CandidateEligibility.STALE_TASK_VERSION
        active = self.store.active_session_for_slot(candidate.epoch_id, candidate.slot_id)
        if (
            active is None
            or active["session_id"] != candidate.session_id
            or int(active["lease_generation"]) != candidate.lease_generation
        ):
            return CandidateEligibility.STALE_FENCED
        if active["role_profile_hash"] != candidate.role_profile_hash:
            return CandidateEligibility.REJECTED
        return CandidateEligibility.ELIGIBLE

    def _valid_review(
        self,
        candidate: FederatedCandidateReceipt,
        required_slot: SlotId,
        reviews: Iterable[FederatedReviewReceipt],
    ) -> FederatedReviewReceipt | None:
        for review in sorted(reviews, key=lambda item: item.review_hash):
            if review.candidate_hash != candidate.candidate_hash or review.reviewer_slot is not required_slot:
                continue
            if review.verdict is not Verdict.PASS or review.session_id == candidate.session_id:
                continue
            active = self.store.active_session_for_slot(candidate.epoch_id, required_slot)
            if active is None:
                continue
            if active["session_id"] != review.session_id or int(active["lease_generation"]) != review.lease_generation:
                continue
            if active["role_profile_hash"] != review.reviewer_role_profile_hash:
                continue
            return review
        return None

    def validate(
        self, epoch_id: str
    ) -> tuple[tuple[FederatedCandidateReceipt, ...], tuple[str, ...], tuple[str, ...], tuple[FederatedReviewReceipt, ...]]:
        collected = self.collect(epoch_id)
        task_by_hash = {task.task_hash: task for task in collected.tasks}
        eligible: list[FederatedCandidateReceipt] = []
        rejected: list[str] = []
        stale: list[str] = []
        accepted_reviews: list[FederatedReviewReceipt] = []
        for candidate in collected.candidates:
            state = self._candidate_base_eligibility(candidate, task_by_hash)
            if state in {CandidateEligibility.STALE_FENCED, CandidateEligibility.STALE_TASK_VERSION}:
                stale.append(candidate.candidate_hash)
                continue
            if state is not CandidateEligibility.ELIGIBLE:
                rejected.append(candidate.candidate_hash)
                continue
            task = task_by_hash[candidate.task_hash]
            required_reviews: list[FederatedReviewReceipt] = []
            review_ok = True
            for slot in task.review_slots:
                review = self._valid_review(candidate, slot, collected.reviews)
                if review is None:
                    review_ok = False
                    break
                required_reviews.append(review)
            if not review_ok:
                rejected.append(candidate.candidate_hash)
                continue
            eligible.append(candidate)
            accepted_reviews.extend(required_reviews)
        return (
            tuple(sorted(eligible, key=lambda item: item.candidate_hash)),
            tuple(sorted(set(rejected))),
            tuple(sorted(set(stale))),
            tuple(sorted(set(accepted_reviews), key=lambda item: item.review_hash)),
        )

    def graph(self, epoch_id: str) -> ConflictGraph:
        collected = self.collect(epoch_id)
        return detect_candidate_conflicts(collected.tasks, collected.candidates, reviews=collected.reviews)

    @staticmethod
    def _lexical_topological_sort(nodes: set[str], edges: Iterable[tuple[str, str]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        outgoing = {node: set() for node in nodes}
        indegree = {node: 0 for node in nodes}
        for left, right in edges:
            if left not in nodes or right not in nodes or left == right:
                continue
            if right not in outgoing[left]:
                outgoing[left].add(right)
                indegree[right] += 1
        heap = [node for node, degree in indegree.items() if degree == 0]
        heapq.heapify(heap)
        ordered: list[str] = []
        while heap:
            node = heapq.heappop(heap)
            ordered.append(node)
            for target in sorted(outgoing[node]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    heapq.heappush(heap, target)
        cyclic = tuple(sorted(node for node, degree in indegree.items() if degree > 0))
        return tuple(ordered), cyclic

    def integration_order(self, epoch_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        collected = self.collect(epoch_id)
        eligible, _, _, accepted_reviews = self.validate(epoch_id)
        task_by_hash = {task.task_hash: task for task in collected.tasks}
        graph = detect_candidate_conflicts(collected.tasks, collected.candidates, reviews=accepted_reviews)

        blocked_candidates: set[str] = set()
        conflict_refs: list[str] = []
        for edge in graph.conflicts:
            conflict_refs.append(f"{edge.conflict_class.value}:{edge.conflict_hash}")
            if edge.left in {candidate.candidate_hash for candidate in eligible}:
                blocked_candidates.add(edge.left)
            if edge.right in {candidate.candidate_hash for candidate in eligible}:
                blocked_candidates.add(edge.right)

        candidates_by_task: dict[str, list[FederatedCandidateReceipt]] = {}
        for candidate in eligible:
            if candidate.candidate_hash not in blocked_candidates:
                candidates_by_task.setdefault(candidate.task_hash, []).append(candidate)
        for task_hash, choices in candidates_by_task.items():
            if len(choices) > 1:
                ref = canonical_digest({"class": ConflictClass.SEMANTIC_DECISION_CONFLICT, "task_hash": task_hash,
                                        "candidates": tuple(sorted(c.candidate_hash for c in choices))})
                conflict_refs.append(f"{ConflictClass.SEMANTIC_DECISION_CONFLICT.value}:{ref}")
                blocked_candidates.update(c.candidate_hash for c in choices)

        candidate_by_task = {
            task_hash: choices[0]
            for task_hash, choices in candidates_by_task.items()
            if len(choices) == 1 and choices[0].candidate_hash not in blocked_candidates
        }
        nodes = set(candidate_by_task)
        ordering_edges = tuple(edge for edge in graph.ordering_edges if edge[0] in nodes and edge[1] in nodes)
        task_order, cyclic = self._lexical_topological_sort(nodes, ordering_edges)
        if cyclic:
            ref = canonical_digest({"class": ConflictClass.DEPENDENCY_VERSION_CONFLICT, "tasks": cyclic})
            conflict_refs.append(f"{ConflictClass.DEPENDENCY_VERSION_CONFLICT.value}:{ref}")
            task_order = tuple(task for task in task_order if task not in set(cyclic))
        order = tuple(candidate_by_task[task].candidate_hash for task in task_order)
        return order, tuple(sorted(set(conflict_refs)))

    def snapshot(self, epoch_id: str) -> SynchronizationSnapshot:
        epoch = self.store.get_epoch(epoch_id)
        if epoch is None:
            raise KeyError(epoch_id)
        eligible, rejected, stale, accepted_reviews = self.validate(epoch_id)
        order, conflict_refs = self.integration_order(epoch_id)
        required_verification_hashes = sorted(
            {value for candidate in eligible for value in candidate.verification_hashes}
            | {value for review in accepted_reviews for value in review.verification_hashes}
        )
        snapshot = SynchronizationSnapshot(
            epoch_id=epoch_id,
            base_checkpoint_id=epoch["base_checkpoint_id"],
            policy_hash=epoch["policy_hash"],
            catalog_hash=epoch["catalog_hash"],
            eligible_candidates=tuple(candidate.candidate_hash for candidate in eligible),
            rejected_candidates=rejected,
            stale_candidates=stale,
            conflict_refs=conflict_refs,
            integration_order=order,
            required_verification_hashes=tuple(required_verification_hashes),
        )
        self.store.put_snapshot(snapshot_hash=snapshot.snapshot_hash, epoch_id=epoch_id, payload=snapshot)
        return snapshot

    def recover(self, epoch_id: str) -> SynchronizationSnapshot:
        epoch = self.store.get_epoch(epoch_id)
        if epoch is None:
            raise KeyError(epoch_id)
        state = str(epoch["state"])
        if state in {"OPEN", "INTEGRATING"}:
            return self.snapshot(epoch_id)
        if state == "CLOSED":
            row = self.store.get_finalization(epoch_id)
            if row is None:
                raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")
            try:
                finalization = EpochFinalization.from_store_row(row)
            except ValueError as exc:
                if str(exc) == "FEDERATION_FINALIZATION_VERSION_UNSUPPORTED":
                    raise
                raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR") from exc
            return recover_from_cut(finalization)
        raise ValueError("FEDERATION_EPOCH_NOT_RECOVERABLE")
