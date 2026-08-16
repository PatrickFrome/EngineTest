# METAENGINE-1 Slice 1 Constitutional Kernel v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile MetaEngine's constitutional rules into a deterministic K0/K1 kernel with a stable hash, machine-readable conformance matrix, closed 5-of-6 handoff gap, and a fail-closed amendment boundary, while preserving all historical hashes and current canonical policy state.

**Architecture:** Use declarative JSON for K0/K1 data and a small dependency-free Python compiler/validator. The kernel exposes `k0_hash`, `k1_hash`, and composite `constitution_hash`; K0 remains compact/general while a conformance matrix carries specific enforcement/test references. Existing 2.3 guardrail hashes remain unchanged and readable, but current handoff execution must require all six legacy guardrails. No OPA/Rego runtime, JSON-Schema dependency, network service, or canonical mutation is introduced.

**Tech Stack:** Python 3.13 stdlib, existing Core `metaengine.util.canonical_hash`, JSON config, pytest, Git.

## Global Constraints

- Slice 0 transition admission is already proven by receipt `235013a00c9e3598227576c20024cde4e10656ed876513f063e1ca6c4b3a7543`.
- Selected architecture after Constitution/Library/Policy comparison: declarative K0/K1 JSON + Python compiler/checker + explicit conformance matrix.
- OPA/Rego is not introduced in Slice 1; it remains a future plugin candidate if cross-language/distributed policy evaluation later justifies its complexity.
- JSON Schema is not treated as semantic enforcement; structural validation stays inside the dependency-free compiler in Slice 1.
- K0 contains exactly the 12 invariants approved in the METAENGINE-1 design.
- K1 contains the approved research-governance topics and an amendment boundary with `ordinary_evolution_allowed = false` and no implemented amendment authority.
- `IMMUTABLE_GUARDRAILS` ordering and `IMMUTABLE_GUARDRAIL_HASH = 7ca26b082e1c4dc1de5f3d098f957d0330a5b9f2cf70da12160a672c01a2eb38` must remain byte-for-byte semantically stable.
- Historical incomplete 5-guardrail handoffs may be classified/read as legacy evidence but must not verify as current executable handoffs.
- Current `ArchitecturePolicy`, D6-G1 shadow adaptation, cp001, champion/active policy, Supabase authority, and 18-tool MCP surface must remain unchanged.
- `constitution_hash` is a new lineage anchor and must not retroactively replace historical `guardrail_hash` values.
- No external source code is downloaded or imported in Slice 1.
- Slice 1 is the gate-bearing DevelopmentStep. Internal Tasks 1–3 are implementation substeps; Task 4 creates the mandatory Development Evolution Review Receipt before Slice 2.

---

### Task 1: Canonical K0/K1 Constitution Kernel

**Files:**
- Create: `config/constitution/k0_v1.json`
- Create: `config/constitution/k1_v1.json`
- Create: `metaengine/constitution.py`
- Create: `tests/test_constitution_kernel.py`
- Modify: `config/development_review_bootstrap_v1.json`

**Interfaces:**
- Consumes: Core `metaengine.util.canonical_hash`; Constitutional Kernel must not depend on DevFabric.
- Produces: `ConstitutionInvariant`, `ConstitutionKernel`, `ConstitutionAmendmentBoundary`, `load_constitution_kernel(root)`, `constitution_hash(root)`.

- [ ] **Step 1: Write RED tests for deterministic K0/K1 loading**

Create tests that require:

