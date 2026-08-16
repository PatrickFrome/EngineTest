# Stage D.6 Federated Chat Fabric — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded, recoverable federation of eight specialized ordinary ChatGPT conversations that develop Metaengine in parallel through immutable tasks, fenced sessions, isolated candidates, deterministic synchronization, and a single Supabase canonical ledger.

**Architecture:** Stage D.6 adds a federation protocol above the existing Stage A–D DevFabric without replacing TaskEnvelope, CandidateReceipt, Git worktrees, deterministic verification, Cloudflare edge, or Supabase checkpoint authority. The implementation is split into seven independently verifiable phases D6-A through D6-G; each phase ends in a working state and may be reviewed or rolled back independently.

**Tech Stack:** Python 3.11+, dataclasses/enums, SQLite local simulator, JSON protocol artifacts, existing `metaengine.devfabric` codec/journal/capsule/verifier, PostgreSQL 17/Supabase private schema, narrow PostgREST RPC, TypeScript/Cloudflare MCP Streamable HTTP, Git/R2 content addressing, PostHog privacy-minimized telemetry.

## Global Constraints

- Base design commit: `ec93dd15f685707a11f5e40b4f425dd211ca525a`.
- Base Stage D commit: `c7da092134aa515d46eb06320260474adae974f3`.
- Base Stage D CONTROL capsule SHA-256: `4f7ac5a55c7d209426af035413def42965382eac1a1ddfeb8dd20d0463a1fffe`.
- Canonical cloud authority remains Supabase project `gzrbxoiuenkksualgpvp`.
- Exactly eight logical slots exist: `C0` through `C7`; changing that hard topology is outside D6 automatic adaptation.
- Ordinary chats are user-instantiated and protocol-assigned; no code may depend on programmatically creating or background-waking ChatGPT UI conversations.
- Shared-read / isolated-write is mandatory: no specialized chat writes another chat workspace or canonical source checkout.
- C0 is disposable and has no promotion bypass.
- C6 independent review cannot be bypassed for configured risk classes.
- P3 remains local-only; role genomes cannot raise privacy ceilings.
- All mutable federation operations are append-only or CAS/fencing guarded.
- Project memory is ambient context only; machine truth comes from federation artifacts/Supabase/Git/R2.
- `session_id` and lease generation are coordination handles, not credentials.
- No service-role/database secret enters the capsule, Git tree, logs, receipts, or chat transcript.
- Zero-spend remains fail-closed: any validation path that requires a paid branch/provider must stop instead of incurring cost.
- Existing Stage A–D tests and the 9,839-lineage invariant must remain green.
- No phase changes champion or directly promotes a checkpoint.

## File Structure Locked by This Plan

```text
metaengine/devfabric/federation/
  __init__.py              # public federation API
  types.py                 # slot/status/integration/conflict enums and value objects
  roles.py                 # role catalog/genome loading + hard/soft validation
  contracts.py             # federated task/candidate/review/snapshot immutable contracts
  store.py                 # local SQLite federation persistence
  simulator.py             # local register/claim/reclaim/submit state machine
  conflicts.py             # deterministic conflict graph and classification
  synchronizer.py          # deterministic C0 collect/validate/graph/integrate/snapshot logic
  bootstrap.py             # common capsule bootstrap and role activation
  adaptation.py            # conflict-budget concurrency + bounded soft-genome updates
  telemetry.py             # privacy-minimized federation metrics projection
  supabase_federation.py   # narrow canonical federation RPC adapter

chat_federation/
  ROLE_CATALOG.json
  ROLE_GENOMES/C0.json, C1.json, C2.json, C3.json, C4.json, C5.json, C6.json, C7.json
  FEDERATION_PROTOCOL.json
  TASK_PROTOCOL.json
  LEASE_PROTOCOL.json
  EPOCH_PROTOCOL.json
  CONFLICT_POLICY.json
  ADAPTATION_POLICY.json
  BOOTSTRAP.md
  PILOT_RUNBOOK.md

storage/federated_chat_fabric_d6.sql

devfabric/cloudflare/src/
  federation_contract.ts   # exact MCP schemas, no transport
  federation_client.ts     # fixed RPC allowlist to Supabase
  federation_tools.ts      # MCP handlers and privacy/fencing guards

tests/devfabric/
  test_federation_roles.py
  test_federation_contracts.py
  test_federation_simulator.py
  test_federation_conflicts.py
  test_federation_synchronizer.py
  test_federation_bootstrap.py
  test_federation_supabase_adapter.py
  test_federation_pilot.py
  test_federation_adaptation.py

devfabric/cloudflare/test/
  federation_contract.test.ts
  federation_tools.test.ts
```

## Dependency Order

```text
D6-A Contracts
   ↓
D6-B Local Simulator
   ↓
D6-C Portable Bootstrap
   ↓
D6-D Supabase Ledger
   ↓
D6-E MCP Federation Surface
   ↓
D6-F Controlled Multi-Chat Epoch Gate
   ↓
D6-G Adaptive Specialization + Telemetry
```

D6-D and D6-E may be developed in parallel after D6-C interfaces are frozen, but D6-F must not start until both are verified.

## Verification Gates

Every phase must run its phase tests plus:

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric
python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric
python -m compileall -q metaengine
```

From D6-E onward also run Stage D edge tests/typecheck through the existing verifier profile. D6-F adds a `federation` verifier profile. Before claiming D6 complete, build the CONTROL capsule twice and require identical SHA-256, `secret_hits=0`, no embedded lineage bytes, and unchanged 9,839-entry lineage lock.

## Phase Deliverables

| Phase | Deliverable | Hard gate |
|---|---|---|
| D6-A | Immutable roles/contracts and common role catalog | 8 slots exactly; federation metadata changes hash; hard genome cannot soft-adapt |
| D6-B | Recoverable local federation simulator | duplicate ownership rejected; fencing and deterministic synchronization proven |
| D6-C | One capsule bootstraps any role | no project-memory dependency; no runtime leases/secrets in capsule |
| D6-D | Supabase canonical federation ledger + narrow RPC | private/RLS fail-closed; no anon/auth writes; branch/transaction-safe validation before canonical migration |
| D6-E | Remote federation MCP tools | fixed allowlist only; no arbitrary SQL/file/promotion tools; secrets never returned/logged |
| D6-F | Controlled epoch integration gate | stale candidates fenced; C6 review enforced; C0 recovery yields same snapshot |
| D6-G | Bounded adaptive specialization | 0.10/0.25 conflict thresholds; concurrency 2–6; hard role fields immutable |

## Execution Strategy for Multi-Chat Development

Once D6-A–C are implemented, later work itself may use the federation experimentally. Until D6-F passes, however, the implementation branch remains authoritative and federation outputs are advisory test artifacts only. Never use an unverified D6 implementation to govern its own promotion.

## Phase Plans

- `2026-08-12-stage-d6-a-federation-contracts.md`
- `2026-08-12-stage-d6-b-local-simulator.md`
- `2026-08-12-stage-d6-c-portable-bootstrap.md`
- `2026-08-12-stage-d6-d-supabase-ledger.md`
- `2026-08-12-stage-d6-e-mcp-surface.md`
- `2026-08-12-stage-d6-f-integration-gate.md`
- `2026-08-12-stage-d6-g-adaptive-specialization.md`
