from __future__ import annotations

import dataclasses

import pytest

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.federation.contracts import FederatedCandidateReceipt, FederatedReviewReceipt, FederatedTaskEnvelope
from metaengine.devfabric.federation.simulator import FederationSimulator
from metaengine.devfabric.federation.store import FederationStore
from metaengine.devfabric.federation.finalization import (
    FINALIZATION_PROTOCOL_VERSION,
    EpochFinalization,
    recovery_cut_hash,
)
from metaengine.devfabric.federation.synchronizer import Synchronizer, build_recovery_cut, recover_from_cut
from metaengine.devfabric.federation.types import CandidateEligibility, IntegrationMode, SlotId
from metaengine.devfabric.models import CandidateReceipt, PrivacyClass, RiskClass, TaskEnvelope, Verdict


def base_task(name: str, *, risk=RiskClass.NORMAL):
    return TaskEnvelope.create(
        source_checkpoint_id="cp1", source_tree_hash=(name[0] * 64), objective=name,
        acceptance_tests=("pytest",), allowed_paths=("metaengine/",), forbidden_paths=("lineages/",),
        capabilities_required=("python",), risk_class=risk, privacy_class=PrivacyClass.P1,
    )


def fed_task(base, *, slot, generation, profile, write, deps=(), reviews=()):
    return FederatedTaskEnvelope.create(
        base_task=base, epoch_id="e1", task_version=1, owner_slot=slot, lease_generation=generation,
        role_profile_hash=profile, base_checkpoint_id="cp1", dependency_task_ids=deps,
        read_set=(), write_set=(write,), interface_set=(), integration_mode=IntegrationMode.PARALLEL,
        review_slots=reviews,
    )


def candidate(task, session_id, patch):
    base = CandidateReceipt.create(
        task_id=task.base_task.task_id, provider_id="local", base_tree_hash="f" * 64,
        patch_hash=patch * 64, changed_paths=task.write_set,
    )
    return FederatedCandidateReceipt.create(
        base_candidate=base, task=task, slot_id=task.owner_slot, session_id=session_id,
        lease_generation=task.lease_generation, patch_digest=base.patch_hash,
        interface_changes=(), verification_hashes=("e" * 64,), claims=(), risks=(),
        dependency_observations=(), summary="candidate",
    )


def setup(tmp_path):
    store = FederationStore(tmp_path / "federation.sqlite3")
    store.put_epoch(epoch_id="e1", base_checkpoint_id="cp1", policy_hash="a" * 64, catalog_hash="b" * 64)
    return store, FederationSimulator(store)


def register(sim, slot, profile, nonce):
    return sim.register(
        epoch_id="e1", requested_slot=slot, capsule_sha256="c" * 64, protocol_version="D6.1",
        role_profile_hash=profile, registration_nonce=nonce,
    )


def test_same_ledger_state_recovers_identical_snapshot_after_c0_replacement(tmp_path):
    store, sim = setup(tmp_path)
    c2 = register(sim, SlotId.C2, "2" * 64, "c2")
    c3 = register(sim, SlotId.C3, "3" * 64, "c3")
    t2 = fed_task(base_task("core"), slot=SlotId.C2, generation=c2.lease_generation, profile="2" * 64, write="core.py")
    t3 = fed_task(base_task("swarm"), slot=SlotId.C3, generation=c3.lease_generation, profile="3" * 64, write="swarm.py")
    sim.publish_task(t3)
    sim.publish_task(t2)
    sim.submit_candidate(candidate(t3, c3.session_id, "7"))
    sim.submit_candidate(candidate(t2, c2.session_id, "6"))

    first = Synchronizer(store).snapshot("e1")
    recovered = Synchronizer(store).recover("e1")
    assert first.snapshot_hash == recovered.snapshot_hash
    assert first.integration_order == recovered.integration_order
    assert len(first.eligible_candidates) == 2


def test_high_risk_candidate_requires_current_independent_c6_review(tmp_path):
    store, sim = setup(tmp_path)
    c2 = register(sim, SlotId.C2, "2" * 64, "c2")
    c6 = register(sim, SlotId.C6, "6" * 64, "c6")
    task = fed_task(
        base_task("critical", risk=RiskClass.HIGH), slot=SlotId.C2, generation=c2.lease_generation,
        profile="2" * 64, write="critical.py", reviews=(SlotId.C6,),
    )
    sim.publish_task(task)
    cand = candidate(task, c2.session_id, "8")
    assert sim.submit_candidate(cand).eligibility is CandidateEligibility.ELIGIBLE

    missing = Synchronizer(store).snapshot("e1")
    assert cand.candidate_hash in missing.rejected_candidates
    assert cand.candidate_hash not in missing.integration_order

    review = FederatedReviewReceipt.create(
        candidate_hash=cand.candidate_hash, reviewer_slot=SlotId.C6, session_id=c6.session_id,
        lease_generation=c6.lease_generation, reviewer_role_profile_hash="6" * 64,
        verification_hashes=("9" * 64,), verdict=Verdict.PASS,
    )
    store.put_review(review)
    accepted = Synchronizer(store).snapshot("e1")
    assert cand.candidate_hash in accepted.eligible_candidates
    assert cand.candidate_hash in accepted.integration_order

    sim.reclaim(
        epoch_id="e1", slot_id=SlotId.C6, capsule_sha256="c" * 64, protocol_version="D6.1",
        role_profile_hash="6" * 64, registration_nonce="c6-new", expected_generation=c6.lease_generation,
    )
    stale_review = Synchronizer(store).snapshot("e1")
    assert cand.candidate_hash in stale_review.rejected_candidates


