# Stage D6-G1 Finalized-Epoch Shadow Adaptation Design

**Status:** APPROVED DESIGN — written specification gate before implementation planning  
**Date:** 2026-08-13  
**Parent stage:** D6-G0 `PASS` / immutable epoch finalization  
**Target stage result:** `PASS_ADAPTATION_SHADOW_READY`  
**Adaptation protocol:** `D6.ADAPTATION.1`

## 1. Purpose

D6-G0 made a closed federation epoch historically recoverable from one immutable terminal recovery cut. D6-G1 builds the first adaptive organization layer on top of that invariant without allowing adaptation to mutate canonical truth, active federation profiles, hard role authority, or already-created tasks.

The stage converts immutable finalized epoch evidence into deterministic metrics and shadow-only adaptation proposals. A proposal may describe a future producer-concurrency change or bounded soft Role Genome change, but D6-G1 never activates that proposal and never makes the proposed Role Genome assignable.

The required causal chain is:

```text
federation execution
  -> immutable D6-G0 finalization
  -> verified finalized recovery cut
  -> deterministic metrics receipt
  -> evidence sufficiency gate
  -> shadow adaptation proposal
  -> deterministic shadow replay / verification
  -> adaptation receipt
```

Activation or materialization into a new assignable `role_profile_hash` is explicitly deferred to D6-G2.

## 2. Evidence baseline and motivation

At the D6-G1 design boundary, canonical federation evidence contains one finalized canary epoch, two candidates, one review, and no persisted role-outcome rows. That sample is sufficient to validate deterministic extraction and fail-closed behavior, but it is not sufficient to justify changing an active organizational policy.

Therefore D6-G1 separates **learning machinery readiness** from **policy activation readiness**. A small canary can prove that the adaptation mechanism is correct while still producing `HOLD_INSUFFICIENT_EVIDENCE`.

## 3. Non-negotiable invariants

1. Supabase remains the sole canonical federation ledger authority.
2. D6-G1 consumes only D6-G0 finalized epochs. No OPEN/INTEGRATING epoch, live session state, mutable ledger head, or prior-chat prose may influence adaptation.
3. Every source finalization must be revalidated through the existing `EpochFinalization` contract before metrics are computed.
4. `finalization_hash` and `recovery_cut_hash` are the evidence roots of every adaptation receipt.
5. Recomputing a receipt from identical protocol version, source finalizations, current policy inputs, and current Role Genome inputs must produce the identical receipt hash.
6. A different computed receipt for the same deterministic input identity fails closed as `FEDERATION_ADAPTATION_NONDETERMINISTIC`.
7. D6-G1 never changes canonical checkpoint, champion policy, active architecture policy, release promotion state, or finalization records.
8. D6-G1 never changes the active Role Genome catalog and never activates a proposed Role Genome.
9. Hard Role Genome fields are immutable and are not proposal targets.
10. Soft proposals may reference only keys already declared by the parent soft genome; unknown keys are rejected.
11. Existing `TaskEnvelope.role_profile_hash` remains pinned forever. Adaptation can affect only future tasks after a later D6-G2 activation gate.
12. Producer concurrency is bounded to `2..6` and may move by at most one per eligible decision.
13. Privacy routing and telemetry signals are not truth metrics.
14. P3 content never enters finalization-derived adaptation receipts or external telemetry.
15. No new chat-facing MCP tools are added. The fixed federation allowlist remains exactly 18 tools.
16. No generic SQL, arbitrary RPC, shell, promote, champion, or policy-mutation surface is introduced.
17. External AI agents have no canonical authority; D6-G1 work remains patch/evidence only until deterministic gates pass.
18. Adaptation output is independent of the runtime capability set: GitHub, Wrangler, PostHog, Replit, Cloudflare, local CLI availability, or any other optional tool may change which verification steps are available, but may not change finalized metrics, evidence sufficiency, concurrency decisions, shadow Role Genome proposals, or receipt hashes.

## 3.1 Environment and provenance continuity contract

D6-G1 begins after a verified Session Handoff V2 recovery rather than from the unavailable original Git object database. The implementation must preserve both identities without conflating them:

- historical original D6-G0 source HEAD: `71d36a12e5b810431739fc5d9b111fa4ffb955f5` — provenance only; its Git object is unavailable and MUST NOT be fabricated;
- verified reconstructed Git root: `0a0cb3eb38205121d4cf091c14ca2591744f0aed` on `recovered/d6g0-control-plane`;
- D6-G0 CONTROL capsule SHA-256: `1a5aaddba68fe5dcc112066ee136846b1fd77d99b233b88ebdb4c96a37db91b7`;
- D6-G0 CONTROL payload root SHA-256: `246e69dbb28fa7e6ab425d20bd4c60b2beffd453e5a04c40fb0acbe06e94ea75`;
- Session Handoff V2 manifest receipt: `fc073c5ecab8aadbe8ab641f73d06196ac031a82336d19aced5ea302ba36026d`;
- lineage lock SHA-256: `fde3ce693062fb3efe4821ecd16cd775b1108b52492c3493028ce606a0e844a4`, verified for `9839/9839` lineage files.

Every D6-G1 stage gate and portable handoff artifact must record these parent provenance anchors plus the actual post-recovery Git commit that contains the D6-G1 implementation. Pure `D6.ADAPTATION.1` receipts MUST NOT include Git commit, branch, filesystem, connector, or runtime provenance because those values would make identical finalized evidence hash differently across runtimes. This creates an explicit continuity bridge at the development-stage boundary without contaminating the model-independent adaptation identity.

Pure adaptation functions receive only explicit finalized evidence and explicit policy/profile inputs. They MUST NOT branch on installed plugins, connector state, CLI presence, network availability, filesystem location, current Git branch name, wall-clock time, or environment variables other than explicit test fixtures. Running the same pure calculation from the same canonical inputs in a minimal portable runtime and a richer development runtime must produce identical canonical outputs and hashes.

## 4. Source-of-truth boundary

### 4.1 Allowed source

The only authoritative adaptation source is a validated `EpochFinalization` whose `protocol_version` is supported and whose `recovery_cut` passes all existing finalization integrity checks.

A D6-G1 loader conceptually performs:

```text
load finalization row
-> EpochFinalization.from_store_row(...)
-> verify finalization_hash
-> verify recovery_cut_hash
-> verify terminal snapshot hash
-> normalize recovery cut
-> compute finalized metrics
```

### 4.2 Forbidden sources

The adaptation engine must not query or consume, for decision-making:

- current active sessions;
- current slot lease generations;
- current mutable task/candidate/review rows outside the frozen cut;
- previous C0 conversation text;
- external PostHog analytics;
- unverified human prose summaries;
- unbound latency/cost/provider observations;
- any OPEN or INTEGRATING epoch.

If an operational metric is not present in a cryptographically bound finalized/derived receipt, D6-G1 marks it `UNOBSERVED`; it does not synthesize or estimate it.

## 5. Deterministic finalized metrics

Create `metaengine/devfabric/federation/adaptation.py` with immutable contracts for finalized metrics, evidence sufficiency, concurrency decisions, shadow Role Genome proposals, and adaptation receipts.

### 5.1 `FinalizedEpochMetrics`

The initial protocol computes only values supported by the frozen recovery cut:

- `finalization_hash`
- `recovery_cut_hash`
- `epoch_id`
- `producer_concurrency`
- `task_count`
- `candidate_count`
- `eligible_candidate_count`
- `rejected_candidate_count`
- `stale_candidate_count`
- `review_count`
- `review_pass_count`
- `review_fail_count`
- `review_inconclusive_count`
- `conflict_count`
- `unresolved_conflict_count`
- `include_count`
- `exclude_count`
- `stale_decision_count`
- `integrated_candidate_count`
- participating `(slot_id, role_profile_hash)` pairs

Derived rates are canonical decimal/rational inputs rather than platform-dependent formatted floats. Public dataclass accessors may expose floats for convenience, but receipt hashing uses integer numerator/denominator pairs.

Required derived values:

```text
conflict_rate = unresolved_conflict_count / max(candidate_count, 1)
verification_pass_rate = review_pass_count / max(review_count, 1)
integration_rate = integrated_candidate_count / max(candidate_count, 1)
stale_rate = stale_candidate_count / max(candidate_count, 1)
```

`conflict_rate` is capped at 1 for policy comparison if pathological data contains more unresolved conflicts than candidates; raw counts remain in the receipt.

### 5.2 Explicitly unobserved metrics

D6-G1 does not claim to measure from the current recovery-cut schema:

- latency;
- token/API cost;
- provider quality;
- human intervention rate;
- benchmark quality delta;
- semantic task quality;
- throughput per wall-clock unit.

These fields are represented as unavailable/absent, not zero. A later protocol may add them only through a separately verified receipt that binds them to the finalization.

## 6. Evidence sufficiency gates

D6-G1 always produces a metrics receipt for a valid finalized epoch. It produces a non-HOLD adaptive proposal only when the relevant evidence gate is satisfied.

### 6.1 Concurrency evidence gate

A concurrency proposal requires all of:

