# Stage D6-G0 Immutable Epoch Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace D6-F's live-witness freeze-window dependency with one immutable, append-only recovery cut per epoch, close the epoch atomically, and recover the same synchronization snapshot after all participant sessions are released.

**Architecture:** Keep the existing D6 federation ledger and 18-tool MCP surface unchanged. Add a pure Python finalization/recovery-cut layer, mirror it in the SQLite simulator, add one separate Supabase migration containing one immutable table, two internal service-role RPCs, and explicit CLOSED/ABORTED guards on every epoch-targeting mutation RPC; validate on `METAENGINE_STAGING` before applying the exact definitions to canonical Supabase and finalizing the already-observed D6-F epoch.

**Tech Stack:** Python 3.13, frozen dataclasses, canonical JSON SHA-256 (`metaengine.devfabric.codec`), SQLite simulator, PostgreSQL 17/Supabase PL/pgSQL + JSONB, pytest, Node 22 core federation tests, TypeScript core typecheck.

## Global Constraints

- Canonical Supabase project remains `gzrbxoiuenkksualgpvp`; staging project remains `sibnfciqcpkuquxzduqr`.
- Canonical checkpoint `metaengine-chat-2.3.0-alpha.1-cp001`, active policy `1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48`, champion pointer, and promotion state must not change.
- One immutable finalization per epoch; UPDATE/DELETE is forbidden even to `service_role`.
- Finalization must be atomic with epoch close and active-session release/fencing.
- Recovery cut protocol is exactly `D6.FINALIZATION.1`.
- Closed recovery must never consult active sessions, slot generations, prior C0 prose, or mutable head state.
- All new PostgreSQL functions are `SECURITY INVOKER`, use fixed `search_path = pg_catalog, destruktion_meta`, revoke `PUBLIC/anon/authenticated`, and grant only `service_role` where callable.
- The chat-facing Federation MCP allowlist remains exactly 18 tools; no finalization RPC is exposed through MCP.
- P3 remains local-only and must never enter a recovery cut.
- No checkpoint proposal/promotion, champion mutation, policy mutation, executable self-modification, or paid Supabase branching is part of D6-G0.
- Current Supabase platform defaults require explicit grants for new database objects; do not rely on implicit table/function exposure.
- Do not use or pin Postgres extension versions in this migration; D6-G0 requires no extension.
- The real D6-F epoch to finalize is `d6f-ui-canary-20260813-e001` and its expected terminal snapshot hash is `00977f5cc3ada234fe2355bd1d8ab2c8479e1a0b9eefbd3f061269c2b74fc056`.
- Identical duplicate finalization is idempotent; conflicting duplicate finalization fails closed. To make this compatible with terminal `CLOSED`, the RPC checks an existing finalization before rejecting a closed epoch.

---

### Task 1: Pure immutable finalization contracts and cut canonicalization

**Files:**
- Create: `metaengine/devfabric/federation/finalization.py`
- Modify: `metaengine/devfabric/federation/contracts.py`
- Create: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- Produces: `FINALIZATION_PROTOCOL_VERSION = "D6.FINALIZATION.1"`.
- Produces: frozen `EpochFinalization` with `finalization_hash`, `epoch_id`, `final_snapshot_hash`, `recovery_cut_hash`, `recovery_cut`, `finalized_by_session_id`, `finalized_by_generation`, `protocol_version`.
- Produces: `normalize_recovery_cut(cut: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `recovery_cut_hash(cut: Mapping[str, Any]) -> str`.
- Produces: `snapshot_payload_from_cut(cut: Mapping[str, Any]) -> dict[str, Any]`.
- Consumes: existing `canonical_digest`, `canonical_bytes`, `SynchronizationSnapshot` field names, D6 task/candidate/review semantics.

- [ ] **Step 1: Write RED tests for protocol/version/hash normalization**

Add tests that deliberately scramble array insertion order and require identical normalized cuts and hashes:

```python
from metaengine.devfabric.federation.finalization import (
    FINALIZATION_PROTOCOL_VERSION,
    normalize_recovery_cut,
    recovery_cut_hash,
)


def test_recovery_cut_normalizes_all_semantic_arrays_before_hashing():
    left = sample_cut(tasks=("b", "a"), candidates=("d", "c"))
    right = sample_cut(tasks=("a", "b"), candidates=("c", "d"))
    assert FINALIZATION_PROTOCOL_VERSION == "D6.FINALIZATION.1"
    assert normalize_recovery_cut(left) == normalize_recovery_cut(right)
    assert recovery_cut_hash(left) == recovery_cut_hash(right)
```

Also test these exact sort keys: `task_hash`, `assignment_id`, `candidate_hash`, `review_hash`, `conflict_hash`, `decision_hash`, `(slot_id, session_id)`.

- [ ] **Step 2: Run RED test and require failure for missing module/API**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/devfabric/test_federation_finalization.py
```

