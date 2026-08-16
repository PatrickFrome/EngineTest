# Stage D6-G0 Immutable Epoch Finalization Design

**Status:** APPROVED DESIGN — specification gate before implementation planning  
**Date:** 2026-08-13  
**Parent evidence:** D6-F `PASS_CANARY_MANUAL_RELAY`  
**Parent attestation commit:** `cf0231e3599ac89382fc15c557df65215ddb9480`

## 1. Purpose

D6-F proved that a replacement ordinary ChatGPT C0 can reproduce the same synchronization snapshot and integration order from federation ledger state only. It also exposed a structural limitation: current `Synchronizer.recover(epoch_id)` is a live re-projection of mutable ledger head state. Historical recovery therefore remains valid only while the producer/reviewer witnesses used by eligibility and review validation remain unchanged.

D6-G0 removes that freeze-window dependency before adaptive Role Genome learning begins.

The stage adds an immutable, append-only finalization record that freezes the semantic recovery projection and final synchronization snapshot of an epoch. After finalization, the epoch is `CLOSED`, its sessions are fenced/released, all federation mutations against the closed epoch fail closed, and historical recovery uses only the frozen cut rather than active session state.

D6-G0 does **not** promote a canonical checkpoint, mutate champion/policy state, deploy MCP, or enable adaptive specialization by itself.

## 2. Non-negotiable invariants

1. Supabase remains the sole canonical federation ledger authority.
2. Canonical checkpoint/champion/architecture-policy authority is unchanged.
3. Exactly one immutable finalization is allowed per epoch.
4. A finalization row is append-only: no UPDATE or DELETE path exists, including for `service_role`.
5. A finalization can be created only by the currently active, unfenced C0 session for that epoch.
6. Finalization is atomic with epoch close and active-session release/fencing.
7. The supplied recovery cut must be semantically identical to the live ledger projection observed inside the finalization transaction.
8. The supplied final snapshot hash must reference an existing snapshot row for the same epoch.
9. Closed-epoch recovery never consults current active sessions, current slot generations, or previous C0 prose.
10. All write RPCs that target an epoch reject `CLOSED`/`ABORTED` epochs unless their operation is explicitly defined as read-only or idempotent cleanup.
11. No finalization operation performs checkpoint promotion, champion mutation, policy mutation, or executable self-modification.
12. D6-G adaptation may consume only finalized epochs.

## 3. Why append-only finalization is the selected design

### Rejected: snapshot-only finalization

Persisting only a final snapshot would preserve the output but not the exact semantic ledger evidence from which the output was derived. It would be insufficient for independent recovery verification and unsafe as a training/adaptation source.

### Rejected for D6-G0: full federation event sourcing

Versioning every federation table and reconstructing arbitrary historical cuts is stronger but substantially expands schema, query, migration, and operational complexity. D6-G0 needs one unambiguous terminal cut per epoch, not general time travel.

### Selected: one immutable terminal recovery cut per epoch

The cut preserves exactly the semantic projection required for deterministic synchronization while keeping the current D6 table model intact. It is small enough for a bounded canary epoch, independently hashable, and sufficient to detach historical recovery from mutable session state.

## 4. New canonical object

Create a new migration, separate from the original D6-D ledger migration:

`storage/federated_chat_fabric_d6_finalization.sql`

It adds one table:

```sql
create table destruktion_meta.federated_epoch_finalization (
  finalization_hash text primary key,
  epoch_id text not null unique
    references destruktion_meta.federated_epoch(epoch_id),
  final_snapshot_hash text not null
    references destruktion_meta.federated_sync_snapshot(snapshot_hash),
  recovery_cut_hash text not null,
  recovery_cut jsonb not null,
  finalized_by_session_id text not null
    references destruktion_meta.federated_session(session_id),
  finalized_by_generation bigint not null check (finalized_by_generation >= 0),
  protocol_version text not null,
  finalized_at timestamptz not null default now(),
  check (finalization_hash ~ '^[0-9a-f]{64}$'),
  check (recovery_cut_hash ~ '^[0-9a-f]{64}$')
);
```

Additional requirements:

- index `final_snapshot_hash` and `finalized_by_session_id` foreign-key paths;
- ENABLE RLS + FORCE RLS;
- `anon`/`authenticated`: no schema/table access;
- `service_role`: SELECT + INSERT only;
- explicit REVOKE UPDATE/DELETE from `service_role`;
- immutable trigger rejects UPDATE and DELETE for every role as defense in depth;
- no `SECURITY DEFINER` functions.

The existing `federated_sync_snapshot` table remains historical and may contain pre-finalization snapshots. The finalization row identifies the single authoritative terminal snapshot for the epoch.