- at least `3` distinct valid finalized epochs;
- at least `6` total candidates across the evidence window;
- identical federation policy hash across the evidence window;
- supported finalization/adaptation protocol versions;
- no integrity failures.

Otherwise the decision is:

`HOLD_INSUFFICIENT_EVIDENCE`.

The evidence window is explicit rather than implicitly "latest": the caller supplies a finite set of finalization identities, each is loaded and verified, and the pure adaptation layer normalizes that set by `finalization_hash`. The exact normalized evidence-set identity is part of `adaptation_input_hash`. No pure adaptation function queries wall-clock time or selects epochs by mutable head state.

### 6.2 Role soft-proposal evidence gate

A slot-specific soft proposal requires all of:

- at least `3` distinct finalized epochs containing that `(slot_id, parent_role_profile_hash)` witness;
- at least `3` attributable finalized observations for that slot/profile, where one observation is either a candidate produced under a task owned by that slot/profile or a review receipt authored by that reviewer slot/profile; mere participant-witness presence does not count;
- no hard-genome mismatch across the evidence window;
- no unsupported or unobserved metric required by the requested soft-field update.

If a candidate soft field depends on provider quality, cost, latency, benchmark quality, or another currently unobserved metric, that field must remain unchanged with reason `HOLD_UNOBSERVED_METRIC`.

This means D6-G1 may initially generate an unchanged Role Genome shadow proposal while still proving the entire deterministic proposal pipeline.

## 7. Producer-concurrency controller

The controller preserves the previously designed bounded conflict-budget rule:

```text
if evidence insufficient:
    HOLD_INSUFFICIENT_EVIDENCE
elif aggregate conflict_rate < 0.10:
    min(current + 1, 6)
elif 0.10 <= aggregate conflict_rate <= 0.25:
    HOLD
else:
    max(current - 1, 2)
```

Aggregate rate is computed from summed integer counts across the deterministic evidence window, not from an average of per-epoch rounded rates:

```text
sum(unresolved_conflict_count) / max(sum(candidate_count), 1)
```

The decision receipt includes current value, proposed value, evidence counts, exact numerator/denominator, threshold branch, and reason code.

## 8. Shadow Role Genome proposal

### 8.1 Hard genome is immutable

The following remain byte-for-byte equal to the parent Role Genome:

- slot identity;
- role name;
- authority boundaries;
- prohibited actions;
- subsystem ownership;
- privacy ceiling;
- mandatory reviewers;
- allowed integration modes.

Any attempted hard-field delta raises `FEDERATION_ADAPTATION_HARD_GENOME_IMMUTABLE`.

### 8.2 Soft field rules

Only existing soft keys may be proposed:

- `capability_weights`
- `preferred_workers`
- `preferred_task_classes`
- `review_pairings`
- `exploration_weight`
- `concurrency_preference`
- `provider_priors`

Bounds remain:

- capability/provider weights: `[0,1]`;
- exploration: `[0,0.25]`;
- concurrency preference: `[2,6]`;
- EWMA alpha, when a metric is actually observable: `0.20`.

A mapping proposal may modify only keys already present in the parent mapping. It cannot dynamically add a new capability or provider. Sequence-valued fields may only select/reorder values already present in the parent field; D6-G1 cannot mint new worker IDs, task classes, or review pairings.

### 8.3 Shadow-only storage semantics

D6-G1 does **not** insert proposed profiles into `federated_role_genome`.

Reason: `federated_role_genome` is already the assignable profile catalog referenced by sessions and tasks. Storing an unverified shadow candidate there would create an unnecessary accidental-assignment surface.

Instead, the complete proposed hard+soft payload and its deterministic `proposed_role_profile_hash` are embedded in an immutable adaptation receipt. D6-G2 may later materialize an accepted proposal into `federated_role_genome` through a separate evidence gate.

## 9. Adaptation receipt

Create an immutable canonical receipt with protocol version `D6.ADAPTATION.1`.

Conceptual payload:

```text
{
  protocol_version,
  evidence_finalization_hashes,
  evidence_recovery_cut_hashes,
  evidence_metrics_hash,
  current_policy_hash,
  current_producer_concurrency,
  concurrency_decision,
  role_proposals[],
  telemetry_schema_hash,
  status
}
```

`adaptation_input_hash` is the canonical digest of the protocol version plus normalized evidence-finalization identities and all current policy/profile inputs that are permitted to influence the calculation. `adaptation_receipt_hash` is the canonical digest of the normalized output payload. This two-hash model gives the persistence layer a stable key for distinguishing exact idempotent repeats from conflicting recomputation.

Allowed statuses:

