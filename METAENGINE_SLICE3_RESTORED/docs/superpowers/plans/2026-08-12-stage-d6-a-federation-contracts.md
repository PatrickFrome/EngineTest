# Stage D.6-A Federation Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the immutable eight-slot federation vocabulary, versioned Role Genomes, and content-addressed federated task/candidate contracts without changing existing Stage A–D hashes.

**Architecture:** Preserve the existing `TaskEnvelope` and `CandidateReceipt` unchanged for backward compatibility. Add composition-based `FederatedTaskEnvelope` and `FederatedCandidateReceipt` that hash the existing object digest plus epoch/role/fencing metadata.

**Tech Stack:** Python dataclasses/enums, `metaengine.devfabric.codec.canonical_digest`, JSON role artifacts, pytest.

## Global Constraints

- Exactly `C0`…`C7`; no dynamic ninth slot.
- Existing `TaskEnvelope.create()` and `CandidateReceipt.create()` behavior/hashes must not change.
- Role hard fields cannot be mutated by soft adaptation.
- Federation hashes must include epoch, task version, role profile, lease generation, checkpoint, dependency/read/write/interface sets, integration mode, review slots, and blind-group ID.
- No secrets or runtime session state in role JSON.

---

### Task 1: Federation enums and slot catalog

**Files:**
- Create: `metaengine/devfabric/federation/__init__.py`
- Create: `metaengine/devfabric/federation/types.py`
- Create: `chat_federation/ROLE_CATALOG.json`
- Test: `tests/devfabric/test_federation_roles.py`

**Interfaces:**
- Produces: `SlotId`, `SlotState`, `IntegrationMode`, `ConflictClass`, `CandidateEligibility`, `SLOT_ORDER`.

- [ ] **Step 1: Write the failing slot-count/order test**

```python
from metaengine.devfabric.federation.types import SLOT_ORDER, SlotId

def test_federation_defines_exactly_eight_ordered_slots():
    assert SLOT_ORDER == tuple(SlotId(f"C{i}") for i in range(8))
    assert len(set(SLOT_ORDER)) == 8
```

- [ ] **Step 2: Run RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_roles.py
```

Expected: import failure for `metaengine.devfabric.federation.types`.

- [ ] **Step 3: Implement exact enums**

```python
class SlotId(str, Enum):
    C0="C0"; C1="C1"; C2="C2"; C3="C3"; C4="C4"; C5="C5"; C6="C6"; C7="C7"

class SlotState(str, Enum):
    ACTIVE="ACTIVE"; IDLE="IDLE"; REVIEW_ONLY="REVIEW_ONLY"; SUSPENDED="SUSPENDED"; RECLAIMABLE="RECLAIMABLE"

class IntegrationMode(str, Enum):
    EXCLUSIVE="EXCLUSIVE"; PARALLEL="PARALLEL"; REDUNDANT="REDUNDANT"; IMPLEMENT_REVIEW="IMPLEMENT_REVIEW"

class CandidateEligibility(str, Enum):
    ELIGIBLE="ELIGIBLE"; STALE_FENCED="STALE_FENCED"; STALE_TASK_VERSION="STALE_TASK_VERSION"; MISSING_REVIEW="MISSING_REVIEW"; REJECTED="REJECTED"

class ConflictClass(str, Enum):
    PATH_WRITE_CONFLICT="PATH_WRITE_CONFLICT"
    INTERFACE_CONTRACT_CONFLICT="INTERFACE_CONTRACT_CONFLICT"
    DEPENDENCY_VERSION_CONFLICT="DEPENDENCY_VERSION_CONFLICT"
    STALE_BASE_CONFLICT="STALE_BASE_CONFLICT"
    SEMANTIC_DECISION_CONFLICT="SEMANTIC_DECISION_CONFLICT"
    VERIFICATION_CONFLICT="VERIFICATION_CONFLICT"
    PRIVACY_POLICY_CONFLICT="PRIVACY_POLICY_CONFLICT"

SLOT_ORDER = tuple(SlotId(f"C{i}") for i in range(8))
```

- [ ] **Step 4: Write `ROLE_CATALOG.json` with all eight semantic roles**

The file must map exactly:

```json
{"C0":"SYNCHRONIZER_INTEGRATOR","C1":"ARCHITECTURE","C2":"CORE_ENGINE","C3":"AI_SWARM","C4":"EDGE_MCP","C5":"DATA_SERVICES","C6":"VERIFICATION_SECURITY","C7":"RESEARCH_BENCHMARK"}
```

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_roles.py
git add metaengine/devfabric/federation chat_federation/ROLE_CATALOG.json tests/devfabric/test_federation_roles.py
git commit -m "feat(d6): define federation slots and roles"
```

