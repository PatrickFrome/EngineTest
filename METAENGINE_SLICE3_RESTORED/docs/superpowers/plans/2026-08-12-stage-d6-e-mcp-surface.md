# Stage D.6-E Federation MCP Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the federation through the existing Cloudflare Streamable HTTP MCP gateway with a fixed, privacy-aware tool allowlist and no arbitrary database/source/promotion capability.

**Architecture:** TypeScript contracts define the external surface; a fixed `FederationApiClient` maps tools only to approved Supabase RPC endpoints. The Cloudflare Worker holds credentials only as managed secrets; tool responses never include those secrets.

**Tech Stack:** TypeScript, existing Stage D Cloudflare Worker/MCP, Zod/MCP SDK once Node lock is resolved, Node built-in tests for core contracts.

## Global Constraints

- Keep Stage D stateless Streamable HTTP transport.
- No arbitrary SQL, shell, canonical file write, direct promotion, champion mutation, role-authority mutation, verifier bypass, or secret retrieval tools.
- P3 remains local-only; P2 uses metadata-only projections.
- Sibling results in an open blind group are hidden until closure.
- Service key/authorization headers must never appear in logs/tool output.

---

### Task 1: MCP federation schemas

**Files:**
- Create: `devfabric/cloudflare/src/federation_contract.ts`
- Create: `devfabric/cloudflare/test/federation_contract.test.ts`

**Interfaces:**
- Produces schemas for read tools `federation_status`, `slot_catalog`, `session_status`, `epoch_status`, `task_get`, `task_dependencies`, `candidate_status`, `conflict_status`, `sync_snapshot_get`; guarded writes `federation_register`, `session_release`, `task_claim`, `task_progress`, `candidate_submit`, `review_submit`, `conflict_submit`, `integration_propose`, `sync_snapshot_publish`.

- [ ] **Step 1: RED exact tool-name test**

Assert the exported tool-name set equals exactly those 18 names and contains none matching `/sql|shell|promote|champion|secret|file_write/i`.

- [ ] **Step 2: Implement request/response types**

Every mutable request includes actor/session/epoch identifiers as applicable; candidate/review writes include content digests rather than patch/source bodies.

- [ ] **Step 3: Run Node GREEN**

```bash
node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts
```

### Task 2: Fixed Supabase RPC client

**Files:**
- Create: `devfabric/cloudflare/src/federation_client.ts`
- Create: `devfabric/cloudflare/test/federation_tools.test.ts`

**Interfaces:**
- Produces: `FederationApiClient` whose public methods correspond one-to-one to approved RPC names; no generic `rpc(name, payload)` is exported.

- [ ] **Step 1: RED secret-leak/allowlist tests**

Use a fake fetch and a sentinel secret assembled at runtime. Assert Authorization exists only in outbound headers and is absent from returned JSON/error strings/log records.

- [ ] **Step 2: Implement fixed client**

Use `SUPABASE_URL` non-secret config and `SUPABASE_SERVICE_ROLE_KEY` Worker secret. Each method posts to one hard-coded `/rest/v1/rpc/metaengine_federation_*_v1` endpoint. Cap error bodies to a safe status/code; do not echo upstream response bodies containing credentials.

### Task 3: Tool handlers and privacy/fencing guard

**Files:**
- Create: `devfabric/cloudflare/src/federation_tools.ts`
- Modify: `devfabric/cloudflare/src/mcp.ts`
- Modify: `devfabric/cloudflare/test/federation_tools.test.ts`

- [ ] **Step 1: RED P3/P2 tests**

P3 task/candidate body must be rejected before network fetch. P2 must strip objective/source/path bodies and preserve only approved metadata/digests.

- [ ] **Step 2: Register the 18 tools with the existing MCP server**

Tool code performs schema validation, privacy projection, fixed client call, and returns structured content. It never performs canonical promotion.

- [ ] **Step 3: Blind-group visibility test**

`candidate_status` for an open blind group returns only caller's own candidate state plus group closure status, not sibling summaries/hashes intended to remain blind.

### Task 4: Edge verifier integration

**Files:**
- Modify: `devfabric/verification/profiles.toml`
- Modify: `tests/devfabric/test_remote_edge_gate.py`

- [ ] **Step 1: Add federation Node tests to the `edge` profile**
- [ ] **Step 2: When npm lock becomes available, additionally require `wrangler types --check`, full `tsc --noEmit`, and `wrangler deploy --dry-run`; until then preserve honest `BLOCKED_EXTERNAL_NODE_TOOLCHAIN` status**
- [ ] **Step 3: Run Stage D + D6-E gates and commit**