Expected: FAIL because `metaengine.devfabric.federation.finalization` and `EpochFinalization` do not yet exist.

- [ ] **Step 3: Implement strict cut validation and canonicalization**

Implement `normalize_recovery_cut()` so it:

```python
required_top = {
    "cut_version", "epoch", "tasks", "assignments", "candidates", "reviews",
    "conflicts", "integration_decisions", "participant_witnesses", "terminal_snapshot",
}
if set(cut) != required_top:
    raise ValueError("FEDERATION_FINALIZATION_CUT_SHAPE_INVALID")
if cut["cut_version"] != FINALIZATION_PROTOCOL_VERSION:
    raise ValueError("FEDERATION_FINALIZATION_VERSION_UNSUPPORTED")
```

Reject any recursively encountered key containing `secret`, `service_role`, `password`, `credential`, `prompt`, or `conversation`, and reject any payload declaring `privacy_class == "P3"`. Preserve P1/P2 receipt metadata only.

- [ ] **Step 4: Implement frozen `EpochFinalization`**

Use existing lowercase 64-hex validation rules. `EpochFinalization.create(...)` must normalize the cut, require `recovery_cut_hash == canonical_digest(normalized_cut)`, require `protocol_version == D6.FINALIZATION.1`, and compute `finalization_hash` over the immutable non-time fields:

```python
canonical_digest({
    "epoch_id": epoch_id,
    "final_snapshot_hash": final_snapshot_hash,
    "recovery_cut_hash": recovery_cut_hash,
    "finalized_by_session_id": finalized_by_session_id,
    "finalized_by_generation": finalized_by_generation,
    "protocol_version": protocol_version,
})
```

- [ ] **Step 5: Implement `snapshot_payload_from_cut()` with exact snapshot fields**

Return only:

```python
{
    "epoch_id": cut["epoch"]["epoch_id"],
    "base_checkpoint_id": cut["epoch"]["base_checkpoint_id"],
    "policy_hash": cut["epoch"]["federation_policy_hash"],
    "catalog_hash": cut["epoch"]["role_catalog_hash"],
    "eligible_candidates": tuple(...),
    "rejected_candidates": tuple(...),
    "stale_candidates": tuple(...),
    "conflict_refs": tuple(...),
    "integration_order": tuple(...),
    "required_verification_hashes": tuple(...),
}
```

Derive eligibility/reviews from the frozen witnesses in the cut; never call a store or current-session API.

- [ ] **Step 6: Run GREEN tests and existing contract tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_finalization.py \
  tests/devfabric/test_federation_contracts.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add metaengine/devfabric/federation/finalization.py \
        metaengine/devfabric/federation/contracts.py \
        tests/devfabric/test_federation_finalization.py
git commit -m "feat(d6): add immutable finalization contracts"
```

---

### Task 2: Extend the local SQLite federation store with terminal evidence and lifecycle state

**Files:**
- Modify: `metaengine/devfabric/federation/store.py`
- Modify: `tests/devfabric/test_federation_simulator.py`
- Modify: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- Produces: `put_finalization(finalization: EpochFinalization) -> bool` where identical duplicate returns `False` and conflicting epoch duplicate raises `ValueError("FEDERATION_FINALIZATION_CONFLICT")`.
- Produces: `get_finalization(epoch_id: str) -> dict[str, Any] | None`.
- Produces: `close_epoch(epoch_id: str, *, finalization: EpochFinalization) -> None`.
- Produces: deterministic row readers needed by cut construction: `list_assignment_rows`, `list_review_rows_for_epoch`, `list_conflict_rows`, `list_integration_decision_rows`, `list_session_rows`, `snapshot_row`.
- Produces: local `put_integration_decision(...)` mirror so local finalization contains the same semantic evidence as Supabase.

- [ ] **Step 1: Write RED local persistence/immutability tests**

Require a fresh store to persist one finalization, reject a conflicting second one, and make UPDATE/DELETE impossible through public store methods. Add:

```python
assert store.put_finalization(finalization) is True
assert store.put_finalization(finalization) is False
with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_CONFLICT"):
    store.put_finalization(other_finalization_same_epoch)
```

- [ ] **Step 2: Write RED close/release test**

Create C0/C2/C4/C6 active sessions plus claimed assignments, call `close_epoch`, then require:

```python
assert store.get_epoch(epoch_id)["state"] == "CLOSED"
assert all(row["released_at"] == "RELEASED" for row in store.list_session_rows(epoch_id))
assert all(row["assignment_state"] != "CLAIMED" for row in store.list_assignment_rows(epoch_id))
```

- [ ] **Step 3: Run RED tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_finalization.py \
  tests/devfabric/test_federation_simulator.py
```