### Task 2: Hard/soft Role Genome

**Files:**
- Create: `metaengine/devfabric/federation/roles.py`
- Create: `chat_federation/ROLE_GENOMES/C0.json` … `C7.json`
- Modify: `tests/devfabric/test_federation_roles.py`

**Interfaces:**
- Produces: `HardRoleGenome`, `SoftRoleGenome`, `RoleGenome`, `load_role_genome(root: Path, slot: SlotId) -> RoleGenome`, `RoleGenome.with_soft_update(changes: Mapping[str, object]) -> RoleGenome`.

- [ ] **Step 1: Write RED proving hard fields cannot change through soft update**

```python
def test_soft_update_cannot_change_hard_authority(tmp_path):
    genome = load_role_genome(PROJECT_ROOT, SlotId.C6)
    updated = genome.with_soft_update({"capability_weights": {"security": 0.95}})
    assert updated.hard == genome.hard
    assert updated.profile_hash != genome.profile_hash
```

- [ ] **Step 2: Implement frozen genome objects**

Use:

```python
@dataclass(frozen=True)
class HardRoleGenome:
    slot: SlotId
    role: str
    authority_boundaries: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    subsystem_ownership: tuple[str, ...]
    privacy_ceiling: PrivacyClass
    mandatory_reviewers: tuple[SlotId, ...]
    allowed_integration_modes: tuple[IntegrationMode, ...]

@dataclass(frozen=True)
class SoftRoleGenome:
    capability_weights: tuple[tuple[str, float], ...]
    preferred_workers: tuple[str, ...]
    preferred_task_classes: tuple[str, ...]
    review_pairings: tuple[SlotId, ...]
    exploration_weight: float
    concurrency_preference: int
    provider_priors: tuple[tuple[str, float], ...]
```

`RoleGenome.profile_hash` must be `canonical_digest({"version": version, "hard": hard, "soft": soft})`.

- [ ] **Step 3: Populate all eight JSON genomes**

Use this exact hard-role matrix; every row also prohibits `CANONICAL_BYPASS` and `SECRET_RETRIEVAL`:

| Slot | Role | Ownership | Mandatory reviewers | Extra prohibition |
|---|---|---|---|---|
| C0 | SYNCHRONIZER_INTEGRATOR | epoch integration, dependency graph, synchronization snapshots | C6 for HIGH/RELEASE integration | DIRECT_PROMOTION |
| C1 | ARCHITECTURE | architecture contracts, ADRs, protocol evolution | C6 for HIGH/RELEASE | DIRECT_CANONICAL_WRITE |
| C2 | CORE_ENGINE | Python core, routing, evidence/policy mechanics, performance | C6 for HIGH/RELEASE | SELF_CERTIFY_HIGH_RISK |
| C3 | AI_SWARM | Ollama/OpenCode/OpenHands/Coder/DevPod orchestration | C6 for HIGH/RELEASE | DIRECT_CANONICAL_WRITE |
| C4 | EDGE_MCP | Cloudflare/MCP/D1/R2/Workflows/Workers AI | C6 for HIGH/RELEASE | DIRECT_CANONICAL_WRITE |
| C5 | DATA_SERVICES | Supabase development schemas, connected services, artifact lineage | C6 for HIGH/RELEASE | DIRECT_PROMOTION |
| C6 | VERIFICATION_SECURITY | deterministic verification, CI, reproducibility, security | C1 for architecture-affecting C6 production changes | SOLE_AUTHOR_AND_CERTIFIER |
| C7 | RESEARCH_BENCHMARK | research, benchmarks, baselines, statistics, falsification | C6 for executable benchmark harness changes | DIRECT_CANONICAL_WRITE |

Set privacy ceiling `P3` for local-capable C2/C3/C6 work but retain the global external P3 deny rule; other roles use ceiling `P2`. Allowed integration modes are all four except C6 defaults to `IMPLEMENT_REVIEW`/`PARALLEL` and C0 does not author `REDUNDANT` candidates.

- [ ] **Step 4: Validate bounds**