```python
from pathlib import Path
import pytest

from metaengine.constitution import load_constitution_kernel

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_K0_IDS = {
    "PROVENANCE_PRIMARY_EVIDENCE",
    "CANONICAL_NOT_SCIENTIFIC_TRUTH",
    "NO_TRUTH_FROM_RANKING_OR_VOTING",
    "PRESERVE_ABSTENTION",
    "MUTATION_REQUIRES_RECEIPT",
    "SEPARATE_GENERATION_AND_PROMOTION",
    "FROZEN_EVALUATION_CONTRACT",
    "NO_NORMAL_KERNEL_SELF_MUTATION",
    "NO_EXECUTABLE_SELF_MODIFICATION",
    "PRIVACY_PERMISSION_FAIL_CLOSED",
    "IMMUTABLE_HISTORY_WITH_SUPERSESSION",
    "ROLLBACK_RECOVERY_REQUIRED",
}


def test_kernel_has_exact_k0_invariants_and_deterministic_hash():
    left = load_constitution_kernel(ROOT)
    right = load_constitution_kernel(ROOT)
    assert {item.invariant_id for item in left.k0_invariants} == EXPECTED_K0_IDS
    assert len(left.k0_invariants) == 12
    assert left.k0_hash == right.k0_hash
    assert left.k1_hash == right.k1_hash
    assert left.constitution_hash == right.constitution_hash
    assert len(left.constitution_hash) == 64


def test_normal_evolution_has_no_constitution_amendment_authority():
    kernel = load_constitution_kernel(ROOT)
    assert kernel.amendment_boundary.ordinary_evolution_allowed is False
    assert kernel.amendment_boundary.authority_status == "NOT_IMPLEMENTED"
    with pytest.raises(RuntimeError, match="CONSTITUTION_AMENDMENT_AUTHORITY_NOT_IMPLEMENTED"):
        kernel.require_amendment_authority()
```

Also add temp-config tests proving duplicate/missing K0 IDs and empty K1 topics fail closed.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_constitution_kernel.py -q
```

Expected: import failure because `metaengine.constitution` does not exist.

- [ ] **Step 3: Create declarative K0/K1 files**

`k0_v1.json` must encode the 12 approved IDs and concise statements. Include a `legacy_guardrail_ids` list per invariant where current 2.3 guardrails provide a predecessor mapping; do not invent mappings for invariants without a legacy equivalent.

`k1_v1.json` must contain these topics exactly as named in the design:

- `RESOURCE_NORMALIZATION`
- `MINIMUM_SUFFICIENT_ORGANIZATION`
- `COMPLEXITY_TAX`
- `DEVELOPMENT_VS_SCIENTIFIC_FEDERATION`
- `REPLICATION_DEFINITION`
- `EVIDENCE_CONFIDENCE_LEVELS`
- `EXTERNAL_SEALED_BENCHMARK_REQUIREMENTS`
- `ARCHITECTURE_ASSIMILATION_RULES`
- `DEVELOPMENT_EVOLUTION_REVIEW`
- `PROVIDER_MODEL_INDEPENDENCE`
- `PROMOTION_EVIDENCE_CEILINGS`

and:

```json
"amendment_boundary": {
  "ordinary_evolution_allowed": false,
  "authority_status": "NOT_IMPLEMENTED",
  "required_process": "INDEPENDENT_EVIDENCE_GATED_CONSTITUTIONAL_AMENDMENT"
}
```

- [ ] **Step 4: Implement minimal compiler/validator**

`ConstitutionKernel` must expose explicit payload methods. Hash semantics:

```python
k0_hash = canonical_hash({"k0_version": ..., "invariants": [...]})
k1_hash = canonical_hash({"k1_version": ..., "topics": [...], "amendment_boundary": ...})
constitution_hash = canonical_hash({
    "constitution_kernel_version": "METAENGINE-CONSTITUTION-KERNEL-1",
    "k0_hash": k0_hash,
    "k1_hash": k1_hash,
})
```

Validation must reject duplicate K0 IDs, missing/extra required K0 IDs, duplicate/empty K1 topics, mutable amendment boundary, or a claimed amendment authority other than `NOT_IMPLEMENTED` in Slice 1.

- [ ] **Step 5: Bind Development Review bootstrap context to compiled constitution sources**

Extend `constitution_paths` in `config/development_review_bootstrap_v1.json` to include:

```text
config/constitution/k0_v1.json
config/constitution/k1_v1.json
metaengine/constitution.py
```

Keep the existing legacy sources in the list so the Slice 1 review sees both compiled and legacy constitutional semantics until global migration in Slice 5.

- [ ] **Step 6: Run GREEN and regressions**

```bash
python -m pytest tests/test_constitution_kernel.py tests/devfabric/test_development_review.py tests/devfabric/test_development_gate.py -q
python -m compileall -q metaengine
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1 implementation**

