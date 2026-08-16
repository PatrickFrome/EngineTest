from __future__ import annotations

import copy
import heapq
from dataclasses import dataclass
from typing import Any, Mapping

from metaengine.devfabric.codec import canonical_bytes, canonical_digest, to_primitive

from .contracts import require_hex64

FINALIZATION_PROTOCOL_VERSION = "D6.FINALIZATION.1"

_REQUIRED_TOP = {
    "cut_version",
    "epoch",
    "tasks",
    "assignments",
    "candidates",
    "reviews",
    "conflicts",
    "integration_decisions",
    "participant_witnesses",
    "terminal_snapshot",
}
_FORBIDDEN_KEY_PARTS = ("secret", "service_role", "password", "credential", "prompt", "conversation")
_SORT_KEYS: dict[str, Any] = {
    "tasks": lambda row: str(row["task_hash"]),
    "assignments": lambda row: str(row["assignment_id"]),
    "candidates": lambda row: str(row["candidate_hash"]),
    "reviews": lambda row: str(row["review_hash"]),
    "conflicts": lambda row: str(row["conflict_hash"]),
    "integration_decisions": lambda row: str(row["decision_hash"]),
    "participant_witnesses": lambda row: (str(row["slot_id"]), str(row["session_id"])),
}
_NESTED_SET_FIELDS = {
    "dependency_task_ids",
    "write_set",
    "interface_set",
    "review_slots",
    "verification_hashes",
    "eligible_candidates",
    "rejected_candidates",
    "stale_candidates",
    "conflict_refs",
    "required_verification_hashes",
}


