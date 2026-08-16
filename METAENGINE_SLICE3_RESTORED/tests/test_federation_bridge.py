"""METAENGINE Step B — Federation ↔ Orchestrator wiring tests.

Tests that the orchestrator can dispatch engine execution through the
FederationStore (C0-C7 slots, epoch, candidates, finalization) instead of
raw ThreadPoolExecutor. The federation bridge creates an epoch, dispatches
tasks to slots, collects candidates, and finalizes the epoch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaengine.federation_bridge import (
    FederationBridge,
    FederationBridgeResult,
    EPOCH_PROTOCOL_VERSION,
)


@pytest.fixture
def bridge(tmp_path):
    """A FederationBridge with a temporary store."""
    return FederationBridge(store_path=tmp_path / "federation.db")


@pytest.fixture
def engine_configs():
    """Minimal engine configs (4 engines for testing)."""
    return [
        {"engine_id": "engine_01", "execution_mode": "PYTHON_REFERENCE_CONTRACT", "roles": ["PRIMARY"]},
        {"engine_id": "engine_02", "execution_mode": "PYTHON_REFERENCE_CONTRACT", "roles": ["PRIMARY"]},
        {"engine_id": "engine_03", "execution_mode": "PYTHON_REFERENCE_CONTRACT", "roles": ["PRIMARY"]},
        {"engine_id": "engine_04", "execution_mode": "PYTHON_REFERENCE_CONTRACT", "roles": ["PRIMARY"]},
    ]


# ---------------------------------------------------------------------------
# 1. FederationBridge creates an epoch
# ---------------------------------------------------------------------------


def test_bridge_creates_epoch(bridge):
    """The bridge must create a federation epoch before dispatching tasks."""
    epoch_id = bridge.create_epoch(
        base_checkpoint_id="metaengine-chat-2.3.0-alpha.1-cp001",
        policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        catalog_hash="0" * 64,
    )
    assert epoch_id
    assert epoch_id.startswith("epoch-")
    # The epoch must be queryable in the store
    epoch = bridge.store.get_epoch(epoch_id)
    assert epoch is not None
    assert epoch["base_checkpoint_id"] == "metaengine-chat-2.3.0-alpha.1-cp001"


# ---------------------------------------------------------------------------
# 2. Bridge dispatches tasks to federation slots
# ---------------------------------------------------------------------------


def test_bridge_dispatches_tasks(bridge, engine_configs):
    """The bridge must dispatch a federated task for each scheduled engine."""
    epoch_id = bridge.create_epoch(
        base_checkpoint_id="cp001",
        policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        catalog_hash="0" * 64,
    )
    task_hash = bridge.dispatch_task(
        epoch_id=epoch_id,
        input_hash="a" * 64,
        engine_configs=engine_configs,
    )
    assert task_hash
    # The task must be in the store
    task_row = bridge.store.task_row(task_hash)
    assert task_row is not None
    assert task_row["epoch_id"] == epoch_id


# ---------------------------------------------------------------------------
# 3. Bridge collects candidates from engine contributions
# ---------------------------------------------------------------------------


def test_bridge_collects_candidates(bridge, engine_configs):
    """The bridge must collect engine contributions as federation candidates."""
    from metaengine.adapters.base import EngineContribution

    epoch_id = bridge.create_epoch(
        base_checkpoint_id="cp001",
        policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        catalog_hash="0" * 64,
    )
    task_hash = bridge.dispatch_task(
        epoch_id=epoch_id,
        input_hash="a" * 64,
        engine_configs=engine_configs,
    )

    # Simulate engine contributions
    contributions = [
        EngineContribution(
            engine_id=cfg["engine_id"],
            status="COMPLETE",
            native={},
            canonical={"kind": "test", "claims": []},
            error=None,
            adapter_kind="REFERENCE_SIMULATION",
            implementation_level="CLEAN_ROOM_CONTRACT_STUB",
        )
        for cfg in engine_configs
    ]

    bridge.collect_candidates(
        epoch_id=epoch_id,
        task_hash=task_hash,
        contributions=contributions,
    )

    # Each contribution must produce a candidate in the store
    candidates = bridge.store.list_candidate_rows(epoch_id)
    assert len(candidates) == len(engine_configs)


# ---------------------------------------------------------------------------
# 4. Bridge finalizes the epoch
# ---------------------------------------------------------------------------


def test_bridge_finalizes_epoch(bridge, engine_configs):
    """The bridge must finalize the epoch after collecting all candidates."""
    from metaengine.adapters.base import EngineContribution

    epoch_id = bridge.create_epoch(
        base_checkpoint_id="cp001",
        policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        catalog_hash="0" * 64,
    )
    task_hash = bridge.dispatch_task(
        epoch_id=epoch_id,
        input_hash="a" * 64,
        engine_configs=engine_configs,
    )
    contributions = [
        EngineContribution(
            engine_id=cfg["engine_id"],
            status="COMPLETE",
            native={},
            canonical={"kind": "test", "claims": []},
            error=None,
            adapter_kind="REFERENCE_SIMULATION",
            implementation_level="CLEAN_ROOM_CONTRACT_STUB",
        )
        for cfg in engine_configs
    ]
    bridge.collect_candidates(epoch_id=epoch_id, task_hash=task_hash, contributions=contributions)

    finalization = bridge.finalize_epoch(epoch_id=epoch_id, session_id="test-session")
    assert finalization is not None
    assert finalization.epoch_id == epoch_id
    assert finalization.finalization_hash
    assert finalization.final_snapshot_hash


# ---------------------------------------------------------------------------
# 5. Full bridge round-trip: epoch → dispatch → collect → finalize
# ---------------------------------------------------------------------------


def test_full_bridge_round_trip(bridge, engine_configs):
    """Full round-trip: create epoch, dispatch, collect, finalize, return result."""
    from metaengine.adapters.base import EngineContribution

    result = bridge.run_federated(
        input_hash="b" * 64,
        base_checkpoint_id="cp001",
        policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        catalog_hash="0" * 64,
        engine_configs=engine_configs,
        contributions=[
            EngineContribution(
                engine_id=cfg["engine_id"],
                status="COMPLETE",
                native={},
                canonical={"kind": "test"},
                error=None,
                adapter_kind="REFERENCE_SIMULATION",
                implementation_level="CLEAN_ROOM_CONTRACT_STUB",
            )
            for cfg in engine_configs
        ],
    )

    assert isinstance(result, FederationBridgeResult)
    assert result.epoch_id
    assert result.task_hash
    assert result.finalization_hash
    assert result.candidate_count == len(engine_configs)
    assert result.epoch_finalized is True


# ---------------------------------------------------------------------------
# 6. Bridge protocol version
# ---------------------------------------------------------------------------


def test_bridge_protocol_version():
    assert EPOCH_PROTOCOL_VERSION == "D6.1"
