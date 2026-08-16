from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .resource_descriptor import ResourceKind, ResourceSecurityClass
from .util import canonical_hash


ORGANIZATION_POLICY_VERSION = "METAENGINE-ORGANIZATION-POLICY-1"


class OrganizationType(str, Enum):
    ONE_RESOURCE = "ONE_RESOURCE"
    RESOURCE_PLUS_VERIFIER = "RESOURCE_PLUS_VERIFIER"
    SEQUENTIAL_PIPELINE = "SEQUENTIAL_PIPELINE"
    PARALLEL_ENSEMBLE = "PARALLEL_ENSEMBLE"
    SPECIALIST_ROUTING = "SPECIALIST_ROUTING"
    HIERARCHICAL_FEDERATION = "HIERARCHICAL_FEDERATION"
    REDUNDANT_REPLICATION = "REDUNDANT_REPLICATION"


class TopologyRelation(str, Enum):
    FLOW = "FLOW"
    ROUTE = "ROUTE"
    DELEGATE = "DELEGATE"
    REVIEW = "REVIEW"
    SYNCHRONIZE = "SYNCHRONIZE"
    REDUNDANT = "REDUNDANT"


class OrganizationPolicyStatus(str, Enum):
    SHADOW = "SHADOW"
    EXPERIMENTAL = "EXPERIMENTAL"
    LEGACY_REFERENCE = "LEGACY_REFERENCE"