Expected: FAIL because the tables/methods are absent.

- [ ] **Step 4: Add SQLite schema objects**

Add `assignment_state TEXT NOT NULL DEFAULT 'CLAIMED'`, `integration_decision`, and `finalization` tables. The local `finalization` row stores canonical JSON for the normalized cut and enforces `UNIQUE(epoch_id)`.

- [ ] **Step 5: Add local mutation guard**

Implement:

```python
def _require_epoch_mutable(self, epoch_id: str) -> None:
    epoch = self.get_epoch(epoch_id)
    if epoch is None:
        raise KeyError(epoch_id)
    if epoch["state"] in {"CLOSED", "ABORTED"}:
        raise ValueError("FEDERATION_EPOCH_IMMUTABLE")
```

Call it from local task/candidate/review/conflict/snapshot/decision mutation paths. `release_session` remains allowed as lifecycle cleanup.

- [ ] **Step 6: Implement atomic `close_epoch`**

Use one `BEGIN IMMEDIATE` transaction to insert finalization, set `epoch.state='CLOSED'`, release/revoke active epoch sessions, and mark remaining claimed assignments `RELEASED`. Do not touch checkpoint/policy data.

- [ ] **Step 7: Run GREEN simulator/finalization suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_finalization.py \
  tests/devfabric/test_federation_simulator.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add metaengine/devfabric/federation/store.py \
        tests/devfabric/test_federation_simulator.py \
        tests/devfabric/test_federation_finalization.py
git commit -m "feat(d6): persist immutable epoch finalizations locally"
```

---

### Task 3: Make `Synchronizer.recover()` state-aware and frozen-cut only for CLOSED epochs

**Files:**
- Modify: `metaengine/devfabric/federation/synchronizer.py`
- Modify: `metaengine/devfabric/federation/finalization.py`
- Modify: `tests/devfabric/test_federation_synchronizer.py`
- Modify: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- Produces: `build_recovery_cut(store: FederationStore, epoch_id: str, final_snapshot_hash: str) -> dict[str, Any]`.
- Produces: `recover_from_cut(finalization: EpochFinalization) -> SynchronizationSnapshot` through the synchronizer-facing API.
- Changes: `Synchronizer.recover(epoch_id)` branches on epoch state.

- [ ] **Step 1: Write RED closed-recovery independence test**

Construct a valid finalization, close the epoch, then mutate/delete local active-session witnesses directly through a test-only SQL connection and require recovery remains byte-identical:

```python
before = synchronizer.snapshot(epoch_id)
finalization = finalize_locally(...)
store.connection.execute("DELETE FROM session WHERE epoch_id=?", (epoch_id,))
after = synchronizer.recover(epoch_id)
assert after == before
assert after.snapshot_hash == before.snapshot_hash
```

This is intentionally a test-only destructive mutation proving CLOSED recovery is detached from current sessions.

- [ ] **Step 2: Write RED integrity/version failure tests**

Require exact exceptions:

```python
with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_INTEGRITY_ERROR"):
    synchronizer.recover(corrupt_epoch_id)
with pytest.raises(ValueError, match="FEDERATION_FINALIZATION_VERSION_UNSUPPORTED"):
    recover_from_cut(unsupported_finalization)
```

No fallback to `snapshot(epoch_id)` is allowed.

- [ ] **Step 3: Run RED tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_synchronizer.py \
  tests/devfabric/test_federation_finalization.py
```

Expected: FAIL because `recover()` still live-reprojects.

- [ ] **Step 4: Implement deterministic cut builder**

`build_recovery_cut()` must read only the epoch's rows, decode minimal receipt metadata, and sort exactly as the spec requires. It embeds the exact referenced terminal snapshot row; it must not choose `latest_snapshot_row()` by lexical hash.

- [ ] **Step 5: Implement CLOSED recovery branch**

Use:

```python
state = epoch["state"]
if state in {"OPEN", "INTEGRATING"}:
    return self.snapshot(epoch_id)
if state == "CLOSED":
    row = self.store.get_finalization(epoch_id)
    if row is None:
        raise ValueError("FEDERATION_FINALIZATION_INTEGRITY_ERROR")
    return recover_from_cut(EpochFinalization.from_store_row(row))
raise ValueError("FEDERATION_EPOCH_NOT_RECOVERABLE")
```

`recover_from_cut()` independently recomputes cut hash, reconstructs snapshot fields, and requires reconstructed `snapshot_hash == final_snapshot_hash`.

- [ ] **Step 6: Run GREEN synchronizer/finalization/pilot tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_finalization.py \
  tests/devfabric/test_federation_synchronizer.py \
  tests/devfabric/test_federation_pilot.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add metaengine/devfabric/federation/finalization.py \
        metaengine/devfabric/federation/synchronizer.py \
        tests/devfabric/test_federation_finalization.py \
        tests/devfabric/test_federation_synchronizer.py