```bash
git add config/constitution metaengine/constitution.py tests/test_constitution_kernel.py config/development_review_bootstrap_v1.json
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: compile METAENGINE constitutional kernel'
```

---

### Task 2: Machine-Readable Constitution Conformance Matrix

**Files:**
- Create: `config/constitution/conformance_matrix_v1.json`
- Modify: `metaengine/constitution.py`
- Modify: `tests/test_constitution_kernel.py`
- Modify: `config/development_review_bootstrap_v1.json`

**Interfaces:**
- Consumes: Task 1 kernel.
- Produces: `ConstitutionConformanceEntry`, `ConstitutionConformanceReport`, `verify_constitution_conformance(root)`.

- [ ] **Step 1: Write RED conformance tests**

Require:

```python
def test_conformance_matrix_covers_every_k0_invariant_once():
    report = verify_constitution_conformance(ROOT)
    assert report.valid is True
    assert report.mapped_invariant_count == 12
    assert report.unmapped_invariants == ()
    assert report.duplicate_invariants == ()


def test_conformance_matrix_requires_enforcement_and_test_refs(tmp_path):
    root = copy_constitution_fixture(tmp_path)
    matrix = load_json(root / "config/constitution/conformance_matrix_v1.json")
    matrix["entries"][0]["enforcement_refs"] = []
    write_json(root / "config/constitution/conformance_matrix_v1.json", matrix)
    report = verify_constitution_conformance(root)
    assert report.valid is False
    assert "CONSTITUTION_CONFORMANCE_ENFORCEMENT_REF_REQUIRED" in report.findings
```

Also test missing and duplicate invariant entries.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_constitution_kernel.py -q
```

Expected: FAIL because conformance APIs/file do not exist.

- [ ] **Step 3: Create the initial 12-entry matrix**

Each entry must contain:

```json
{
  "invariant_id": "...",
  "enforcement_refs": ["repository/path.py#symbol-or-contract"],
  "test_refs": ["tests/path.py#test_name"]
}
```

Use real existing enforcement locations. Examples:

- provenance → `metaengine/security.py#verify_handoff`, release integrity, native re-entry source binding;
- no truth from ranking/voting → legacy guardrail + verifier/promotion tests;
- preserve abstention → verifier plane insufficient-evidence behavior;
- mutation requires receipt → architecture mutation receipt + DevFabric/federation receipts;
- separate generation/promotion → `PolicyStore.promote` and D6 integration/review separation;
- frozen evaluation → immutable verifier/benchmark fields;
- no kernel mutation → Task 1 amendment boundary;
- no executable self-modification → evolution policy `self_modifying_code_allowed=false`;
- privacy fail closed → DevFabric P3 policy and Cloudflare pre-network tests;
- immutable history → policy/finalization append-only behavior;
- rollback required → promotion gate + `PolicyStore.rollback`.

Do not claim an enforcement ref that does not exist in the repository.

- [ ] **Step 4: Implement matrix verification**

`verify_constitution_conformance(root)` must:

1. load the current kernel and matrix;
2. reject duplicate/missing/unknown invariant IDs;
3. require non-empty enforcement and test refs for every K0 invariant;
4. require the repository path portion of every ref to exist;
5. return a deterministic report whose `report_hash` is a canonical digest of the validation result.

It does not execute tests dynamically; pytest remains the execution authority.

- [ ] **Step 5: Add matrix to Constitution review snapshot**

Add `config/constitution/conformance_matrix_v1.json` to `constitution_paths`.

- [ ] **Step 6: Run GREEN**

```bash
python -m pytest tests/test_constitution_kernel.py -q
python -m pytest tests/test_controlled_learning_2_3.py -q
```

Expected: PASS before the 5-of-6 behavior change in Task 3.

- [ ] **Step 7: Commit Task 2 implementation**

```bash
git add config/constitution/conformance_matrix_v1.json config/development_review_bootstrap_v1.json metaengine/constitution.py tests/test_constitution_kernel.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: add constitutional conformance matrix'
```

---

