# Stage D.6-B Local Federation Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, recoverable local federation state machine that proves slot uniqueness, fencing, assignment, conflict detection, and disposable synchronizer recovery before any cloud mutation.

**Architecture:** Use a project-local SQLite database under excluded runtime state. The simulator mirrors canonical semantics but is never canonical; all integration eligibility derives from task/session generation checks and immutable receipts.

**Tech Stack:** Python sqlite3, dataclasses, existing canonical codec, pytest.

## Global Constraints

- No wall-clock lease expiry required for correctness.
- Exactly one non-revoked active session may own a slot.
- Reclaim increments generation; stale generation receipts are stored but ineligible.
- Deterministic ordering uses lexical tie-breakers after dependency constraints.
- Simulator state belongs under `devfabric/state/` and must remain capsule-excluded.

---

### Task 1: SQLite federation store

**Files:**
- Create: `metaengine/devfabric/federation/store.py`
- Test: `tests/devfabric/test_federation_simulator.py`

**Interfaces:**
- Produces: `FederationStore(path)`, `transaction()`, `put_epoch`, `get_epoch`, `put_session`, `active_session_for_slot`, `put_task`, `put_candidate`, `put_snapshot`.

- [ ] **Step 1: RED — two active sessions cannot occupy one slot**

Use a temporary SQLite file and attempt two inserts for `(epoch-1,C2)`.

- [ ] **Step 2: Implement schema with uniqueness constraint**

Create local tables `epoch`, `slot`, `session`, `task`, `assignment`, `candidate`, `review`, `conflict`, `snapshot`; set `PRAGMA journal_mode=WAL` and `foreign_keys=ON`. Add partial unique index:

```sql
CREATE UNIQUE INDEX one_active_session_per_slot
ON session(epoch_id, slot_id)
WHERE revoked = 0 AND released_at IS NULL;
```

- [ ] **Step 3: Run GREEN and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_simulator.py
git add metaengine/devfabric/federation/store.py tests/devfabric/test_federation_simulator.py
git commit -m "feat(d6): add local federation store"
```

### Task 2: Registration, release, reclaim, fencing

**Files:**
- Create: `metaengine/devfabric/federation/simulator.py`
- Modify: `tests/devfabric/test_federation_simulator.py`

**Interfaces:**
- Produces: `Registration`, `FederationSimulator.register`, `.release`, `.reclaim`, `.submit_candidate`.

- [ ] **Step 1: RED — reclaim increments generation and old candidate becomes `STALE_FENCED`**

```python
first = sim.register(epoch_id="e1", requested_slot=SlotId.C3, capsule_sha256="a"*64, protocol_version="D6.1", role_profile_hash="b"*64, registration_nonce="n1")
sim.release(first.session_id, expected_generation=first.lease_generation)
second = sim.register(epoch_id="e1", requested_slot=SlotId.C3, capsule_sha256="a"*64, protocol_version="D6.1", role_profile_hash="b"*64, registration_nonce="n2")
assert second.lease_generation == first.lease_generation + 1
assert sim.submit_candidate(old_receipt).eligibility is CandidateEligibility.STALE_FENCED
```

- [ ] **Step 2: Implement deterministic AUTO assignment**

AUTO scans `SLOT_ORDER` and returns the first eligible free slot after applying role-state restrictions. Explicit role assignment must CAS the current generation. Generate session IDs as `session-<canonical digest first20>` from epoch/slot/generation/capsule/protocol plus a caller-provided registration nonce; never infer ChatGPT UI identifiers.

- [ ] **Step 3: Make stale receipts auditable**

Store every syntactically valid candidate with an eligibility column. Never delete or rewrite an old candidate because a new generation exists.

- [ ] **Step 4: Run GREEN and commit**

### Task 3: Conflict graph

**Files:**
- Create: `metaengine/devfabric/federation/conflicts.py`
- Test: `tests/devfabric/test_federation_conflicts.py`

**Interfaces:**
- Produces: `ConflictEdge`, `ConflictGraph`, `detect_candidate_conflicts(tasks, candidates)`.

- [ ] **Step 1: RED path/interface tests**

Prove overlapping `write_set` yields `PATH_WRITE_CONFLICT`; overlapping `interface_set` with different candidate hashes yields `INTERFACE_CONTRACT_CONFLICT`; explicit dependency only creates a directed ordering edge, not a conflict by itself.

- [ ] **Step 2: Implement deterministic graph**

Sort nodes by `task_hash`, then candidate hash. Return edges sorted by `(class, left, right)`. Never use set iteration order in serialized output.

- [ ] **Step 3: Add stale-base and verification conflicts**

Different pinned base checkpoint where no declared dependency checkpoint permits it => `STALE_BASE_CONFLICT`. Required review missing/FAIL => `VERIFICATION_CONFLICT`.

- [ ] **Step 4: Run GREEN and commit**

### Task 4: Deterministic synchronizer and recovery

**Files:**
- Create: `metaengine/devfabric/federation/synchronizer.py`
- Test: `tests/devfabric/test_federation_synchronizer.py`

**Interfaces:**
- Produces: `SynchronizationSnapshot`, `Synchronizer.collect`, `.validate`, `.graph`, `.integration_order`, `.snapshot`, `.recover`.

- [ ] **Step 1: RED — same ledger state gives identical snapshot after C0 replacement**

Create candidates in different insertion orders, construct snapshot, instantiate a new Synchronizer from the same store, recover, and assert identical `snapshot_hash` and integration order.

- [ ] **Step 2: Implement lexical topological sort**

Use Kahn's algorithm with a heap/ordered list keyed by task hash. A cycle does not trigger hidden manual ordering; emit a conflict task/reference and no integration order for the cyclic component.

- [ ] **Step 3: Enforce C6 review**

For `RiskClass.HIGH` and `RiskClass.RELEASE`, eligibility requires an independent review from `C6` whose session/lease is current and whose review verdict is PASS. C6 cannot satisfy this with a candidate authored by the same C6 session.

- [ ] **Step 4: Create content-addressed snapshot**

Snapshot includes epoch/checkpoint/policy/catalog hashes, eligible candidates, rejected/stale candidates, ordered conflicts, integration order, required verification hashes, and no source/patch bodies.

- [ ] **Step 5: Run full D6-B gate and commit**

```bash
python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_simulator.py tests/devfabric/test_federation_conflicts.py tests/devfabric/test_federation_synchronizer.py
python -m metaengine.devfabric.pytest_runner -q tests/devfabric
python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric
git add metaengine/devfabric/federation tests/devfabric/test_federation_*.py
git commit -m "feat(d6): add recoverable federation simulator"
```