git commit -m "feat(d6): recover closed epochs from immutable cuts"
```

---

### Task 4: Create the separate Supabase finalization migration and immutable table/RPCs

**Files:**
- Create: `storage/federated_chat_fabric_d6_finalization.sql`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`
- Modify: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- Produces table: `destruktion_meta.federated_epoch_finalization`.
- Produces internal RPC: `public.metaengine_federation_finalize_epoch_v1(text,bigint,text,text,text,text,jsonb,text)`.
- Produces internal read RPC: `public.metaengine_federation_finalization_get_v1(text)`.
- Produces immutable trigger function in `destruktion_meta`; it is not a chat/API RPC.

- [ ] **Step 1: Write RED SQL contract tests for one table and two RPCs**

Require the migration text to contain:

```python
assert "create table destruktion_meta.federated_epoch_finalization" in sql
assert "grant select, insert on table destruktion_meta.federated_epoch_finalization to service_role" in sql
assert "revoke update, delete on table destruktion_meta.federated_epoch_finalization from service_role" in sql
assert "metaengine_federation_finalize_epoch_v1" in sql
assert "metaengine_federation_finalization_get_v1" in sql
assert "security definer" not in sql.lower()
```

Also require two indexes: `final_snapshot_hash`, `finalized_by_session_id`.

- [ ] **Step 2: Write RED immutable-trigger tests**

Statically require `BEFORE UPDATE OR DELETE` and error token `FEDERATION_FINALIZATION_IMMUTABLE`.

- [ ] **Step 3: Run RED SQL tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_supabase_adapter.py \
  tests/devfabric/test_federation_finalization.py
```

Expected: FAIL because the migration does not exist.

- [ ] **Step 4: Implement table/grants/RLS/trigger**

Use the exact schema from the approved spec. Explicitly:

```sql
alter table destruktion_meta.federated_epoch_finalization enable row level security;
alter table destruktion_meta.federated_epoch_finalization force row level security;
revoke all on table destruktion_meta.federated_epoch_finalization from public, anon, authenticated;
revoke all on table destruktion_meta.federated_epoch_finalization from service_role;
grant select, insert on table destruktion_meta.federated_epoch_finalization to service_role;
```

The immutable trigger raises `FEDERATION_FINALIZATION_IMMUTABLE` on every UPDATE/DELETE.

- [ ] **Step 5: Implement `finalization_get_v1`**

Return the immutable row as JSON or SQL `null`; use `SECURITY INVOKER`, fixed search path, revoke execute from `PUBLIC/anon/authenticated`, grant only `service_role`.

- [ ] **Step 6: Implement `finalize_epoch_v1` with server-side cut reconstruction**

The function must:

1. validate lowercase 64-hex hashes and `p_protocol_version='D6.FINALIZATION.1'`;
2. lock epoch `FOR UPDATE`;
3. check existing finalization first: exact same `finalization_hash` returns `already_finalized=true`; different row raises `FEDERATION_FINALIZATION_CONFLICT`;
4. require mutable epoch state and current active C0 generation;
5. load the referenced snapshot for the same epoch;
6. build `v_live_cut` with deterministic `jsonb_agg(... ORDER BY ...)` for all arrays;
7. require `v_live_cut IS NOT DISTINCT FROM p_recovery_cut`;
8. require embedded terminal snapshot matches the referenced snapshot row;
9. insert finalization;
10. set epoch `CLOSED`, set `closed_at`;
11. release/revoke active epoch sessions;
12. turn remaining `CLAIMED` assignments into `RELEASED`;
13. restore globally shared slot state only when no other active session occupies the slot.

Return only hashes/ids and `already_finalized`.

- [ ] **Step 7: Run GREEN static SQL tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_supabase_adapter.py \
  tests/devfabric/test_federation_finalization.py
```

Expected: PASS for table/RPC/privilege contracts.

- [ ] **Step 8: Commit Task 4**

```bash
git add storage/federated_chat_fabric_d6_finalization.sql \
        tests/devfabric/test_federation_supabase_adapter.py \
        tests/devfabric/test_federation_finalization.py
git commit -m "feat(d6): add immutable epoch finalization migration"
```

---

### Task 5: Add explicit CLOSED/ABORTED barriers to every epoch-targeting mutation RPC