### Task 3: Close the Handoff 5-of-6 Gap Without Rewriting History

**Files:**
- Modify: `metaengine/security.py`
- Modify: `tests/test_controlled_learning_2_3.py`
- Modify: `tests/test_constitution_kernel.py`

**Interfaces:**
- Consumes: current six-element `IMMUTABLE_GUARDRAILS`, stable legacy hash, compiled K0 mapping.
- Produces: current complete handoff verification and `legacy_guardrail_set_status()` for read-only historical classification.

- [ ] **Step 1: Write RED regression for the sixth guardrail**

First update the valid `handoff()` test fixture to supply all six current guardrails, then add:

```python
def test_current_handoff_rejects_missing_self_update_guardrail():
    value = handoff()
    value["guardrails"] = list(IMMUTABLE_GUARDRAILS[:5])
    value["handoff_hash"] = canonical_hash({k: v for k, v in value.items() if k != "handoff_hash"})
    with pytest.raises(SecurityViolation, match="SELF_UPDATE_CANNOT_MUTATE_VERIFIERS_OR_SAFETY_BOUNDARY"):
        verify_handoff(value)
```

Add a separate test that classifies the old 5-element set as historical/read-only rather than executable.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_controlled_learning_2_3.py::test_current_handoff_rejects_missing_self_update_guardrail -q
```

Expected: FAIL because current `verify_handoff()` still checks `IMMUTABLE_GUARDRAILS[:5]`.

- [ ] **Step 3: Implement the minimal security fix**

Change only current verification semantics:

```python
missing = tuple(rule for rule in IMMUTABLE_GUARDRAILS if rule not in supplied)
```

Do not reorder or rename the six legacy strings and do not change `IMMUTABLE_GUARDRAIL_HASH`.

Add a read-only classifier:

```python
LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3 = IMMUTABLE_GUARDRAILS[:5]
LEGACY_INCOMPLETE_HANDOFF_GUARDRAIL_HASH_2_3 = canonical_hash(LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3)


def legacy_guardrail_set_status(supplied):
    if tuple(supplied) == IMMUTABLE_GUARDRAILS:
        return "CURRENT_COMPLETE"
    if tuple(supplied) == LEGACY_INCOMPLETE_HANDOFF_GUARDRAILS_2_3:
        return "LEGACY_INCOMPLETE_READ_ONLY"
    return "UNKNOWN"
```

This function does not authorize execution.

- [ ] **Step 4: Prove legacy hash stability and compiled mapping**

Add tests asserting:

```python
assert IMMUTABLE_GUARDRAIL_HASH == "7ca26b082e1c4dc1de5f3d098f957d0330a5b9f2cf70da12160a672c01a2eb38"
assert legacy_guardrail_set_status(IMMUTABLE_GUARDRAILS[:5]) == "LEGACY_INCOMPLETE_READ_ONLY"
```

and that every legacy guardrail string is referenced by at least one K0 invariant's `legacy_guardrail_ids`.

- [ ] **Step 5: Run GREEN and security regressions**

```bash
python -m pytest tests/test_controlled_learning_2_3.py tests/test_constitution_kernel.py -q
python -m pytest tests/devfabric/test_review.py tests/devfabric/test_gate.py tests/devfabric/test_development_review.py tests/devfabric/test_development_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3 implementation**

```bash
git add metaengine/security.py tests/test_controlled_learning_2_3.py tests/test_constitution_kernel.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'fix: enforce complete constitutional handoff guardrails'
```

Record this commit as the completed implementation state for `METAENGINE-1-SLICE-1`.

---

### Task 4: Slice 1 Constitutional/Library/Policy Review and Slice 2 Admission

**Files:**
- Create: `devfabric/artifacts/reviews/development/metaengine-1-slice-1-review.json`
- Create: `devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-1-*.json`
- Create: `tests/devfabric/test_constitution_review_artifact.py`

**Interfaces:**
- Consumes: Slice 0 Development Evolution Review Gate and final Slice 1 implementation commit.
- Produces: first review receipt using the compiled Constitution sources and proof of `METAENGINE-1-SLICE-1 → METAENGINE-1-SLICE-2` admission.

