# Stage D.6-C Portable Chat Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one deterministic CONTROL capsule able to bootstrap any of the eight federation roles without ChatGPT Project memory, secrets, or per-role archives.

**Architecture:** Store static federation protocol/role artifacts in `chat_federation/`; bootstrap code verifies those artifacts, activates one role profile, and can run against the local simulator when MCP is unavailable. Runtime sessions/leases remain in excluded state.

**Tech Stack:** JSON/Markdown protocol artifacts, Python CLI, existing capsule builder/verifier.

## Global Constraints

- One common capsule only.
- No runtime `session_id`, lease token, DB credential, OAuth token, or role-specific secret in capsule.
- Project memory absence must not block bootstrap.
- Offline bootstrap may work on an already-pinned TaskEnvelope but may not invent new authoritative assignments.

---

### Task 1: Protocol artifacts

**Files:**
- Create: `chat_federation/FEDERATION_PROTOCOL.json`
- Create: `chat_federation/TASK_PROTOCOL.json`
- Create: `chat_federation/LEASE_PROTOCOL.json`
- Create: `chat_federation/EPOCH_PROTOCOL.json`
- Create: `chat_federation/CONFLICT_POLICY.json`
- Create: `chat_federation/ADAPTATION_POLICY.json`
- Create: `chat_federation/BOOTSTRAP.md`
- Test: `tests/devfabric/test_federation_bootstrap.py`

- [ ] **Step 1: RED schema-version test**

Assert all six JSON files exist, contain `protocol_version: "D6.1"`, canonical authority `SUPABASE_ONLY`, fixed slot count `8`, and no keys matching `secret|token|password|service_role` except explanatory deny-list strings.

- [ ] **Step 2: Write exact static policies**

`ADAPTATION_POLICY.json` must set producer concurrency `{min:2, default:4, max:6}`, conflict thresholds `{increase_below:0.10, reduce_above:0.25}`. `LEASE_PROTOCOL.json` must state correctness mode `FENCING_GENERATION_NOT_HEARTBEAT_EXPIRY`.

- [ ] **Step 3: Run GREEN and commit**

### Task 2: Bootstrap runtime

**Files:**
- Create: `metaengine/devfabric/federation/bootstrap.py`
- Modify: `tests/devfabric/test_federation_bootstrap.py`

**Interfaces:**
- Produces: `BootstrapContext`, `load_bootstrap(root: Path) -> BootstrapContext`, `activate_role(context: BootstrapContext, slot: SlotId) -> RoleGenome`, `offline_role_packet(context: BootstrapContext, slot: SlotId, pinned_task: FederatedTaskEnvelope | None) -> dict[str, object]`.

- [ ] **Step 1: RED — bootstrap succeeds with no Project memory/env variables**

Clear environment variables matching cloud/service names and load from filesystem only.

- [ ] **Step 2: Implement bootstrap integrity checks**

Verify role catalog has 8 entries, every role profile hash recomputes, protocol versions agree, capsule/source binding exists, and role hard invariants load. Fail with explicit codes rather than falling back to remembered prose.

- [ ] **Step 3: Implement offline packet**

Offline packet contains role instructions, current pinned task if supplied, and `federation_state="FROZEN_OFFLINE"`; it must not fabricate `session_id`, `epoch_id`, or authoritative lease.

### Task 3: CLI surface

**Files:**
- Modify: `metaengine/devfabric/cli.py`
- Modify: `tests/devfabric/test_cli.py`
- Modify: `tests/devfabric/test_federation_bootstrap.py`

**Interfaces:**
- Adds commands: `federation-status`, `role-show`, `federation-bootstrap`, `federation-sim-register`.

- [ ] **Step 1: RED CLI tests**

`metaengine-dev federation-status --json` must report protocol, exact slot count, static role profile hashes, and no cloud call. `role-show C4 --json` returns only C4 hard/soft genome.

- [ ] **Step 2: Implement CLI without connector side effects**

`federation-bootstrap` defaults to read-only static mode. A local simulator DB must be explicitly supplied for `federation-sim-register`.

- [ ] **Step 3: Preserve old CLI help/tests**

Run existing `tests/devfabric/test_cli.py` and old `destruktion-meta16 --help` smoke test.

### Task 4: Capsule integration

**Files:**
- Modify: `metaengine/devfabric/capsule.py`
- Modify: `tests/devfabric/test_capsule.py`
- Modify: `tests/devfabric/test_federation_bootstrap.py`

- [ ] **Step 1: RED — built capsule contains all `chat_federation/` static files and excludes runtime SQLite/session artifacts**

- [ ] **Step 2: Add future D6 gate receipt exclusion**

Extend exclusion set with `devfabric/artifacts/manifests/stage-d6-gate.json`; do not exclude federation static protocol files.

- [ ] **Step 3: Build twice and compare**

```bash
metaengine-dev capsule-build --out /tmp/d6c-1.zip
metaengine-dev capsule-build --out /tmp/d6c-2.zip
sha256sum /tmp/d6c-1.zip /tmp/d6c-2.zip
```

Expected: identical SHA values; both `recover-test` PASS; `secret_hits=[]`.

- [ ] **Step 4: Run full D6-C gate and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_bootstrap.py tests/devfabric/test_capsule.py tests/devfabric/test_cli.py
python -m compileall -q metaengine
git add chat_federation metaengine/devfabric tests/devfabric
git commit -m "feat(d6): add portable federation bootstrap"
```
