# METAENGINE-1 Slice 2 OrganizationPolicy and ResourceDescriptor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce provider-independent `ResourceDescriptor v1` and `OrganizationPolicy v1` Core types, plus deterministic adapters for existing 16X ArchitecturePolicy and C0-C7 federation roles, without changing canonical champion or D6-G1 runtime semantics.

**Architecture:** `ResourceDescriptor` is a self-describing, constitution-bound manifest for any intelligence resource. `OrganizationPolicy` is a canonical declarative IR describing resource requirements, roles, topology, routing/policy sections, evaluation binding, and lineage. Existing DevFabric providers, A2A-style agents, model APIs, and federation sessions remain adapters/runtimes rather than Core types.

**Tech Stack:** Python 3.13, dataclasses/enums, existing `metaengine.util.canonical_hash`, pytest, no new runtime dependencies.

## Global Constraints

- K0 remains exactly 12 invariants and cannot be mutated by OrganizationPolicy.
- K1 remains non-amendable by ordinary evolution.
- No provider/model-specific business logic enters Core.
- Missing resource observations are `UNOBSERVED`, never implicit zero/success.
- Existing `ArchitecturePolicy` remains intact and canonical active/champion policy is not changed.
- D6-G1 remains shadow-only; no Role Genome materialization.
- Federation MCP surface remains exactly 18 chat-facing tools.
- No Supabase/Cloudflare/GitHub writes are required for Slice 2 implementation.
- Every completed task is followed by Constitution/Architecture-Library/Policy review; Slice 3 is blocked until the Slice 2 review receipt admits it.

---

### Task 1: ResourceDescriptor v1 Core Contract

**Files:**
- Create: `metaengine/resource_descriptor.py`
- Create: `tests/test_resource_descriptor.py`

**Interfaces:**
- Consumes: `metaengine.util.canonical_hash`; compiled constitution hash supplied by caller.
- Produces: `ResourceKind`, `ObservationStatus`, `DeterminismClass`, `ResourceSecurityClass`, `EvidenceBoundObservation`, `ResourceDescriptor`.

- [ ] **Step 1: Write RED tests for deterministic model-like and deterministic-worker resources**

Require a model-like descriptor and a deterministic Python verifier descriptor to share one API and produce stable hashes. Tests must assert order-independent capability/tool/mode normalization and direct constitution binding.

```python
model = ResourceDescriptor.create(
    constitution_hash="a" * 64,
    resource_id="model.reasoner.v1",
    resource_kind=ResourceKind.MODEL,
    runtime_identity="runtime:model:reasoner:v1",
    capabilities=("reasoning", "tool-use"),
    tool_capabilities=("search",),
    input_modes=("text/plain",),
    output_modes=("text/plain",),
    determinism_class=DeterminismClass.STOCHASTIC,
    security_class=ResourceSecurityClass.P2,
    adapter_ref="adapter:model-runtime:v1",
)

verifier = ResourceDescriptor.create(
    constitution_hash="a" * 64,
    resource_id="python.pytest.v1",
    resource_kind=ResourceKind.VERIFIER,
    runtime_identity="python:3.13:pytest",
    capabilities=("deterministic-verification",),
    tool_capabilities=(),
    input_modes=("application/json",),
    output_modes=("application/json",),
    determinism_class=DeterminismClass.DETERMINISTIC,
    security_class=ResourceSecurityClass.P3,
    adapter_ref="adapter:local-python:v1",
)

assert model.descriptor_hash == ResourceDescriptor.from_dict(model.as_dict()).descriptor_hash
assert verifier.resource_kind is ResourceKind.VERIFIER
```

- [ ] **Step 2: Write RED tests for `UNOBSERVED` semantics**

