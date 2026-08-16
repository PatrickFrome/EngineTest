# Stage D.6-F Controlled Multi-Chat Integration Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove end-to-end federation semantics with a controlled epoch, deterministic synchronization, C6 review, stale fencing, recovery of C0, and portable pilot packets for real ordinary chats.

**Architecture:** First run a fully deterministic machine pilot using the same contracts/RPC semantics; then generate role bootstrap packets for a human-instantiated ordinary-chat canary. The machine pilot may certify development semantics; actual UI multi-chat operational status remains explicit until the user opens multiple chats and completes the canary.

**Tech Stack:** Python simulator/Supabase adapter, existing verifier/capsule, JSON pilot receipts.

## Global Constraints

- D6-F starts only after D6-D and D6-E gates pass or are explicitly marked external-blocked with local semantics proven.
- Never call the pilot itself canonical promotion.
- Same-project ordinary chats are not used as evidence of blindness for REDUNDANT tasks.
- C0 recovery must not use prior C0 conversation prose.

---

### Task 1: Federation verifier profile

**Files:**
- Modify: `devfabric/verification/profiles.toml`
- Modify: `metaengine/devfabric/capsule.py`
- Test: `tests/devfabric/test_federation_pilot.py`

- [ ] **Step 1: RED gate-version test**

Add support for `METAENGINE-DEVFABRIC-STAGE-D6-GATE-1`; ensure `stage-d6-gate.json` remains capsule-excluded.

- [ ] **Step 2: Add `profiles.federation`**

Commands must run federation Python tests, Stage D edge/federation Node tests, full legacy DevFabric tests, and engine tests. Do not silently replace unresolved `uv`/npm certification checks; record them separately.

### Task 2: Deterministic machine epoch

**Files:**
- Create: `metaengine/devfabric/federation/pilot.py`
- Modify: `tests/devfabric/test_federation_pilot.py`

**Interfaces:**
- Produces: `run_controlled_epoch(store, checkpoint_id, payload_root) -> PilotReport`.

- [ ] **Step 1: RED controlled scenario**

Scenario must contain:
- C0 synchronizer;
- C2 core implementation task;
- C3 AI-swarm parallel task;
- C4 edge task conflicting on one declared interface with C2;
- C6 independent review;
- C7 benchmark task;
- one released/reassigned session whose old candidate is stale-fenced.

- [ ] **Step 2: Implement pilot**

Create epoch, register sessions, claim tasks, submit content-addressed synthetic patches, record C6 PASS review for the eligible high-risk candidate, detect the intentional interface conflict, emit conflict task/reference, integrate non-conflicting candidates in deterministic order, then snapshot.

- [ ] **Step 3: Replace C0 and recover**

Instantiate a new synchronizer only from persisted ledger/store state and require same snapshot hash/integration order.

### Task 3: Real-chat pilot kit

**Files:**
- Create: `chat_federation/PILOT_RUNBOOK.md`
- Create: `chat_federation/ROLE_BOOTSTRAP_TEMPLATE.md`
- Modify: `metaengine/devfabric/federation/bootstrap.py`

- [ ] **Step 1: Generate eight role packets from one capsule**

Packets contain no archive duplication; each is generated from the same role catalog and includes role profile hash plus commands/tool calls to register and fetch work.

- [ ] **Step 2: Define minimum UI canary**

Use four ordinary chats for the first canary: C0, C2, C4, C6. The user opens them manually. Success is: unique registration, two isolated tasks, one candidate each, C6 review, C0 sync snapshot, and loss/recreation of C0 without state loss.

- [ ] **Step 3: Mark operational status honestly**

Before the manual canary: `MULTI_CHAT_UI_STATUS=READY_FOR_CANARY_NOT_OBSERVED`. After observed successful receipts: `MULTI_CHAT_UI_STATUS=PASS_CANARY`.

### Task 4: Gate receipt and capsule determinism

- [ ] **Step 1: Run `metaengine-dev verify --profile federation` and store its receipt hash**
- [ ] **Step 2: Run controlled epoch twice from fresh stores and require identical final synchronization snapshot hash**
- [ ] **Step 3: Build CONTROL capsule twice, require identical SHA, no secrets, no lineage bytes, 9,839-entry lineage lock**
- [ ] **Step 4: Create external `stage-d6-gate.json` with separate `development_status`, `supabase_status`, `mcp_status`, `multi_chat_ui_status`, `certification_status`, `release_promotion_status`**
- [ ] **Step 5: Verify receipt integrity, commit attestation, then run a fresh post-attestation federation verifier without further tracked changes**
