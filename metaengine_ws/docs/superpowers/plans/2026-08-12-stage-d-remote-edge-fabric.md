# Stage D — Remote Edge Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a narrow remote MCP/control gateway and free-tier edge execution without making Cloudflare or Noodle Seed canonical.

**Architecture:** A TypeScript Cloudflare Worker exposes bounded MCP tools backed by content-addressed task references. D1 stores ephemeral leases/health/quota pointers, R2 stores digest-addressed artifacts, Workflows coordinate durable low-CPU steps, and Workers AI is an optional lightweight worker.

**Tech Stack:** Cloudflare Workers, project-local Wrangler, TypeScript, MCP, D1, R2, Workflows, Workers AI, optional Noodle Seed.

## Global Constraints

- Stage A must be green.
- Wrangler stays project-local; configure `nodejs_compat`, observability, no hard-coded secrets, no global request state, no floating promises.
- Free plan budget is fail-closed; no Workers Paid-only feature is enabled by default.
- MCP cannot expose arbitrary SQL, shell, secret-read, or direct canonical promotion tools.

---

### Task 1: Scaffold and lock Cloudflare package

**Files:** `devfabric/cloudflare/package.json`, `package-lock.json`, `wrangler.jsonc`, `src/index.ts`, `test/config.test.ts`.

- [ ] Write config test for `compatibility_date: "2026-08-12"`, `nodejs_compat`, observability, and no plaintext secrets.
- [ ] Run tests; expect FAIL.
- [ ] Add local `wrangler` plus test/type dependencies; lock with `npm install`.
- [ ] Run tests; expect PASS.
- [ ] Commit `build: scaffold Cloudflare edge package`.

### Task 2: Implement narrow MCP contract

**Files:** `devfabric/cloudflare/src/mcp.ts`, tests.

- [ ] Test only allowed tools exist: project read, task ref creation/status, candidate listing, verification request, quota/health, checkpoint proposal reference.
- [ ] Implement Zod validation and content-addressed outputs; no direct promotion.
- [ ] Run tests/typecheck; commit `feat: expose bounded remote MCP tools`.

### Task 3: Add D1 ephemeral state

**Files:** `src/d1.ts`, `migrations/0001_ephemeral_router.sql`, tests.

- [ ] Test schema has leases/quota/task pointers only and no champion/policy tables.
- [ ] Implement TTL and idempotent lease CAS.
- [ ] Run local D1 tests; commit `feat: add ephemeral D1 router state`.

### Task 4: Add R2 content-addressed artifacts

**Files:** `src/r2.ts`, tests.

- [ ] Test key format `sha256/<first2>/<digest>` and body-digest mismatch rejection.
- [ ] Implement streaming put/get with digest metadata.
- [ ] Run tests; commit `feat: replicate digest-addressed artifacts to R2`.

### Task 5: Add Workflows orchestration

**Files:** `src/workflow.ts`, tests.

- [ ] Test steps store references rather than source/patch bodies and surface `QUOTA_EXHAUSTED` rather than paid fallback.
- [ ] Implement retries/idempotency and delegate CPU-heavy work outside Worker CPU.
- [ ] Run tests; commit `feat: coordinate durable free-tier edge workflows`.

### Task 6: Add Workers AI lightweight adapter

**Files:** `src/workers_ai.ts`, tests.

- [ ] Test daily quota unknown/over-limit => ineligible or `QUOTA_EXHAUSTED`.
- [ ] Implement P0/P1 classification/critique only and content-addressed review receipt.
- [ ] Run tests; commit `feat: add quota-guarded Workers AI helper`.

### Task 7: Add Noodle Seed alternative profile

**Files:** `devfabric/noodle/server.ts`, `devfabric/noodle/README.md`, validation receipt.

- [ ] Reconcile using Noodle Seed lifecycle rather than hand-authoring hosted manifests.
- [ ] Mirror the same narrow tool surface with no extra authority.
- [ ] Validate locally; do not deploy without separate explicit authorization.
- [ ] Record `NO_DEPLOYMENT_PERFORMED` when not authorized and commit `feat: add portable Noodle MCP profile`.

### Task 8: Stage D local/preview gate

- [ ] Run TypeScript tests/typecheck plus Python full gates.
- [ ] Run `npx wrangler dev` against local bindings only.
- [ ] Verify no deployment/secrets mutation occurred unless separately authorized.
- [ ] Generate and commit `stage-d-gate.json`.

---

## Execution Status — 2026-08-12

Stage D local implementation is complete for the dependency-free/core surface. The Cloudflare SDK transport source is present but is not release-certified until the pinned npm graph can be resolved and Wrangler can run locally.

### Current implementation decisions

- New remote MCP code uses stateless **Streamable HTTP** with `createMcpHandler()`; no new `McpAgent` dependency is introduced.
- Cloudflare is a non-canonical edge control plane. Supabase remains the sole canonical checkpoint/policy authority.
- D1 persists ephemeral references, leases, quota snapshots, and verification-request hashes only.
- R2 artifacts are SHA-256 content addressed and read-back verifies digest metadata.
- Workflows persist references only and dispatch only when the known Free-plan step budget is sufficient.
- Workers AI is advisory-only, limited to P0/P1, and refuses unknown/exhausted free quota.
- Noodle Seed remains an optional alternative MCP profile. No `server.ts` is hand-authored while the `noodle` lifecycle is unavailable; this follows the installed Noodle Seed bootstrap boundary.
- No Cloudflare resources were provisioned, no secrets were written, and no deployment was performed during the local Stage D gate.

### Verification completed

- [x] Cloudflare config/security contract tests.
- [x] Narrow MCP tool surface and P3/P2 privacy boundary.
- [x] D1 ephemeral schema, lease CAS, task/quota/verification reference operations.
- [x] R2 SHA-256 CAS put/get contract and metadata verification.
- [x] Workflow reference-only plan and free-quota fail-closed behavior.
- [x] Workers AI advisory adapter with content-addressed receipts.
- [x] Static Stage D manifest/CLI/gate integration in Metaengine DevFabric.
- [x] Capsule excludes `node_modules`, `.wrangler`, `.dev.vars`, runtime state, and Stage D attestation.
- [x] 25/25 dependency-free Node edge tests PASS.
- [x] `tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json` PASS.
- [x] 107/107 DevFabric Python tests PASS.
- [x] 69/69 historical engine tests PASS.
- [x] Unified `edge` verifier PASS before final attestation.

### External blockers — not fabricated

- [ ] `package-lock.json`: **BLOCKED_EXTERNAL_NODE_TOOLCHAIN**. Observed `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` timed out with exit 124 on this host; no lock file was created.
- [ ] `wrangler types/check/dev --local`: cannot be claimed until the pinned npm dependency graph is installed.
- [ ] D1/R2/Workflow/Worker resources: **NOT PROVISIONED**; provisioning is a separately authorized cloud mutation.
- [ ] Noodle Seed reconciliation/validation: `noodle` CLI/readiness transport unavailable on this host; no hosted mutation was attempted.

### Promotion boundary

Stage D may be used for continued development and portable recovery after its local gate receipt verifies. It must remain release/promotion-blocked until the external Node toolchain gate is closed and a real Wrangler local preview passes. Cloudflare/Noodle must never obtain direct champion or checkpoint-promotion authority.