**Files:**
- Modify: `storage/federated_chat_fabric_d6_finalization.sql`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`
- Modify: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- Replaces existing RPC definitions in the new migration using `CREATE OR REPLACE`, without editing the historical D6-D migration.
- Error contract: `FEDERATION_EPOCH_IMMUTABLE` for CLOSED/ABORTED epoch writes.

- [ ] **Step 1: Write RED parameterized barrier test**

Require explicit immutable-epoch protection in these exact functions:

```python
MUTATING_RPCS = (
    "metaengine_federation_register_v1",
    "metaengine_federation_claim_task_v1",
    "metaengine_federation_progress_v1",
    "metaengine_federation_submit_candidate_v1",
    "metaengine_federation_submit_review_v1",
    "metaengine_federation_submit_conflict_v1",
    "metaengine_federation_propose_integration_v1",
    "metaengine_federation_publish_snapshot_v1",
    "metaengine_federation_seed_task_v1",
    "metaengine_federation_reclaim_slot_v1",
)
```

Each function body must contain `FEDERATION_EPOCH_IMMUTABLE` after deriving/locking its epoch.

- [ ] **Step 2: Run RED test**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_supabase_adapter.py -k immutable
```

Expected: FAIL until all ten replacement definitions exist in the finalization migration.

- [ ] **Step 3: Add fail-closed guards without changing successful OPEN behavior**

For direct `p_epoch_id` RPCs:

```sql
select state into v_epoch_state
from destruktion_meta.federated_epoch
where epoch_id = p_epoch_id;
if v_epoch_state in ('CLOSED','ABORTED') then
  raise exception 'FEDERATION_EPOCH_IMMUTABLE';
end if;
```

For task/candidate/review RPCs, derive epoch from the task/candidate before checking caller freshness so CLOSED writes consistently return the immutable-epoch error.

- [ ] **Step 4: Keep `release_v1`, read RPCs, role-genome seed, and `open_epoch_v1` unchanged**

Do not add a global block to `metaengine_federation_seed_role_genome_v1`; it is not epoch-local. Do not add finalization to MCP.

- [ ] **Step 5: Run full federation SQL contract suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_supabase_adapter.py \
  tests/devfabric/test_federation_finalization.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add storage/federated_chat_fabric_d6_finalization.sql \
        tests/devfabric/test_federation_supabase_adapter.py \
        tests/devfabric/test_federation_finalization.py
git commit -m "fix(d6): freeze writes after epoch finalization"
```

---

### Task 6: Add fixed Supabase adapter methods and prove the MCP surface stays exactly 18 tools

**Files:**
- Modify: `metaengine/devfabric/federation/supabase_federation.py`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`
- Modify: `devfabric/cloudflare/test/federation_contract.test.ts`
- Modify: `devfabric/cloudflare/test/federation_tools.test.ts`

**Interfaces:**
- Produces: `finalize_epoch_internal(...) -> object` calling only `metaengine_federation_finalize_epoch_v1`.
- Produces: `finalization_get_internal(epoch_id: str) -> object` calling only `metaengine_federation_finalization_get_v1`.
- Does not change `FederationRpcTransport` or expose generic RPC/SQL.

- [ ] **Step 1: Write RED adapter routing/validation tests**

Test exact parameter names and pre-transport validation:

```python
adapter.finalize_epoch_internal(
    session_id="c0-session",
    expected_generation=2,
    epoch_id="epoch-1",
    finalization_hash="a" * 64,
    final_snapshot_hash="b" * 64,
    recovery_cut_hash="c" * 64,
    recovery_cut=sample_cut(),
    protocol_version="D6.FINALIZATION.1",
)
assert transport.calls[-1][0] == "metaengine_federation_finalize_epoch_v1"
```

Reject generation `< 0`, malformed hashes, empty epoch/session IDs, unsupported protocol version, and non-mapping cut before transport.

- [ ] **Step 2: Write RED MCP invariance tests**

Keep exact set equality to the existing 18 names. Add explicit negative assertions for `finalize`, `finalization_get`, `epoch_close`, `recovery_cut` substrings in exported chat tools.

- [ ] **Step 3: Implement the two fixed internal adapter methods**

Use `_call()` with hard-coded RPC names; do not add them to `devfabric/cloudflare/src/federation_client.ts`, `federation_contract.ts`, `federation_tools.ts`, or `mcp.ts`.

- [ ] **Step 4: Run Python + Node tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_supabase_adapter.py \
  tests/devfabric/test_federation_finalization.py
node --experimental-strip-types --test \
  devfabric/cloudflare/test/federation_contract.test.ts \
  devfabric/cloudflare/test/federation_tools.test.ts
```

Expected: all PASS; MCP still exactly 18 tools.

- [ ] **Step 5: Commit Task 6**

```bash
git add metaengine/devfabric/federation/supabase_federation.py \
        tests/devfabric/test_federation_supabase_adapter.py \
        devfabric/cloudflare/test/federation_contract.test.ts \
        devfabric/cloudflare/test/federation_tools.test.ts
