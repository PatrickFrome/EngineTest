from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .architecture_policy import ArchitecturePolicy, ENGINE_ARCHITECTURE_MIX
from .devfabric.federation.roles import load_role_genome
from .devfabric.federation.types import SlotId
from .organization_policy import (
    OrganizationPolicy,
    OrganizationPolicyStatus,
    OrganizationType,
    ResourceRequirement,
    TopologyEdge,
    TopologyRelation,
    WorkerRole,
)
from .resource_descriptor import ResourceKind, ResourceSecurityClass


def _compact_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def organization_from_architecture_policy(
    policy: ArchitecturePolicy,
    constitution_hash: str,
) -> OrganizationPolicy:
    """Project a legacy 16X ArchitecturePolicy into OrganizationPolicy v1 without mutation.

    The adapter is intentionally loss-aware. Architecture operators remain provenance/routing
    metadata; they are not promoted into Resource capabilities or WorkerRole responsibilities.
    """

    policy.validate()
    source_hash = policy.policy_hash
    flattened = tuple(engine_id for wave in policy.waves for engine_id in wave)
    expected = set(ENGINE_ARCHITECTURE_MIX)
    if len(flattened) != len(set(flattened)) or set(flattened) != expected:
        raise ValueError("LEGACY_ARCHITECTURE_POLICY_NOT_FULLY_REPRESENTABLE")
    if len(policy.waves) < 2:
        raise ValueError("LEGACY_ARCHITECTURE_POLICY_SEQUENTIAL_WAVES_REQUIRED")

    all_security = tuple(ResourceSecurityClass)
    requirements = tuple(
        ResourceRequirement.create(
            requirement_id=f"legacy.{engine_id}",
            required_capabilities=(),
            allowed_resource_kinds=(ResourceKind.LEGACY_ENGINE,),
            allowed_security_classes=all_security,
        )
        for engine_id in sorted(expected)
    )
    roles = tuple(
        WorkerRole.create(
            role_id=engine_id,
            resource_requirement_id=f"legacy.{engine_id}",
            responsibilities=(),
        )
        for engine_id in sorted(expected)
    )

    routing: list[tuple[str, str]] = [
        ("legacy_topology_id", policy.topology_id),
        ("legacy_dialectic_operators", ",".join(policy.dialectic_operators)),
    ]
    for engine_id in sorted(ENGINE_ARCHITECTURE_MIX):
        routing.append((f"legacy_mix.{engine_id}", ",".join(ENGINE_ARCHITECTURE_MIX[engine_id])))

    lineage: list[tuple[str, str]] = [
        ("source_kind", "ArchitecturePolicy"),
        ("source_policy_hash", source_hash),
        ("source_policy_version", str(policy.payload()["policy_version"])),
        ("source_generation", str(policy.generation)),
        ("source_status", str(policy.status)),
        ("source_guardrail_hash", policy.guardrail_hash),
        ("source_verifier_hash", policy.verifier_hash),
    ]
    if policy.parent_policy_hash is not None:
        lineage.append(("source_parent_policy_hash", policy.parent_policy_hash))

    return OrganizationPolicy.create(
        constitution_hash=constitution_hash,
        organization_type=OrganizationType.SEQUENTIAL_PIPELINE,
        parent_policy_hash=None,
        resource_requirements=requirements,
        worker_roles=roles,
        execution_groups=policy.waves,
        topology_edges=(),
        routing=routing,
        resource_budget=(
            ("legacy_max_rounds", str(policy.max_rounds)),
            ("legacy_max_deep_engines", str(policy.max_deep_engines)),
            ("legacy_exploration_rate", repr(policy.exploration_rate)),
        ),
        evaluation_contract_ref=policy.benchmark_hash,
        status=OrganizationPolicyStatus.LEGACY_REFERENCE,
        lineage=lineage,
    )


def _load_federation_protocol(root: Path) -> dict[str, Any]:
    value = json.loads((root / "chat_federation" / "FEDERATION_PROTOCOL.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("LEGACY_FEDERATION_PROTOCOL_INVALID")
    slot_ids = tuple(str(item) for item in value.get("slot_ids", ()))
    if slot_ids != tuple(slot.value for slot in SlotId):
        raise ValueError("LEGACY_FEDERATION_SLOT_CATALOG_MISMATCH")
    if value.get("synchronizer_slot") != SlotId.C0.value:
        raise ValueError("LEGACY_FEDERATION_SYNCHRONIZER_UNSUPPORTED")
    return value


def organization_from_role_genomes(root: str | Path, constitution_hash: str) -> OrganizationPolicy:
    """Project the pinned C0-C7 role catalogue into a legacy OrganizationPolicy reference."""

    root = Path(root).resolve()
    protocol = _load_federation_protocol(root)
    genomes = {slot: load_role_genome(root, slot) for slot in SlotId}

    requirements = tuple(
        ResourceRequirement.create(
            requirement_id=f"role.{slot.value}",
            required_capabilities=tuple(name for name, _weight in genomes[slot].soft.capability_weights),
            allowed_resource_kinds=(ResourceKind.REMOTE_AGENT,),
            allowed_security_classes=(ResourceSecurityClass(genomes[slot].hard.privacy_ceiling.value),),
        )
        for slot in SlotId
    )
    roles = tuple(
        WorkerRole.create(
            role_id=slot.value,
            resource_requirement_id=f"role.{slot.value}",
            responsibilities=genomes[slot].hard.subsystem_ownership,
        )
        for slot in SlotId
    )

    edges: list[TopologyEdge] = []
    for slot, genome in genomes.items():
        for reviewer in genome.hard.mandatory_reviewers:
            edges.append(TopologyEdge.create(slot.value, reviewer.value, TopologyRelation.REVIEW))
    for slot in SlotId:
        if slot is not SlotId.C0:
            edges.append(TopologyEdge.create(SlotId.C0.value, slot.value, TopologyRelation.SYNCHRONIZE))

    lineage: list[tuple[str, str]] = [
        ("source_kind", "D6_ROLE_GENOMES"),
        ("federation_protocol", str(protocol["protocol_version"])),
        ("synchronizer_slot", str(protocol["synchronizer_slot"])),
        ("verification_slot", str(protocol["verification_slot"])),
        ("state_model", str(protocol["state_model"])),
    ]
    for slot in SlotId:
        lineage.append((f"role_profile_{slot.value}", genomes[slot].profile_hash))
        lineage.append((f"role_version_{slot.value}", genomes[slot].version))

    return OrganizationPolicy.create(
        constitution_hash=constitution_hash,
        organization_type=OrganizationType.HIERARCHICAL_FEDERATION,
        parent_policy_hash=None,
        resource_requirements=requirements,
        worker_roles=roles,
        execution_groups=(tuple(slot.value for slot in SlotId),),
        topology_edges=edges,
        review_policy=(("verification_slot", str(protocol["verification_slot"])),),
        recovery_policy=(("synchronizer_recovery", str(protocol["synchronizer_recovery"])),),
        evaluation_contract_ref="chat_federation/PILOT_RUNBOOK.md",
        status=OrganizationPolicyStatus.LEGACY_REFERENCE,
        lineage=lineage,
    )
