from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAT_FEDERATION = ROOT / "chat_federation"
PROTOCOL_FILES = (
    "FEDERATION_PROTOCOL.json",
    "TASK_PROTOCOL.json",
    "LEASE_PROTOCOL.json",
    "EPOCH_PROTOCOL.json",
    "CONFLICT_POLICY.json",
    "ADAPTATION_POLICY.json",
)


def _load(name: str) -> dict[str, object]:
    payload = json.loads((CHAT_FEDERATION / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _walk_keys(value: object, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(_walk_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            keys.extend(_walk_keys(child, f"{prefix}[{index}]"))
    return keys


def test_static_protocol_artifacts_are_common_versioned_and_secret_free():
    for name in PROTOCOL_FILES:
        path = CHAT_FEDERATION / name
        assert path.is_file(), name
        payload = _load(name)
        assert payload["protocol_version"] == "D6.1", name
        assert payload["canonical_authority"] == "SUPABASE_ONLY", name
        assert payload["slot_count"] == 8, name
        dangerous = [
            key
            for key in _walk_keys(payload)
            if re.search(r"secret|token|password|service_role", key, flags=re.I)
        ]
        assert dangerous == [], (name, dangerous)


def test_adaptation_and_lease_protocol_have_exact_safety_bounds():
    adaptation = _load("ADAPTATION_POLICY.json")
    assert adaptation["producer_concurrency"] == {"min": 2, "default": 4, "max": 6}
    assert adaptation["conflict_thresholds"] == {
        "increase_below": 0.10,
        "reduce_above": 0.25,
    }
    lease = _load("LEASE_PROTOCOL.json")
    assert lease["correctness_mode"] == "FENCING_GENERATION_NOT_HEARTBEAT_EXPIRY"
    assert lease["late_receipt_policy"] == "STORE_AUDITABLE_MARK_STALE_FENCED"


def test_bootstrap_document_declares_one_capsule_and_no_memory_authority():
    text = (CHAT_FEDERATION / "BOOTSTRAP.md").read_text(encoding="utf-8")
    assert "ONE COMMON CONTROL CAPSULE" in text
    assert "PROJECT MEMORY IS NOT MACHINE TRUTH" in text
    assert "FROZEN_OFFLINE" in text

import os
import shutil

import pytest

from metaengine.devfabric.codec import to_primitive
from metaengine.devfabric.federation.bootstrap import (
    BootstrapError,
    activate_role,
    load_bootstrap,
    offline_role_packet,
)
from metaengine.devfabric.federation.contracts import FederatedTaskEnvelope
from metaengine.devfabric.federation.roles import load_role_genome
from metaengine.devfabric.federation.types import IntegrationMode, SlotId
from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope


def _base_task() -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id="cp-d6",
        source_tree_hash="a" * 64,
        objective="offline pinned work",
        acceptance_tests=("python -m pytest -q",),
        allowed_paths=("metaengine/",),
        forbidden_paths=("lineages/",),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.NORMAL,
        privacy_class=PrivacyClass.P1,
        zero_spend=True,
    )


def _pinned_task(slot: SlotId = SlotId.C4) -> FederatedTaskEnvelope:
    role = load_role_genome(ROOT, slot)
    return FederatedTaskEnvelope.create(
        base_task=_base_task(),
        epoch_id="epoch-offline-pinned",
        task_version=1,
        owner_slot=slot,
        lease_generation=7,
        role_profile_hash=role.profile_hash,
        base_checkpoint_id="cp-d6",
        dependency_task_ids=(),
        read_set=("metaengine/devfabric/",),
        write_set=("metaengine/devfabric/federation/",),
        interface_set=("BootstrapContext",),
        integration_mode=IntegrationMode.PARALLEL,
        review_slots=(SlotId.C6,),
    )


def test_bootstrap_loads_from_filesystem_without_project_memory_or_cloud_env(monkeypatch):
    for key in tuple(os.environ):
        if any(fragment in key.upper() for fragment in ("SUPABASE", "OPENAI", "POSTHOG", "GOOGLE", "CLOUDFLARE")):
            monkeypatch.delenv(key, raising=False)
    context = load_bootstrap(ROOT)
    assert context.protocol_version == "D6.1"
    assert context.canonical_authority == "SUPABASE_ONLY"
    assert context.slot_count == 8
    assert tuple(slot.value for slot, _ in context.role_catalog) == tuple(f"C{i}" for i in range(8))
    assert len(context.role_profile_hashes) == 8
    assert context.source_artifact_sha256 == "8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0"


def test_activate_role_returns_exact_verified_profile():
    context = load_bootstrap(ROOT)
    role = activate_role(context, SlotId.C4)
    assert role.hard.slot is SlotId.C4
    assert role.hard.role == "EDGE_MCP"
    assert dict(context.role_profile_hashes)[SlotId.C4] == role.profile_hash


def test_offline_packet_never_fabricates_authoritative_session_epoch_or_lease():
    context = load_bootstrap(ROOT)
    packet = offline_role_packet(context, SlotId.C4, pinned_task=None)
    assert packet["federation_state"] == "FROZEN_OFFLINE"
    assert packet["slot_id"] == "C4"
    assert packet["role"] == "EDGE_MCP"
    assert "session_id" not in packet
    assert "epoch_id" not in packet
    assert "lease_generation" not in packet
    assert "pinned_task" not in packet


def test_offline_packet_may_carry_only_an_explicitly_pinned_task():
    context = load_bootstrap(ROOT)
    task = _pinned_task(SlotId.C4)
    packet = offline_role_packet(context, SlotId.C4, pinned_task=task)
    assert packet["federation_state"] == "FROZEN_OFFLINE"
    assert packet["pinned_task_source"] == "EXPLICIT_PINNED_INPUT"
    assert packet["pinned_task"]["task_hash"] == task.task_hash
    assert packet["pinned_task"]["epoch_id"] == "epoch-offline-pinned"
    assert packet["pinned_task"]["lease_generation"] == 7
    assert "session_id" not in packet


def test_bootstrap_fails_closed_on_protocol_version_mismatch(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(ROOT / "chat_federation", root / "chat_federation")
    shutil.copytree(ROOT / "devfabric", root / "devfabric")
    path = root / "chat_federation" / "LEASE_PROTOCOL.json"
    payload = json.loads(path.read_text())
    payload["protocol_version"] = "D6.BAD"
    path.write_text(json.dumps(payload))
    with pytest.raises(BootstrapError, match="PROTOCOL_VERSION_MISMATCH") as exc:
        load_bootstrap(root)
    assert exc.value.code == "PROTOCOL_VERSION_MISMATCH"


def test_bootstrap_fails_closed_when_source_binding_is_missing(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(ROOT / "chat_federation", root / "chat_federation")
    shutil.copytree(ROOT / "devfabric", root / "devfabric")
    (root / "devfabric" / "source_binding.json").unlink()
    with pytest.raises(BootstrapError, match="SOURCE_BINDING_MISSING") as exc:
        load_bootstrap(root)
    assert exc.value.code == "SOURCE_BINDING_MISSING"


def test_finalization_protocol_is_internal_closed_epoch_contract_and_secret_free():
    payload = _load("FINALIZATION_PROTOCOL.json")
    assert payload == {
        "protocol_version": "D6.FINALIZATION.1",
        "authority": "SUPABASE_ONLY",
        "chat_facing": False,
        "closed_recovery_source": "IMMUTABLE_RECOVERY_CUT",
        "adaptation_eligible_state": "CLOSED",
    }
    dangerous = [
        key for key in _walk_keys(payload)
        if re.search(r"secret|token|password|service_role", key, flags=re.I)
    ]
    assert dangerous == []