git commit -m "feat(d6): expose fixed internal finalization RPCs"
```

---

### Task 7: Add portable finalization protocol and D6-G0 verification/gate contract

**Files:**
- Create: `chat_federation/FINALIZATION_PROTOCOL.json`
- Modify: `chat_federation/PILOT_RUNBOOK.md`
- Modify: `devfabric/verification/profiles.toml`
- Modify: `metaengine/devfabric/capsule.py`
- Modify: `tests/devfabric/test_federation_pilot.py`
- Modify: `tests/devfabric/test_federation_bootstrap.py`
- Modify: `tests/devfabric/test_federation_finalization.py`

**Interfaces:**
- New external gate version: `METAENGINE-DEVFABRIC-STAGE-D6-G0-GATE-1`.
- New verifier profile: `federation-finalization`.
- Portable protocol marks finalization/internal RPCs as non-chat-facing.

- [ ] **Step 1: Write RED protocol/gate tests**

Require `FINALIZATION_PROTOCOL.json` to declare:

```json
{
  "protocol_version": "D6.FINALIZATION.1",
  "authority": "SUPABASE_ONLY",
  "chat_facing": false,
  "closed_recovery_source": "IMMUTABLE_RECOVERY_CUT",
  "adaptation_eligible_state": "CLOSED"
}
```

Require the gate verifier to accept `METAENGINE-DEVFABRIC-STAGE-D6-G0-GATE-1` and keep `stage-d6-g0-gate.json` outside CONTROL capsules.

- [ ] **Step 2: Add `profiles.federation-finalization`**

Commands must be exactly the observable local surfaces:

```toml
[profiles.federation-finalization]
commands = [
  "python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_finalization.py tests/devfabric/test_federation_synchronizer.py tests/devfabric/test_federation_simulator.py tests/devfabric/test_federation_supabase_adapter.py tests/devfabric/test_federation_pilot.py",
  "node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts devfabric/cloudflare/test/federation_tools.test.ts",
  "tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json",
  "python -m metaengine.devfabric.isolated_suite_runner tests/devfabric --timeout-seconds 180",
  "python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric",
]
```

Do not hide existing `uv/npm/Wrangler` certification blockers inside this profile.

- [ ] **Step 3: Update PILOT_RUNBOOK lifecycle**

Document `PASS_CANARY_MANUAL_RELAY -> FINALIZE -> CLOSED -> release witnesses -> frozen-cut recovery`. Explicitly state manual-relay PASS is not MCP deployment PASS.

- [ ] **Step 4: Run protocol/gate/bootstrap tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/devfabric/test_federation_finalization.py \
  tests/devfabric/test_federation_pilot.py \
  tests/devfabric/test_federation_bootstrap.py
```

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```bash
git add chat_federation/FINALIZATION_PROTOCOL.json \
        chat_federation/PILOT_RUNBOOK.md \
        devfabric/verification/profiles.toml \
        metaengine/devfabric/capsule.py \
        tests/devfabric/test_federation_pilot.py \
        tests/devfabric/test_federation_bootstrap.py \
        tests/devfabric/test_federation_finalization.py
git commit -m "test(d6): add immutable finalization gate"
```

---

### Task 8: Prove the exact migration and recovery semantics on `METAENGINE_STAGING`

**Files:**
- No production source edits during the live probe unless a failing staging gate first produces a new RED regression test.
- Create after PASS: `devfabric/artifacts/manifests/stage-d6-g0-staging-validation.json`.

**Interfaces:**
- Uses staging project `sibnfciqcpkuquxzduqr` only.
- Uses the exact tracked `storage/federated_chat_fabric_d6_finalization.sql`; no hand-reconstructed function bodies.

- [ ] **Step 1: Run the full local pre-deploy verifier**

```bash
python -m metaengine.devfabric.cli verify --profile federation-finalization
```

If the wrapper has the known teardown/transport hang, execute the five profile commands separately and record every exit code; do not convert a timed-out wrapper into PASS.

- [ ] **Step 2: Read-only staging preflight**

Require existing D6-D objects, no `federated_epoch_finalization`, and no open production-like data that would collide with the synthetic epoch.

- [ ] **Step 3: Apply the exact finalization migration to staging**

Use Supabase `apply_migration` with a single named migration such as `metaengine_d6_g0_immutable_epoch_finalization`. Do not modify the canonical project.

- [ ] **Step 4: Audit schema/security after migration**

Require:

- exactly one new finalization table;
- exactly two new public internal finalization RPCs;
- both RPCs `SECURITY INVOKER`;
- RLS + FORCE RLS;
- `service_role`: SELECT + INSERT only on finalization table;
- no UPDATE/DELETE privilege;
- immutable trigger exists;
- no execute for PUBLIC/anon/authenticated;
- no new MCP tools;
- Supabase security advisor has no HIGH/ERROR finding caused by D6-G0;
- performance advisor has no D6-G0 unindexed-FK finding.