- `HOLD_INSUFFICIENT_EVIDENCE`
- `HOLD_UNOBSERVED_METRIC`
- `SHADOW_PROPOSAL_READY`
- `SHADOW_REPLAY_PASS`
- `SHADOW_REPLAY_FAIL`

The same logical input must normalize to the same payload and hash regardless of input map ordering.

## 10. Canonical persistence

Create a separate migration:

`storage/federated_chat_fabric_d6_adaptation.sql`

### 10.1 New table

Add one append-only table:

`destruktion_meta.federated_adaptation_receipt`

Required columns:

- `adaptation_receipt_hash text primary key`
- `adaptation_input_hash text not null unique`
- `protocol_version text not null`
- `evidence_finalization_hashes jsonb not null`
- `evidence_metrics_hash text not null`
- `status text not null`
- `receipt jsonb not null`
- `created_at timestamptz not null default now()`

The migration must enforce lowercase 64-hex hashes for both receipt and input identities and a supported status set.

The table is RLS-enabled + FORCE RLS, inaccessible to `anon`/`authenticated`, and grants `service_role` only `SELECT, INSERT`. Explicitly revoke `UPDATE, DELETE, TRUNCATE` from runtime roles.

### 10.2 Existing table hardening

Because `federated_role_genome` and `federated_role_outcome` currently grant broader DML than their intended append-only semantics require, the D6-G1 migration narrows runtime privileges to `SELECT, INSERT` and explicitly revokes `UPDATE, DELETE, TRUNCATE` for those two tables.

D6-G1 does not use legacy `federated_role_outcome` as adaptation truth because existing rows are not structurally bound to a D6-G0 finalization hash. It may remain available as diagnostic/legacy data. A future protocol can replace or bind it explicitly.

### 10.3 RPC surface

Add internal-only fixed RPCs:

- `metaengine_federation_record_adaptation_receipt_v1(...)`
- `metaengine_federation_adaptation_receipt_get_v1(...)`

Both use `SECURITY INVOKER`, fixed `search_path`, exact argument validation, and service-role-only execution. The write RPC accepts the complete pre-hashed receipt and verifies deterministic identity/duplicate behavior.

No adaptation RPC is exposed through the chat-facing Cloudflare MCP allowlist.

## 11. Idempotence and conflict semantics

For one `adaptation_input_hash`:

- exact repeat with the same `adaptation_receipt_hash` -> `ALREADY_RECORDED`;
- same `adaptation_input_hash` with a different receipt hash/payload -> `FEDERATION_ADAPTATION_NONDETERMINISTIC`;
- malformed hash/payload -> fail closed;
- unknown finalization reference -> fail closed;
- non-finalized/open epoch evidence -> impossible through the FK/query boundary and must still be rejected locally.

A receipt is immutable once inserted.

## 12. Privacy-minimized telemetry

Create `metaengine/devfabric/federation/telemetry.py` with an explicit allowlist serializer.

External telemetry may contain only bounded diagnostic fields such as:

- adaptation protocol version;
- hashed epoch/finalization/profile identifiers;
- slot IDs;
- counts and rational/rounded rates;
- categorical decision/status codes;
- bounded timing only after a verified timing receipt exists;
- telemetry schema hash.

It must reject or omit:

- objective/source text;
- prompts/conversation content;
- patch bodies;
- full file paths;
- secrets/tokens/credentials;
- P3 fields/content;
- arbitrary nested payloads.

PostHog or another telemetry sink is observational only. Its data is never read back as adaptation truth.

## 13. Shadow replay

D6-G1 must be able to replay a proposal without modifying active federation state.

For concurrency proposals, shadow replay recomputes the controller from the same finalized evidence and proves deterministic identity and bounds.

For Role Genome proposals, shadow replay proves:

1. parent hard genome equals proposed hard genome;
2. every proposed soft key existed in the parent;
3. every value remains within bounds;
4. no new provider/capability/worker/task-class/reviewer identity is introduced;
5. repeated proposal generation yields the same proposed hash;
6. the proposed profile is not present in any current task/session assignment merely as a consequence of D6-G1.

No live task is dispatched with the shadow proposal.

## 14. Python interfaces

Expected pure/local interfaces, names subject only to implementation-level refinement without changing semantics:

```text
FinalizedEpochMetrics
EvidenceSufficiency
ConcurrencyDecision
ShadowRoleGenomeProposal
AdaptationReceipt

metrics_from_finalization(finalization)
evaluate_evidence(metrics_window, ...)
next_producer_concurrency(current, metrics_window)
propose_soft_role_genome(parent, evidence_window, ...)
build_adaptation_receipt(...)
verify_shadow_receipt(...)
federation_adaptation_event(receipt)
```

