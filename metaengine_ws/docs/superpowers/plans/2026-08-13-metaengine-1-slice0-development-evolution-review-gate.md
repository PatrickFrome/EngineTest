# METAENGINE-1 Slice 0 Development Evolution Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deterministic, content-addressed development transition gate so every completed MetaEngine development step must review the Constitution, Architecture/Mechanism Library, current policies, and alternatives before the next gate-bearing step can begin.

**Architecture:** Slice 0 adds a pure Python review protocol with canonical receipts, deterministic file-snapshot hashing, and a transition checker. The checker remains METAENGINE-1-local for now: it validates explicit completed-step identity/evidence plus current Constitution/Library/Policy snapshot hashes and admits exactly those decisions whose protocol semantics allow continuation. Slice 0 then reviews itself, records a tracked governance receipt, and proves that Slice 1 is blocked without that receipt and allowed with it. No canonical database, champion, D6-G1 adaptation state, MCP surface, or existing policy is mutated.

**Tech Stack:** Python 3.13, frozen dataclasses/enums, existing `metaengine.devfabric.codec.canonical_digest`, pytest, Git.

## Global Constraints

- METAENGINE-1 design source: `docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md` at design commit `0752b3f`.
- No normal development step may advance without a valid `DevelopmentEvolutionReviewReceipt` once Slice 0 is active.
- Review order is Constitution → Architecture/Mechanism Library → Policy → alternatives → decision → receipt.
- Review receipts are content-addressed and append-only artifacts; they never rewrite prior development evidence.
- A review receipt must bind the completed implementation commit and at least one deterministic verification evidence hash.
- Constitution, Architecture/Mechanism Library, and policy snapshots are explicit content hashes over ordered path/hash manifests; no conversational memory is authoritative.
- `next_step_allowed` is derived from the decision and cannot be supplied independently by callers.
- Only `ACCEPT_CONTINUE` and `ACCEPT_WITH_FOLLOWUP_EXPERIMENT` admit the next gate-bearing step in Slice 0.
- `REVISE_BEFORE_CONTINUE`, `REVERT_BEFORE_CONTINUE`, `DEFER_EXPERIMENT_REQUIRED`, and `BLOCK_CONSTITUTIONAL_CONFLICT` must fail closed.
- Slice 0 must not change cp001, current champion/active architecture policy, Supabase canonical state, D6-G1 shadow-only semantics, or the 18-tool federation MCP surface.
- Slice 0 must not introduce network calls, downloaded code, new runtime dependencies, provider-specific Core logic, or secrets.
- The tracked Slice 0 self-review receipt is a governance artifact created after the implementation commit; it references the implementation commit rather than attempting a self-referential Git hash.

---

### Task 1: Canonical Development Review Receipt Protocol

**Files:**
- Create: `metaengine/devfabric/development_review.py`
- Create: `tests/devfabric/test_development_review.py`

**Interfaces:**
- Consumes: `metaengine.devfabric.codec.canonical_digest(value) -> str`.
- Produces: `DevelopmentReviewDecision`, `DevelopmentAlternativeKind`, `DevelopmentAlternative`, `DevelopmentEvolutionReviewReceipt`, and `verify_receipt_integrity()`.

- [ ] **Step 1: Write the failing receipt integrity tests**

Add tests that import the new module and specify the public behavior:

```python
from dataclasses import replace

import pytest

from metaengine.devfabric.development_review import (
    DevelopmentAlternative,
    DevelopmentAlternativeKind,
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewDecision,
    verify_receipt_integrity,
)


def _alternatives():
    return tuple(
        DevelopmentAlternative(kind=kind, summary=f"{kind.value}-summary", evidence_hashes=("a" * 64,))
        for kind in DevelopmentAlternativeKind
    )


def _receipt(decision=DevelopmentReviewDecision.ACCEPT_CONTINUE):
    return DevelopmentEvolutionReviewReceipt.create(
        completed_step_id="METAENGINE-1-SLICE-0-TASK-1",
        completed_step_commit="1" * 40,
        completed_step_evidence_hashes=("2" * 64,),
        constitution_hash="3" * 64,
        architecture_library_snapshot_hash="4" * 64,
        policy_snapshot_hash="5" * 64,
        relevant_mechanism_ids=("LEGACY_GUARDRAILS",),
        alternatives_considered=_alternatives(),
        decision=decision,
        rationale="Current design is the minimal deterministic bootstrap gate.",
        complexity_delta="SMALL_BOUNDED",
        capability_hypothesis="Prevents ungated architectural drift between committed steps.",
        required_followup_experiment="NONE",
        constitutional_findings=("NO_K0_CONFLICT_OBSERVED",),
        library_findings=("BOOTSTRAP_LIBRARY_REVIEWED",),
        policy_findings=("NO_POLICY_AUTHORITY_EXPANSION",),
    )


def test_receipt_hash_is_deterministic_and_integrity_verifies():
    left = _receipt()
    right = _receipt()
    assert left.receipt_hash == right.receipt_hash
    assert verify_receipt_integrity(left).valid is True


def test_next_step_allowed_is_derived_from_decision():
    assert _receipt(DevelopmentReviewDecision.ACCEPT_CONTINUE).next_step_allowed is True
    assert _receipt(DevelopmentReviewDecision.ACCEPT_WITH_FOLLOWUP_EXPERIMENT).next_step_allowed is True
    assert _receipt(DevelopmentReviewDecision.REVISE_BEFORE_CONTINUE).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.REVERT_BEFORE_CONTINUE).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.DEFER_EXPERIMENT_REQUIRED).next_step_allowed is False
    assert _receipt(DevelopmentReviewDecision.BLOCK_CONSTITUTIONAL_CONFLICT).next_step_allowed is False


def test_receipt_tamper_is_detected():
    receipt = _receipt()
    tampered = replace(receipt, rationale="tampered")
    result = verify_receipt_integrity(tampered)
    assert result.valid is False
    assert result.reason == "DEVELOPMENT_REVIEW_RECEIPT_HASH_MISMATCH"


def test_receipt_requires_all_review_domains_and_alternative_kinds():
    receipt = _receipt()
    with pytest.raises(ValueError, match="DEVELOPMENT_REVIEW_ALTERNATIVES_INCOMPLETE"):
        DevelopmentEvolutionReviewReceipt.create(
            **{
                **receipt.creation_fields(),
                "alternatives_considered": (
                    DevelopmentAlternative(
                        kind=DevelopmentAlternativeKind.CURRENT,
                        summary="only current",
                        evidence_hashes=("a" * 64,),
                    ),
                ),
            }
        )
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
python -m pytest tests/devfabric/test_development_review.py -q
```

Expected: FAIL during import because `metaengine.devfabric.development_review` does not exist.

- [ ] **Step 3: Implement the minimal immutable protocol**

Create `development_review.py` with:

```python
class DevelopmentReviewDecision(str, Enum):
    ACCEPT_CONTINUE = "ACCEPT_CONTINUE"
    ACCEPT_WITH_FOLLOWUP_EXPERIMENT = "ACCEPT_WITH_FOLLOWUP_EXPERIMENT"
    REVISE_BEFORE_CONTINUE = "REVISE_BEFORE_CONTINUE"
    REVERT_BEFORE_CONTINUE = "REVERT_BEFORE_CONTINUE"
    DEFER_EXPERIMENT_REQUIRED = "DEFER_EXPERIMENT_REQUIRED"
    BLOCK_CONSTITUTIONAL_CONFLICT = "BLOCK_CONSTITUTIONAL_CONFLICT"


class DevelopmentAlternativeKind(str, Enum):
    CURRENT = "CURRENT"
    MINIMAL = "MINIMAL"
    LIBRARY = "LIBRARY"
    SYNTHESIS = "SYNTHESIS"
```

