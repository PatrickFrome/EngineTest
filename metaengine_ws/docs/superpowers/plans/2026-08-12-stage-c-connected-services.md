# Stage C — Connected Existing Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect existing project services through guarded adapters without creating a second canonical authority or leaking source/secrets.

**Architecture:** Each connector has read-first contract tests, dry-run semantics, privacy filtering, quota/health snapshot, and an explicit mutation boundary. Supabase alone may perform canonical writes, only through narrow compare-and-swap/append operations.

**Tech Stack:** Stage A adapter protocol, Supabase, Create State, Google Drive, Linear, PostHog, Neon, Replit.

## Global Constraints

- Stage A must be green.
- OAuth tokens remain in managed connector stores, never project files.
- P3 is never sent externally.
- Neon is disposable sandbox-only.
- Linear/PostHog/Drive/Create State are projections/replicas, never canonical evidence.
- Supabase mutation methods require explicit `write_intent` and source checkpoint CAS.

---

### Task 1: Add connector-neutral external guards

**Files:** `metaengine/devfabric/providers/external.py`, `tests/devfabric/test_external_base.py`.

- [x] Write P2/P3 redaction/blocking and missing-write-intent tests.
- [x] Run tests; expect FAIL.
- [x] Implement `sanitize_task()`, `require_write_intent()`, `ConnectorReceipt` with stable reason codes.
- [x] Run tests; expect PASS.
- [x] Commit `feat: guard external connector dispatch`.

### Task 2: Implement guarded Supabase canonical adapter

**Files:** `metaengine/devfabric/providers/supabase.py`, `tests/devfabric/test_supabase_guard.py`.

**Interfaces:** read checkpoint/champion; append development receipt; propose checkpoint with expected parent; no arbitrary SQL or direct `promote()` shortcut.

- [x] Fake-transport tests: wrong parent => `CAS_CONFLICT`; read-only rejects writes; only allowlisted methods exist.
- [x] Implement narrow methods; credentials stay managed externally.
- [x] Run tests; expect PASS.
- [x] Commit `feat: add guarded canonical Supabase adapter`.

### Task 3: Implement Create State semantic memory adapter

**Files:** `metaengine/devfabric/providers/create_state.py`, tests.

- [x] Test payload excludes patch bodies, secrets, and P3 fields.
- [x] Implement summary-only handoff/decision capture plus local outbox fallback.
- [x] Run tests; commit `feat: add semantic memory projection`.

### Task 4: Implement Google Drive artifact replica adapter

**Files:** `metaengine/devfabric/providers/drive.py`, tests.

- [x] Test digest dedupe and post-upload digest mismatch rejection.
- [x] Implement manifest-before-upload and content-addressed receipt.
- [x] Run tests; commit `feat: replicate recovery artifacts to Drive`.

### Task 5: Implement Linear projection adapter

**Files:** `metaengine/devfabric/providers/linear.py`, tests.

- [x] Test deleting/updating a Linear issue cannot mutate local TaskEnvelope state and retries are idempotent.
- [x] Implement read-first project/issue lookup and task projection.
- [x] Run tests; commit `feat: project development tasks into Linear`.

### Task 6: Implement PostHog privacy-minimized telemetry adapter

**Files:** `metaengine/devfabric/providers/posthog.py`, `metaengine/devfabric/telemetry_policy.py`, tests.

- [x] Property test: arbitrary source/objective strings never appear in serialized telemetry.
- [x] Implement strict allowlist fields: provider class, task class, latency, token/compute estimate, result, test delta, patch size, verifier verdict, promotion outcome, quota/fallback.
- [x] Run tests; commit `feat: add privacy-minimized development telemetry`.

### Task 7: Implement Neon disposable branch adapter

**Files:** `metaengine/devfabric/providers/neon.py`, tests.

- [x] Test canonical-role use is rejected; sensitive tasks require schema-only/approved fixture policy and expiry.
- [x] Implement `create_sandbox`, `run_migration_test`, `destroy_sandbox` with task/candidate tags and cleanup receipt.
- [x] Run tests; commit `feat: add disposable Neon database worlds`.

### Task 8: Implement Replit independent worker adapter

**Files:** `metaengine/devfabric/providers/replit.py`, tests.

- [x] Test unknown free-credit state makes provider ineligible under zero-spend.
- [x] Implement P0/P1 bounded independent worker and CandidateReceipt/report return; no canonical credentials.
- [x] Run tests; commit `feat: add quota-guarded Replit worker`.

### Task 9: Implement Antigravity CLI independent AI adapter

**Files:** `metaengine/devfabric/providers/antigravity.py`, `devfabric/antigravity/settings.json`, `.agents/rules/metaengine-devfabric.md`, `tests/devfabric/test_antigravity_adapter.py`.

**Interfaces:** `AntigravityAdapter.health_check()`, quota snapshot derived from `/usage`/local quota state where machine-readable access is available, and bounded independent implementation/review execution.

- [x] Write tests asserting `useG1Credits` is `false`, `allowNonWorkspaceAccess` is `false`, dangerous skip-permissions flags are forbidden, and P2/P3 external dispatch policy is enforced.
- [x] Run tests; expect FAIL before adapter/config exists.
- [x] Implement `agy` discovery and execution with workspace-scoped permissions; install/auth is user-managed outside the capsule. When baseline quota is exhausted or cannot be safely determined, return `QUOTA_EXHAUSTED`/`ZERO_SPEND_QUOTA_UNKNOWN` rather than using credits.
- [x] Add an always-on workspace rule stating `NO_CANONICAL_AUTHORITY`, protected paths, required deterministic gates, and patch-only output contract; run adapter tests and a no-write health probe.
- [x] Commit `feat: add zero-spend Antigravity worker`.

### Task 10: Connected-services dry-run gate

- [x] Run full deterministic suite.
- [x] Query health/read-only state of each connector, including Antigravity availability/quota mode.
- [x] Perform no canonical writes; only disposable/explicit test projections if required by adapter tests.
- [x] Generate `stage-c-gate.json` with availability/reason codes and no secrets.
- [x] Commit `docs: certify connected service adapters`.

## Stage C execution evidence

- Live read-only probes: Supabase, Create State, Google Drive, Linear, and PostHog connected successfully.
- Replit read-only app listing succeeded; new worker creation remains blocked by the current subscription gate, so Replit is optional and fail-closed.
- Neon was not contacted because project policy keeps it retired; the adapter remains disabled by default.
- Antigravity safe configuration is present, but the `agy` binary is unavailable on this executor.
- Actual cloud writes during the connected-services health gate: `0`.
- Exactly one connector has canonical authority: Supabase; external services reject P3 dispatch.