- [ ] **Step 5: Seed a synthetic staging epoch and terminal snapshot**

Use synthetic hashes/role genomes and an epoch ID unique to the staging test. Create C0/C2/C4/C6 sessions, tasks, candidates, C6 review, decisions, and terminal snapshot using the existing internal RPCs.

- [ ] **Step 6: Prove atomic failure cases before successful finalization**

Each test uses its own transaction or synthetic epoch and must leave the epoch OPEN with sessions active after failure:

- stale C0 generation -> `FEDERATION_SYNCHRONIZER_FENCED`;
- wrong/nonexistent snapshot -> `FEDERATION_FINAL_SNAPSHOT_INVALID`;
- one-field recovery-cut drift -> `FEDERATION_FINALIZATION_CUT_DRIFT`;
- unsupported version -> `FEDERATION_FINALIZATION_VERSION_UNSUPPORTED`.

- [ ] **Step 7: Finalize staging epoch successfully**

Require one finalization row, epoch `CLOSED`, zero active sessions, claimed assignments released, terminal snapshot hash unchanged, and exact cut hash returned.

- [ ] **Step 8: Prove idempotence/immutability/closed barriers**

Require:

- exact repeat finalization -> `already_finalized=true`;
- different repeat -> `FEDERATION_FINALIZATION_CONFLICT`;
- UPDATE/DELETE finalization -> `FEDERATION_FINALIZATION_IMMUTABLE`;
- late register/claim/progress/candidate/review/conflict/integration/snapshot/task-seed/reclaim -> `FEDERATION_EPOCH_IMMUTABLE`.

- [ ] **Step 9: Prove frozen recovery after witness release**

Fetch `finalization_get_v1`, run Python `recover_from_cut`, require same final snapshot hash and same integration order after all staging sessions are released.

- [ ] **Step 10: Run advisors and write staging evidence manifest**

Record project ref, migration file SHA-256, object counts, RPC signatures, privilege audit, advisor summaries, negative-test outcomes, final snapshot hash, cut hash, and `canonical_writes=0`.

- [ ] **Step 11: Commit only the staging evidence manifest after PASS**

```bash
git add devfabric/artifacts/manifests/stage-d6-g0-staging-validation.json
git commit -m "test(d6): attest staging epoch finalization"
```

If any staging invariant fails, stop canonical rollout, write a failing regression first, fix source through TDD, re-run from Step 1, and do not patch staging ad hoc.

---

### Task 9: Deploy to canonical, finalize the real D6-F epoch, recover after witness release, and attest D6-G0

**Files:**
- Modify/Create: `devfabric/artifacts/manifests/stage-d6-g0-gate.json`
- Create external evidence copy under `/mnt/data/METAENGINE_DEVFABRIC_STAGE_D6G0_GATE_2026-08-13.json` after the tracked gate is committed.
- Rebuild external CONTROL capsules after the final tracked commit.

**Interfaces:**
- Canonical project: `gzrbxoiuenkksualgpvp`.
- Real epoch: `d6f-ui-canary-20260813-e001`.
- Expected terminal snapshot: `00977f5cc3ada234fe2355bd1d8ab2c8479e1a0b9eefbd3f061269c2b74fc056`.
- Expected integration order: C4 candidate `a169aa60f13d372cefacf12aece37e797d7fddb9bd9a10f12e7a1eed0c0c5b02`, then C2 candidate `e63c442005f07e4f111ab8871d77b880870c5639c260913c8bf8eed6e5c127a2`.

- [ ] **Step 1: Canonical read-only preflight**

Require:

- epoch remains `OPEN`;
- C0-g2, C2-g1, C4-g1, C6-g1 are the active witnesses expected by the D6-F receipt;
- final snapshot row exists exactly once with the expected hash;
- no finalization row exists yet;
- cp001/current policy/champion/promotion state match pre-D6-G0 evidence.

Abort canonical deployment on any mismatch.

- [ ] **Step 2: Apply the exact staging-validated migration to canonical**

Use the exact tracked migration bytes/SHA validated on staging. Do not reconstruct SQL in the tool call from memory; pass the tracked migration content.

- [ ] **Step 3: Post-DDL canonical security/object audit**

Repeat the same table/RPC/RLS/grant/trigger/advisor checks that passed on staging before calling finalization.

- [ ] **Step 4: Build the real recovery cut from canonical rows**

Read the epoch/tasks/assignments/candidates/reviews/conflicts/decisions/sessions/terminal snapshot, normalize with the Python finalization module, compute `recovery_cut_hash`, and compute `finalization_hash`. The cut must contain no chat prose, prompt bodies, secrets, P3, or arbitrary source content.