Add frozen dataclasses for `DevelopmentAlternative`, `DevelopmentEvolutionReviewReceipt`, and `DevelopmentReceiptVerification`. `DevelopmentEvolutionReviewReceipt.create()` must:

1. validate Git SHA length/hex for `completed_step_commit`;
2. require non-empty 64-hex verification evidence hashes;
3. require non-empty Constitution/Library/Policy findings;
4. require exactly one alternative for all four `DevelopmentAlternativeKind` values;
5. derive `next_step_allowed` from `DevelopmentReviewDecision`;
6. canonicalize mechanism IDs/evidence hashes deterministically;
7. calculate `receipt_hash = canonical_digest(payload_without_receipt_hash)`.

Expose `as_dict()`, `creation_fields()`, and `verify_receipt_integrity()` so later tasks can serialize and re-verify the same object without hidden state.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
python -m pytest tests/devfabric/test_development_review.py -q
```

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Run existing DevFabric receipt/review regressions**

Run:

```bash
python -m pytest tests/devfabric/test_gate.py tests/devfabric/test_review.py -q
```

Expected: PASS with no changes to existing gate/review semantics.

- [ ] **Step 6: Commit Task 1**

```bash
git add metaengine/devfabric/development_review.py tests/devfabric/test_development_review.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: add development evolution review receipts'
```

Record the resulting commit as the completed step that must be reviewed before Task 2.

---

### Task 2: Deterministic Constitution / Library / Policy Snapshot Binding

**Files:**
- Modify: `metaengine/devfabric/development_review.py`
- Modify: `tests/devfabric/test_development_review.py`
- Create: `config/development_review_bootstrap_v1.json`

**Interfaces:**
- Consumes: Task 1 receipt protocol.
- Produces: `ContentSnapshot`, `snapshot_paths(root, paths)`, `load_bootstrap_review_context(root)`, and deterministic bootstrap review-domain hashes.

- [ ] **Step 1: Write failing snapshot tests**

Add tests:

```python
def test_snapshot_paths_is_order_independent(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    left = snapshot_paths(tmp_path, ("b.txt", "a.txt"))
    right = snapshot_paths(tmp_path, ("a.txt", "b.txt"))
    assert left.snapshot_hash == right.snapshot_hash
    assert tuple(row["path"] for row in left.files) == ("a.txt", "b.txt")


def test_snapshot_detects_content_change(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    before = snapshot_paths(tmp_path, ("a.txt",))
    (tmp_path / "a.txt").write_text("B")
    after = snapshot_paths(tmp_path, ("a.txt",))
    assert before.snapshot_hash != after.snapshot_hash


def test_bootstrap_context_binds_all_three_review_domains(project_root):
    context = load_bootstrap_review_context(project_root)
    assert len(context.constitution.files) >= 3
    assert len(context.architecture_library.files) >= 2
    assert len(context.policy.files) >= 2
    assert all(len(value.snapshot_hash) == 64 for value in (
        context.constitution, context.architecture_library, context.policy
    ))
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m pytest tests/devfabric/test_development_review.py -q
```

Expected: FAIL because snapshot APIs/config do not exist.

- [ ] **Step 3: Add bootstrap review context manifest**

Create `config/development_review_bootstrap_v1.json` containing only repository-relative paths and a protocol version. Use these initial authoritative inputs:

```json
{
  "review_context_version": "METAENGINE-DEVELOPMENT-REVIEW-BOOTSTRAP-1",
  "constitution_paths": [
    "metaengine/security.py",
    "metaengine/architecture_policy.py",
    "config/evolution_policy_2_3.json",
    ".agents/rules/metaengine-devfabric.md"
  ],
  "architecture_library_paths": [
    "FRONTIER_ARCHITECTURE_INTEGRATION_REPORT_RU.md",
    "ARCHITECTURE_2_3.md",
    "docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md"
  ],
  "policy_paths": [
    "metaengine/architecture_policy.py",
    "config/evolution_policy_2_3.json",
    "docs/superpowers/specs/2026-08-13-stage-d6-g1-finalized-shadow-adaptation-design.md"
  ]
}
```

This is explicitly a bootstrap manifest. Slice 1 replaces the Constitution snapshot source with compiled K0/K1 artifacts; Slice 3 replaces the Architecture Library source with the content-addressed registry. Historical bootstrap receipts remain valid against this manifest and are not rewritten.

- [ ] **Step 4: Implement deterministic file snapshots**

Add frozen dataclasses `ContentSnapshot` and `DevelopmentReviewContext` and functions that:

- reject absolute/escaping paths;
- fail closed if any listed file is missing;
- compute each file SHA-256 from bytes;
- sort by POSIX path;
- compute snapshot hash with `canonical_digest({"version": ..., "files": ...})`;
- load all three domains from `development_review_bootstrap_v1.json`.

Do not parse or semantically reinterpret the source files in Slice 0; semantic review findings remain explicit receipt content. Slice 0 establishes cryptographic binding, not an LLM-as-authority rule engine.

- [ ] **Step 5: Run focused and regression tests**

```bash
python -m pytest tests/devfabric/test_development_review.py tests/devfabric/test_gate.py tests/devfabric/test_review.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add metaengine/devfabric/development_review.py tests/devfabric/test_development_review.py config/development_review_bootstrap_v1.json
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: bind development reviews to source snapshots'
```

Before Task 3 begins, generate and verify a Development Evolution Review Receipt for Task 2 using the transition machinery completed in Task 3 only after its RED/GREEN unit is complete; Task 2 itself is the last bootstrap exception within Slice 0. This exception ends before Slice 1 and is recorded explicitly in the Slice 0 self-review receipt.

---

### Task 3: Fail-Closed Development Transition Checker

**Files:**
- Create: `metaengine/devfabric/development_gate.py`
- Create: `tests/devfabric/test_development_gate.py`

**Interfaces:**
- Consumes: `DevelopmentEvolutionReviewReceipt`, `DevelopmentReviewContext`, and receipt/snapshot verification from Tasks 1–2.
- Produces: `DevelopmentTransitionRequest`, `DevelopmentTransitionResult`, `verify_development_transition()`.

- [ ] **Step 1: Write failing transition tests**

Define a helper that creates a valid receipt against a temporary review context, then add:

```python
def test_next_step_without_receipt_is_blocked(context):
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="S0",
            previous_step_commit="1" * 40,
            next_step_id="S1",
            current_context=context,
            receipt=None,
        )
    )
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_RECEIPT_REQUIRED"


