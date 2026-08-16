"""METAENGINE Phase 11 — Organization Policy Generator + Tournament→Mechanism pipeline.

Two loops closed:
1. tournament → mechanism_library: tournament winner becomes a MechanismCandidate
2. mechanism_library → organization_policy: A2/A3 mechanisms generate candidate policies

This completes the knowledge accumulation cycle:
mechanism → policy → tournament → evidence → mechanism
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .util import canonical_hash
from .mechanism_library import MechanismCandidate, MechanismState, MechanismLibrary
from .organization_policy import (
    OrganizationPolicy,
    OrganizationType,
    OrganizationPolicyStatus,
    ResourceRequirement,
    WorkerRole,
    TopologyEdge,
    TopologyRelation,
)
from .resource_descriptor import ResourceKind, ResourceSecurityClass


POLICY_GENERATOR_VERSION = "METAENGINE-ORGANIZATION-POLICY-GENERATOR-1"


@dataclass(frozen=True)
class GeneratedPolicyCandidate:
    """A candidate organization policy generated from mechanism library evidence."""
    generator_version: str
    policy_hash: str
    organization_type: OrganizationType
    source_mechanism_ids: tuple[str, ...]
    generation_rationale: str
    shadow_status: OrganizationPolicyStatus
    truth_effect: str
    candidate_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "generator_version": self.generator_version,
            "policy_hash": self.policy_hash,
            "organization_type": self.organization_type.value,
            "source_mechanism_ids": list(self.source_mechanism_ids),
            "generation_rationale": self.generation_rationale,
            "shadow_status": self.shadow_status.value,
            "truth_effect": self.truth_effect,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "candidate_hash": self.candidate_hash}


def _mechanism_to_organization_type(mechanism: MechanismCandidate) -> OrganizationType:
    """Map a mechanism's task_scope to a recommended organization type."""
    task_scope = set(mechanism.task_scope)
    if "ROUTING" in task_scope or "MIXED_RETRIEVAL" in task_scope:
        return OrganizationType.SPECIALIST_ROUTING
    if "MULTI_WAVE" in task_scope:
        return OrganizationType.SEQUENTIAL_PIPELINE
    if "REASONING" in task_scope:
        return OrganizationType.RESOURCE_PLUS_VERIFIER
    if "AGENTIC" in task_scope or "PLANNING" in task_scope:
        return OrganizationType.HIERARCHICAL_FEDERATION
    return OrganizationType.ONE_RESOURCE


def generate_policy_from_mechanisms(
    library: MechanismLibrary,
    *,
    constitution_hash: str,
) -> GeneratedPolicyCandidate | None:
    """Generate a shadow organization policy candidate from A2+ mechanisms.

    Only A2_TRANSFERABLE or A3_ASSIMILATED mechanisms can generate policies.
    A0/A1 are hypotheses, not evidence — they cannot generate policies.
    """
    eligible = [
        c for c in library.candidates
        if c.status in (MechanismState.A2_TRANSFERABLE, MechanismState.A3_ASSIMILATED)
    ]
    if not eligible:
        return None

    # Use the highest-status mechanism (A3 > A2)
    best = max(eligible, key=lambda c: (
        c.status == MechanismState.A3_ASSIMILATED,
        len(c.transfer_receipts),
    ))
    org_type = _mechanism_to_organization_type(best)

    # Build a minimal shadow policy
    requirement = ResourceRequirement.create(
        requirement_id=f"req.{best.mechanism_id[:12]}",
        required_capabilities=best.task_scope,
        allowed_resource_kinds=(ResourceKind.MODEL, ResourceKind.DETERMINISTIC_WORKER),
        allowed_security_classes=(ResourceSecurityClass.P0, ResourceSecurityClass.P1),
        required_tool_capabilities=(),
    )
    role = WorkerRole.create(
        role_id=f"role.{best.mechanism_id[:12]}",
        resource_requirement_id=requirement.requirement_id,
        responsibilities=best.task_scope,
    )

    if org_type == OrganizationType.SEQUENTIAL_PIPELINE:
        execution_groups = ((role.role_id, role.role_id),)
    elif org_type == OrganizationType.PARALLEL_ENSEMBLE:
        execution_groups = ((role.role_id, role.role_id),)
    elif org_type == OrganizationType.HIERARCHICAL_FEDERATION:
        execution_groups = ((role.role_id,), (role.role_id, role.role_id))
    else:
        execution_groups = ((role.role_id,),)

    policy = OrganizationPolicy.create(
        constitution_hash=constitution_hash,
        organization_type=org_type,
        parent_policy_hash=None,
        resource_requirements=(requirement,),
        worker_roles=(role,),
        execution_groups=execution_groups,
        topology_edges=(),
        evaluation_contract_ref=f"mechanism:{best.mechanism_id}",
        status=OrganizationPolicyStatus.SHADOW,
        lineage=(
            ("generator", "mechanism_policy_generator"),
            ("source_mechanism", best.mechanism_id),
            ("mechanism_status", best.status.value),
            ("mechanism_confidence", best.confidence),
        ),
    )

    candidate = GeneratedPolicyCandidate(
        generator_version=POLICY_GENERATOR_VERSION,
        policy_hash=policy.policy_hash,
        organization_type=org_type,
        source_mechanism_ids=tuple(c.mechanism_id for c in eligible),
        generation_rationale=f"Generated from {len(eligible)} eligible mechanism(s); primary: {best.mechanism_id} ({best.status.value})",
        shadow_status=OrganizationPolicyStatus.SHADOW,
        truth_effect="NONE",
        candidate_hash="",
    )
    h = canonical_hash(candidate.payload())
    return GeneratedPolicyCandidate(**{**candidate.__dict__, "candidate_hash": h})


def extract_mechanism_from_tournament(
    tournament_result: Mapping[str, Any],
    *,
    mechanism_id_prefix: str = "mec.tournament",
) -> MechanismCandidate | None:
    """Extract a MechanismCandidate from a tournament result.

    The tournament winner (non-dominated Pareto frontier policy) becomes an
    A0_OBSERVED mechanism candidate — the tournament observed that this
    organization performs well, but hasn't yet established WHY.
    """
    pareto = tournament_result.get("pareto_frontier", [])
    non_dominated = [e for e in pareto if not e.get("dominated", True)]
    if not non_dominated:
        return None

    # Best non-dominated policy
    best = max(non_dominated, key=lambda e: e.get("metrics", {}).get("quality", 0.0))
    policy_id = best.get("policy_id", "unknown")
    metrics = best.get("metrics", {})

    return MechanismCandidate.create(
        mechanism_id=f"{mechanism_id_prefix}.{policy_id[:12]}",
        semantic_definition=f"Tournament-winning organization: {policy_id}",
        origin_source_ids=("tournament",),
        source_fact_boundary="Tournament result with Pareto-optimal performance",
        hypothesized_effect=f"Organization {policy_id} achieves quality={metrics.get('quality', 0.0)}, cost={metrics.get('cost', 0.0)}",
        task_scope=("TOURNAMENT",),
        prerequisites=(),
        resource_cost="UNOBSERVED",
        complexity_cost="UNOBSERVED",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=(),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="LOW",
        status=MechanismState.A0_OBSERVED,
    )
