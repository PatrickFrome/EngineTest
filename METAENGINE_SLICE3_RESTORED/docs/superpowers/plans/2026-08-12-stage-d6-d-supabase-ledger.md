# Stage D.6-D Supabase Federation Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a private, RLS-hardened Supabase federation ledger with CAS/fencing semantics and a narrow service-role-only RPC surface, while preserving `chat_capsule_checkpoint(checkpoint_id)` as the checkpoint chain.

**Architecture:** Federation tables live in `destruktion_meta`. Public RPC functions are `SECURITY INVOKER`, fixed-function, service-role-only entry points so the Cloudflare/MCP layer cannot issue arbitrary SQL. All federation tables use RLS + FORCE RLS and deny anon/authenticated table privileges.

**Tech Stack:** PostgreSQL 17/Supabase, SQL migration, existing Supabase connector, Python adapter tests.

## Global Constraints

- Actual current checkpoint PK is `destruktion_meta.chat_capsule_checkpoint.checkpoint_id TEXT`.
- `service_role` currently has SELECT/INSERT/UPDATE/DELETE on the checkpoint table; anon/authenticated have no table grants in the private schema.
- DDL must be performed through `apply_migration`, never `execute_sql`.
- Before canonical DDL, validate on a Supabase development branch if a zero-cost branch is available. If creating the branch would incur cost or cannot be confirmed zero-spend, stop with `BLOCKED_ZERO_SPEND_BRANCH_VALIDATION`; do not silently apply canonical DDL.
- No `SECURITY DEFINER` federation function.
- No public/anon/authenticated execute grants on write RPCs.

---

### Task 1: Write migration contract tests before SQL

**Files:**
- Create: `tests/devfabric/test_federation_supabase_adapter.py`
- Create: `storage/federated_chat_fabric_d6.sql`

- [ ] **Step 1: RED static migration assertions**