def _scan_private(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError("FEDERATION_FINALIZATION_PRIVATE_FIELD_FORBIDDEN")
            if lowered == "privacy_class" and str(child).upper() == "P3":
                raise ValueError("FEDERATION_FINALIZATION_P3_FORBIDDEN")
            _scan_private(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _scan_private(child)


def _normalize_nested(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize_nested(v, key=str(k)) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        normalized = [_normalize_nested(item) for item in value]
        if key in _NESTED_SET_FIELDS:
            return sorted(normalized, key=canonical_bytes)
        return normalized
    return to_primitive(value)


def normalize_recovery_cut(cut: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(cut, Mapping) or set(cut) != _REQUIRED_TOP:
        raise ValueError("FEDERATION_FINALIZATION_CUT_SHAPE_INVALID")
    if cut.get("cut_version") != FINALIZATION_PROTOCOL_VERSION:
        raise ValueError("FEDERATION_FINALIZATION_VERSION_UNSUPPORTED")
    _scan_private(cut)

    normalized = _normalize_nested(copy.deepcopy(dict(cut)))
    for field, sort_key in _SORT_KEYS.items():
        rows = normalized[field]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("FEDERATION_FINALIZATION_CUT_SHAPE_INVALID")
        try:
            rows.sort(key=sort_key)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("FEDERATION_FINALIZATION_CUT_SHAPE_INVALID") from exc
    if not isinstance(normalized.get("epoch"), dict) or not isinstance(normalized.get("terminal_snapshot"), dict):
        raise ValueError("FEDERATION_FINALIZATION_CUT_SHAPE_INVALID")
    return normalized


def recovery_cut_hash(cut: Mapping[str, Any]) -> str:
    return canonical_digest(normalize_recovery_cut(cut))


def _active_witnesses(cut: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    witnesses: dict[str, Mapping[str, Any]] = {}
    for witness in cut["participant_witnesses"]:
        if bool(witness.get("revoked")) or witness.get("released_at") is not None:
            continue
        witnesses[str(witness["slot_id"])] = witness
    return witnesses


def _lexical_topological_sort(
    nodes: set[str], dependencies: Mapping[str, tuple[str, ...]]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    outgoing = {node: set() for node in nodes}
    indegree = {node: 0 for node in nodes}
    for node in nodes:
        for dependency in dependencies.get(node, ()):
            if dependency not in nodes or dependency == node:
                continue
            if node not in outgoing[dependency]:
                outgoing[dependency].add(node)
                indegree[node] += 1
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


def snapshot_payload_from_cut(cut: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_recovery_cut(cut)
    epoch = normalized["epoch"]
    tasks = {str(row["task_hash"]): row for row in normalized["tasks"]}
    witnesses = _active_witnesses(normalized)
    reviews = normalized["reviews"]

    eligible: list[Mapping[str, Any]] = []
    rejected: list[str] = []
    stale: list[str] = []
    accepted_reviews: list[Mapping[str, Any]] = []

    for candidate in normalized["candidates"]:
        candidate_hash = str(candidate["candidate_hash"])
        task = tasks.get(str(candidate["task_hash"]))
        if task is None or int(candidate.get("task_version", -1)) != int(task.get("task_version", -2)):
            stale.append(candidate_hash)
            continue
        if str(candidate.get("eligibility")) in {"STALE_FENCED", "STALE_TASK_VERSION"}:
            stale.append(candidate_hash)
            continue
        if str(candidate.get("eligibility")) != "ELIGIBLE":
            rejected.append(candidate_hash)
            continue

        owner_slot = str(task["owner_slot"])
        owner = witnesses.get(owner_slot)
        if (
            owner is None
            or str(owner.get("session_id")) != str(candidate.get("session_id"))
            or int(owner.get("lease_generation", -1)) != int(candidate.get("lease_generation", -2))
            or str(owner.get("role_profile_hash")) != str(candidate.get("role_profile_hash"))
        ):
            stale.append(candidate_hash)
            continue

        candidate_reviews: list[Mapping[str, Any]] = []
        review_ok = True
        for required_slot in task.get("review_slots", []):
            reviewer = witnesses.get(str(required_slot))
            valid = None
            for review in reviews:
                if str(review.get("candidate_hash")) != candidate_hash or str(review.get("reviewer_slot")) != str(required_slot):
                    continue
                if str(review.get("verdict")) != "PASS" or reviewer is None:
                    continue
                if (
                    str(reviewer.get("session_id")) == str(review.get("session_id"))
                    and int(reviewer.get("lease_generation", -1)) == int(review.get("lease_generation", -2))
                    and str(reviewer.get("role_profile_hash")) == str(review.get("reviewer_role_profile_hash"))
                    and str(review.get("session_id")) != str(candidate.get("session_id"))
                ):
                    valid = review
                    break
            if valid is None:
                review_ok = False
                break
            candidate_reviews.append(valid)
        if not review_ok:
            rejected.append(candidate_hash)
            continue
        eligible.append(candidate)
        accepted_reviews.extend(candidate_reviews)

    eligible_hashes = {str(row["candidate_hash"]) for row in eligible}

    blocked: set[str] = set()
    conflict_refs: list[str] = []
    for conflict in normalized["conflicts"]:
        if bool(conflict.get("resolved")):
            continue
        conflict_hash = str(conflict["conflict_hash"])
        conflict_class = str(conflict.get("conflict_class", "UNKNOWN"))
        conflict_refs.append(f"{conflict_class}:{conflict_hash}")
        for ref_key in ("left_ref", "right_ref"):
            ref = str(conflict.get(ref_key, ""))
            if ref in eligible_hashes:
                blocked.add(ref)

    decision_by_candidate: dict[str, str] = {}
    for decision in normalized["integration_decisions"]:
        candidate_hash = decision.get("candidate_hash")
        if candidate_hash is not None:
            decision_by_candidate[str(candidate_hash)] = str(decision.get("decision"))

    choices_by_task: dict[str, list[str]] = {}
    for candidate in eligible:
        candidate_hash = str(candidate["candidate_hash"])
        if candidate_hash in blocked or decision_by_candidate.get(candidate_hash) != "INCLUDE":
            continue
        choices_by_task.setdefault(str(candidate["task_hash"]), []).append(candidate_hash)

    candidate_by_task: dict[str, str] = {}
    for task_hash, choices in choices_by_task.items():
        unique = tuple(sorted(set(choices)))
        if len(unique) == 1:
            candidate_by_task[task_hash] = unique[0]
            continue
        ref = canonical_digest(
            {"class": "SEMANTIC_DECISION_CONFLICT", "task_hash": task_hash, "candidates": unique}
        )
        conflict_refs.append(f"SEMANTIC_DECISION_CONFLICT:{ref}")

    base_task_to_hash = {
        str(task.get("base_task_id")): task_hash
        for task_hash, task in tasks.items()
        if task.get("base_task_id")
    }
    dependencies = {
        task_hash: tuple(
            base_task_to_hash.get(str(dep), str(dep)) for dep in task.get("dependency_task_ids", [])
        )
        for task_hash, task in tasks.items()
    }
    task_order, cyclic = _lexical_topological_sort(set(candidate_by_task), dependencies)
    if cyclic:
        ref = canonical_digest({"class": "DEPENDENCY_VERSION_CONFLICT", "tasks": cyclic})
        conflict_refs.append(f"DEPENDENCY_VERSION_CONFLICT:{ref}")
        blocked_tasks = set(cyclic)
        task_order = tuple(task for task in task_order if task not in blocked_tasks)
    integration_order = tuple(candidate_by_task[task_hash] for task_hash in task_order)

    verification_hashes = {
        str(value)
        for candidate in eligible
        for value in candidate.get("verification_hashes", [])
    }
    verification_hashes.update(
        str(value)
        for review in accepted_reviews
        for value in review.get("verification_hashes", [])
    )

    return {
        "epoch_id": str(epoch["epoch_id"]),
        "base_checkpoint_id": str(epoch["base_checkpoint_id"]),
        "policy_hash": str(epoch["federation_policy_hash"]),
        "catalog_hash": str(epoch["role_catalog_hash"]),
        "eligible_candidates": tuple(sorted(eligible_hashes)),
        "rejected_candidates": tuple(sorted(set(rejected))),
        "stale_candidates": tuple(sorted(set(stale))),
        "conflict_refs": tuple(sorted(set(conflict_refs))),
        "integration_order": integration_order,
        "required_verification_hashes": tuple(sorted(verification_hashes)),
    }


@dataclass(frozen=True)
class EpochFinalization:
    finalization_hash: str
    epoch_id: str
    final_snapshot_hash: str
    recovery_cut_hash: str
    recovery_cut: Mapping[str, Any]
    finalized_by_session_id: str
    finalized_by_generation: int
    protocol_version: str

    @classmethod
    def create(
        cls,
        *,
        epoch_id: str,
        final_snapshot_hash: str,
        recovery_cut_hash: str,
        recovery_cut: Mapping[str, Any],
        finalized_by_session_id: str,
        finalized_by_generation: int,
        protocol_version: str = FINALIZATION_PROTOCOL_VERSION,
    ) -> "EpochFinalization":
        if protocol_version != FINALIZATION_PROTOCOL_VERSION:
            raise ValueError("FEDERATION_FINALIZATION_VERSION_UNSUPPORTED")
        if not epoch_id or not finalized_by_session_id:
            raise ValueError("FEDERATION_FINALIZATION_IDENTITY_INVALID")
        if int(finalized_by_generation) < 0:
            raise ValueError("FEDERATION_FINALIZATION_GENERATION_INVALID")
        require_hex64("final_snapshot_hash", str(final_snapshot_hash))
        require_hex64("recovery_cut_hash", str(recovery_cut_hash))

        normalized = normalize_recovery_cut(recovery_cut)
        actual_cut_hash = canonical_digest(normalized)
        if actual_cut_hash != recovery_cut_hash:
            raise ValueError("FEDERATION_FINALIZATION_CUT_HASH_MISMATCH")
        if str(normalized["epoch"].get("epoch_id")) != str(epoch_id):
            raise ValueError("FEDERATION_FINALIZATION_EPOCH_MISMATCH")
        terminal = normalized["terminal_snapshot"]
        if str(terminal.get("snapshot_hash")) != str(final_snapshot_hash):
            raise ValueError("FEDERATION_FINAL_SNAPSHOT_INVALID")
        snapshot = terminal.get("snapshot")
        if not isinstance(snapshot, Mapping) or canonical_digest(snapshot) != final_snapshot_hash:
            raise ValueError("FEDERATION_FINAL_SNAPSHOT_INVALID")
        if canonical_digest(snapshot_payload_from_cut(normalized)) != final_snapshot_hash:
            raise ValueError("FEDERATION_FINALIZATION_CUT_SNAPSHOT_MISMATCH")

        finalization_hash = canonical_digest(
            {
                "epoch_id": str(epoch_id),
                "final_snapshot_hash": str(final_snapshot_hash),
                "recovery_cut_hash": str(recovery_cut_hash),
                "finalized_by_session_id": str(finalized_by_session_id),
                "finalized_by_generation": int(finalized_by_generation),
                "protocol_version": str(protocol_version),
            }
        )
        return cls(
            finalization_hash=finalization_hash,
            epoch_id=str(epoch_id),
            final_snapshot_hash=str(final_snapshot_hash),
            recovery_cut_hash=str(recovery_cut_hash),
            recovery_cut=normalized,
            finalized_by_session_id=str(finalized_by_session_id),
            finalized_by_generation=int(finalized_by_generation),
            protocol_version=str(protocol_version),
        )

    @classmethod
    def from_store_row(cls, row: Mapping[str, Any]) -> "EpochFinalization":
        finalization = cls.create(
            epoch_id=str(row["epoch_id"]),
            final_snapshot_hash=str(row["final_snapshot_hash"]),
            recovery_cut_hash=str(row["recovery_cut_hash"]),
            recovery_cut=row["recovery_cut"],
            finalized_by_session_id=str(row["finalized_by_session_id"]),
            finalized_by_generation=int(row["finalized_by_generation"]),
            protocol_version=str(row["protocol_version"]),
        )
        if str(row["finalization_hash"]) != finalization.finalization_hash:
            raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")
        return finalization