def test_dependency_cycle_is_not_silently_ordered(tmp_path):
    store, sim = setup(tmp_path)
    c2 = register(sim, SlotId.C2, "2" * 64, "c2")
    c3 = register(sim, SlotId.C3, "3" * 64, "c3")
    b2, b3 = base_task("alpha"), base_task("beta")
    t2 = fed_task(b2, slot=SlotId.C2, generation=c2.lease_generation, profile="2" * 64, write="a.py", deps=(b3.task_id,))
    t3 = fed_task(b3, slot=SlotId.C3, generation=c3.lease_generation, profile="3" * 64, write="b.py", deps=(b2.task_id,))
    sim.publish_task(t2); sim.publish_task(t3)
    c2r, c3r = candidate(t2, c2.session_id, "6"), candidate(t3, c3.session_id, "7")
    sim.submit_candidate(c2r); sim.submit_candidate(c3r)
    snap = Synchronizer(store).snapshot("e1")
    assert c2r.candidate_hash not in snap.integration_order
    assert c3r.candidate_hash not in snap.integration_order
    assert any("DEPENDENCY" in item for item in snap.conflict_refs)



def test_closed_epoch_recovery_is_independent_of_live_session_witnesses(tmp_path):
    store, sim = setup(tmp_path)
    c0 = register(sim, SlotId.C0, "0" * 64, "c0")
    c2 = register(sim, SlotId.C2, "2" * 64, "c2")
    c3 = register(sim, SlotId.C3, "3" * 64, "c3")
    t2 = fed_task(base_task("core"), slot=SlotId.C2, generation=c2.lease_generation, profile="2" * 64, write="core.py")
    t3 = fed_task(base_task("swarm"), slot=SlotId.C3, generation=c3.lease_generation, profile="3" * 64, write="swarm.py")
    sim.publish_task(t2)
    sim.publish_task(t3)
    c2r = candidate(t2, c2.session_id, "6")
    c3r = candidate(t3, c3.session_id, "7")
    sim.submit_candidate(c2r)
    sim.submit_candidate(c3r)

    before = Synchronizer(store).snapshot("e1")
    for receipt in (c2r, c3r):
        store.put_integration_decision(
            decision_hash=canonical_digest({"candidate": receipt.candidate_hash, "decision": "INCLUDE"}),
            epoch_id="e1",
            candidate_hash=receipt.candidate_hash,
            decision="INCLUDE",
            reason="test",
        )
    cut = build_recovery_cut(store, "e1", before.snapshot_hash)
    finalization = EpochFinalization.create(
        epoch_id="e1",
        final_snapshot_hash=before.snapshot_hash,
        recovery_cut_hash=recovery_cut_hash(cut),
        recovery_cut=cut,
        finalized_by_session_id=c0.session_id,
        finalized_by_generation=c0.lease_generation,
    )
    store.close_epoch("e1", finalization=finalization)

    # Test-only destruction: prove CLOSED recovery is detached from mutable session head.
    store.connection.execute("PRAGMA foreign_keys=OFF")
    store.connection.execute("DELETE FROM assignment WHERE task_hash IN (SELECT task_hash FROM task WHERE epoch_id='e1')")
    store.connection.execute("DELETE FROM session WHERE epoch_id='e1'")
    store.connection.execute("PRAGMA foreign_keys=ON")

    after = Synchronizer(store).recover("e1")
    assert after == before
    assert after.snapshot_hash == before.snapshot_hash
    assert after.integration_order == before.integration_order


def test_closed_recovery_fails_closed_on_corrupt_cut_or_unsupported_version(tmp_path):
    store, sim = setup(tmp_path)
    c0 = register(sim, SlotId.C0, "0" * 64, "c0")
    snapshot = Synchronizer(store).snapshot("e1")
    cut = build_recovery_cut(store, "e1", snapshot.snapshot_hash)
    finalization = EpochFinalization.create(
        epoch_id="e1",
        final_snapshot_hash=snapshot.snapshot_hash,
        recovery_cut_hash=recovery_cut_hash(cut),
        recovery_cut=cut,
        finalized_by_session_id=c0.session_id,
        finalized_by_generation=c0.lease_generation,
    )
    store.close_epoch("e1", finalization=finalization)
    store.connection.execute(
        "UPDATE finalization SET recovery_cut_hash=? WHERE epoch_id='e1'", ("f" * 64,)
    )
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_INTEGRITY_ERROR"):
        Synchronizer(store).recover("e1")

    unsupported = dataclasses.replace(finalization, protocol_version="D6.FINALIZATION.999")
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_VERSION_UNSUPPORTED"):
        recover_from_cut(unsupported)