`EvidenceBoundObservation.unobserved()` must contain no value/unit/evidence hashes. `observed(...)` requires at least one valid evidence hash. Creating `UNOBSERVED` with value `0`, `0.0`, `False`, or an evidence hash must fail closed.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_resource_descriptor.py -q
```

Expected: import failure because `metaengine.resource_descriptor` does not exist.

- [ ] **Step 4: Implement minimal Core resource types**

`ResourceKind` values:

```text
MODEL
DETERMINISTIC_WORKER
VERIFIER
SEARCH
HUMAN
REMOTE_AGENT
LEGACY_ENGINE
```

`DeterminismClass` values:

```text
DETERMINISTIC
SEEDED_STOCHASTIC
STOCHASTIC
UNKNOWN
```

`ResourceSecurityClass`: `P0`, `P1`, `P2`, `P3`.

`EvidenceBoundObservation.payload()` must serialize `status`, `value`, `unit`, `evidence_hashes`. `ResourceDescriptor.payload()` must use only primitive canonical values and sorted unique collections.

- [ ] **Step 5: Add validation**

Reject empty identities, malformed constitution hashes, duplicate/empty capability IDs, empty adapter refs, invalid observed evidence hashes, and non-`None` values for `UNOBSERVED`.

- [ ] **Step 6: Run GREEN and Constitution regression**

```bash
python -m pytest tests/test_resource_descriptor.py tests/test_constitution_kernel.py -q
python -m compileall -q metaengine
```

- [ ] **Step 7: Perform development review for Task 1 and commit**

Review K0/K1, A2A self-describing Agent Card pattern, current ProviderDescriptor, and the minimal dict-only alternative. If no conflict is found:

```bash
git add metaengine/resource_descriptor.py tests/test_resource_descriptor.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: add provider-independent resource descriptors'
```

---

### Task 2: OrganizationPolicy v1 Declarative IR

**Files:**
- Create: `metaengine/organization_policy.py`
- Create: `tests/test_organization_policy.py`

**Interfaces:**
- Consumes: Task 1 resource enums and `canonical_hash`.
- Produces: `OrganizationType`, `TopologyRelation`, `OrganizationPolicyStatus`, `ResourceRequirement`, `WorkerRole`, `TopologyEdge`, `OrganizationPolicy`.

- [ ] **Step 1: Write RED tests for the seven generic organization families**

Require valid examples for:

```text
ONE_RESOURCE
RESOURCE_PLUS_VERIFIER
SEQUENTIAL_PIPELINE
PARALLEL_ENSEMBLE
SPECIALIST_ROUTING
HIERARCHICAL_FEDERATION
REDUNDANT_REPLICATION
```

Each example must use the same Core type and provider-neutral resource requirements.

- [ ] **Step 2: Write RED canonicalization and fail-closed tests**

Require:
- deterministic policy hash for reordered unordered inputs;
- topology group order remains meaningful while role order within a parallel group canonicalizes;
- unknown role/requirement references fail;
- duplicate role/requirement IDs fail;
- self-loop topology edges fail unless relation is explicitly `REDUNDANT` between distinct roles;
- malformed constitution hash fails;
- status defaults to `SHADOW` and cannot imply canonical promotion.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_organization_policy.py -q
```

- [ ] **Step 4: Implement minimal IR**

`ResourceRequirement` fields:
- `requirement_id`;
- `required_capabilities`;
- `allowed_resource_kinds`;
- `allowed_security_classes`;
- `required_tool_capabilities`.

`WorkerRole` fields:
- `role_id`;
- `resource_requirement_id`;
- `responsibilities`;
- `tool_allowlist`;
- `information_scopes`.

`TopologyEdge` fields:
- `source_role_id`;
- `target_role_id`;
- `relation` where relation is one of `FLOW`, `ROUTE`, `DELEGATE`, `REVIEW`, `SYNCHRONIZE`, `REDUNDANT`.

`OrganizationPolicy` must expose all conceptual design sections using immutable sorted key/value tuples for routing, memory, tool, information-boundary, review, budget, termination, recovery, and lineage metadata.

- [ ] **Step 5: Enforce type-specific minimum topology constraints**

Examples:
- `ONE_RESOURCE`: exactly one role and one execution group;
- `RESOURCE_PLUS_VERIFIER`: at least one `REVIEW` edge;
- `SEQUENTIAL_PIPELINE`: at least two ordered execution groups;
- `PARALLEL_ENSEMBLE`: at least two roles in one parallel group;
- `SPECIALIST_ROUTING`: at least one `ROUTE` edge;
- `HIERARCHICAL_FEDERATION`: at least one `DELEGATE` or `SYNCHRONIZE` edge;
- `REDUNDANT_REPLICATION`: at least one `REDUNDANT` edge.

- [ ] **Step 6: Run GREEN and Core regressions**

```bash
python -m pytest tests/test_organization_policy.py tests/test_resource_descriptor.py tests/test_constitution_kernel.py -q
python -m compileall -q metaengine
```

- [ ] **Step 7: Perform development review for Task 2 and commit**

Compare typed IR against a generic JSON mapping, OpenAI Agents SDK agent/handoff primitives, and A2A task/skill manifests. Retain provider-neutral Core unless evidence favors a simpler representation.

```bash
git add metaengine/organization_policy.py tests/test_organization_policy.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: add organization policy core IR'
```

---

### Task 3: Deterministic Legacy Adapters for 16X and C0-C7

**Files:**
- Create: `metaengine/organization_legacy.py`
- Create: `tests/test_organization_legacy.py`

**Interfaces:**
- Consumes: existing `ArchitecturePolicy`, `ENGINE_ARCHITECTURE_MIX`, federation `RoleGenome`, Slice 2 Core types.
- Produces: `organization_from_architecture_policy(policy, constitution_hash)` and `organization_from_role_genomes(root, constitution_hash)`.

- [ ] **Step 1: Write RED 16X adapter tests**

Map a legacy `ArchitecturePolicy` without modifying it. Assert:
- all engine IDs remain represented;
- legacy waves become ordered execution groups;
- architecture operators are preserved only in lineage/routing metadata, not reinterpreted as new capabilities;
- source policy hash is preserved in lineage;
- resulting OrganizationPolicy is `LEGACY_REFERENCE`, not a new active champion.