- [ ] **Step 5: Finalize through current C0-g2**

Call `metaengine_federation_finalize_epoch_v1` with the current actual C0 generation. Require:

- returned terminal snapshot hash equals `00977f5cc3ada234fe2355bd1d8ab2c8479e1a0b9eefbd3f061269c2b74fc056`;
- one immutable finalization row;
- epoch state `CLOSED`;
- active sessions for the epoch = `0`;
- remaining CLAIMED assignments = `0`.

- [ ] **Step 6: Prove post-close recovery without witnesses**

Fetch the finalization row through `finalization_get_v1`, independently recompute cut hash, reconstruct snapshot in Python, and require:

```text
snapshot_hash = 00977f5cc3ada234fe2355bd1d8ab2c8479e1a0b9eefbd3f061269c2b74fc056
integration_order = [C4 candidate, C2 candidate]
active_sessions = 0
```

This is the proof that the D6-F freeze window has been removed.

- [ ] **Step 7: Run canonical late-write adversarial probes**

Attempt register, candidate/review/integration/snapshot/task-seed/reclaim against the CLOSED epoch with valid-looking current identifiers. Every write must fail `FEDERATION_EPOCH_IMMUTABLE`, and row counts must be unchanged after each probe.

- [ ] **Step 8: Re-audit canonical authority objects**

Require cp001 still `VERIFIED/current`, payload root unchanged, active architecture policy unchanged, champion pointer unchanged, no promotion receipt created by D6-G0, and no checkpoint proposal created by finalization.

- [ ] **Step 9: Update the D6-G0 gate manifest**

Use these status families:

```json
{
  "development_status": "PASS",
  "staging_status": "PASS_IMMUTABLE_FINALIZATION",
  "canonical_status": "PASS_D6F_EPOCH_FINALIZED",
  "closed_recovery_status": "PASS_FROZEN_CUT_NO_LIVE_WITNESSES",
  "multi_chat_ui_status": "PASS_CANARY_MANUAL_RELAY",
  "mcp_status": "PASS_LOCAL_CORE_EXTERNAL_DEPLOYMENT_NOT_CLAIMED",
  "adaptation_readiness": "READY_FINALIZED_EPOCHS_ONLY",
  "certification_status": "BLOCKED_EXTERNAL_NODE_TOOLCHAIN",
  "release_promotion_status": "BLOCKED"
}
```

Record finalization hash, recovery-cut hash, terminal snapshot hash, migration SHA, staging/canonical project refs, zero active sessions, closed-epoch adversarial results, and unchanged canonical authority hashes.

- [ ] **Step 10: Fresh post-attestation local verification**

After committing the gate manifest, run the five `federation-finalization` profile commands from the final HEAD. If the wrapper hangs, record the five individual exit codes. Also run:

```bash
python -m compileall -q metaengine

git diff --check HEAD~1..HEAD
```

Require all available local development checks PASS; retain external npm/Wrangler/uv blockers explicitly.

- [ ] **Step 11: Build CONTROL capsule twice and verify deterministic recovery**

Build two capsules from the final tracked HEAD. Require identical archive SHA-256, identical payload root, `secret_hits=0`, `bad=0`, `missing=0`, `extra=0`, and the existing 9,839-entry lineage lock unchanged.

- [ ] **Step 12: Commit final D6-G0 attestation**

```bash
git add devfabric/artifacts/manifests/stage-d6-g0-gate.json
git commit -m "attest(d6): finalize immutable federation epoch"
```

Then create the external gate receipt/capsule copies without feeding them back into the capsule payload.

---

## Plan Self-Review Checklist

- Spec coverage: all invariants in Sections 2-16 map to Tasks 1-9; adaptation itself remains out of scope, but `adaptation_readiness` requires verified CLOSED epochs only.
- Placeholder scan: clean; every code/error/test step is explicit and self-contained.
- Type consistency: protocol is `D6.FINALIZATION.1`; Python and SQL use `recovery_cut_hash`, `final_snapshot_hash`, `finalization_hash`; internal RPC names match the approved spec.
- Historical migration discipline: original `storage/federated_chat_fabric_d6.sql` is not edited by D6-G0; replacements live only in `storage/federated_chat_fabric_d6_finalization.sql`.
- Idempotence/state consistency: identical re-finalization is checked before CLOSED rejection; conflicting re-finalization is rejected.
- Security consistency: finalization table is service-role SELECT/INSERT only plus immutable trigger; no `SECURITY DEFINER`; no new MCP tools.
- Recovery consistency: CLOSED recovery has no fallback to mutable head state.
- Rollout consistency: exact tracked migration is validated on staging before canonical apply; canonical epoch finalization occurs only after post-DDL audit.