def test_stale_completed_step_commit_is_blocked(context, valid_receipt):
    result = verify_development_transition(request(context, valid_receipt, previous_commit="9" * 40))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_COMPLETED_STEP_MISMATCH"


def test_stale_review_context_is_blocked(context, valid_receipt):
    stale = replace(context, policy=replace(context.policy, snapshot_hash="f" * 64))
    result = verify_development_transition(request(stale, valid_receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_POLICY_SNAPSHOT_STALE"


def test_blocking_decision_cannot_advance(context):
    receipt = valid_receipt_for(context, DevelopmentReviewDecision.BLOCK_CONSTITUTIONAL_CONFLICT)
    result = verify_development_transition(request(context, receipt))
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_DECISION_BLOCKS_NEXT_STEP"


def test_valid_accept_continue_allows_exact_requested_transition(context, valid_receipt):
    result = verify_development_transition(request(context, valid_receipt))
    assert result.allowed is True
    assert result.reason == "DEVELOPMENT_REVIEW_TRANSITION_ALLOWED"
    assert result.next_step_id == "S1"
```

Also test tampered receipt hash, missing evidence hashes, and changed Constitution/Library snapshots.

- [ ] **Step 2: Run transition tests and verify RED**

```bash
python -m pytest tests/devfabric/test_development_gate.py -q
```

Expected: FAIL because `development_gate` does not exist.

- [ ] **Step 3: Implement minimal checker**

`verify_development_transition()` must execute in this order:

1. reject missing receipt;
2. call `verify_receipt_integrity()`;
3. require receipt `completed_step_id` and commit to match the explicit previous step;
4. require receipt Constitution/Library/Policy snapshot hashes to equal `current_context`;
5. require `next_step_allowed is True` and an admissible decision;
6. return an immutable result containing previous/next step IDs, receipt hash, and `allowed`.

The checker must not infer success from Git timestamps, filenames, conversational history, or "latest" ordering.

- [ ] **Step 4: Run transition and receipt tests**

```bash
python -m pytest tests/devfabric/test_development_gate.py tests/devfabric/test_development_review.py -q
```

Expected: PASS.

- [ ] **Step 5: Run D6-G1 invariance regressions**

```bash
python -m pytest tests/devfabric/test_federation_adaptation.py tests/devfabric/test_federation_finalization.py -q
(cd devfabric/cloudflare && npm run test:core -- --test-name-pattern='federation')
```

Expected: PASS; no MCP tool surface changes.

- [ ] **Step 6: Commit Task 3**

```bash
git add metaengine/devfabric/development_gate.py tests/devfabric/test_development_gate.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'feat: enforce reviewed development transitions'
```

Record this commit as the completed Slice 0 implementation state.

---

### Task 4: Slice 0 Self-Review, Governance Receipt, and Slice 1 Admission Proof

**Files:**
- Create: `devfabric/artifacts/reviews/development/metaengine-1-slice-0-review.json`
- Create: `tests/devfabric/test_development_review_artifact.py`
- Modify: `docs/superpowers/plans/2026-08-13-metaengine-1-slice0-development-evolution-review-gate.md` only to check completed boxes after evidence exists.

**Interfaces:**
- Consumes: Tasks 1–3 protocol/checker and the current bootstrap review context.
- Produces: the first tracked `DevelopmentEvolutionReviewReceipt` and proof that `METAENGINE-1-SLICE-1` is admitted only when this exact receipt/context is supplied.

- [ ] **Step 1: Write the failing governance-artifact test before creating the artifact**

```python
def test_slice0_self_review_receipt_admits_slice1(project_root):
    receipt_path = project_root / "devfabric/artifacts/reviews/development/metaengine-1-slice-0-review.json"
    assert receipt_path.is_file()
    receipt = DevelopmentEvolutionReviewReceipt.from_dict(json.loads(receipt_path.read_text()))
    context = load_bootstrap_review_context(project_root)
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="METAENGINE-1-SLICE-0",
            previous_step_commit=receipt.completed_step_commit,
            next_step_id="METAENGINE-1-SLICE-1",
            current_context=context,
            receipt=receipt,
        )
    )
    assert result.allowed is True
