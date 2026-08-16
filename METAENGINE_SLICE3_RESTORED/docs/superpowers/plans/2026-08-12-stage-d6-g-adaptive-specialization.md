# Stage D.6-G Adaptive Specialization and Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt producer concurrency and soft Role Genome preferences from measured outcomes while making hard roles, privacy, authority, mandatory review, and eight-slot topology structurally immutable.

**Architecture:** Compute bounded epoch metrics and deterministic next-policy proposals locally/canonically; soft updates produce new profile hashes and are pinned only to future tasks. Structural changes remain proposal-only and require later Stage F/G benchmarks.

**Tech Stack:** Python dataclasses, canonical hashing, Supabase role outcomes, existing PostHog telemetry adapter.

## Global Constraints

- Producer concurrency bounds: min 2, default 4, max 6.
- Conflict rate `<0.10` may increase by at most one; `0.10–0.25` holds; `>0.25` decreases by at most one.
- Soft adaptation cannot change slot count, hard ownership, authority, promotion rules, mandatory review, or privacy ceilings.
- Routing signals are not truth metrics.
- New profile applies only to future tasks; current TaskEnvelope keeps pinned `role_profile_hash`.

---

### Task 1: Epoch metrics and conflict-budget policy

**Files:**
- Create: `metaengine/devfabric/federation/adaptation.py`
- Test: `tests/devfabric/test_federation_adaptation.py`

**Interfaces:**
- Produces: `EpochMetrics`, `ConcurrencyDecision`, `next_producer_concurrency(current, metrics)`.

- [ ] **Step 1: RED threshold tests**

```python
assert next_producer_concurrency(4, metrics(conflict_rate=0.05)).value == 5
assert next_producer_concurrency(4, metrics(conflict_rate=0.20)).value == 4
assert next_producer_concurrency(4, metrics(conflict_rate=0.30)).value == 3
assert next_producer_concurrency(6, metrics(conflict_rate=0.00)).value == 6
assert next_producer_concurrency(2, metrics(conflict_rate=1.00)).value == 2
```

- [ ] **Step 2: Implement metrics**

Record candidate/clean/conflicting/stale/duplicate/rework counts, integration latency, throughput, verification pass rate, regression rate, human interventions, active slots, and observable cost. Compute rates with denominator `max(count,1)`.

### Task 2: Bounded soft Role Genome updater

**Files:**
- Modify: `metaengine/devfabric/federation/adaptation.py`
- Modify: `metaengine/devfabric/federation/roles.py`
- Modify: `tests/devfabric/test_federation_adaptation.py`

- [ ] **Step 1: RED hard-field immutability/property test**

Across repeated soft updates, assert hard genome object equality and fixed slot identity/privacy/authority/review constraints.

- [ ] **Step 2: Implement deterministic bounded EWMA**

Use configurable alpha `0.20`; update only keys already declared in soft genome. Clamp capability/provider weights to `[0,1]`, exploration to `[0,0.25]`, concurrency preference to `[2,6]`. Unknown keys are rejected, not added dynamically.

- [ ] **Step 3: Version new profile**

New soft profile gets a new content hash and `parent_profile_hash`; do not rewrite prior genome rows.

### Task 3: Privacy-minimized telemetry

**Files:**
- Create: `metaengine/devfabric/federation/telemetry.py`
- Modify: `tests/devfabric/test_federation_adaptation.py`

**Interfaces:**
- Produces: `federation_epoch_event(metrics, decisions)` allowlisted mapping.

- [ ] **Step 1: RED deny-content test**

Assert event has no objective, source text, prompts, patch body, full paths, secrets, or P3 content.

- [ ] **Step 2: Implement allowlist**

Only epoch hash/id, counts/rates, slot IDs, role profile hashes, task classes, timings, verdict categories, provider class, and bounded numeric metrics may leave for PostHog.

### Task 4: Persist role outcomes and adaptation receipts

**Files:**
- Modify: `metaengine/devfabric/federation/supabase_federation.py`
- Create: `storage/federated_chat_fabric_d6_adaptation.sql`
- Modify: `tests/devfabric/test_federation_supabase_adapter.py`

- [ ] **Step 1: Add a second migration with narrow `metaengine_federation_record_outcome_v1` and `metaengine_federation_add_soft_role_genome_v1` RPCs**

Both SECURITY INVOKER, service-role-only. The second inserts a new immutable genome row only after verifying parent hash/slot/hard genome equality against the parent row; it may change only the supplied soft genome and version/hash.

- [ ] **Step 2: No in-place genome update**

SQL and adapter tests must prove there is no UPDATE path for hard/soft genome JSON; adaptation is append-only new version creation.

### Task 5: Final D6 completion gate

- [ ] **Step 1: Run adaptation tests plus full `federation` verifier**
- [ ] **Step 2: Re-run Stage A–D engine/devfabric gates and lineage invariant**
- [ ] **Step 3: Build capsule twice and recover-test both**
- [ ] **Step 4: Update Stage D6 gate measurements with adaptation policy hash and telemetry schema hash**
- [ ] **Step 5: Do not change `release_promotion_status=BLOCKED` while historical Python/Node external toolchain blockers remain unresolved**
- [ ] **Step 6: Commit final D6 implementation and perform post-commit verification before any merge/push decision**
