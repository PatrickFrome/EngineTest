from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.federation.finalization import (
    FINALIZATION_PROTOCOL_VERSION,
    EpochFinalization,
    normalize_recovery_cut,
    recovery_cut_hash,
    snapshot_payload_from_cut,
)


def sample_cut(*, reverse: bool = False) -> dict:
    tasks = [
        {
            "task_hash": "1" * 64,
            "task_version": 1,
            "owner_slot": "C2",
            "lease_generation": 1,
            "role_profile_hash": "a" * 64,
            "dependency_task_ids": [],
            "write_set": ["docs/c2.md"],
            "interface_set": ["core-v1"],
            "risk_class": "HIGH",
            "review_slots": ["C6"],
        },
        {
            "task_hash": "2" * 64,
            "task_version": 1,
            "owner_slot": "C4",
            "lease_generation": 1,
            "role_profile_hash": "b" * 64,
            "dependency_task_ids": [],
            "write_set": ["docs/c4.md"],
            "interface_set": ["edge-v1"],
            "risk_class": "NORMAL",
            "review_slots": [],
        },
    ]
    assignments = [
        {"assignment_id": "assign-b", "task_hash": "2" * 64, "assignment_state": "COMPLETED", "lease_generation": 1},
        {"assignment_id": "assign-a", "task_hash": "1" * 64, "assignment_state": "COMPLETED", "lease_generation": 1},
    ]
    candidates = [
        {
            "candidate_hash": "d" * 64,
            "task_hash": "2" * 64,
            "session_id": "session-c4",
            "lease_generation": 1,
            "role_profile_hash": "b" * 64,
            "task_version": 1,
            "eligibility": "ELIGIBLE",
            "verification_hashes": [],
            "privacy_class": "P1",
        },
        {
            "candidate_hash": "c" * 64,
            "task_hash": "1" * 64,
            "session_id": "session-c2",
            "lease_generation": 1,
            "role_profile_hash": "a" * 64,
            "task_version": 1,
            "eligibility": "ELIGIBLE",
            "verification_hashes": ["7" * 64],
            "privacy_class": "P1",
        },
    ]
    reviews = [
        {
            "review_hash": "e" * 64,
            "candidate_hash": "c" * 64,
            "reviewer_slot": "C6",
            "session_id": "session-c6",
            "lease_generation": 1,
            "reviewer_role_profile_hash": "6" * 64,
            "verdict": "PASS",
            "verification_hashes": ["8" * 64],
            "privacy_class": "P1",
        }
    ]
    conflicts = [
        {"conflict_hash": "f" * 64, "conflict_class": "PATH_WRITE_CONFLICT", "resolved": True, "left_ref": "x", "right_ref": "y"}
    ]
    decisions = [
        {"decision_hash": "9" * 64, "candidate_hash": "c" * 64, "decision": "INCLUDE"},
        {"decision_hash": "0" * 64, "candidate_hash": "d" * 64, "decision": "INCLUDE"},
    ]
    witnesses = [
        {
            "slot_id": "C6",
            "session_id": "session-c6",
            "lease_generation": 1,
            "role_profile_hash": "6" * 64,
            "revoked": False,
            "released_at": None,
        },
        {
            "slot_id": "C4",
            "session_id": "session-c4",
            "lease_generation": 1,
            "role_profile_hash": "b" * 64,
            "revoked": False,
            "released_at": None,
        },
        {
            "slot_id": "C2",
            "session_id": "session-c2",
            "lease_generation": 1,
            "role_profile_hash": "a" * 64,
            "revoked": False,
            "released_at": None,
        },
    ]

    if reverse:
        for value in (tasks, assignments, candidates, reviews, conflicts, decisions, witnesses):
            value.reverse()

    snapshot = {
        "epoch_id": "epoch-final-1",
        "base_checkpoint_id": "cp001",
        "policy_hash": "3" * 64,
        "catalog_hash": "4" * 64,
        "eligible_candidates": ["c" * 64, "d" * 64],
        "rejected_candidates": [],
        "stale_candidates": [],
        "conflict_refs": [],
        "integration_order": ["c" * 64, "d" * 64],
        "required_verification_hashes": ["7" * 64, "8" * 64],
    }
    terminal_snapshot = {"snapshot_hash": canonical_digest(snapshot), "snapshot": snapshot}
    return {
        "cut_version": "D6.FINALIZATION.1",
        "epoch": {
            "epoch_id": "epoch-final-1",
            "base_checkpoint_id": "cp001",
            "base_payload_root": "5" * 64,
            "federation_policy_hash": "3" * 64,
            "role_catalog_hash": "4" * 64,
            "producer_concurrency": 2,
        },
        "tasks": tasks,
        "assignments": assignments,
        "candidates": candidates,
        "reviews": reviews,
        "conflicts": conflicts,
        "integration_decisions": decisions,
        "participant_witnesses": witnesses,
        "terminal_snapshot": terminal_snapshot,
    }