```

Add a second test copying the receipt and changing its policy snapshot hash; it must fail with `DEVELOPMENT_REVIEW_POLICY_SNAPSHOT_STALE` or receipt-integrity failure.

- [ ] **Step 2: Run artifact test and verify RED**

```bash
python -m pytest tests/devfabric/test_development_review_artifact.py -q
```

Expected: FAIL because the tracked self-review receipt does not yet exist.

- [ ] **Step 3: Perform the actual Slice 0 review cycle**

Use the just-completed Task 3 commit as `completed_step_commit`. Compute fresh bootstrap snapshot hashes. Record deterministic verification evidence hashes for:

- focused development review/gate pytest output receipt;
- D6-G1 adaptation/finalization regression receipt;
- Node 18-tool MCP invariance receipt;
- `git diff --check`/clean tracked-tree evidence.

The review content must explicitly cover:

**Constitution findings**
- Slice 0 adds no authority/promotion/privacy/truth mutation.
- The known 5-of-6 handoff gap remains intentionally unfixed until Slice 1 and is a required follow-up.
- The gate itself does not claim to be K0 yet.

**Architecture/Mechanism Library findings**
- CURRENT: typed immutable receipt + explicit transition checker.
- MINIMAL: prose checklist only; reject because not machine-enforceable.
- LIBRARY: existing content-addressed DevFabric gate/receipt pattern; select as the principal reusable mechanism.
- SYNTHESIS: content-addressed receipt + explicit Constitution/Library/Policy snapshots + fail-closed transition semantics; select as implemented design.

**Policy findings**
- no change to `ArchitecturePolicy`, D6-G1 policy, champion, cp001, or federation authority;
- Slice 1 should move Constitution semantics out of duplicated legacy fragments into compiled K0/K1 while preserving historical hashes.

Decision: `ACCEPT_CONTINUE` only if all fresh verification evidence is green. Required follow-up experiment: `METAENGINE-1-SLICE-1-CONSTITUTIONAL-CONFORMANCE`.

Generate the JSON by instantiating `DevelopmentEvolutionReviewReceipt.create()` and writing `as_dict()` with sorted keys/indentation; do not hand-author `receipt_hash`.

- [ ] **Step 4: Run artifact/transition tests and verify GREEN**

```bash
python -m pytest tests/devfabric/test_development_review.py tests/devfabric/test_development_gate.py tests/devfabric/test_development_review_artifact.py -q
```

Expected: PASS and Slice 1 admission succeeds only with the exact receipt/context.

- [ ] **Step 5: Run full Slice 0 verification**

```bash
python -m pytest tests/devfabric -q
python -m compileall -q metaengine
(cd devfabric/cloudflare && npm run test:core)
git diff --check
```

Expected: all commands exit 0. If a pre-existing recovery-only missing artifact causes a known unrelated failure, restore only the attested external runtime evidence as done in D6-G1 verification, rerun, and remove it before the clean-tree check; never commit recovery-only evidence implicitly.

- [ ] **Step 6: Commit the governance receipt and its verifier test**

```bash
git add devfabric/artifacts/reviews/development/metaengine-1-slice-0-review.json tests/devfabric/test_development_review_artifact.py docs/superpowers/plans/2026-08-13-metaengine-1-slice0-development-evolution-review-gate.md
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m 'docs: certify METAENGINE-1 slice 0 review gate'
```

- [ ] **Step 7: Prove Slice 1 transition from the committed governance state**

Run a small Python verification that loads the committed receipt and current bootstrap review context and calls `verify_development_transition()` for `METAENGINE-1-SLICE-0 → METAENGINE-1-SLICE-1`.

Expected result:

```text
allowed=True
reason=DEVELOPMENT_REVIEW_TRANSITION_ALLOWED
```

Do not start Slice 1 in the same atomic task. The receipt proves admission; Slice 1 planning begins only after this task is complete.

---

## Plan Self-Review Mapping

- Spec §6.1–6.3 mandatory cycle → Tasks 1, 3, 4.
- Spec §6.4 Constitution review → Task 4 self-review findings and snapshot binding in Task 2.
- Spec §6.5 Architecture/Mechanism Library review → Task 2 bootstrap library snapshot + Task 4 alternatives/findings.
- Spec §6.6 Policy review → Task 2 policy snapshot + Task 4 policy findings.
- Spec §6.7 alternatives CURRENT/MINIMAL/LIBRARY/SYNTHESIS → Task 1 required alternative kinds + Task 4 actual comparison.
- Spec §6.8 receipt schema → Task 1.
- Spec §6.9 hard transition invariant → Task 3.
- Spec Slice 0 bootstrap/self-application → Task 4.
- Required negative tests: missing receipt, stale commit, stale snapshots, blocking decision, tamper → Tasks 1 and 3.
- No canonical/D6-G1/MCP mutation → Global Constraints + Task 3/4 regression checks.

Placeholder scan: plan contains no unresolved placeholder markers or unspecified implementation actions. The word `follow-up` appears only as an explicit receipt field/required experiment, not as a placeholder.