## 5. Recovery-cut schema

The recovery cut is protocol-versioned JSON. Its first version is `D6.FINALIZATION.1`.

Required shape:

```json
{
  "cut_version": "D6.FINALIZATION.1",
  "epoch": {
    "epoch_id": "...",
    "base_checkpoint_id": "...",
    "base_payload_root": "...",
    "federation_policy_hash": "...",
    "role_catalog_hash": "...",
    "producer_concurrency": 2
  },
  "tasks": [],
  "assignments": [],
  "candidates": [],
  "reviews": [],
  "conflicts": [],
  "integration_decisions": [],
  "participant_witnesses": [],
  "terminal_snapshot": {
    "snapshot_hash": "...",
    "snapshot": {}
  }
}
```

### 5.1 Included semantic evidence

The cut includes the fields that can affect synchronization or independent audit:

- epoch identity and pinned checkpoint/policy/catalog/concurrency;
- task identity, version, owner slot, role profile, dependency set, write/interface sets, risk/review requirements;
- assignment identity/state/generation relevant to the epoch;
- candidate identity, task/session/generation, eligibility, verification hashes, and receipt metadata required for audit;
- review identity, reviewer session/slot/generation, verdict, verification hashes, and receipt metadata required for audit;
- conflict identities/classes/candidate references/resolution references;
- integration decision identities/candidate references/decision values;
- participant session witnesses `(slot_id, session_id, lease_generation, role_profile_hash, revoked, released_at)` at the cut boundary;
- the terminal synchronization snapshot row.

### 5.2 Explicit exclusions

The cut never stores:

- ordinary-chat prose or conversation history;
- prompts;
- secrets or service-role credentials;
- P3 content;
- arbitrary source files or patch bodies;
- ambient Project memory;
- external telemetry payloads.

P1/P2 receipt content must remain within the already defined federation privacy rules. P3 remains local-only and cannot enter the finalization cut.

### 5.3 Determinism

Arrays are constructed in deterministic order:

- tasks by `task_hash`;
- assignments by `assignment_id`;
- candidates by `candidate_hash`;
- reviews by `review_hash`;
- conflicts by `conflict_hash`;
- integration decisions by `decision_hash`;
- participant witnesses by `(slot_id, session_id)`.

The client computes `recovery_cut_hash` with the existing Metaengine canonical JSON SHA-256 function. The database does not treat the supplied hash alone as authority: it reconstructs the live semantic projection inside the transaction and requires JSON semantic equality with the supplied cut before committing finalization. Read-side verification recomputes the canonical hash independently.

## 6. Internal RPC surface

D6-G0 adds two service-role-only RPCs. They are **not** added to the 18-tool chat-facing MCP allowlist.

### 6.1 `metaengine_federation_finalize_epoch_v1`

Inputs:

- `p_session_id text`
- `p_expected_generation bigint`
- `p_epoch_id text`
- `p_finalization_hash text`
- `p_final_snapshot_hash text`
- `p_recovery_cut_hash text`
- `p_recovery_cut jsonb`
- `p_protocol_version text`

Behavior, in one transaction:

1. Validate all hashes and protocol version.
2. Lock `federated_epoch` row `FOR UPDATE`.
3. Require epoch state `OPEN` or `INTEGRATING`; reject `CLOSED` and `ABORTED`.
4. Lock/validate the supplied C0 session and current C0 slot generation.
5. Require session to be active, unfenced, in the same epoch, role `C0`, and generation equal to `p_expected_generation`.
6. Require `p_final_snapshot_hash` to reference a snapshot row in the same epoch.
7. Construct `v_live_cut` from the federation tables using deterministic ordering.
8. Require `v_live_cut IS NOT DISTINCT FROM p_recovery_cut`; otherwise raise `FEDERATION_FINALIZATION_CUT_DRIFT`.
9. Require the terminal snapshot embedded in the cut to match the referenced snapshot row exactly.
10. Require no existing finalization for the epoch. If one exists with the exact same `finalization_hash`, return an idempotent `already_finalized=true`; any different content raises `FEDERATION_FINALIZATION_CONFLICT`.
11. Insert the immutable finalization row.
12. Set epoch state to `CLOSED` and `closed_at=now()`.
13. Revoke/release all still-active sessions for the epoch and update their `last_seen_at`.
14. Change any remaining `CLAIMED` assignments for those sessions to `RELEASED`; already completed/stale assignments remain unchanged.
15. Restore each globally shared slot to its non-active base state (`C6 -> REVIEW_ONLY`, others -> IDLE`) only if no other active session currently occupies that slot.
16. Return only non-secret finalization identifiers and hashes.

The RPC performs no checkpoint proposal, checkpoint promotion, champion mutation, or architecture-policy mutation.

### 6.2 `metaengine_federation_finalization_get_v1`

Input: `p_epoch_id text`.

Returns the immutable finalization row or `null`. This RPC is service-role-only and internal to synchronizer/adaptation code. It is not exposed as a new ordinary-chat MCP tool in D6-G0.

## 7. Closed-epoch mutation barrier

Finalization is incomplete if other RPCs can mutate the same epoch afterward.

The following epoch-targeting mutations must check epoch state and reject `CLOSED`/`ABORTED` with `FEDERATION_EPOCH_IMMUTABLE`:

- registration into an existing epoch;
- task claim/progress;
- candidate submission;
- review submission;
- conflict submission;
- integration proposal;
- snapshot publication;
- internal task seeding;
- internal slot reclaim scoped to the closed epoch.

`release_v1` remains a session-lifecycle operation, but finalization already releases all active sessions atomically; a second release on an inactive session continues to fail as inactive/idempotent cleanup policy dictates.

Read-only RPCs remain available for historical inspection.

Role-genome insertion is not epoch-local and is therefore not blocked globally by the closure of one epoch.

## 8. Synchronizer recovery semantics

Current behavior:

```python
def recover(epoch_id):
    return snapshot(epoch_id)  # live head re-projection
```

D6-G0 behavior:

```text
if epoch is OPEN/INTEGRATING:
    recover = live snapshot/re-projection
elif epoch is CLOSED:
    load immutable finalization
    verify recovery_cut_hash
    reconstruct snapshot from frozen cut only
    verify reconstructed snapshot_hash == final_snapshot_hash
    return reconstructed snapshot
else:
    fail closed
```

### 8.1 New local interfaces

Add a typed immutable `EpochFinalization` contract and store methods conceptually equivalent to:

- `put_finalization(...)` for the local simulator;
- `get_finalization(epoch_id)`;
- `close_epoch(...)`;
- `recover_from_cut(finalization)`.

For Supabase, `SupabaseFederationAdapter` receives only fixed methods for the two new RPCs. No generic SQL/RPC method is introduced.

### 8.2 Recovery verification

Closed recovery must verify all of the following:

1. `canonical_digest(recovery_cut) == recovery_cut_hash`;
2. finalization epoch ID equals the requested epoch;
3. terminal snapshot embedded in the cut has the recorded `final_snapshot_hash`;
4. deterministic reconstruction from the frozen cut produces the same `SynchronizationSnapshot` fields;
5. reconstructed `snapshot_hash == final_snapshot_hash`.

Any mismatch raises a finalization/recovery integrity error and must not fall back to mutable live state.

## 9. Epoch lifecycle

D6-G0 makes the state machine operationally strict:

```text
OPEN
  ├─ normal federation work
  └─> INTEGRATING (optional orchestration state)
          └─> CLOSED  -- only by successful immutable finalization

OPEN/INTEGRATING
  └─> ABORTED -- failure path, never adaptation-eligible

CLOSED
  └─ terminal; no reopen transition
```

A CLOSED epoch is historical evidence, not an active coordination domain.

## 10. Interaction with D6-G adaptive specialization

D6-G must consume only epochs satisfying all of:

- `federated_epoch.state = 'CLOSED'`;
- exactly one `federated_epoch_finalization` row exists;
- recovery-cut hash independently verifies;
- closed recovery reproduces `final_snapshot_hash`;
- finalization protocol version is supported.

Metrics/adaptation derived from OPEN, INTEGRATING, ABORTED, corrupt, or unverifiable epochs are rejected.

Soft Role Genome updates remain append-only and apply only to future tasks. D6-G0 does not relax any hard Role Genome field, mandatory review rule, privacy ceiling, slot topology, or authority boundary.

## 11. Failure handling

Finalization is fail-closed and transactionally atomic.

Examples:

- stale C0 generation -> `FEDERATION_SYNCHRONIZER_FENCED`;
- non-C0 caller -> `FEDERATION_FINALIZER_FORBIDDEN`;
- missing/wrong snapshot -> `FEDERATION_FINAL_SNAPSHOT_INVALID`;
- live ledger changed after cut construction -> `FEDERATION_FINALIZATION_CUT_DRIFT`;
- conflicting second finalization -> `FEDERATION_FINALIZATION_CONFLICT`;
- write against CLOSED epoch -> `FEDERATION_EPOCH_IMMUTABLE`;
- hash mismatch during read/recovery -> `FEDERATION_FINALIZATION_INTEGRITY_ERROR`;
- unsupported cut/protocol version -> `FEDERATION_FINALIZATION_VERSION_UNSUPPORTED`.

No error path silently reopens a closed epoch, rewrites a finalization row, or falls back from frozen recovery to live-head recovery.

## 12. Security model

- All new functions are `SECURITY INVOKER`.
- `search_path` is fixed to `pg_catalog, destruktion_meta`.
- Default PUBLIC execute is explicitly revoked.
- Execute is granted only to `service_role`.
- No finalization tool is added to the ordinary-chat MCP allowlist.
- Service-role credentials remain outbound/server-only and are not stored in cuts/receipts/errors.
- Table UPDATE/DELETE are revoked and also blocked by immutable trigger.
- RLS + FORCE RLS remain defense in depth on the private schema.
- Supabase security/performance advisors are mandatory after migration.

## 13. Migration and validation sequence

The implementation must preserve the project’s zero-spend staging discipline:

1. TDD locally against SQLite/contracts and SQL static checks.
2. Apply the new migration to `METAENGINE_STAGING` only.
3. Run live staging finalization with synthetic/noncanonical epoch data.
4. Verify table/RPC/grants/RLS/immutable-trigger/advisors.
5. Verify finalization cut drift rejection and conflicting second-finalization rejection.
6. Verify all closed-epoch write barriers.
7. Verify closed recovery after all participant sessions have been released.
8. Only after staging PASS apply the exact migration/RPC definitions to canonical Supabase.
9. Finalize the real D6-F epoch `d6f-ui-canary-20260813-e001`.
10. Expected final snapshot hash must remain:
   `00977f5cc3ada234fe2355bd1d8ab2c8479e1a0b9eefbd3f061269c2b74fc056`.
11. Confirm active sessions for that epoch become zero.
12. Recover after witness release and require the same snapshot hash and the same C4 -> C2 integration order.
13. Attempt late registration/candidate/review/integration/snapshot/task-seed mutation and require `FEDERATION_EPOCH_IMMUTABLE`.
14. Re-audit cp001, active policy, champion pointer, and promotion state as unchanged.

Canonical deployment remains a separate explicit gate after staging validation.

## 14. Test strategy

### Contract/unit tests

- deterministic recovery-cut canonicalization;
- cut-order invariance to database row insertion order;
- immutable finalization object hashing;
- closed recovery independent of active sessions;
- recovery hash mismatch fail-closed;
- unsupported cut version fail-closed;
- duplicate identical finalization idempotent;
- duplicate conflicting finalization rejected.

### SQL contract tests

- one new table only;
- table has RLS + FORCE RLS;
- service role has SELECT/INSERT and lacks UPDATE/DELETE;
- immutable trigger covers UPDATE and DELETE;
- two expected internal RPCs only;
- both functions are `SECURITY INVOKER`;
- PUBLIC/anon/authenticated execute revoked;
- no new MCP tool names;
- every epoch-targeting mutation RPC contains closed-state protection.

### Live Supabase tests

- finalization succeeds with current C0 generation;
- stale C0 finalization rejected;
- cut drift rejected atomically;
- final snapshot mismatch rejected atomically;
- sessions released only after successful insert/close;
- post-close active session count = 0;
- late mutation attempts rejected;
- finalization row update/delete rejected;
- finalization get returns exact immutable cut;
- recovery after witness disappearance reproduces final snapshot.

### Regression gates

- full federation Python profile;
- Stage D/D6 Node core tests;
- core TypeScript typecheck where available;
- engine suite;
- `compileall`;
- `git diff --check`;
- 9,839 lineage invariant;
- CONTROL capsule deterministic rebuild/recovery;
- no new secrets.

External npm/Wrangler/toolchain blockers remain separate certification facts and cannot be converted into PASS by D6-G0.

## 15. Completion criteria

D6-G0 is complete only when all are true:

1. The new finalization migration is tracked and reproducible.
2. Staging finalization and closed recovery pass.
3. Exact canonical migration passes post-deploy security/privilege checks.
4. The real D6-F canary epoch is `CLOSED` with one immutable finalization row.
5. C0/C2/C4/C6 active sessions for that epoch are zero.
6. Closed recovery reproduces snapshot hash `00977f5c...c056` and the same integration order.
7. Old/live witness state is no longer required for recovery.
8. Late mutations against the closed epoch fail closed.
9. cp001/champion/active policy remain unchanged.
10. D6-G adaptation code is still disabled until this gate is PASS.

## 16. Explicitly out of scope

- full event sourcing or arbitrary historical time-travel cuts;
- Cloudflare/Federation MCP deployment;
- checkpoint promotion;
- champion or architecture-policy mutation;
- new slot types or more than C0-C7;
- hard Role Genome adaptation;
- executable self-modification;
- adaptation itself (implemented in D6-G after D6-G0 PASS).