def test_recovery_cut_normalizes_all_semantic_arrays_before_hashing():
    left = sample_cut(reverse=False)
    right = sample_cut(reverse=True)
    assert FINALIZATION_PROTOCOL_VERSION == "D6.FINALIZATION.1"
    assert normalize_recovery_cut(left) == normalize_recovery_cut(right)
    assert recovery_cut_hash(left) == recovery_cut_hash(right)

    normalized = normalize_recovery_cut(left)
    assert [row["task_hash"] for row in normalized["tasks"]] == sorted(row["task_hash"] for row in left["tasks"])
    assert [row["assignment_id"] for row in normalized["assignments"]] == ["assign-a", "assign-b"]
    assert [row["candidate_hash"] for row in normalized["candidates"]] == sorted(row["candidate_hash"] for row in left["candidates"])
    assert [row["review_hash"] for row in normalized["reviews"]] == sorted(row["review_hash"] for row in left["reviews"])
    assert [row["conflict_hash"] for row in normalized["conflicts"]] == sorted(row["conflict_hash"] for row in left["conflicts"])
    assert [row["decision_hash"] for row in normalized["integration_decisions"]] == sorted(row["decision_hash"] for row in left["integration_decisions"])
    assert [(row["slot_id"], row["session_id"]) for row in normalized["participant_witnesses"]] == [
        ("C2", "session-c2"), ("C4", "session-c4"), ("C6", "session-c6")
    ]


@pytest.mark.parametrize("bad_key", ["secret", "service_role_key", "password", "credential_value", "prompt_text", "conversation_id"])
def test_recovery_cut_rejects_secret_or_conversation_keys_recursively(bad_key: str):
    cut = sample_cut()
    cut["candidates"][0][bad_key] = "forbidden"
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_PRIVATE_FIELD_FORBIDDEN"):
        normalize_recovery_cut(cut)


def test_recovery_cut_rejects_p3_and_wrong_top_level_shape_or_version():
    p3 = sample_cut()
    p3["candidates"][0]["privacy_class"] = "P3"
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_P3_FORBIDDEN"):
        normalize_recovery_cut(p3)

    extra = sample_cut()
    extra["extra"] = []
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CUT_SHAPE_INVALID"):
        normalize_recovery_cut(extra)

    bad_version = sample_cut()
    bad_version["cut_version"] = "D6.FINALIZATION.999"
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_VERSION_UNSUPPORTED"):
        normalize_recovery_cut(bad_version)


def test_snapshot_payload_from_cut_uses_frozen_witnesses_and_required_reviews():
    cut = sample_cut()
    expected = dict(cut["terminal_snapshot"]["snapshot"])
    for field in (
        "eligible_candidates", "rejected_candidates", "stale_candidates", "conflict_refs",
        "integration_order", "required_verification_hashes",
    ):
        expected[field] = tuple(expected[field])
    assert snapshot_payload_from_cut(cut) == expected

    # Freeze a reviewer as released: HIGH candidate must no longer be eligible.
    released = sample_cut()
    c6 = next(row for row in released["participant_witnesses"] if row["slot_id"] == "C6")
    c6["released_at"] = "RELEASED"
    payload = snapshot_payload_from_cut(released)
    assert payload["eligible_candidates"] == ("d" * 64,)
    assert payload["rejected_candidates"] == ("c" * 64,)
    assert payload["integration_order"] == ("d" * 64,)
    assert payload["required_verification_hashes"] == ()