Test that the SQL file must contain all twelve physical federation tables, `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, an explicit `REVOKE ALL ON TABLE` statement for each of the twelve named federation tables against both `anon` and `authenticated`, and must not contain `SECURITY DEFINER` or any grant to `anon`/`authenticated`.

- [ ] **Step 2: Write complete private table schema**

The migration must create:

```sql
create table if not exists destruktion_meta.federated_epoch (
  epoch_id text primary key,
  base_checkpoint_id text not null references destruktion_meta.chat_capsule_checkpoint(checkpoint_id),
  base_payload_root text not null check (base_payload_root ~ '^[0-9a-f]{64}$'),
  federation_policy_hash text not null check (federation_policy_hash ~ '^[0-9a-f]{64}$'),
  role_catalog_hash text not null check (role_catalog_hash ~ '^[0-9a-f]{64}$'),
  producer_concurrency integer not null check (producer_concurrency between 2 and 6),
  state text not null check (state in ('OPEN','INTEGRATING','CLOSED','ABORTED')),
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create table if not exists destruktion_meta.federated_slot (
  slot_id text primary key check (slot_id in ('C0','C1','C2','C3','C4','C5','C6','C7')),
  role_name text not null,
  state text not null check (state in ('ACTIVE','IDLE','REVIEW_ONLY','SUSPENDED','RECLAIMABLE')),
  lease_generation bigint not null default 0 check (lease_generation >= 0)
);

create table if not exists destruktion_meta.federated_role_genome (
  role_profile_hash text primary key check (role_profile_hash ~ '^[0-9a-f]{64}$'),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  genome_version text not null,
  parent_profile_hash text references destruktion_meta.federated_role_genome(role_profile_hash),
  hard_genome jsonb not null,
  soft_genome jsonb not null,
  created_at timestamptz not null default now(),
  unique (slot_id, genome_version)
);

create table if not exists destruktion_meta.federated_session (
  session_id text primary key,
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  lease_generation bigint not null,
  capsule_sha256 text not null check (capsule_sha256 ~ '^[0-9a-f]{64}$'),
  protocol_version text not null,
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  revoked boolean not null default false,
  released_at timestamptz,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create unique index if not exists federated_session_one_active_slot
  on destruktion_meta.federated_session(epoch_id, slot_id)
  where revoked = false and released_at is null;

create table if not exists destruktion_meta.federated_task (
  task_hash text primary key check (task_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  task_version integer not null check (task_version > 0),
  owner_slot text not null references destruktion_meta.federated_slot(slot_id),
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  base_checkpoint_id text not null references destruktion_meta.chat_capsule_checkpoint(checkpoint_id),
  envelope jsonb not null,
  state text not null check (state in ('OPEN','CLAIMED','TERMINAL','CANCELLED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_assignment (
  assignment_id text primary key,
  task_hash text not null references destruktion_meta.federated_task(task_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  assignment_state text not null check (assignment_state in ('CLAIMED','RELEASED','COMPLETED','STALE_FENCED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_candidate_receipt (
  candidate_hash text primary key check (candidate_hash ~ '^[0-9a-f]{64}$'),
  task_hash text not null references destruktion_meta.federated_task(task_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  receipt jsonb not null,
  eligibility text not null check (eligibility in ('ELIGIBLE','STALE_FENCED','STALE_TASK_VERSION','MISSING_REVIEW','REJECTED')),
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_conflict_event (
  conflict_hash text primary key check (conflict_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  conflict_class text not null,
  left_candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  right_candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  resolution_receipt_hash text,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_integration_decision (
  decision_hash text primary key check (decision_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  candidate_hash text references destruktion_meta.federated_candidate_receipt(candidate_hash),
  decision text not null check (decision in ('INCLUDE','EXCLUDE','CONFLICT_TASK','STALE')),
  reason text not null,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_sync_snapshot (
  snapshot_hash text primary key check (snapshot_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  snapshot jsonb not null,
  checkpoint_proposal_hash text,
  created_at timestamptz not null default now()
);

create table if not exists destruktion_meta.federated_role_outcome (
  outcome_hash text primary key check (outcome_hash ~ '^[0-9a-f]{64}$'),
  epoch_id text not null references destruktion_meta.federated_epoch(epoch_id),
  slot_id text not null references destruktion_meta.federated_slot(slot_id),
  role_profile_hash text not null references destruktion_meta.federated_role_genome(role_profile_hash),
  metrics jsonb not null,
  created_at timestamptz not null default now()
);
```

Add the twelfth physical table explicitly:

```sql
create table if not exists destruktion_meta.federated_review_receipt (
  review_hash text primary key check (review_hash ~ '^[0-9a-f]{64}$'),
  candidate_hash text not null references destruktion_meta.federated_candidate_receipt(candidate_hash),
  session_id text not null references destruktion_meta.federated_session(session_id),
  lease_generation bigint not null,
  verdict text not null check (verdict in ('PASS','FAIL','INCONCLUSIVE','INCONCLUSIVE_SECURITY_FEED')),
  receipt jsonb not null,
  created_at timestamptz not null default now()
);
```

This keeps C6 independence persisted rather than embedding review state only inside candidate JSON.

- [ ] **Step 3: Enable/force RLS and revoke grants on every federation table**

Generate explicit statements for all twelve physical tables (the eleven design entities plus separate review receipt). Grant DML only to `service_role`; do not create anon/authenticated policies.

### Task 2: Narrow RPC functions

**Files:**
- Modify: `storage/federated_chat_fabric_d6.sql`

- [ ] **Step 1: Add service-role-only `SECURITY INVOKER` functions in `public`**

Functions and exact parameter signatures:

Read RPCs used by the MCP allowlist:

```text
metaengine_federation_status_v1(p_epoch_id text)
metaengine_federation_slot_catalog_v1()
metaengine_federation_session_status_v1(p_session_id text)
metaengine_federation_epoch_status_v1(p_epoch_id text)
metaengine_federation_task_get_v1(p_session_id text, p_task_hash text)
metaengine_federation_task_dependencies_v1(p_session_id text, p_task_hash text)
metaengine_federation_candidate_status_v1(p_session_id text, p_candidate_hash text)
metaengine_federation_conflict_status_v1(p_session_id text, p_epoch_id text)
metaengine_federation_sync_snapshot_get_v1(p_session_id text, p_epoch_id text)
```

Guarded write RPCs used by the MCP allowlist:

```text
metaengine_federation_register_v1(p_epoch_id text, p_requested_slot text, p_session_id text, p_capsule_sha256 text, p_protocol_version text, p_role_profile_hash text)
metaengine_federation_release_v1(p_session_id text, p_expected_generation bigint)
metaengine_federation_claim_task_v1(p_session_id text, p_task_hash text, p_expected_generation bigint)
metaengine_federation_progress_v1(p_session_id text, p_task_hash text, p_expected_generation bigint, p_progress jsonb)
metaengine_federation_submit_candidate_v1(p_session_id text, p_expected_generation bigint, p_candidate_hash text, p_task_hash text, p_receipt jsonb)
metaengine_federation_submit_review_v1(p_session_id text, p_expected_generation bigint, p_review_hash text, p_candidate_hash text, p_receipt jsonb)
metaengine_federation_submit_conflict_v1(p_session_id text, p_expected_generation bigint, p_conflict_hash text, p_epoch_id text, p_payload jsonb)
metaengine_federation_propose_integration_v1(p_session_id text, p_expected_generation bigint, p_decision_hash text, p_epoch_id text, p_candidate_hash text, p_decision text, p_reason text)
metaengine_federation_publish_snapshot_v1(p_session_id text, p_expected_generation bigint, p_snapshot_hash text, p_epoch_id text, p_snapshot jsonb, p_checkpoint_proposal_hash text)
```

Internal service-role-only control-plane RPCs, deliberately **not** registered as MCP tools:

```text
metaengine_federation_open_epoch_v1(p_epoch_id text, p_base_checkpoint_id text, p_base_payload_root text, p_federation_policy_hash text, p_role_catalog_hash text, p_producer_concurrency integer)
metaengine_federation_seed_task_v1(p_task_hash text, p_epoch_id text, p_task_version integer, p_owner_slot text, p_role_profile_hash text, p_base_checkpoint_id text, p_envelope jsonb)
metaengine_federation_seed_role_genome_v1(p_role_profile_hash text, p_slot_id text, p_genome_version text, p_parent_profile_hash text, p_hard_genome jsonb, p_soft_genome jsonb)
metaengine_federation_reclaim_slot_v1(p_epoch_id text, p_slot_id text, p_expected_generation bigint)
```

The internal functions let the synchronizer backend publish an approved epoch/task plan without granting ordinary chats a `task_create` or role-authority tool.

Every write function must validate session epoch/slot/generation inside one transaction. `register` locks the chosen slot row `FOR UPDATE`, increments/reads generation, and inserts one active session. Candidate submit recomputes eligibility from current session generation; caller may not choose `ELIGIBLE` directly.

- [ ] **Step 2: Harden privileges**

For each RPC:

```sql
revoke all on function public.metaengine_federation_register_v1(text,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.metaengine_federation_register_v1(text,text,text,text,text,text) to service_role;
```

Set function `search_path = pg_catalog, destruktion_meta` and keep default SECURITY INVOKER.

### Task 3: Python Supabase federation adapter

**Files:**
- Create: `metaengine/devfabric/federation/supabase_federation.py`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`

**Interfaces:**
- Produces: `SupabaseFederationAdapter(transport)` with fixed methods matching the ten RPC names.

- [ ] **Step 1: RED allowlist test**

A fake transport records RPC names. Assert no method accepts a caller-provided SQL string or RPC name.

- [ ] **Step 2: Implement typed fixed calls**

Adapter validates 64-hex hashes and enum values before transport, then returns remote receipt hashes/objects. It exposes typed methods for the nine read and nine guarded-write RPCs plus separate `open_epoch_internal`, `seed_task_internal`, `seed_role_genome_internal`, and `reclaim_slot_internal`; no method accepts a caller-provided RPC name or service key.

### Task 4: Zero-spend migration validation and canonical apply gate

- [ ] **Step 1: Run local/static tests and re-read current Supabase schema**
- [ ] **Step 2: Attempt a development branch only after explicit zero-cost confirmation through Supabase tooling**
- [ ] **Step 3: Apply `federated_chat_fabric_d6` migration to the development branch, then query information_schema/pg_catalog to prove tables, FKs, RLS/FORCE RLS, functions, grants, indexes, and zero SECURITY DEFINER federation functions**
- [ ] **Step 4: Run a branch transaction scenario: register C2, reject duplicate active C2, release/reassign with generation+1, submit stale candidate and prove `STALE_FENCED`**
- [ ] **Step 5: Only if branch gate is PASS and zero-spend remains true, apply the exact reviewed migration to canonical with `apply_migration`; otherwise stop D6-D as blocked and do not mutate canonical**
- [ ] **Step 6: Commit code/migration after observed validation receipts are stored outside the capsule**