`SupabaseFederationAdapter` receives only fixed methods for the two internal adaptation RPCs. No arbitrary SQL/RPC escape hatch is added.

## 15. Failure codes

At minimum, implementation must use stable fail-closed errors for:

- `FEDERATION_ADAPTATION_FINALIZED_EVIDENCE_REQUIRED`
- `FEDERATION_ADAPTATION_PROTOCOL_UNSUPPORTED`
- `FEDERATION_ADAPTATION_NONDETERMINISTIC`
- `FEDERATION_ADAPTATION_HARD_GENOME_IMMUTABLE`
- `FEDERATION_ADAPTATION_UNKNOWN_SOFT_KEY`
- `FEDERATION_ADAPTATION_SOFT_VALUE_OUT_OF_BOUNDS`
- `FEDERATION_ADAPTATION_NEW_IDENTITY_FORBIDDEN`
- `FEDERATION_ADAPTATION_RECEIPT_HASH_MISMATCH`
- `FEDERATION_ADAPTATION_PRIVATE_FIELD_FORBIDDEN`

Evidence insufficiency and unobserved metrics are HOLD decisions, not exceptions.

## 16. Test strategy

Implementation is TDD-first.

### 16.1 RED unit/property tests

Tests must initially fail for:

- open/non-finalized evidence rejection;
- finalization integrity tampering;
- deterministic metrics independent of input ordering;
- exact integer/rational rate calculation;
- concurrency thresholds and `2..6` bounds;
- `HOLD_INSUFFICIENT_EVIDENCE` at the current one-epoch baseline;
- hard Role Genome equality across repeated soft proposals;
- unknown soft-key rejection;
- new provider/capability identity rejection;
- unobserved provider/cost/latency metrics producing HOLD/no change;
- deterministic proposal/receipt hashes;
- privacy denylist and P3 rejection;
- no chat-facing MCP adaptation tools;
- no active task/profile mutation;
- identical adaptation receipt hash under two synthetic runtime-capability inventories for identical explicit finalized inputs;
- provenance metadata records the historical original HEAD and reconstructed root as distinct identities.

### 16.2 SQL contract tests

Prove:

- adaptation receipts are INSERT/SELECT only;
- UPDATE/DELETE/TRUNCATE fail for runtime role;
- role genome/outcome UPDATE/DELETE privileges are removed;
- exact repeat is idempotent;
- conflicting repeat fails closed;
- only existing finalization hashes can be referenced;
- RPCs are `SECURITY INVOKER` with fixed `search_path`;
- no generic RPC exists.

### 16.3 Regression gates

Re-run:

- federation tests;
- D6-G0 finalization subset;
- DevFabric groups;
- engine suite;
- lineage lock/invariant;
- Node MCP invariance tests where the local toolchain permits;
- capsule deterministic rebuild/recovery.

No historical PASS may be silently converted into a new deployment claim.

## 17. Stage acceptance criteria

D6-G1 may report `PASS_ADAPTATION_SHADOW_READY` only when all of the following hold:

1. finalized-only source enforcement passes;
2. deterministic metrics/receipts pass repeated rebuild tests;
3. current one-epoch evidence correctly yields HOLD rather than a live mutation;
4. hard genome immutability is property-tested;
5. shadow proposals cannot become assignable profiles;
6. append-only adaptation persistence is verified;
7. legacy role genome/outcome runtime mutation privileges are narrowed as designed;
8. privacy telemetry tests pass;
9. fixed 18-tool MCP allowlist is unchanged;
10. full available regression gates pass;
11. lineage invariant remains unchanged;
12. no canonical checkpoint/champion/policy promotion occurs;
13. release promotion remains BLOCKED unless separately resolved by its own gate;
14. external MCP deployment is not claimed without external deployment evidence;
15. D6-G1 gate records the Session Handoff provenance anchors and the actual post-recovery implementation commit while pure adaptation receipts exclude those runtime provenance fields;
16. pure adaptation outputs are proven invariant to optional runtime/plugin capability inventory.

## 18. Explicit non-goals

D6-G1 does not:

- activate a new Role Genome;
- materialize a shadow profile into the assignable genome catalog;
- autonomously promote checkpoints or architecture policy;
- change the eight-slot topology;
- change authority or reviewer requirements;
- infer missing quality/cost/latency data;
- deploy Federation MCP;
- increase the MCP tool allowlist;
- use PostHog as a verifier;
- enable executable self-modification.

Those boundaries are deliberate. D6-G1 makes adaptive evolution measurable, replayable, and auditable before allowing it to influence future federation execution.
