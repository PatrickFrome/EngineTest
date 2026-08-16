# Stage D6-G1 Finalized-Epoch Shadow Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, finalized-only adaptive specialization that produces shadow concurrency/Role Genome proposals and immutable adaptation receipts without changing active federation truth or assignable profiles.

**Architecture:** Pure Python derives metrics and proposals only from verified `EpochFinalization` objects plus explicit policy/profile inputs; persistence is an append-only Supabase adaptation-receipt table accessed through two fixed internal RPCs. Runtime/plugin availability is observational only and cannot influence canonical calculation. D6-G1 ends at `PASS_ADAPTATION_SHADOW_READY`; materialization/activation remains D6-G2.

**Tech Stack:** Python 3 dataclasses and `metaengine.devfabric.codec` canonical hashing, pytest, PostgreSQL/Supabase SQL with RLS + `SECURITY INVOKER`, existing fixed Supabase adapter, Node/TypeScript MCP invariance tests, deterministic CONTROL capsule tooling.

## Global Constraints

- Parent historical D6-G0 source HEAD `71d36a12e5b810431739fc5d9b111fa4ffb955f5` is provenance-only and MUST NOT be fabricated as an available Git object.
- Verified reconstructed Git root is `0a0cb3eb38205121d4cf091c14ca2591744f0aed`; D6-G1 development continues from its real descendant commits.
- Parent CONTROL capsule SHA-256 is `1a5aaddba68fe5dcc112066ee136846b1fd77d99b233b88ebdb4c96a37db91b7`; parent CONTROL payload root is `246e69dbb28fa7e6ab425d20bd4c60b2beffd453e5a04c40fb0acbe06e94ea75`.
- Session Handoff V2 manifest receipt is `fc073c5ecab8aadbe8ab641f73d06196ac031a82336d19aced5ea302ba36026d`.
- Lineage lock SHA-256 is `fde3ce693062fb3efe4821ecd16cd775b1108b52492c3493028ce606a0e844a4`; all `9839` lineage files remain immutable.
- Supabase remains the sole canonical federation authority.
- Only validated D6-G0 finalized epochs may influence D6-G1 adaptation.
- No OPEN/INTEGRATING epoch, live session state, mutable ledger head, chat prose, telemetry sink, wall-clock time, environment variable, filesystem location, optional plugin, connector, or local CLI availability may influence pure adaptation outputs.
- Producer concurrency bounds are `2..6`; one eligible decision may move by at most one.
- Concurrency evidence requires at least `3` distinct finalized epochs and at least `6` total candidates with identical federation policy hash.
- Soft Role Genome changes may use only identities and keys already present in the parent soft genome; hard genome is byte-for-byte immutable.
- Shadow proposals are never inserted into `federated_role_genome` during D6-G1.
- Existing `TaskEnvelope.role_profile_hash` remains pinned; D6-G1 performs no active task/profile mutation.
- P3 content and forbidden private fields never enter adaptation receipts or external telemetry.
- The chat-facing federation MCP allowlist remains exactly `18` tools; no SQL/shell/promote/champion/policy mutation tool is added.
- Release promotion remains `BLOCKED`; external Federation MCP deployment remains unclaimed without independent deployment evidence.

---

### Task 1: Finalized-Epoch Metrics Contract

**Files:**
- Create: `metaengine/devfabric/federation/adaptation.py`
- Create: `tests/devfabric/test_federation_adaptation.py`

**Interfaces:**
- Consumes: `metaengine.devfabric.federation.finalization.EpochFinalization`.
- Produces: `ADAPTATION_PROTOCOL_VERSION`, `RationalRate`, `FinalizedEpochMetrics`, `metrics_from_finalization(finalization: EpochFinalization) -> FinalizedEpochMetrics`.

- [ ] **Step 1: Write the failing finalized-only metrics tests**

Add a local helper in `tests/devfabric/test_federation_adaptation.py` that builds a valid `EpochFinalization` by copying the frozen-cut shape used in `test_federation_finalization.py`, then assert exact counts and ordering:

```python
from dataclasses import replace

import pytest

from metaengine.devfabric.codec import canonical_digest
from metaengine.devfabric.federation.adaptation import metrics_from_finalization
from metaengine.devfabric.federation.finalization import EpochFinalization, recovery_cut_hash


def _finalization(cut: dict) -> EpochFinalization:
    cut_hash = recovery_cut_hash(cut)
    snapshot_hash = cut["terminal_snapshot"]["snapshot_hash"]
    return EpochFinalization.create(
        epoch_id=cut["epoch"]["epoch_id"],
        final_snapshot_hash=snapshot_hash,
        recovery_cut_hash=cut_hash,
        recovery_cut=cut,
        finalized_by_session_id="sync-c0",
        finalized_by_generation=2,
    )


def test_metrics_are_derived_only_from_verified_finalized_cut():
    finalization = _finalization(_sample_cut())
    metrics = metrics_from_finalization(finalization)
    assert metrics.epoch_id == "epoch-final-1"
    assert metrics.producer_concurrency == 2
    assert metrics.task_count == 2
    assert metrics.candidate_count == 2
    assert metrics.eligible_candidate_count == 2
    assert metrics.review_pass_count == 1
    assert metrics.conflict_count == 1
    assert metrics.unresolved_conflict_count == 0
    assert metrics.include_count == 2
    assert metrics.integrated_candidate_count == 2
    assert metrics.participants == (("C2", "a" * 64), ("C4", "b" * 64), ("C6", "6" * 64))
```

Also test an unresolved conflict, rejected/stale candidate accounting, PASS/FAIL/INCONCLUSIVE review counts, and that reversing all semantic arrays in the source cut yields identical metrics.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py
```

Expected: collection/import failure because `metaengine.devfabric.federation.adaptation` does not exist.

- [ ] **Step 3: Implement immutable rational metrics**

Create `adaptation.py` with these initial contracts:

```python
from __future__ import annotations

from dataclasses import dataclass

from .finalization import EpochFinalization

ADAPTATION_PROTOCOL_VERSION = "D6.ADAPTATION.1"


@dataclass(frozen=True)
class RationalRate:
    numerator: int
    denominator: int

    @property
    def value(self) -> float:
        return self.numerator / self.denominator


@dataclass(frozen=True)
class FinalizedEpochMetrics:
    finalization_hash: str
    recovery_cut_hash: str
    epoch_id: str
    federation_policy_hash: str
    producer_concurrency: int
    task_count: int
    candidate_count: int
    eligible_candidate_count: int
    rejected_candidate_count: int
    stale_candidate_count: int
    review_count: int
    review_pass_count: int
    review_fail_count: int
    review_inconclusive_count: int
    conflict_count: int
    unresolved_conflict_count: int
    include_count: int
    exclude_count: int
    stale_decision_count: int
    integrated_candidate_count: int
    participants: tuple[tuple[str, str], ...]

    @property
    def conflict_rate(self) -> RationalRate:
        return RationalRate(min(self.unresolved_conflict_count, max(self.candidate_count, 1)), max(self.candidate_count, 1))
```

`metrics_from_finalization()` must consume `finalization.recovery_cut`, which is already normalized and integrity-checked by `EpochFinalization.create/from_store_row`. Use terminal snapshot eligible/rejected/stale lists as the canonical candidate classification, `resolved == False` for unresolved conflicts, review `verdict` values `PASS/FAIL/INCONCLUSIVE`, integration decisions `INCLUDE/EXCLUDE/STALE`, and terminal `integration_order` length for `integrated_candidate_count`.

- [ ] **Step 4: Add tamper/revalidation tests**

Prove that callers constructing from a store row cannot bypass finalization integrity:

```python
def test_tampered_store_row_fails_before_adaptation():
    finalization = _finalization(_sample_cut())
    row = {
        **finalization.__dict__,
        "recovery_cut": {**finalization.recovery_cut, "epoch": {**finalization.recovery_cut["epoch"], "producer_concurrency": 6}},
    }
    with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CUT_HASH_MISMATCH"):
        EpochFinalization.from_store_row(row)
```

- [ ] **Step 5: Run focused tests and commit**

Run the adaptation and finalization suites, then commit only Task 1 files:

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py tests/devfabric/test_federation_finalization.py
git add metaengine/devfabric/federation/adaptation.py tests/devfabric/test_federation_adaptation.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: derive D6-G1 finalized epoch metrics"
```