- [ ] **Step 1: Write RED artifact/admission tests**

Require the receipt file to exist, pass `DevelopmentEvolutionReviewReceipt.from_dict()`, match the current review context, and admit Slice 2. A modified `k0_v1.json` snapshot or blocking decision must deny admission.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/devfabric/test_constitution_review_artifact.py -q
```

Expected: FAIL because the Slice 1 review receipt does not exist.

- [ ] **Step 3: Run fresh final verification on the clean Slice 1 implementation commit**

Use a clean detached worktree at the Task 3 commit. Restore only a generated `devfabric/CAPSULE_MANIFEST.json` if the known CONTROL-runtime bootstrap tests require it. Run:

```bash
python -m pytest tests/test_constitution_kernel.py tests/test_controlled_learning_2_3.py -q
python -m pytest tests/devfabric -q
python -m compileall -q metaengine
(cd devfabric/cloudflare && npm run test:core)
git diff --check
```

Record content-addressed evidence receipts without timestamps or secrets.

- [ ] **Step 4: Perform the mandatory post-step analysis**

Review all five domains:

**Constitution**
- K0 remains exactly 12 immutable invariants;
- K1 has no ordinary amendment path;
- the 5-of-6 gap is closed;
- legacy guardrail hash remains unchanged;
- identify any invariant whose enforcement remains only partial for future work.

**Architecture/Mechanism Library**
- compare CURRENT compiled JSON/Python kernel against MINIMAL tuple-only guardrails, LIBRARY policy-as-code pattern (OPA-style decision/enforcement separation), and SYNTHESIS compact-general-principles + specific conformance matrix;
- retain the no-new-runtime-dependency choice unless evidence now favors OPA/Rego.

**Policy**
- verify `ArchitecturePolicy`, D6-G1 adaptation, evolution policy, cp001/champion semantics are unchanged;
- classify the new kernel as Core, not plugin, while amendment authority remains external/not implemented.

**Code/architecture decision**
- explicitly decide whether the compiled kernel is accepted, revised, reverted, or needs experiment.

**Next step**
- Slice 2 OrganizationPolicy/ResourceDescriptor is allowed only if the review decision permits continuation.

- [ ] **Step 5: Create and verify the Slice 1 review receipt**

Use `DevelopmentEvolutionReviewReceipt.create()` with all four alternatives (`CURRENT`, `MINIMAL`, `LIBRARY`, `SYNTHESIS`) and current Constitution/Library/Policy snapshots. Decision may be `ACCEPT_CONTINUE` only if all fresh verification evidence is green and no K0 conflict is found.

- [ ] **Step 6: Run artifact tests and transition proof**

```bash
python -m pytest tests/devfabric/test_constitution_review_artifact.py tests/devfabric/test_development_review_artifact.py -q
```

Then call `verify_development_transition()` for `METAENGINE-1-SLICE-1 → METAENGINE-1-SLICE-2`; expected `allowed=True` only with the exact receipt/context.

- [ ] **Step 7: Commit governance artifacts**

```bash
git add devfabric/artifacts/reviews/development tests/devfabric/test_constitution_review_artifact.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'docs: certify METAENGINE-1 slice 1 constitutional kernel'
```

Do not start Slice 2 until the committed receipt is reloaded and transition verification succeeds.

---

## Plan Self-Review Mapping

- Canonical K0 representation + hash → Task 1.
- K1 research governance + amendment boundary skeleton → Task 1.
- Conformance matrix → Task 2.
- All 12 K0 IDs mapped to enforcement/tests → Task 2.
- 5-of-6 handoff fix → Task 3.
- Legacy guardrail compatibility/no history rewrite → Task 3.
- Development review context now includes compiled Constitution sources → Tasks 1–2.
- No current champion/cp001/D6-G1/MCP mutation → Global Constraints + Task 4 regression.
- Mandatory Constitution/Library/Policy re-analysis before next slice → Task 4.
- No new runtime dependency → Global Constraints; OPA/Rego explicitly retained as deferred alternative.

Placeholder scan: no unresolved implementation markers or unspecified code steps remain.
