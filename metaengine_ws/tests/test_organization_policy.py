from __future__ import annotations

import pytest

from metaengine.organization_policy import (
    OrganizationPolicy,
    OrganizationPolicyStatus,
    OrganizationType,
    ResourceRequirement,
    TopologyEdge,
    TopologyRelation,
    WorkerRole,
)
from metaengine.resource_descriptor import ResourceKind, ResourceSecurityClass


C = "a" * 64


def _req(name: str, *, capabilities=("reasoning",), kinds=(ResourceKind.MODEL,)):
    return ResourceRequirement.create(
        requirement_id=name,
        required_capabilities=capabilities,
        allowed_resource_kinds=kinds,
        allowed_security_classes=(ResourceSecurityClass.P0, ResourceSecurityClass.P1, ResourceSecurityClass.P2),
        required_tool_capabilities=(),
    )


def _role(role_id: str, requirement_id: str):
    return WorkerRole.create(
        role_id=role_id,
        resource_requirement_id=requirement_id,
        responsibilities=(f"responsibility:{role_id}",),
        tool_allowlist=(),
        information_scopes=("task",),
    )


def _make(kind: OrganizationType) -> OrganizationPolicy:
    if kind is OrganizationType.ONE_RESOURCE:
        reqs = (_req("main"),)
        roles = (_role("main", "main"),)
        groups = (("main",),)
        edges = ()
    elif kind is OrganizationType.RESOURCE_PLUS_VERIFIER:
        reqs = (_req("main"), _req("verify", capabilities=("verification",), kinds=(ResourceKind.VERIFIER,)))
        roles = (_role("main", "main"), _role("verify", "verify"))
        groups = (("main",), ("verify",))
        edges = (TopologyEdge.create("main", "verify", TopologyRelation.REVIEW),)
    elif kind is OrganizationType.SEQUENTIAL_PIPELINE:
        reqs = (_req("a"), _req("b"))
        roles = (_role("a", "a"), _role("b", "b"))
        groups = (("a",), ("b",))
        edges = (TopologyEdge.create("a", "b", TopologyRelation.FLOW),)
    elif kind is OrganizationType.PARALLEL_ENSEMBLE:
        reqs = (_req("a"), _req("b"))
        roles = (_role("a", "a"), _role("b", "b"))
        groups = (("a", "b"),)
        edges = ()
    elif kind is OrganizationType.SPECIALIST_ROUTING:
        reqs = (_req("router"), _req("specialist"))
        roles = (_role("router", "router"), _role("specialist", "specialist"))
        groups = (("router",), ("specialist",))
        edges = (TopologyEdge.create("router", "specialist", TopologyRelation.ROUTE),)
    elif kind is OrganizationType.HIERARCHICAL_FEDERATION:
        reqs = (_req("coord"), _req("worker"))
        roles = (_role("coord", "coord"), _role("worker", "worker"))
        groups = (("coord",), ("worker",))
        edges = (TopologyEdge.create("coord", "worker", TopologyRelation.DELEGATE),)
    else:
        reqs = (_req("left"), _req("right"))
        roles = (_role("left", "left"), _role("right", "right"))
        groups = (("left", "right"),)
        edges = (TopologyEdge.create("left", "right", TopologyRelation.REDUNDANT),)
    return OrganizationPolicy.create(
        constitution_hash=C,
        organization_type=kind,
        parent_policy_hash=None,
        resource_requirements=reqs,
        worker_roles=roles,
        execution_groups=groups,
        topology_edges=edges,
        routing=(("selection", "deterministic"),),
        memory_policy=(("mode", "none"),),
        tool_policy=(("default", "deny"),),
        information_boundaries=(("default", "task-scoped"),),
        review_policy=(("mode", "explicit"),),
        resource_budget=(("budget", "bounded"),),
        termination_policy=(("mode", "contract"),),
        recovery_policy=(("mode", "receipt-based"),),
        evaluation_contract_ref="evaluation:sealed:v1",
        status=OrganizationPolicyStatus.SHADOW,
        lineage=(("origin", "test"),),
    )


def test_all_initial_organization_families_share_one_core_type():
    policies = tuple(_make(kind) for kind in OrganizationType)
    assert len(policies) == 7
    assert {policy.organization_type for policy in policies} == set(OrganizationType)
    assert all(policy.status is OrganizationPolicyStatus.SHADOW for policy in policies)
    assert all(len(policy.policy_hash) == 64 for policy in policies)