---

### Task 2: Evidence Sufficiency and Bounded Concurrency Controller

**Files:**
- Modify: `metaengine/devfabric/federation/adaptation.py`
- Modify: `tests/devfabric/test_federation_adaptation.py`

**Interfaces:**
- Consumes: `tuple[FinalizedEpochMetrics, ...]` and explicit current concurrency.
- Produces: `EvidenceSufficiency`, `ConcurrencyDecision`, `evaluate_concurrency_evidence(...)`, `next_producer_concurrency(...)`.

- [ ] **Step 1: Write RED tests for insufficiency, thresholds, and explicit evidence-set identity**

Add tests equivalent to:

```python
def test_current_one_epoch_baseline_holds_for_insufficient_evidence():
    m = metrics_from_finalization(_finalization(_sample_cut()))
    decision = next_producer_concurrency(4, (m,))
    assert decision.status == "HOLD_INSUFFICIENT_EVIDENCE"
    assert decision.current == 4
    assert decision.proposed == 4


@pytest.mark.parametrize(
    ("unresolved", "candidates", "expected"),
    [(0, 30, 5), (3, 30, 4), (8, 30, 3)],
)
def test_conflict_budget_uses_summed_exact_counts(unresolved, candidates, expected):
    window = _three_metrics(total_candidates=candidates, total_unresolved=unresolved, policy_hash="3" * 64)
    assert next_producer_concurrency(4, window).proposed == expected
```

Also assert bounds at `2` and `6`, policy-hash mismatch yields HOLD/fail-closed reason, and two permutations of the same explicit finalization set have the same normalized `evidence_finalization_hashes`.

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py -k 'evidence or concurrency or conflict_budget'
```

Expected: missing symbols.

- [ ] **Step 3: Implement evidence normalization and exact thresholds**

Add immutable contracts:

```python
@dataclass(frozen=True)
class EvidenceSufficiency:
    sufficient: bool
    distinct_finalized_epochs: int
    total_candidates: int
    federation_policy_hash: str | None
    reason: str


@dataclass(frozen=True)
class ConcurrencyDecision:
    status: str
    current: int
    proposed: int
    conflict_numerator: int
    conflict_denominator: int
    evidence_finalization_hashes: tuple[str, ...]
    reason: str
```

Normalize evidence by `finalization_hash`; reject duplicate hashes with conflicting metric payloads; require `>=3` distinct epochs, `>=6` candidates, and one policy hash. Compare `10 * numerator < denominator` for `<0.10`, `4 * numerator <= denominator` for `<=0.25`, otherwise decrease. Never compare rounded floats.

- [ ] **Step 4: Add environment-independence test for pure controller**

Call the controller with two arbitrary capability inventories that are deliberately not parameters to the function and assert identical output. The test should make the architectural boundary explicit:

```python
def test_concurrency_decision_has_no_runtime_capability_input():
    window = _three_metrics(total_candidates=12, total_unresolved=0, policy_hash="3" * 64)
    first = next_producer_concurrency(4, window)
    second = next_producer_concurrency(4, tuple(reversed(window)))
    assert first == second
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py
git add metaengine/devfabric/federation/adaptation.py tests/devfabric/test_federation_adaptation.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: gate D6-G1 concurrency adaptation on finalized evidence"
```

---

### Task 3: Shadow Role Genome Proposal Without Catalog Materialization

**Files:**
- Modify: `metaengine/devfabric/federation/adaptation.py`
- Modify: `tests/devfabric/test_federation_adaptation.py`
- Read-only regression dependency: `metaengine/devfabric/federation/roles.py`

**Interfaces:**
- Consumes: parent `RoleGenome`, explicit finalized metrics/evidence, explicit requested soft changes supported by observable evidence.
- Produces: `ShadowRoleGenomeProposal`, `propose_soft_role_genome(...)`, `verify_shadow_role_genome(...)`.

- [ ] **Step 1: Write RED property tests for immutable hard genome and identity preservation**

Use `load_role_genome(PROJECT_ROOT, SlotId.C2)` and assert:

```python
def test_shadow_proposal_preserves_hard_genome_and_parent_identities():
    parent = load_role_genome(PROJECT_ROOT, SlotId.C2)
    proposal = propose_soft_role_genome(
        parent=parent,
        evidence_window=_slot_evidence(parent.profile_hash),
        changes={"concurrency_preference": 5},
    )
    assert proposal.hard == parent.hard
    assert proposal.parent_role_profile_hash == parent.profile_hash
    assert proposal.proposed_role_profile_hash != parent.profile_hash