- [ ] **Step 2: Write RED C0-C7 adapter tests**

Load all eight role genomes. Map each slot to one WorkerRole and ResourceRequirement using existing hard/soft capabilities only. Preserve mandatory review relations as `REVIEW` edges and C0 synchronization ownership as `SYNCHRONIZE` relations where the existing catalog supports it. Do not materialize new Role Genomes.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_organization_legacy.py -q
```

- [ ] **Step 4: Implement deterministic adapters**

Adapters may depend on legacy modules; Core `resource_descriptor.py` and `organization_policy.py` must not import legacy ArchitecturePolicy, DevFabric, Supabase, Cloudflare, OpenAI, or A2A packages.

- [ ] **Step 5: Prove source immutability and stable mapping**

Round-trip source policy hashes must remain unchanged. Calling the adapter twice produces identical OrganizationPolicy hashes. Existing federation role profile hashes remain unchanged.

- [ ] **Step 6: Run GREEN and federation regressions**

```bash
python -m pytest tests/test_organization_legacy.py tests/test_organization_policy.py tests/devfabric/test_federation_roles.py tests/devfabric/test_federation_adaptation.py -q
python -m pytest tests/test_controlled_learning_2_3.py -q
```

- [ ] **Step 7: Perform development review for Task 3 and commit**

```bash
git add metaengine/organization_legacy.py tests/test_organization_legacy.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: map legacy organizations into organization policy'
```

---

### Task 4: Slice 2 Review Receipt and Slice 3 Admission

**Files:**
- Create: `devfabric/artifacts/reviews/development/metaengine-1-slice-2-review.json`
- Create: `devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-2-*.json`
- Create: `tests/devfabric/test_organization_policy_review_artifact.py`

**Interfaces:**
- Consumes: Development Evolution Review Gate and final Slice 2 implementation commit.
- Produces: verified admission `METAENGINE-1-SLICE-2 → METAENGINE-1-SLICE-3`.

- [ ] **Step 1: Write RED admission artifact tests**

Receipt must be required, current-context bound, tamper-resistant, and block Slice 3 after Constitution/Library/Policy drift.

- [ ] **Step 2: Run clean final verification on completed Slice 2 implementation commit**

```bash
python -m pytest tests/test_resource_descriptor.py tests/test_organization_policy.py tests/test_organization_legacy.py tests/test_constitution_kernel.py -q
python -m pytest tests/devfabric -q
python -m pytest tests/test_controlled_learning_2_3.py -q
python -m compileall -q metaengine
(cd devfabric/cloudflare && npm run test:core)
git diff --check
```

Also perform read-only canonical state verification: cp001/current active policy unchanged; adaptation receipts remain zero unless a separately authorized later experiment changed them.

- [ ] **Step 3: Perform mandatory post-step Constitution/Library/Policy analysis**

Compare:
- CURRENT typed Resource/Organization IR;
- MINIMAL generic JSON/pairs-only schema;
- LIBRARY A2A Agent Card/task + Agents SDK composition semantics;
- SYNTHESIS Core IR + adapter ecosystem.

Explicitly review whether ResourceDescriptor duplicated DevFabric ProviderDescriptor unnecessarily, whether OrganizationPolicy still contains provider-specific assumptions, and whether the legacy adapters overclaim semantics.

- [ ] **Step 4: Create Slice 2 review receipt**

Decision may be `ACCEPT_CONTINUE` only if all fresh verification is green and no K0/K1 conflict or canonical mutation occurred.

- [ ] **Step 5: Prove Slice 3 admission and commit governance artifacts**

```bash
python -m pytest tests/devfabric/test_organization_policy_review_artifact.py tests/devfabric/test_constitution_review_artifact.py -q
git add devfabric/artifacts/reviews/development tests/devfabric/test_organization_policy_review_artifact.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'docs: certify METAENGINE-1 slice 2 organization policy'
```

Do not begin Slice 3 Architecture Source Registry until the committed receipt reloads and admits the exact transition.

---

## Plan Self-Review Mapping

- Provider/model-independent `ResourceDescriptor v1` → Task 1.
- `UNOBSERVED` evidence semantics → Task 1.
- OrganizationPolicy conceptual schema and supported initial organizations → Task 2.
- Canonical hashing/lineage → Tasks 1-2.
- Legacy 16X adapter without mutation → Task 3.
- C0-C7 federation representation without Role Genome mutation → Task 3.
- No canonical champion/D6-G1/MCP change → Global Constraints + Task 4 regressions.
- Mandatory Constitution/Architecture-Library/Policy review → after Tasks 1-3 and formal receipt in Task 4.
- No new runtime dependencies/provider-specific Core logic → Global Constraints and import-boundary tests.

Placeholder scan: no unresolved implementation markers remain.
