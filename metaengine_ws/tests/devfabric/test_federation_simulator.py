from __future__ import annotations

import sqlite3

import pytest

from metaengine.devfabric.federation.store import FederationStore
from metaengine.devfabric.federation.types import SlotId


def test_store_allows_only_one_active_session_per_epoch_slot(tmp_path):
    store = FederationStore(tmp_path / "federation.sqlite3")
    store.put_epoch(epoch_id="e1", base_checkpoint_id="cp1", policy_hash="a" * 64, catalog_hash="b" * 64)
    store.put_session(
        session_id="session-1",
        epoch_id="e1",
        slot_id=SlotId.C2,
        lease_generation=1,
        capsule_sha256="c" * 64,
        protocol_version="D6.1",
        role_profile_hash="d" * 64,
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.put_session(
            session_id="session-2",
            epoch_id="e1",
            slot_id=SlotId.C2,
            lease_generation=2,
            capsule_sha256="c" * 64,
            protocol_version="D6.1",
            role_profile_hash="d" * 64,
        )
    active = store.active_session_for_slot("e1", SlotId.C2)
    assert active is not None
    assert active["session_id"] == "session-1"
    assert active["lease_generation"] == 1


def test_store_enables_wal_and_foreign_keys(tmp_path):
    store = FederationStore(tmp_path / "federation.sqlite3")
    assert store.connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert store.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

from metaengine.devfabric.federation.contracts import FederatedCandidateReceipt, FederatedTaskEnvelope
from metaengine.devfabric.federation.simulator import FederationSimulator
from metaengine.devfabric.federation.types import CandidateEligibility, IntegrationMode
from metaengine.devfabric.models import CandidateReceipt, PrivacyClass, RiskClass, TaskEnvelope


def _base_task(checkpoint: str = "cp1") -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id=checkpoint,
        source_tree_hash="1" * 64,
        objective="federation change",
        acceptance_tests=("pytest",),
        allowed_paths=("metaengine/",),
        forbidden_paths=("lineages/",),
        capabilities_required=("python",),
        risk_class=RiskClass.NORMAL,
        privacy_class=PrivacyClass.P1,
    )


def _federated_task(*, generation: int, slot: SlotId = SlotId.C3, version: int = 1) -> FederatedTaskEnvelope:
    base = _base_task()
    return FederatedTaskEnvelope.create(
        base_task=base,
        epoch_id="e1",
        task_version=version,
        owner_slot=slot,
        lease_generation=generation,
        role_profile_hash="d" * 64,
        base_checkpoint_id="cp1",
        dependency_task_ids=(),
        read_set=("metaengine/",),
        write_set=("metaengine/swarm.py",),
        interface_set=("swarm-v1",),
        integration_mode=IntegrationMode.EXCLUSIVE,
        review_slots=(),
    )


def _federated_candidate(task: FederatedTaskEnvelope, session_id: str) -> FederatedCandidateReceipt:
    base = CandidateReceipt.create(
        task_id=task.base_task.task_id,
        provider_id="local",
        base_tree_hash="2" * 64,
        patch_hash="3" * 64,
        changed_paths=("metaengine/swarm.py",),
    )
    return FederatedCandidateReceipt.create(
        base_candidate=base,
        task=task,
        slot_id=task.owner_slot,
        session_id=session_id,
        lease_generation=task.lease_generation,
        patch_digest=base.patch_hash,
        interface_changes=("swarm-v1",),
        verification_hashes=("4" * 64,),
        claims=("deterministic",),
        risks=(),
        dependency_observations=(),
        summary="candidate",
    )


def _sim(tmp_path) -> FederationSimulator:
    store = FederationStore(tmp_path / "federation.sqlite3")
    store.put_epoch(epoch_id="e1", base_checkpoint_id="cp1", policy_hash="a" * 64, catalog_hash="b" * 64)
    return FederationSimulator(store)


def test_release_then_reregister_increments_generation_and_old_candidate_is_stale_fenced(tmp_path):
    sim = _sim(tmp_path)
    first = sim.register(
        epoch_id="e1", requested_slot=SlotId.C3, capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="d" * 64, registration_nonce="n1"
    )
    task = _federated_task(generation=first.lease_generation)
    sim.publish_task(task)
    old = _federated_candidate(task, first.session_id)
    assert sim.release(first.session_id, expected_generation=first.lease_generation)
    second = sim.register(
        epoch_id="e1", requested_slot=SlotId.C3, capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="d" * 64, registration_nonce="n2"
    )
    assert second.lease_generation == first.lease_generation + 1
    result = sim.submit_candidate(old)
    assert result.eligibility is CandidateEligibility.STALE_FENCED
    assert sim.store.candidate_row(old.candidate_hash)["eligibility"] == CandidateEligibility.STALE_FENCED.value


def test_reclaim_revokes_current_owner_and_fences_late_result(tmp_path):
    sim = _sim(tmp_path)
    first = sim.register(
        epoch_id="e1", requested_slot=SlotId.C2, capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="d" * 64, registration_nonce="a"
    )
    task = _federated_task(generation=first.lease_generation, slot=SlotId.C2)
    sim.publish_task(task)
    old = _federated_candidate(task, first.session_id)
    second = sim.reclaim(
        epoch_id="e1", slot_id=SlotId.C2, capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="d" * 64, registration_nonce="b",
        expected_generation=first.lease_generation,
    )
    assert second.lease_generation == 2
    assert sim.submit_candidate(old).eligibility is CandidateEligibility.STALE_FENCED


def test_auto_assignment_is_deterministic_and_skips_occupied_slots(tmp_path):
    sim = _sim(tmp_path)
    first = sim.register(
        epoch_id="e1", requested_slot="AUTO", capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="d" * 64, registration_nonce="a"
    )
    second = sim.register(
        epoch_id="e1", requested_slot="AUTO", capsule_sha256="c" * 64,
        protocol_version="D6.1", role_profile_hash="e" * 64, registration_nonce="b"
    )
    assert first.slot_id is SlotId.C0
    assert second.slot_id is SlotId.C1
    assert first.session_id == sim.session_id_for(
        epoch_id="e1", slot_id=SlotId.C0, lease_generation=1,
        capsule_sha256="c" * 64, protocol_version="D6.1", registration_nonce="a"
    )
