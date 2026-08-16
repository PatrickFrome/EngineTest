from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from metaengine.devfabric.codec import to_primitive

from .contracts import FederatedTaskEnvelope
from .roles import RoleGenome, load_role_genome
from .types import SlotId

_PROTOCOL_FILES = (
    "FEDERATION_PROTOCOL.json",
    "TASK_PROTOCOL.json",
    "LEASE_PROTOCOL.json",
    "EPOCH_PROTOCOL.json",
    "CONFLICT_POLICY.json",
    "ADAPTATION_POLICY.json",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class BootstrapError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"{self.code}:{self.detail}")


@dataclass(frozen=True)
class BootstrapContext:
    root: Path
    protocol_version: str
    canonical_authority: str
    slot_count: int
    role_catalog: tuple[tuple[SlotId, str], ...]
    role_genomes: tuple[tuple[SlotId, RoleGenome], ...]
    role_profile_hashes: tuple[tuple[SlotId, str], ...]
    protocol_documents: tuple[tuple[str, Mapping[str, object]], ...]
    source_artifact_sha256: str
    release_version: str
    capsule_manifest_version: str


def _read_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BootstrapError(code, str(path)) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("BOOTSTRAP_JSON_INVALID", f"{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise BootstrapError("BOOTSTRAP_JSON_INVALID", f"{path}:expected object")
    return payload


def _validate_source_binding(root: Path) -> tuple[str, str, str]:
    binding_path = root / "devfabric" / "source_binding.json"
    binding = _read_json(binding_path, code="SOURCE_BINDING_MISSING")
    artifact_sha = str(binding.get("artifact_sha256", ""))
    release_version = str(binding.get("release_version", ""))
    if not _HEX64.fullmatch(artifact_sha):
        raise BootstrapError("SOURCE_BINDING_INVALID", "artifact_sha256")
    if not release_version:
        raise BootstrapError("SOURCE_BINDING_INVALID", "release_version")

    manifest_path = root / "devfabric" / "CAPSULE_MANIFEST.json"
    manifest = _read_json(manifest_path, code="CAPSULE_BINDING_MISSING")
    if str(manifest.get("source_artifact_sha256", "")) != artifact_sha:
        raise BootstrapError("CAPSULE_SOURCE_BINDING_MISMATCH", "source_artifact_sha256")
    if str(manifest.get("release_version", "")) != release_version:
        raise BootstrapError("CAPSULE_SOURCE_BINDING_MISMATCH", "release_version")
    manifest_version = str(manifest.get("manifest_version", ""))
    if not manifest_version:
        raise BootstrapError("CAPSULE_BINDING_INVALID", "manifest_version")
    return artifact_sha, release_version, manifest_version


def load_bootstrap(root: Path) -> BootstrapContext:
    root = Path(root).resolve()
    artifact_sha, release_version, manifest_version = _validate_source_binding(root)

    chat_root = root / "chat_federation"
    protocol_docs: list[tuple[str, Mapping[str, object]]] = []
    versions: set[str] = set()
    authorities: set[str] = set()
    slot_counts: set[int] = set()
    for name in _PROTOCOL_FILES:
        payload = _read_json(chat_root / name, code="PROTOCOL_FILE_MISSING")
        versions.add(str(payload.get("protocol_version", "")))
        authorities.add(str(payload.get("canonical_authority", "")))
        try:
            slot_counts.add(int(payload.get("slot_count", -1)))
        except (TypeError, ValueError) as exc:
            raise BootstrapError("SLOT_COUNT_INVALID", name) from exc
        protocol_docs.append((name, payload))
    if len(versions) != 1 or "" in versions:
        raise BootstrapError("PROTOCOL_VERSION_MISMATCH", repr(sorted(versions)))
    if authorities != {"SUPABASE_ONLY"}:
        raise BootstrapError("CANONICAL_AUTHORITY_MISMATCH", repr(sorted(authorities)))
    if slot_counts != {8}:
        raise BootstrapError("SLOT_COUNT_INVALID", repr(sorted(slot_counts)))
    protocol_version = next(iter(versions))

    catalogue_raw = _read_json(chat_root / "ROLE_CATALOG.json", code="ROLE_CATALOG_MISSING")
    expected_slots = tuple(SlotId)
    if set(catalogue_raw) != {slot.value for slot in expected_slots} or len(catalogue_raw) != 8:
        raise BootstrapError("ROLE_CATALOG_INVALID", "expected exactly C0-C7")

    role_catalog: list[tuple[SlotId, str]] = []
    role_genomes: list[tuple[SlotId, RoleGenome]] = []
    role_hashes: list[tuple[SlotId, str]] = []
    for slot in expected_slots:
        try:
            genome = load_role_genome(root, slot)
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BootstrapError("ROLE_PROFILE_INVALID", f"{slot.value}:{exc}") from exc
        catalog_role = str(catalogue_raw[slot.value])
        if genome.hard.role != catalog_role:
            raise BootstrapError(
                "ROLE_CATALOG_INVALID",
                f"{slot.value}:catalog={catalog_role}:profile={genome.hard.role}",
            )
        profile_hash = genome.profile_hash
        if not _HEX64.fullmatch(profile_hash):
            raise BootstrapError("ROLE_PROFILE_HASH_INVALID", slot.value)
        role_catalog.append((slot, catalog_role))
        role_genomes.append((slot, genome))
        role_hashes.append((slot, profile_hash))

    federation = dict(protocol_docs)["FEDERATION_PROTOCOL.json"]
    if tuple(federation.get("slot_ids", ())) != tuple(slot.value for slot in expected_slots):
        raise BootstrapError("ROLE_CATALOG_INVALID", "FEDERATION_PROTOCOL slot_ids mismatch")

    return BootstrapContext(
        root=root,
        protocol_version=protocol_version,
        canonical_authority="SUPABASE_ONLY",
        slot_count=8,
        role_catalog=tuple(role_catalog),
        role_genomes=tuple(role_genomes),
        role_profile_hashes=tuple(role_hashes),
        protocol_documents=tuple(protocol_docs),
        source_artifact_sha256=artifact_sha,
        release_version=release_version,
        capsule_manifest_version=manifest_version,
    )


def activate_role(context: BootstrapContext, slot: SlotId) -> RoleGenome:
    slot = SlotId(slot)
    roles = dict(context.role_genomes)
    try:
        role = roles[slot]
    except KeyError as exc:
        raise BootstrapError("ROLE_NOT_AVAILABLE", slot.value) from exc
    expected_hash = dict(context.role_profile_hashes)[slot]
    if role.profile_hash != expected_hash:
        raise BootstrapError("ROLE_PROFILE_HASH_MISMATCH", slot.value)
    return role


def offline_role_packet(
    context: BootstrapContext,
    slot: SlotId,
    pinned_task: FederatedTaskEnvelope | None,
) -> dict[str, object]:
    slot = SlotId(slot)
    role = activate_role(context, slot)
    if pinned_task is not None and pinned_task.owner_slot is not slot:
        raise BootstrapError("PINNED_TASK_ROLE_MISMATCH", f"{pinned_task.owner_slot.value}!={slot.value}")
    packet: dict[str, object] = {
        "federation_state": "FROZEN_OFFLINE",
        "protocol_version": context.protocol_version,
        "canonical_authority": context.canonical_authority,
        "source_artifact_sha256": context.source_artifact_sha256,
        "release_version": context.release_version,
        "slot_id": slot.value,
        "role": role.hard.role,
        "role_profile_hash": role.profile_hash,
        "role_genome": to_primitive(role),
        "offline_authority": "NO_NEW_AUTHORITATIVE_ASSIGNMENTS",
    }
    if pinned_task is not None:
        task_payload = to_primitive(pinned_task)
        task_payload["task_hash"] = pinned_task.task_hash
        task_payload["task_id"] = pinned_task.task_id
        packet["pinned_task_source"] = "EXPLICIT_PINNED_INPUT"
        packet["pinned_task"] = task_payload
    return packet


def connected_role_packet(context: BootstrapContext, slot: SlotId) -> dict[str, object]:
    """Build a non-authoritative connected bootstrap packet for one UI chat slot."""
    slot = SlotId(slot)
    role = activate_role(context, slot)
    return {
        "packet_version": "METAENGINE-FEDERATION-ROLE-PACKET-D6.1",
        "multi_chat_ui_status": "READY_FOR_CANARY_NOT_OBSERVED",
        "protocol_version": context.protocol_version,
        "canonical_authority": context.canonical_authority,
        "slot_id": slot.value,
        "role": role.hard.role,
        "role_profile_hash": role.profile_hash,
        "role_genome": to_primitive(role),
        "capsule_reference": {
            "mode": "ONE_COMMON_CONTROL_CAPSULE",
            "source_artifact_sha256": context.source_artifact_sha256,
            "release_version": context.release_version,
            "manifest_version": context.capsule_manifest_version,
        },
        "authority_rule": "REGISTRATION_RESPONSE_AND_LEDGER_ARE_MACHINE_TRUTH",
        "tool_sequence": (
            {
                "tool": "federation_register",
                "arguments": {
                    "epoch_id": "<ACTIVE_EPOCH_ID>",
                    "requested_slot": slot.value,
                    "capsule_sha256": "<CONTROL_CAPSULE_SHA256>",
                    "protocol_version": context.protocol_version,
                    "role_profile_hash": role.profile_hash,
                    "registration_nonce": "<UNIQUE_REGISTRATION_NONCE>",
                },
            },
            {
                "tool": "session_status",
                "arguments": {"session_id": "<SESSION_ID_FROM_REGISTRATION>"},
            },
            {
                "tool": "federation_status",
                "arguments": {"epoch_id": "<ACTIVE_EPOCH_ID>"},
            },
            {
                "tool": "task_get",
                "arguments": {
                    "session_id": "<SESSION_ID_FROM_REGISTRATION>",
                    "task_hash": "<ASSIGNED_TASK_HASH>",
                },
            },
            {
                "tool": "task_dependencies",
                "arguments": {
                    "session_id": "<SESSION_ID_FROM_REGISTRATION>",
                    "task_hash": "<ASSIGNED_TASK_HASH>",
                },
            },
        ),
    }


def connected_role_packets(context: BootstrapContext) -> tuple[dict[str, object], ...]:
    """Generate all C0-C7 packets from the same verified CONTROL capsule context."""
    return tuple(connected_role_packet(context, slot) for slot in SlotId)