def _text(value: object, code: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(code)
    return text


def _strings(values: Iterable[object], *, code: str, require: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({_text(value, code) for value in values}))
    if require and not normalized:
        raise ValueError(code)
    return normalized


def _pairs(values: Iterable[tuple[object, object]], *, code: str) -> tuple[tuple[str, str], ...]:
    result: dict[str, str] = {}
    for key, value in values:
        key_text = _text(key, f"{code}_KEY_REQUIRED")
        value_text = _text(value, f"{code}_VALUE_REQUIRED")
        if key_text in result and result[key_text] != value_text:
            raise ValueError(f"{code}_DUPLICATE_KEY")
        result[key_text] = value_text
    return tuple(sorted(result.items()))


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


@dataclass(frozen=True)
class ResourceRequirement:
    requirement_id: str
    required_capabilities: tuple[str, ...]
    allowed_resource_kinds: tuple[ResourceKind, ...]
    allowed_security_classes: tuple[ResourceSecurityClass, ...]
    required_tool_capabilities: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        requirement_id: str,
        required_capabilities: Iterable[str],
        allowed_resource_kinds: Iterable[ResourceKind],
        allowed_security_classes: Iterable[ResourceSecurityClass],
        required_tool_capabilities: Iterable[str] = (),
    ) -> "ResourceRequirement":
        kinds = tuple(sorted({ResourceKind(value) for value in allowed_resource_kinds}, key=lambda item: item.value))
        security = tuple(
            sorted({ResourceSecurityClass(value) for value in allowed_security_classes}, key=lambda item: item.value)
        )
        if not kinds:
            raise ValueError("ORGANIZATION_RESOURCE_KIND_REQUIRED")
        if not security:
            raise ValueError("ORGANIZATION_SECURITY_CLASS_REQUIRED")
        return cls(
            requirement_id=_text(requirement_id, "ORGANIZATION_RESOURCE_REQUIREMENT_ID_REQUIRED"),
            required_capabilities=_strings(
                required_capabilities,
                code="ORGANIZATION_REQUIRED_CAPABILITY_REQUIRED",
            ),
            allowed_resource_kinds=kinds,
            allowed_security_classes=security,
            required_tool_capabilities=_strings(
                required_tool_capabilities,
                code="ORGANIZATION_REQUIRED_TOOL_CAPABILITY_REQUIRED",
            ),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "required_capabilities": list(self.required_capabilities),
            "allowed_resource_kinds": [item.value for item in self.allowed_resource_kinds],
            "allowed_security_classes": [item.value for item in self.allowed_security_classes],
            "required_tool_capabilities": list(self.required_tool_capabilities),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResourceRequirement":
        return cls.create(
            requirement_id=str(value["requirement_id"]),
            required_capabilities=tuple(value.get("required_capabilities", ())),
            allowed_resource_kinds=tuple(ResourceKind(str(x)) for x in value.get("allowed_resource_kinds", ())),
            allowed_security_classes=tuple(
                ResourceSecurityClass(str(x)) for x in value.get("allowed_security_classes", ())
            ),
            required_tool_capabilities=tuple(value.get("required_tool_capabilities", ())),
        )


@dataclass(frozen=True)
class WorkerRole:
    role_id: str
    resource_requirement_id: str
    responsibilities: tuple[str, ...]
    tool_allowlist: tuple[str, ...]
    information_scopes: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        role_id: str,
        resource_requirement_id: str,
        responsibilities: Iterable[str],
        tool_allowlist: Iterable[str] = (),
        information_scopes: Iterable[str] = (),
    ) -> "WorkerRole":
        return cls(
            role_id=_text(role_id, "ORGANIZATION_ROLE_ID_REQUIRED"),
            resource_requirement_id=_text(
                resource_requirement_id,
                "ORGANIZATION_ROLE_REQUIREMENT_ID_REQUIRED",
            ),
            responsibilities=_strings(
                responsibilities,
                code="ORGANIZATION_ROLE_RESPONSIBILITY_REQUIRED",
            ),
            tool_allowlist=_strings(tool_allowlist, code="ORGANIZATION_ROLE_TOOL_ID_REQUIRED"),
            information_scopes=_strings(
                information_scopes,
                code="ORGANIZATION_INFORMATION_SCOPE_REQUIRED",
            ),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "resource_requirement_id": self.resource_requirement_id,
            "responsibilities": list(self.responsibilities),
            "tool_allowlist": list(self.tool_allowlist),
            "information_scopes": list(self.information_scopes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkerRole":
        return cls.create(
            role_id=str(value["role_id"]),
            resource_requirement_id=str(value["resource_requirement_id"]),
            responsibilities=tuple(value.get("responsibilities", ())),
            tool_allowlist=tuple(value.get("tool_allowlist", ())),
            information_scopes=tuple(value.get("information_scopes", ())),
        )


@dataclass(frozen=True)
class TopologyEdge:
    source_role_id: str
    target_role_id: str
    relation: TopologyRelation

    @classmethod
    def create(
        cls,
        source_role_id: str,
        target_role_id: str,
        relation: TopologyRelation,
    ) -> "TopologyEdge":
        source = _text(source_role_id, "ORGANIZATION_TOPOLOGY_SOURCE_REQUIRED")
        target = _text(target_role_id, "ORGANIZATION_TOPOLOGY_TARGET_REQUIRED")
        if source == target:
            raise ValueError("ORGANIZATION_TOPOLOGY_SELF_LOOP_FORBIDDEN")
        return cls(source, target, TopologyRelation(relation))

    def payload(self) -> dict[str, str]:
        return {
            "source_role_id": self.source_role_id,
            "target_role_id": self.target_role_id,
            "relation": self.relation.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TopologyEdge":
        return cls.create(
            str(value["source_role_id"]),
            str(value["target_role_id"]),
            TopologyRelation(str(value["relation"])),
        )


@dataclass(frozen=True)
class OrganizationPolicy:
    constitution_hash: str
    organization_type: OrganizationType
    parent_policy_hash: str | None
    resource_requirements: tuple[ResourceRequirement, ...]
    worker_roles: tuple[WorkerRole, ...]
    execution_groups: tuple[tuple[str, ...], ...]
    topology_edges: tuple[TopologyEdge, ...]
    routing: tuple[tuple[str, str], ...]
    memory_policy: tuple[tuple[str, str], ...]
    tool_policy: tuple[tuple[str, str], ...]
    information_boundaries: tuple[tuple[str, str], ...]
    review_policy: tuple[tuple[str, str], ...]
    resource_budget: tuple[tuple[str, str], ...]
    termination_policy: tuple[tuple[str, str], ...]
    recovery_policy: tuple[tuple[str, str], ...]
    evaluation_contract_ref: str
    status: OrganizationPolicyStatus
    lineage: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        constitution_hash: str,
        organization_type: OrganizationType,
        parent_policy_hash: str | None,
        resource_requirements: Iterable[ResourceRequirement],
        worker_roles: Iterable[WorkerRole],
        execution_groups: Iterable[Iterable[str]],
        topology_edges: Iterable[TopologyEdge] = (),
        routing: Iterable[tuple[str, str]] = (),
        memory_policy: Iterable[tuple[str, str]] = (),
        tool_policy: Iterable[tuple[str, str]] = (),
        information_boundaries: Iterable[tuple[str, str]] = (),
        review_policy: Iterable[tuple[str, str]] = (),
        resource_budget: Iterable[tuple[str, str]] = (),
        termination_policy: Iterable[tuple[str, str]] = (),
        recovery_policy: Iterable[tuple[str, str]] = (),
        evaluation_contract_ref: str,
        status: OrganizationPolicyStatus = OrganizationPolicyStatus.SHADOW,
        lineage: Iterable[tuple[str, str]] = (),
    ) -> "OrganizationPolicy":
        constitution_hash = str(constitution_hash)
        if not _is_hex(constitution_hash, 64):
            raise ValueError("ORGANIZATION_CONSTITUTION_HASH_INVALID")
        if parent_policy_hash is not None and not _is_hex(str(parent_policy_hash), 64):
            raise ValueError("ORGANIZATION_PARENT_POLICY_HASH_INVALID")

        raw_requirements = tuple(resource_requirements)
        req_ids = [item.requirement_id for item in raw_requirements]
        if len(req_ids) != len(set(req_ids)):
            raise ValueError("ORGANIZATION_RESOURCE_REQUIREMENT_DUPLICATE")
        requirements = tuple(sorted(raw_requirements, key=lambda item: item.requirement_id))

        raw_roles = tuple(worker_roles)
        role_ids = [item.role_id for item in raw_roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("ORGANIZATION_WORKER_ROLE_DUPLICATE")
        roles = tuple(sorted(raw_roles, key=lambda item: item.role_id))

        groups: list[tuple[str, ...]] = []
        for raw in execution_groups:
            group = tuple(sorted({_text(value, "ORGANIZATION_EXECUTION_GROUP_ROLE_REQUIRED") for value in raw}))
            if not group:
                raise ValueError("ORGANIZATION_EXECUTION_GROUP_EMPTY")
            groups.append(group)

        edges = tuple(
            sorted(
                tuple(topology_edges),
                key=lambda item: (item.source_role_id, item.target_role_id, item.relation.value),
            )
        )

        item = cls(
            constitution_hash=constitution_hash,
            organization_type=OrganizationType(organization_type),
            parent_policy_hash=str(parent_policy_hash) if parent_policy_hash is not None else None,
            resource_requirements=requirements,
            worker_roles=roles,
            execution_groups=tuple(groups),
            topology_edges=edges,
            routing=_pairs(routing, code="ORGANIZATION_ROUTING"),
            memory_policy=_pairs(memory_policy, code="ORGANIZATION_MEMORY_POLICY"),
            tool_policy=_pairs(tool_policy, code="ORGANIZATION_TOOL_POLICY"),
            information_boundaries=_pairs(
                information_boundaries,
                code="ORGANIZATION_INFORMATION_BOUNDARY",
            ),
            review_policy=_pairs(review_policy, code="ORGANIZATION_REVIEW_POLICY"),
            resource_budget=_pairs(resource_budget, code="ORGANIZATION_RESOURCE_BUDGET"),
            termination_policy=_pairs(
                termination_policy,
                code="ORGANIZATION_TERMINATION_POLICY",
            ),
            recovery_policy=_pairs(recovery_policy, code="ORGANIZATION_RECOVERY_POLICY"),
            evaluation_contract_ref=_text(
                evaluation_contract_ref,
                "ORGANIZATION_EVALUATION_CONTRACT_REF_REQUIRED",
            ),
            status=OrganizationPolicyStatus(status),
            lineage=_pairs(lineage, code="ORGANIZATION_LINEAGE"),
        )
        item.validate()
        return item

    def validate(self) -> None:
        req_ids = {item.requirement_id for item in self.resource_requirements}
        role_ids = {item.role_id for item in self.worker_roles}
        if not req_ids:
            raise ValueError("ORGANIZATION_RESOURCE_REQUIREMENTS_REQUIRED")
        if not role_ids:
            raise ValueError("ORGANIZATION_WORKER_ROLES_REQUIRED")
        for role in self.worker_roles:
            if role.resource_requirement_id not in req_ids:
                raise ValueError("ORGANIZATION_ROLE_REQUIREMENT_UNKNOWN")

        flattened = [role_id for group in self.execution_groups for role_id in group]
        if any(role_id not in role_ids for role_id in flattened):
            raise ValueError("ORGANIZATION_EXECUTION_GROUP_ROLE_UNKNOWN")
        if set(flattened) != role_ids or len(flattened) != len(set(flattened)):
            raise ValueError("ORGANIZATION_EXECUTION_GROUP_ROLE_COVERAGE_INVALID")

        for edge in self.topology_edges:
            if edge.source_role_id not in role_ids or edge.target_role_id not in role_ids:
                raise ValueError("ORGANIZATION_TOPOLOGY_ROLE_UNKNOWN")

        kind = self.organization_type
        relations = {edge.relation for edge in self.topology_edges}
        if kind is OrganizationType.ONE_RESOURCE:
            if len(self.worker_roles) != 1 or len(self.execution_groups) != 1:
                raise ValueError("ORGANIZATION_ONE_RESOURCE_EXACTLY_ONE_ROLE")
        elif kind is OrganizationType.RESOURCE_PLUS_VERIFIER:
            if TopologyRelation.REVIEW not in relations:
                raise ValueError("ORGANIZATION_VERIFIER_REVIEW_EDGE_REQUIRED")
        elif kind is OrganizationType.SEQUENTIAL_PIPELINE:
            if len(self.execution_groups) < 2:
                raise ValueError("ORGANIZATION_SEQUENTIAL_PIPELINE_GROUPS_REQUIRED")
        elif kind is OrganizationType.PARALLEL_ENSEMBLE:
            if not any(len(group) >= 2 for group in self.execution_groups):
                raise ValueError("ORGANIZATION_PARALLEL_GROUP_REQUIRED")
        elif kind is OrganizationType.SPECIALIST_ROUTING:
            if TopologyRelation.ROUTE not in relations:
                raise ValueError("ORGANIZATION_ROUTE_EDGE_REQUIRED")
        elif kind is OrganizationType.HIERARCHICAL_FEDERATION:
            if not ({TopologyRelation.DELEGATE, TopologyRelation.SYNCHRONIZE} & relations):
                raise ValueError("ORGANIZATION_HIERARCHICAL_EDGE_REQUIRED")
        elif kind is OrganizationType.REDUNDANT_REPLICATION:
            if TopologyRelation.REDUNDANT not in relations:
                raise ValueError("ORGANIZATION_REDUNDANT_EDGE_REQUIRED")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "policy_version": ORGANIZATION_POLICY_VERSION,
            "constitution_hash": self.constitution_hash,
            "organization_type": self.organization_type.value,
            "parent_policy_hash": self.parent_policy_hash,
            "resource_requirements": [item.payload() for item in self.resource_requirements],
            "worker_roles": [item.payload() for item in self.worker_roles],
            "execution_groups": [list(group) for group in self.execution_groups],
            "topology_edges": [item.payload() for item in self.topology_edges],
            "routing": [list(item) for item in self.routing],
            "memory_policy": [list(item) for item in self.memory_policy],
            "tool_policy": [list(item) for item in self.tool_policy],
            "information_boundaries": [list(item) for item in self.information_boundaries],
            "review_policy": [list(item) for item in self.review_policy],
            "resource_budget": [list(item) for item in self.resource_budget],
            "termination_policy": [list(item) for item in self.termination_policy],
            "recovery_policy": [list(item) for item in self.recovery_policy],
            "evaluation_contract_ref": self.evaluation_contract_ref,
            "status": self.status.value,
            "lineage": [list(item) for item in self.lineage],
            "truth_effect": "NONE",
            "self_modifying_code_allowed": False,
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "policy_hash": self.policy_hash}

    def creation_fields(self) -> dict[str, Any]:
        return {
            "constitution_hash": self.constitution_hash,
            "organization_type": self.organization_type,
            "parent_policy_hash": self.parent_policy_hash,
            "resource_requirements": self.resource_requirements,
            "worker_roles": self.worker_roles,
            "execution_groups": self.execution_groups,
            "topology_edges": self.topology_edges,
            "routing": self.routing,
            "memory_policy": self.memory_policy,
            "tool_policy": self.tool_policy,
            "information_boundaries": self.information_boundaries,
            "review_policy": self.review_policy,
            "resource_budget": self.resource_budget,
            "termination_policy": self.termination_policy,
            "recovery_policy": self.recovery_policy,
            "evaluation_contract_ref": self.evaluation_contract_ref,
            "status": self.status,
            "lineage": self.lineage,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OrganizationPolicy":
        claimed = value.get("policy_hash")
        policy = cls.create(
            constitution_hash=str(value["constitution_hash"]),
            organization_type=OrganizationType(str(value["organization_type"])),
            parent_policy_hash=value.get("parent_policy_hash"),
            resource_requirements=tuple(
                ResourceRequirement.from_dict(item) for item in value.get("resource_requirements", ())
            ),
            worker_roles=tuple(WorkerRole.from_dict(item) for item in value.get("worker_roles", ())),
            execution_groups=tuple(tuple(group) for group in value.get("execution_groups", ())),
            topology_edges=tuple(TopologyEdge.from_dict(item) for item in value.get("topology_edges", ())),
            routing=tuple(tuple(item) for item in value.get("routing", ())),
            memory_policy=tuple(tuple(item) for item in value.get("memory_policy", ())),
            tool_policy=tuple(tuple(item) for item in value.get("tool_policy", ())),
            information_boundaries=tuple(tuple(item) for item in value.get("information_boundaries", ())),
            review_policy=tuple(tuple(item) for item in value.get("review_policy", ())),
            resource_budget=tuple(tuple(item) for item in value.get("resource_budget", ())),
            termination_policy=tuple(tuple(item) for item in value.get("termination_policy", ())),
            recovery_policy=tuple(tuple(item) for item in value.get("recovery_policy", ())),
            evaluation_contract_ref=str(value["evaluation_contract_ref"]),
            status=OrganizationPolicyStatus(str(value["status"])),
            lineage=tuple(tuple(item) for item in value.get("lineage", ())),
        )
        if claimed is not None and str(claimed) != policy.policy_hash:
            raise ValueError("ORGANIZATION_POLICY_HASH_MISMATCH")
        return policy