```

Add failures for a new capability key, new provider key, new worker ID, new task class, new reviewer identity, unknown soft field, and out-of-bounds values. Add an unobserved metric case that returns `HOLD_UNOBSERVED_METRIC` and an unchanged proposal hash/payload.

- [ ] **Step 2: Verify RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py -k 'role or genome or identity or unobserved'
```

- [ ] **Step 3: Implement strict shadow proposal validation in `adaptation.py`**

Do not weaken or broaden `RoleGenome.with_soft_update()`. Add an adaptation-specific strict precheck:

```python
@dataclass(frozen=True)
class ShadowRoleGenomeProposal:
    parent_role_profile_hash: str
    proposed_role_profile_hash: str
    hard: object
    soft: object
    status: str
    reason: str


def _require_existing_mapping_keys(parent_pairs, proposed: dict[str, float], error: str) -> None:
    allowed = {key for key, _ in parent_pairs}
    if not set(proposed) <= allowed:
        raise ValueError(error)
```

For sequence fields, proposed values must be a subset/permutation of parent values. Build the candidate through `parent.with_soft_update(changes)` only after identity checks. Assert `candidate.hard == parent.hard`; if not, raise `FEDERATION_ADAPTATION_HARD_GENOME_IMMUTABLE`. The proposal remains an in-memory receipt payload only.

- [ ] **Step 4: Prove D6-G1 does not materialize profiles**

Add a repository-level test that `adaptation.py` imports neither the Supabase adapter nor any store write path and that the D6-G1 migration introduced later contains no `insert into destruktion_meta.federated_role_genome`.