Reject soft weights outside `[0.0,1.0]`, exploration outside `[0.0,0.25]`, and concurrency preference outside `[2,6]`. Reject any JSON whose `slot` does not match its filename.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_roles.py
git add metaengine/devfabric/federation/roles.py chat_federation/ROLE_GENOMES tests/devfabric/test_federation_roles.py
git commit -m "feat(d6): add versioned role genomes"
```

### Task 3: Federated TaskEnvelope

**Files:**
- Create: `metaengine/devfabric/federation/contracts.py`
- Test: `tests/devfabric/test_federation_contracts.py`

**Interfaces:**
- Consumes: existing `TaskEnvelope`.
- Produces: `FederatedTaskEnvelope.create(*, base_task: TaskEnvelope, epoch_id: str, task_version: int, owner_slot: SlotId, lease_generation: int, role_profile_hash: str, base_checkpoint_id: str, dependency_task_ids: Iterable[str], read_set: Iterable[str], write_set: Iterable[str], interface_set: Iterable[str], integration_mode: IntegrationMode, review_slots: Iterable[SlotId], blind_group_id: str | None = None) -> FederatedTaskEnvelope`.

- [ ] **Step 1: Write RED that changing lease generation or role profile changes `task_hash` while the base Stage A task hash stays identical**

```python
base = TaskEnvelope.create(
    source_checkpoint_id="cp1",
    source_tree_hash="b"*64,
    objective="change router",
    acceptance_tests=("python -m pytest -q",),
    allowed_paths=("metaengine/",),
    forbidden_paths=("lineages/",),
    capabilities_required=("python",),
    risk_class=RiskClass.HIGH,
    privacy_class=PrivacyClass.P1,
)
a = FederatedTaskEnvelope.create(base_task=base, epoch_id="epoch-1", task_version=1, owner_slot=SlotId.C2, lease_generation=3, role_profile_hash="a"*64, base_checkpoint_id="cp1", dependency_task_ids=(), read_set=("metaengine/",), write_set=("metaengine/core.py",), interface_set=("router-v1",), integration_mode=IntegrationMode.EXCLUSIVE, review_slots=(SlotId.C6,))
b = dataclasses.replace(a, lease_generation=4)
assert a.base_task.task_hash == base.task_hash
assert a.task_hash != b.task_hash
```

- [ ] **Step 2: Implement immutable contract**

Hash payload must use `base_task.task_hash` plus sorted set-like fields. `task_id` is `ftask-<first20>`; `blind_group_id` is optional and serialized as `None` when absent.

- [ ] **Step 3: Add validation**

Reject negative/zero `task_version`, negative lease generation, `base_checkpoint_id != base_task.source_checkpoint_id`, owner slot missing from review/role rules when required, or duplicate self-review for C6 high-risk configuration.

- [ ] **Step 4: Run GREEN**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_contracts.py
```

### Task 4: Federated CandidateReceipt and ReviewReceipt

**Files:**
- Modify: `metaengine/devfabric/federation/contracts.py`
- Modify: `tests/devfabric/test_federation_contracts.py`

**Interfaces:**
- Consumes: existing `CandidateReceipt`, `VerificationReceipt` hashes.
- Produces: `FederatedCandidateReceipt.create(*, base_candidate: CandidateReceipt, task: FederatedTaskEnvelope, slot_id: SlotId, session_id: str, lease_generation: int, patch_digest: str, interface_changes: Iterable[str], verification_hashes: Iterable[str], claims: Iterable[str], risks: Iterable[str], dependency_observations: Iterable[str], summary: str) -> FederatedCandidateReceipt` and `FederatedReviewReceipt.create(*, candidate_hash: str, reviewer_slot: SlotId, session_id: str, lease_generation: int, verification_hashes: Iterable[str], verdict: Verdict) -> FederatedReviewReceipt`.

- [ ] **Step 1: Write RED for stale-generation hash binding**

Candidate hash must change when `session_id`, `lease_generation`, task version, interface changes, verification refs, or claims/risks change.

- [ ] **Step 2: Implement exact receipt fields**

```python
@dataclass(frozen=True)
class FederatedCandidateReceipt:
    candidate_hash: str
    base_candidate_hash: str
    task_hash: str
    epoch_id: str
    task_version: int
    slot_id: SlotId
    session_id: str
    lease_generation: int
    role_profile_hash: str
    base_checkpoint_id: str
    patch_digest: str
    changed_paths: tuple[str, ...]
    interface_changes: tuple[str, ...]
    verification_hashes: tuple[str, ...]
    claims: tuple[str, ...]
    risks: tuple[str, ...]
    dependency_observations: tuple[str, ...]
    summary: str
```

`FederatedReviewReceipt` must bind `candidate_hash`, reviewer slot/session/generation, verifier hashes, verdict, and review hash.

- [ ] **Step 3: Preserve content-addressing**

Require 64-hex digests for `patch_digest`, `role_profile_hash`, and all verification hashes. Large patch/source/log bodies are forbidden fields.

- [ ] **Step 4: Run full D6-A gate and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_roles.py tests/devfabric/test_federation_contracts.py
python -m metaengine.devfabric.pytest_runner -q tests/devfabric
python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric
python -m compileall -q metaengine
git add metaengine/devfabric/federation chat_federation tests/devfabric/test_federation_roles.py tests/devfabric/test_federation_contracts.py
git commit -m "feat(d6): add federated task and candidate contracts"
```