def test_epoch_finalization_is_frozen_content_addressed_and_strict():
    cut = sample_cut()
    cut_hash = recovery_cut_hash(cut)
    final_snapshot_hash = cut["terminal_snapshot"]["snapshot_hash"]
    finalization = EpochFinalization.create(
        epoch_id="epoch-final-1",
        final_snapshot_hash=final_snapshot_hash,
        recovery_cut_hash=cut_hash,
        recovery_cut=cut,
        finalized_by_session_id="session-c0-g2",
        finalized_by_generation=2,
        protocol_version=FINALIZATION_PROTOCOL_VERSION,
    )
    assert finalization.recovery_cut_hash == canonical_digest(normalize_recovery_cut(cut))
    assert finalization.finalization_hash == canonical_digest(
        {
            "epoch_id": "epoch-final-1",
            "final_snapshot_hash": final_snapshot_hash,
            "recovery_cut_hash": cut_hash,
            "finalized_by_session_id": "session-c0-g2",
            "finalized_by_generation": 2,
            "protocol_version": FINALIZATION_PROTOCOL_VERSION,
        }
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        finalization.epoch_id = "other"  # type: ignore[misc]

    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CUT_HASH_MISMATCH"):
        EpochFinalization.create(
            epoch_id="epoch-final-1",
            final_snapshot_hash=final_snapshot_hash,
            recovery_cut_hash="0" * 64,
            recovery_cut=cut,
            finalized_by_session_id="session-c0-g2",
            finalized_by_generation=2,
            protocol_version=FINALIZATION_PROTOCOL_VERSION,
        )


def _make_finalization_for_store() -> EpochFinalization:
    cut = sample_cut()
    return EpochFinalization.create(
        epoch_id="epoch-final-1",
        final_snapshot_hash=cut["terminal_snapshot"]["snapshot_hash"],
        recovery_cut_hash=recovery_cut_hash(cut),
        recovery_cut=cut,
        finalized_by_session_id="session-c0-g2",
        finalized_by_generation=2,
    )


def test_store_persists_finalization_idempotently_and_rejects_conflict(tmp_path):
    from metaengine.devfabric.federation.store import FederationStore

    store = FederationStore(tmp_path / "federation.sqlite3")
    store.put_epoch(
        epoch_id="epoch-final-1", base_checkpoint_id="cp001", policy_hash="3" * 64, catalog_hash="4" * 64
    )
    finalization = _make_finalization_for_store()
    store.put_session(
        session_id="session-c0-g2", epoch_id="epoch-final-1", slot_id=__import__(
            "metaengine.devfabric.federation.types", fromlist=["SlotId"]
        ).SlotId.C0, lease_generation=2, capsule_sha256="5" * 64,
        protocol_version="D6.1", role_profile_hash="0" * 64,
    )
    store.put_snapshot(
        snapshot_hash=finalization.final_snapshot_hash,
        epoch_id="epoch-final-1",
        payload=finalization.recovery_cut["terminal_snapshot"]["snapshot"],
    )
    assert store.put_finalization(finalization) is True
    assert store.put_finalization(finalization) is False
    row = store.get_finalization("epoch-final-1")
    assert row is not None
    assert row["finalization_hash"] == finalization.finalization_hash
    assert row["recovery_cut"] == normalize_recovery_cut(finalization.recovery_cut)
    assert not hasattr(store, "update_finalization")
    assert not hasattr(store, "delete_finalization")

    conflict = dataclasses.replace(finalization, finalization_hash="f" * 64)
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CONFLICT"):
        store.put_finalization(conflict)


def test_close_epoch_atomically_persists_terminal_evidence_and_releases_witnesses(tmp_path):
    from metaengine.devfabric.federation.store import FederationStore
    from metaengine.devfabric.federation.types import SlotId

    store = FederationStore(tmp_path / "federation.sqlite3")
    store.put_epoch(
        epoch_id="epoch-final-1", base_checkpoint_id="cp001", policy_hash="3" * 64, catalog_hash="4" * 64
    )
    for slot, session_id, generation, profile in (
        (SlotId.C0, "session-c0-g2", 2, "0" * 64),
        (SlotId.C2, "session-c2", 1, "a" * 64),
        (SlotId.C4, "session-c4", 1, "b" * 64),
        (SlotId.C6, "session-c6", 1, "6" * 64),
    ):
        store.put_session(
            session_id=session_id,
            epoch_id="epoch-final-1",
            slot_id=slot,
            lease_generation=generation,
            capsule_sha256="5" * 64,
            protocol_version="D6.1",
            role_profile_hash=profile,
        )

    for task_hash, owner, generation, session_id in (
        ("1" * 64, SlotId.C2, 1, "session-c2"),
        ("2" * 64, SlotId.C4, 1, "session-c4"),
    ):
        @dataclasses.dataclass(frozen=True)
        class StoredTask:
            task_hash: str
            epoch_id: str
            task_version: int
            owner_slot: SlotId
            lease_generation: int

        task = StoredTask(
            task_hash=task_hash,
            epoch_id="epoch-final-1",
            task_version=1,
            owner_slot=owner,
            lease_generation=generation,
        )
        store.put_task(task)
        store.put_assignment(task_hash=task_hash, session_id=session_id, lease_generation=generation)

    finalization = _make_finalization_for_store()
    store.put_snapshot(
        snapshot_hash=finalization.final_snapshot_hash,
        epoch_id="epoch-final-1",
        payload=finalization.recovery_cut["terminal_snapshot"]["snapshot"],
    )
    store.close_epoch("epoch-final-1", finalization=finalization)

    assert store.get_epoch("epoch-final-1")["state"] == "CLOSED"
    assert all(row["released_at"] == "RELEASED" and row["revoked"] == 1 for row in store.list_session_rows("epoch-final-1"))
    assert all(row["assignment_state"] != "CLAIMED" for row in store.list_assignment_rows("epoch-final-1"))
    assert store.get_finalization("epoch-final-1")["finalization_hash"] == finalization.finalization_hash


def test_portable_finalization_protocol_matches_runtime_constant() -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "chat_federation" / "FINALIZATION_PROTOCOL.json").read_text(encoding="utf-8"))
    assert payload["protocol_version"] == FINALIZATION_PROTOCOL_VERSION
    assert payload["chat_facing"] is False
    assert payload["closed_recovery_source"] == "IMMUTABLE_RECOVERY_CUT"
    assert payload["adaptation_eligible_state"] == "CLOSED"
