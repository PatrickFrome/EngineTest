from __future__ import annotations

from pathlib import Path

from metaengine.architecture_policy import ENGINE_ARCHITECTURE_MIX, initial_policy
from metaengine.constitution import constitution_hash
from metaengine.devfabric.federation.roles import load_role_genome
from metaengine.devfabric.federation.types import SlotId
from metaengine.organization_policy import (
    OrganizationPolicyStatus,
    OrganizationType,
    ResourceRequirement,
    TopologyRelation,
    WorkerRole,
)
from metaengine.resource_descriptor import ResourceKind, ResourceSecurityClass


def test_core_ir_can_represent_legacy_unknowns_without_fabricating_semantics():
    requirement = ResourceRequirement.create(
        requirement_id="legacy.engine_01",
        required_capabilities=(),
        allowed_resource_kinds=(ResourceKind.LEGACY_ENGINE,),
        allowed_security_classes=tuple(ResourceSecurityClass),
    )
    role = WorkerRole.create(
        role_id="engine_01",
        resource_requirement_id=requirement.requirement_id,
        responsibilities=(),
    )
    assert requirement.required_capabilities == ()
    assert role.responsibilities == ()


def test_16x_adapter_preserves_source_identity_waves_and_does_not_invent_capabilities():
    from metaengine.organization_legacy import organization_from_architecture_policy

    root = Path(__file__).resolve().parents[1]
    source = initial_policy()
    before_hash = source.policy_hash
    result = organization_from_architecture_policy(source, constitution_hash(root))

    assert source.policy_hash == before_hash
    assert result.status is OrganizationPolicyStatus.LEGACY_REFERENCE
    assert result.organization_type is OrganizationType.SEQUENTIAL_PIPELINE
    assert result.execution_groups == source.waves
    assert {role.role_id for role in result.worker_roles} == set(ENGINE_ARCHITECTURE_MIX)
    assert {req.requirement_id for req in result.resource_requirements} == {
        f"legacy.{engine_id}" for engine_id in ENGINE_ARCHITECTURE_MIX
    }
    assert all(req.required_capabilities == () for req in result.resource_requirements)
    assert all(role.responsibilities == () for role in result.worker_roles)

    lineage = dict(result.lineage)
    routing = dict(result.routing)
    assert lineage["source_policy_hash"] == before_hash
    assert lineage["source_policy_version"] == "16X-DECLARATIVE-ARCHITECTURE-POLICY-2.3"
    assert routing["legacy_topology_id"] == source.topology_id
    assert routing["legacy_dialectic_operators"] == ",".join(source.dialectic_operators)
    assert result.evaluation_contract_ref == source.benchmark_hash
    assert result.policy_hash == organization_from_architecture_policy(source, constitution_hash(root)).policy_hash


def test_16x_adapter_keeps_operator_metadata_out_of_capability_and_responsibility_fields():
    from metaengine.organization_legacy import organization_from_architecture_policy

    root = Path(__file__).resolve().parents[1]
    source = initial_policy()
    result = organization_from_architecture_policy(source, constitution_hash(root))
    serialized_roles = {value for role in result.worker_roles for value in role.responsibilities}
    serialized_caps = {value for req in result.resource_requirements for value in req.required_capabilities}
    operators = {value for values in ENGINE_ARCHITECTURE_MIX.values() for value in values} | set(source.dialectic_operators)
    assert serialized_roles.isdisjoint(operators)
    assert serialized_caps.isdisjoint(operators)


def test_c0_c7_adapter_uses_only_existing_genome_capabilities_and_preserves_profile_hashes():
    from metaengine.organization_legacy import organization_from_role_genomes

    root = Path(__file__).resolve().parents[1]
    before = {slot: load_role_genome(root, slot) for slot in SlotId}
    result = organization_from_role_genomes(root, constitution_hash(root))
    after = {slot: load_role_genome(root, slot) for slot in SlotId}

    assert result.status is OrganizationPolicyStatus.LEGACY_REFERENCE
    assert result.organization_type is OrganizationType.HIERARCHICAL_FEDERATION
    assert {role.role_id for role in result.worker_roles} == {slot.value for slot in SlotId}
    assert {req.requirement_id for req in result.resource_requirements} == {
        f"role.{slot.value}" for slot in SlotId
    }
    requirements = {req.requirement_id: req for req in result.resource_requirements}
    roles = {role.role_id: role for role in result.worker_roles}
    lineage = dict(result.lineage)

    for slot in SlotId:
        genome = before[slot]
        assert after[slot].profile_hash == genome.profile_hash
        assert lineage[f"role_profile_{slot.value}"] == genome.profile_hash
        assert requirements[f"role.{slot.value}"].required_capabilities == tuple(
            sorted(name for name, _weight in genome.soft.capability_weights)
        )
        assert roles[slot.value].responsibilities == tuple(sorted(genome.hard.subsystem_ownership))
        assert requirements[f"role.{slot.value}"].allowed_resource_kinds == (ResourceKind.REMOTE_AGENT,)
        assert requirements[f"role.{slot.value}"].allowed_security_classes == (
            ResourceSecurityClass(genome.hard.privacy_ceiling.value),
        )


def test_c0_c7_adapter_preserves_review_edges_and_protocol_supported_synchronizer_role():
    from metaengine.organization_legacy import organization_from_role_genomes

    root = Path(__file__).resolve().parents[1]
    result = organization_from_role_genomes(root, constitution_hash(root))
    edges = {(edge.source_role_id, edge.target_role_id, edge.relation) for edge in result.topology_edges}

    for slot in SlotId:
        genome = load_role_genome(root, slot)
        for reviewer in genome.hard.mandatory_reviewers:
            assert (slot.value, reviewer.value, TopologyRelation.REVIEW) in edges

    for slot in SlotId:
        if slot is not SlotId.C0:
            assert (SlotId.C0.value, slot.value, TopologyRelation.SYNCHRONIZE) in edges

    assert dict(result.lineage)["federation_protocol"] == "D6.1"
    assert dict(result.lineage)["synchronizer_slot"] == "C0"
    assert result.policy_hash == organization_from_role_genomes(root, constitution_hash(root)).policy_hash


def test_legacy_adapter_is_one_way_and_does_not_import_legacy_into_core_modules():
    root = Path(__file__).resolve().parents[1]
    for relative in ("metaengine/resource_descriptor.py", "metaengine/organization_policy.py"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "architecture_policy" not in text
        assert "devfabric" not in text
        assert "supabase" not in text.lower()
        assert "cloudflare" not in text.lower()
        assert "openai" not in text.lower()
        assert "a2a" not in text.lower()