def test_unordered_inputs_canonicalize_but_execution_group_order_is_semantic():
    base = _make(OrganizationType.SEQUENTIAL_PIPELINE)
    reordered = OrganizationPolicy.create(
        constitution_hash=C,
        organization_type=base.organization_type,
        parent_policy_hash=None,
        resource_requirements=tuple(reversed(base.resource_requirements)),
        worker_roles=tuple(reversed(base.worker_roles)),
        execution_groups=base.execution_groups,
        topology_edges=tuple(reversed(base.topology_edges)),
        routing=tuple(reversed(base.routing)),
        memory_policy=base.memory_policy,
        tool_policy=base.tool_policy,
        information_boundaries=base.information_boundaries,
        review_policy=base.review_policy,
        resource_budget=base.resource_budget,
        termination_policy=base.termination_policy,
        recovery_policy=base.recovery_policy,
        evaluation_contract_ref=base.evaluation_contract_ref,
        status=base.status,
        lineage=base.lineage,
    )
    assert reordered.policy_hash == base.policy_hash
    reversed_groups = OrganizationPolicy.create(
        **{**base.creation_fields(), "execution_groups": tuple(reversed(base.execution_groups))}
    )
    assert reversed_groups.policy_hash != base.policy_hash


def test_parallel_group_role_order_is_not_semantic():
    base = _make(OrganizationType.PARALLEL_ENSEMBLE)
    swapped = OrganizationPolicy.create(**{**base.creation_fields(), "execution_groups": (("b", "a"),)})
    assert swapped.policy_hash == base.policy_hash


def test_unknown_requirement_and_role_references_fail_closed():
    base = _make(OrganizationType.SEQUENTIAL_PIPELINE)
    bad_role = WorkerRole.create(
        role_id="x",
        resource_requirement_id="missing",
        responsibilities=("x",),
        tool_allowlist=(),
        information_scopes=("task",),
    )
    with pytest.raises(ValueError, match="ORGANIZATION_ROLE_REQUIREMENT_UNKNOWN"):
        OrganizationPolicy.create(**{**base.creation_fields(), "worker_roles": base.worker_roles + (bad_role,), "execution_groups": base.execution_groups + (("x",),)})
    with pytest.raises(ValueError, match="ORGANIZATION_TOPOLOGY_ROLE_UNKNOWN"):
        OrganizationPolicy.create(**{**base.creation_fields(), "topology_edges": (TopologyEdge.create("a", "ghost", TopologyRelation.FLOW),)})


def test_duplicate_ids_and_topology_self_loops_fail_closed():
    base = _make(OrganizationType.ONE_RESOURCE)
    with pytest.raises(ValueError, match="ORGANIZATION_RESOURCE_REQUIREMENT_DUPLICATE"):
        OrganizationPolicy.create(**{**base.creation_fields(), "resource_requirements": base.resource_requirements * 2})
    with pytest.raises(ValueError, match="ORGANIZATION_WORKER_ROLE_DUPLICATE"):
        OrganizationPolicy.create(**{**base.creation_fields(), "worker_roles": base.worker_roles * 2})
    with pytest.raises(ValueError, match="ORGANIZATION_TOPOLOGY_SELF_LOOP_FORBIDDEN"):
        TopologyEdge.create("main", "main", TopologyRelation.FLOW)


def test_type_specific_minimum_constraints_fail_closed():
    one = _make(OrganizationType.ONE_RESOURCE)
    with pytest.raises(ValueError, match="ORGANIZATION_ONE_RESOURCE_EXACTLY_ONE_ROLE"):
        OrganizationPolicy.create(**{**one.creation_fields(), "worker_roles": one.worker_roles + (_role("extra", "main"),), "execution_groups": (("main", "extra"),)})
    verifier = _make(OrganizationType.RESOURCE_PLUS_VERIFIER)
    with pytest.raises(ValueError, match="ORGANIZATION_VERIFIER_REVIEW_EDGE_REQUIRED"):
        OrganizationPolicy.create(**{**verifier.creation_fields(), "topology_edges": ()})
    routing = _make(OrganizationType.SPECIALIST_ROUTING)
    with pytest.raises(ValueError, match="ORGANIZATION_ROUTE_EDGE_REQUIRED"):
        OrganizationPolicy.create(**{**routing.creation_fields(), "topology_edges": ()})


def test_policy_hash_roundtrip_and_tamper_detection():
    policy = _make(OrganizationType.HIERARCHICAL_FEDERATION)
    restored = OrganizationPolicy.from_dict(policy.as_dict())
    assert restored.policy_hash == policy.policy_hash
    value = policy.as_dict()
    value["evaluation_contract_ref"] = "tampered"
    with pytest.raises(ValueError, match="ORGANIZATION_POLICY_HASH_MISMATCH"):
        OrganizationPolicy.from_dict(value)


def test_status_cannot_claim_active_canonical_authority():
    assert {item.value for item in OrganizationPolicyStatus} == {"SHADOW", "EXPERIMENTAL", "LEGACY_REFERENCE"}
    with pytest.raises(ValueError):
        OrganizationPolicyStatus("ACTIVE")