- [ ] **Step 5: Run role/adaptation regression and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py tests/devfabric/test_federation_roles.py
git add metaengine/devfabric/federation/adaptation.py tests/devfabric/test_federation_adaptation.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: add shadow-only role genome proposals"
```

---

### Task 4: Deterministic Adaptation Receipt and Shadow Replay

**Files:**
- Modify: `metaengine/devfabric/federation/adaptation.py`
- Modify: `tests/devfabric/test_federation_adaptation.py`

**Interfaces:**
- Produces: `AdaptationReceipt`, `build_adaptation_receipt(...)`, `verify_shadow_receipt(...)`.
- Runtime/Git provenance is intentionally excluded from pure adaptation receipt identity and is recorded later in the D6-G1 stage gate/handoff artifact.

- [ ] **Step 1: Write RED hash/idempotence/runtime-independence tests**

Tests must assert:

```python
def test_receipt_hash_is_order_independent_and_runtime_independent():
    left = build_adaptation_receipt(
        metrics_window=(m1, m2, m3),
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    right = build_adaptation_receipt(
        metrics_window=(m3, m1, m2),
        current_policy_hash="3" * 64,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="a" * 64,
    )
    assert left.adaptation_input_hash == right.adaptation_input_hash
    assert left.adaptation_receipt_hash == right.adaptation_receipt_hash
    assert "implementation_commit" not in repr(left)
    assert "git" not in repr(left).lower()
```

Mutate one allowed explicit policy/profile input and assert `adaptation_input_hash` changes. A fake runtime capability inventory must not be accepted as a parameter and must not appear in canonical payloads.

- [ ] **Step 2: Verify RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py -k 'receipt or replay or runtime_independent'
```

- [ ] **Step 3: Implement canonical two-hash model**

Use `canonical_digest()` and `to_primitive()` only.

`adaptation_input_hash` must cover exactly the explicit model inputs:

```python
{
    "protocol_version": "D6.ADAPTATION.1",
    "evidence_finalization_hashes": tuple(sorted(...)),
    "current_policy_hash": current_policy_hash,
    "current_producer_concurrency": current_producer_concurrency,
    "parent_role_profile_hashes": tuple(sorted(proposal.parent_role_profile_hash for proposal in role_proposals)),
}
```

It MUST NOT include Git HEAD, branch, filesystem path, environment variables, installed tools, connector availability, current time, Session Handoff receipt, or CONTROL capsule path.

`adaptation_receipt_hash` covers the normalized output payload: evidence recovery-cut identities, metrics hash, concurrency decision, shadow proposals, telemetry schema hash, and status. Stable protocol identifiers may appear; runtime/development provenance may not.

- [ ] **Step 4: Implement deterministic shadow replay verifier**

`verify_shadow_receipt(receipt, *, metrics_window, current_policy_hash, current_producer_concurrency, role_proposals, telemetry_schema_hash)` rebuilds the receipt from exactly those explicit inputs and requires both hashes and normalized payload equality. Hash/payload mismatch raises `FEDERATION_ADAPTATION_RECEIPT_HASH_MISMATCH`.

- [ ] **Step 5: Run tests and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py
git add metaengine/devfabric/federation/adaptation.py tests/devfabric/test_federation_adaptation.py docs/superpowers/specs/2026-08-13-stage-d6-g1-finalized-shadow-adaptation-design.md docs/superpowers/plans/2026-08-13-stage-d6-g1-finalized-shadow-adaptation.md
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: add runtime-independent D6 adaptation receipts"
```

---

### Task 5: Privacy-Minimized Adaptation Telemetry

**Files:**
- Create: `metaengine/devfabric/federation/telemetry.py`
- Create: `tests/devfabric/test_federation_telemetry.py`

**Interfaces:**
- Consumes: `AdaptationReceipt`.
- Produces: `TELEMETRY_SCHEMA_VERSION`, `TELEMETRY_SCHEMA_HASH`, `federation_adaptation_event(receipt) -> dict[str, object]`.

- [ ] **Step 1: Write RED allowlist/denylist tests**

Assert the event includes only protocol/status, hash identifiers, counts/rational rates, slot IDs and decision categories. Parameterize forbidden keys over `objective`, `prompt`, `conversation`, `patch`, `path`, `secret`, `token`, `credential`, `password`, and explicit P3 markers; passing arbitrary mappings instead of a typed receipt must not create an escape hatch.

- [ ] **Step 2: Verify RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_telemetry.py
```

- [ ] **Step 3: Implement a closed-schema serializer**

Create a serializer that constructs a new dict field-by-field rather than filtering arbitrary input:

```python
TELEMETRY_SCHEMA_VERSION = "D6.ADAPTATION.TELEMETRY.1"


def federation_adaptation_event(receipt: AdaptationReceipt) -> dict[str, object]:
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "protocol_version": receipt.protocol_version,
        "adaptation_receipt_hash": receipt.adaptation_receipt_hash,
        "adaptation_input_hash": receipt.adaptation_input_hash,
        "status": receipt.status,
        "evidence_epoch_count": len(receipt.evidence_finalization_hashes),
        "concurrency_current": receipt.concurrency_decision.current,
        "concurrency_proposed": receipt.concurrency_decision.proposed,
        "concurrency_reason": receipt.concurrency_decision.reason,
    }
```

Compute `TELEMETRY_SCHEMA_HASH = canonical_digest({...field names/schema version...})`. Do not add a PostHog read path.

- [ ] **Step 4: Run tests and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_telemetry.py tests/devfabric/test_federation_adaptation.py
git add metaengine/devfabric/federation/telemetry.py tests/devfabric/test_federation_telemetry.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: add privacy-minimized adaptation telemetry"
```

---

### Task 6: Append-Only Supabase Adaptation Persistence

**Files:**
- Create: `storage/federated_chat_fabric_d6_adaptation.sql`
- Create: `tests/devfabric/test_federation_adaptation_sql.py`
- Modify: `metaengine/devfabric/federation/supabase_federation.py`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`

**Interfaces:**
- Produces SQL table `destruktion_meta.federated_adaptation_receipt`.
- Produces fixed internal RPCs `metaengine_federation_record_adaptation_receipt_v1` and `metaengine_federation_adaptation_receipt_get_v1`.
- Produces adapter methods `record_adaptation_receipt_internal(...)` and `adaptation_receipt_get_internal(...)`.

- [ ] **Step 1: Write RED SQL contract tests**

`test_federation_adaptation_sql.py` must read only the new migration and assert:

```python
assert "create table destruktion_meta.federated_adaptation_receipt" in sql
assert "adaptation_input_hash text not null unique" in sql
assert "security definer" not in sql
assert "security invoker" in _function_block("metaengine_federation_record_adaptation_receipt_v1")
assert "set search_path = pg_catalog, destruktion_meta" in _function_block(...)
assert "revoke update, delete, truncate on table destruktion_meta.federated_role_genome from service_role" in sql
assert "revoke update, delete, truncate on table destruktion_meta.federated_role_outcome from service_role" in sql
assert "insert into destruktion_meta.federated_role_genome" not in sql
```

Also assert an immutable trigger rejects UPDATE/DELETE on adaptation receipts and that `anon/authenticated` receive no table/function grants.

- [ ] **Step 2: Write RED adapter routing/validation tests**

Add:

```python
def test_adapter_routes_fixed_adaptation_receipt_calls():
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    adapter.record_adaptation_receipt_internal(
        adaptation_receipt_hash=_h("a"),
        adaptation_input_hash=_h("b"),
        protocol_version="D6.ADAPTATION.1",
        evidence_finalization_hashes=(_h("c"), _h("d")),
        evidence_metrics_hash=_h("e"),
        status="HOLD_INSUFFICIENT_EVIDENCE",
        receipt={"adaptation_receipt_hash": _h("a"), "adaptation_input_hash": _h("b")},
    )
    adapter.adaptation_receipt_get_internal(_h("b"))
    assert [name for name, _ in transport.calls] == [
        "metaengine_federation_record_adaptation_receipt_v1",
        "metaengine_federation_adaptation_receipt_get_v1",
    ]
```

Invalid hash, unsupported status, empty evidence list, or unsupported protocol must fail before transport.

- [ ] **Step 3: Verify RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation_sql.py tests/devfabric/test_federation_supabase_adapter.py
```

- [ ] **Step 4: Implement migration with idempotent/conflict semantics**

The write RPC must:

1. validate lowercase 64-hex `adaptation_receipt_hash`, `adaptation_input_hash`, `evidence_metrics_hash`, and every evidence finalization hash;
2. require protocol `D6.ADAPTATION.1` and a supported status;
3. require each evidence hash to exist in `federated_epoch_finalization`;
4. lock/select by `adaptation_input_hash`;
5. return `{"status":"ALREADY_RECORDED"}` for exact hash + exact receipt repeat;
6. raise `FEDERATION_ADAPTATION_NONDETERMINISTIC` for same input hash with different receipt hash/payload;
7. insert once otherwise.

Use `RLS + FORCE RLS`, `service_role SELECT, INSERT`, explicit revocation of `UPDATE, DELETE, TRUNCATE`, and an immutable trigger analogous to D6-G0 finalization.

- [ ] **Step 5: Implement fixed adapter methods**

Add methods after `finalization_get_internal()`; use existing `_require_hex64`, `_mapping`, and `_call`. Do not add generic SQL/RPC access.

- [ ] **Step 6: Run local tests and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation_sql.py tests/devfabric/test_federation_supabase_adapter.py tests/devfabric/test_federation_adaptation.py
git add storage/federated_chat_fabric_d6_adaptation.sql metaengine/devfabric/federation/supabase_federation.py tests/devfabric/test_federation_adaptation_sql.py tests/devfabric/test_federation_supabase_adapter.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "feat: persist immutable D6 adaptation receipts"
```

- [ ] **Step 7: Apply and verify on staging before canonical**

Use the connected Supabase staging project `sibnfciqcpkuquxzduqr`. Apply exactly `storage/federated_chat_fabric_d6_adaptation.sql`, then execute read-only catalog queries proving RLS/privileges/function security attributes. Insert one deterministic staging receipt, repeat it for `ALREADY_RECORDED`, then attempt a conflicting repeat and verify `FEDERATION_ADAPTATION_NONDETERMINISTIC`. Do not touch canonical until every staging assertion passes.

- [ ] **Step 8: Apply the same migration to canonical and perform readback-only verification**

Use canonical project `gzrbxoiuenkksualgpvp` only after staging PASS. Apply the byte-identical migration. Verify schema/function privileges and current D6-G0 finalization readback. Do not create an active Role Genome, checkpoint, promotion, or new federation epoch as part of this task.

---

### Task 7: D6-G1 Verification Profile, MCP Invariance, and External Gate Receipt

**Files:**
- Modify: `devfabric/verification/profiles.toml`
- Modify: `metaengine/devfabric/capsule.py`
- Modify: `tests/devfabric/test_federation_pilot.py`
- Modify: `tests/devfabric/test_capsule.py`
- Runtime artifact (external to CONTROL capsule): `devfabric/artifacts/manifests/stage-d6-g1-gate.json`

**Interfaces:**
- Produces verifier profile `federation-adaptation`.
- Produces recognized gate version `METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1`.

- [ ] **Step 1: Write RED gate/capsule/profile tests**

Add assertions that:

```python
assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-g1-gate.json"))
receipt = make_gate_receipt(
    {
        "stage": "D6-G1",
        "development_status": "PASS_ADAPTATION_SHADOW_READY",
        "original_source_head_provenance": "71d36a12e5b810431739fc5d9b111fa4ffb955f5",
        "reconstructed_git_root": "0a0cb3eb38205121d4cf091c14ca2591744f0aed",
    },
    gate_version="METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1",
)
```

`verify_gate_receipt()` must accept that exact version. `profiles.toml` must contain `federation-adaptation` with adaptation/finalization/adapter/pilot tests plus the existing two Node MCP invariance tests and TypeScript compile command.

- [ ] **Step 2: Verify RED**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_pilot.py tests/devfabric/test_capsule.py
```

- [ ] **Step 3: Extend capsule gate exclusion and verifier gate-version allowlist**

Add only `stage-d6-g1-gate.json` to `_excluded()` and `METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1` to `verify_gate_receipt()` accepted versions. Do not change payload inclusion rules otherwise.

- [ ] **Step 4: Add `federation-adaptation` verification profile**

Use this exact command set:

```toml
[profiles.federation-adaptation]
commands = [
  "python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py tests/devfabric/test_federation_telemetry.py tests/devfabric/test_federation_adaptation_sql.py tests/devfabric/test_federation_finalization.py tests/devfabric/test_federation_supabase_adapter.py tests/devfabric/test_federation_pilot.py",
  "node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts devfabric/cloudflare/test/federation_tools.test.ts",
  "tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json",
  "python -m metaengine.devfabric.isolated_suite_runner tests/devfabric --timeout-seconds 180",
  "python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric",
]
```

- [ ] **Step 5: Prove fixed 18-tool MCP invariance**

Run:

```bash
node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts devfabric/cloudflare/test/federation_tools.test.ts
tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json
```

Expected: `FEDERATION_TOOL_NAMES.length == 18`; no adaptation tool exists in `federation_contract.ts`, `federation_tools.ts`, or `mcp.ts`.

- [ ] **Step 6: Commit verification plumbing**

```bash
git add devfabric/verification/profiles.toml metaengine/devfabric/capsule.py tests/devfabric/test_federation_pilot.py tests/devfabric/test_capsule.py
git -c user.name='MetaEngine DevFabric' -c user.email='devfabric@local.invalid' commit -m "test: add D6-G1 adaptation verification gate"
```

---

### Task 8: Full Regression, Deterministic Capsule, D6-G1 Gate, and Portable Continuation Cut

**Files:**
- Runtime artifact: `devfabric/artifacts/manifests/stage-d6-g1-gate.json` (excluded from CONTROL payload)
- Runtime artifact: deterministic D6-G1 CONTROL capsule output path under `/mnt/data` or another external artifact directory
- No lineage file modifications.

**Interfaces:**
- Produces final stage state `PASS_ADAPTATION_SHADOW_READY` if and only if every acceptance criterion passes.

- [ ] **Step 1: Run focused D6-G1 profile**

Run every command from `profiles.federation-adaptation`. If Node/TypeScript tooling is unavailable, preserve the historical `BLOCKED_EXTERNAL_NODE_TOOLCHAIN` certification boundary and do not convert a missing command into PASS. In the current recovered runtime Node is available, so the expected local result is execution, not waiver.

- [ ] **Step 2: Run full Python/DevFabric regressions**

```bash
python -m metaengine.devfabric.isolated_suite_runner tests/devfabric --timeout-seconds 180
python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric
python -m compileall -q metaengine
```

Expected: all available suites PASS.

- [ ] **Step 3: Verify lineage immutability**

Run a local verifier that parses `devfabric/LINEAGE_LOCK_SHA256.txt`, hashes every listed file, requires `9839/9839`, and rejects missing/extra/bad lineage bytes. Record the unchanged lock SHA-256 `fde3ce693062fb3efe4821ecd16cd775b1108b52492c3493028ce606a0e844a4` in the stage gate.

- [ ] **Step 4: Build CONTROL capsule twice and compare**

Use `metaengine.devfabric.capsule.build_control_capsule()` twice from the clean tracked tree, then require identical capsule SHA-256 and identical payload root. Run `verify_control_capsule()` on the result and require `bad=[]`, `missing=[]`, `extra=[]`, `secret_hits=[]`.

- [ ] **Step 5: Read canonical D6-G0 state and adaptation persistence state**

Perform fresh read-only Supabase queries confirming:

- D6-F/D6-G0 epoch remains `CLOSED` with finalization hash `e096f3ce66831670359430e31bbe7e5104fd77109d796e976f57f6425699923e`;
- checkpoint `metaengine-chat-2.3.0-alpha.1-cp001` remains `VERIFIED/current`;
- active architecture policy remains `1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48`;
- current one-epoch D6-G1 calculation is `HOLD_INSUFFICIENT_EVIDENCE`;
- no shadow proposal has been materialized into `federated_role_genome`;
- release promotion state has not changed.

- [ ] **Step 6: Create the external D6-G1 gate receipt**

Use `make_gate_receipt()` with `METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1`. Include at minimum:

```python
{
    "stage": "D6-G1",
    "development_status": "PASS_ADAPTATION_SHADOW_READY",
    "adaptation_protocol": "D6.ADAPTATION.1",
    "current_evidence_status": "HOLD_INSUFFICIENT_EVIDENCE",
    "mcp_tool_count": 18,
    "lineage_file_count": 9839,
    "lineage_lock_sha256": "fde3ce693062fb3efe4821ecd16cd775b1108b52492c3493028ce606a0e844a4",
    "original_source_head_provenance": "71d36a12e5b810431739fc5d9b111fa4ffb955f5",
    "reconstructed_git_root": "0a0cb3eb38205121d4cf091c14ca2591744f0aed",
    "handoff_manifest_receipt": "fc073c5ecab8aadbe8ab641f73d06196ac031a82336d19aced5ea302ba36026d",
    "parent_control_capsule_sha256": "1a5aaddba68fe5dcc112066ee136846b1fd77d99b233b88ebdb4c96a37db91b7",
    "parent_control_payload_root": "246e69dbb28fa7e6ab425d20bd4c60b2beffd453e5a04c40fb0acbe06e94ea75",
    "implementation_commit": git_head,
    "release_promotion_status": "BLOCKED",
    "external_mcp_deployment_status": "NOT_CLAIMED",
}
```

Add actual test/capsule/Supabase measurements and verify the receipt with `verify_gate_receipt()`.

- [ ] **Step 7: Ensure Git tree is clean and make the final implementation commit if required**

If the external gate is excluded and no tracked files remain, `git status --porcelain` must be empty. If a tracked verification receipt or documentation update is required, commit it first and regenerate the gate so `implementation_commit` points at the final clean tracked HEAD.

- [ ] **Step 8: Produce a new portable Git/session continuation artifact**

Create a fresh `git bundle --all` from the final D6-G1 repository and record its SHA-256 together with the new CONTROL capsule and D6-G1 gate. Preserve both provenance identities (`71d36...` historical and `0a0cb3...` reconstructed root) in the next handoff. This is the first normal post-recovery Git continuation point; future chats must restore this real Git DAG rather than reconstructing another root.
