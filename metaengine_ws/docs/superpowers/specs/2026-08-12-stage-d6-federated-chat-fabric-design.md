# Stage D.6 — Federated Chat Fabric Design Specification

**Date:** 2026-08-12  
**Status:** WRITTEN_SPEC_REVIEW_GATE  
**Target:** Destruktion 4.0 METAENGINE 16X 2.3.0-alpha.1  
**Base Stage D commit:** `c7da092134aa515d46eb06320260474adae974f3`  
**Base Stage D CONTROL capsule SHA-256:** `4f7ac5a55c7d209426af035413def42965382eac1a1ddfeb8dd20d0463a1fffe`  
**Canonical cloud authority:** Supabase project `gzrbxoiuenkksualgpvp`  
**Design principle:** fixed logical chat federation, shared-read / isolated-write, epoch-fenced synchronization, adaptive specialization, deterministic integration.

## 1. Purpose

Stage D.6 turns the portable Metaengine development environment into a bounded federation of ordinary ChatGPT conversations that can develop different parts of the project in parallel without sharing mutable source state.

The federation consists of exactly eight logical chat slots, `C0` through `C7`. A user creates or opens ordinary chats; the portable project bootstraps in each chat and registers it through the Metaengine federation interface. The federation assigns a role, current epoch, bounded task scope, and a fenced lease. Chats propose content-addressed results. They do not directly mutate canonical project state.

The goal is to increase development throughput and review diversity while preserving reproducibility, conflict control, recoverability, and a single canonical authority.

## 2. Feasibility boundary

The design deliberately separates what can be automated by Metaengine from what cannot be assumed about the ChatGPT UI.

### 2.1 Supported assumptions

- The same portable CONTROL capsule can be made available to multiple ordinary chats.
- A ChatGPT Project may be used as an optional human-facing shell for shared files, instructions, and ambient project context.
- A custom ChatGPT app / MCP-backed tool surface can let a chat register, acquire work, submit receipts, read synchronization state, and request integration actions permitted by policy.
- Supabase can provide transactional identity, role assignment, task/lease state, append-only receipts, epoch state, and compare-and-swap guards.
- Git/R2 can hold source patches and large artifacts by digest.

### 2.2 Unsupported assumptions

Stage D.6 MUST NOT depend on any unsupported ability to:

- programmatically create ordinary ChatGPT UI conversations;
- force a sleeping chat to execute in the background;
- treat ChatGPT project memory as a transactional database;
- infer a durable globally unique UI chat identifier from the product;
- guarantee blinded independence between chats that share ambient project memory.

Therefore the UI federation is **user-instantiated but protocol-assigned**. Machine autonomy and background fan-out belong to the existing OpenHands/OpenCode/Coder/Ollama worker fabric, not to ordinary UI chats.

## 3. Chosen architecture and alternatives

### 3.1 Alternative A — shared mutable project

All chats edit common source/database state directly.

Rejected because it creates race conditions, stale edits, partial writes, hidden ordering dependencies, and unverifiable conflict resolution.

### 3.2 Alternative B — one orchestrator chat plus only machine workers

A single chat coordinates OpenHands/OpenCode/Coder/Ollama workers.

This is efficient for mechanical development but loses durable human-readable specialization, independent long-horizon reasoning contexts, and explicit separation between architecture, implementation, verification, and research.

### 3.3 Alternative C — unbounded chat swarm

Create a new chat for every task.

Rejected because coordination cost, context duplication, stale checkpoints, task duplication, and integration work grow faster than useful parallelism.

### 3.4 Selected approach — bounded hybrid federation

Use exactly eight logical chat slots as long-lived cognitive specializations. Each slot may invoke the existing machine swarm beneath it. The fixed slot count controls coordination complexity; actual concurrent activity is adaptive and may be lower than eight.

This preserves the strongest properties of both models:

- long-horizon specialized reasoning in chats;
- cheap high-volume execution in machine agents;
- a single deterministic integration protocol.

## 4. Federation topology

### C0 — SYNCHRONIZER / INTEGRATOR

Responsibilities:

- maintain the epoch integration view;
- decompose cross-slot dependencies;
- allocate or recommend work;
- detect path/interface conflicts;
- assemble an integration candidate from verified receipts;
- publish synchronization snapshots;
- propose the next checkpoint.

C0 is disposable. Its authoritative state MUST be recoverable from the federation ledger and artifacts. C0 cannot directly promote a champion.

### C1 — ARCHITECTURE

Owns architecture contracts, ADRs, subsystem boundaries, protocol evolution, dependency decomposition, and architectural criticism.

### C2 — CORE ENGINE

Owns Metaengine Python core, routing, policy/evidence mechanics, engine topology, execution semantics, and performance-sensitive core changes.

### C3 — AI SWARM

Owns Ollama, OpenCode, OpenHands, Coder, DevPod, model/provider routing, candidate-world orchestration, and worker capability adapters.

### C4 — EDGE / MCP

Owns Cloudflare Workers, MCP, D1, R2, Workflows, Workers AI, edge budget policies, and remote gateway concerns.

### C5 — DATA / SERVICES

Owns Supabase development schemas, connected-service adapters, artifact lineage, Drive, Create State, Linear, PostHog, and synchronization persistence contracts.

### C6 — VERIFICATION / SECURITY

Owns deterministic verification, test strategy, CI, reproducibility, supply-chain checks, security review, conflict validation, and independent review gates.

C6 MUST NOT be the sole author of production changes that it independently certifies.

### C7 — RESEARCH / BENCHMARK

Owns external research, benchmark design, baselines, statistical evaluation, frontier comparisons, falsification, and holdout methodology.

## 5. Fixed slots versus active concurrency

The federation always has eight logical slots, but not all slots must work simultaneously.

Each slot has one of:

- `ACTIVE`
- `IDLE`
- `REVIEW_ONLY`
- `SUSPENDED`
- `RECLAIMABLE`

The scheduler chooses active producer slots from the dependency DAG and conflict budget. C0 and C6 are coordination/verification roles and are not counted as ordinary producer capacity.

Initial policy:

- eight logical slots fixed;
- default producer concurrency: four;
- minimum useful producer concurrency: two;
- maximum producer concurrency: six;
- C0 may reduce concurrency when conflicts/rework rise;
- increasing or decreasing the hard eight-slot topology requires a separately benchmarked architecture-policy proposal.

## 6. Portable bootstrap

All chats use the same CONTROL capsule. No per-role archive is created.

The capsule adds:

```text
chat_federation/
  ROLE_CATALOG.json
  ROLE_GENOMES/
    C0.json ... C7.json
  FEDERATION_PROTOCOL.json
  TASK_PROTOCOL.json
  LEASE_PROTOCOL.json
  EPOCH_PROTOCOL.json
  CONFLICT_POLICY.json
  ADAPTATION_POLICY.json
  BOOTSTRAP.md
```

On bootstrap a chat:

1. verifies capsule integrity;
2. reads project identity and federation protocol version;
3. connects to the federation MCP surface if available;
4. calls `federation_register` with the capsule digest, protocol version, and `AUTO` or an explicitly requested eligible role;
5. receives `session_id`, `slot_id`, `role_genome_version`, `role_profile_hash`, `epoch_id`, `base_checkpoint`, and `lease_generation`;
6. loads only the role-specific operational instructions plus global invariants;
7. obtains the current task or reports itself `IDLE`.

`session_id` and lease identifiers are coordination handles, not secrets. Authentication/authorization remains at the MCP/app identity layer.

## 7. Registration and role assignment

### 7.1 Slot uniqueness

At most one non-revoked active session owns a logical slot for an epoch.

Role allocation is compare-and-swap guarded by `(epoch_id, slot_id, lease_generation)`.

### 7.2 Replacement

If a chat is abandoned or replaced, C0 or the user can reclaim its slot. Reassignment increments `lease_generation`.

Any late receipt from an older generation is stored for audit as `STALE_FENCED` but is not integration-eligible.

### 7.3 No heartbeat dependency

Ordinary chats are not assumed to execute background heartbeats. Leases therefore use explicit activity/reclaim state rather than relying on short periodic heartbeats.

`last_seen_at` is diagnostic. Correctness comes from fencing generations, not wall-clock expiry.

## 8. Role Genome

Every slot has a versioned Role Genome with two layers.

### 8.1 Hard role genome

Changes only through reviewed federation-policy updates:

- slot identity;
- authority boundaries;
- prohibited actions;
- subsystem ownership;
- privacy ceiling;
- mandatory reviewers;
- allowed integration modes.

### 8.2 Soft role genome

May adapt from outcomes within predefined bounds:

- capability weights;
- preferred machine workers;
- preferred task classes;
- review pairings;
- exploration/exploitation weight;
- concurrency preference;
- tool/provider ranking priors.

Soft adaptation can change routing priority but cannot alter truth rules, privacy, canonical authority, or promotion permissions.

Each TaskEnvelope pins `role_profile_hash`; a task does not silently change behavior if the genome evolves mid-epoch.

## 9. Epoch model

Development proceeds in explicit epochs.

An epoch contains:

- `epoch_id`;
- `base_checkpoint_id`;
- `base_payload_root`;
- `federation_policy_hash`;
- `role_catalog_hash`;
- task dependency DAG;
- active-slot plan;
- conflict budget;
- integration state;
- final synchronization snapshot.

All candidate work is based on the epoch's pinned checkpoint unless a task explicitly declares a newer dependency checkpoint.

C0 cannot silently rebase a submitted candidate. Rebase creates a new candidate receipt.

## 10. TaskEnvelope extension

The existing immutable TaskEnvelope is extended with federation metadata:

- `epoch_id`;
- `task_version`;
- `owner_slot`;
- `lease_generation`;
- `role_profile_hash`;
- `base_checkpoint_id`;
- `dependency_task_ids`;
- `read_set`;
- `write_set`;
- `interface_set`;
- `integration_mode`;
- `review_slots`;
- `blind_group_id` when applicable.

Supported integration modes:

- `EXCLUSIVE`
- `PARALLEL`
- `REDUNDANT`
- `IMPLEMENT_REVIEW`

## 11. CandidateReceipt extension

A specialized chat never writes the canonical source tree directly. It submits a CandidateReceipt containing at minimum:

- `task_hash`;
- `epoch_id`;
- `task_version`;
- `slot_id`;
- `session_id`;
- `lease_generation`;
- `role_profile_hash`;
- `base_checkpoint_id`;
- `patch_digest` or artifact references;
- `changed_paths`;
- `interface_changes`;
- deterministic test/verification references;
- claims and risks;
- dependency observations;
- candidate summary;
- receipt hash.

Large source/patch/log payloads belong in Git/R2 CAS, not in mutable database columns.

## 12. Shared-read / isolated-write rule

All specialized chats may read the current canonical snapshot and approved shared artifacts within privacy policy.

No specialized chat writes another chat's workspace or the canonical source checkout.

Writes occur only to:

- an isolated Git worktree / worker workspace;
- content-addressed artifact storage;
- append-only or CAS-guarded federation ledger records.

Integration is a separate action from submission.

## 13. Synchronizer protocol

C0 performs synchronization in five phases:

1. **Collect** — obtain all terminal candidate receipts for the epoch or integration window.
2. **Validate** — reject stale lease generations, stale task versions, incompatible bases, missing mandatory verification, or privacy violations.
3. **Graph** — build a change dependency/conflict graph from `write_set`, `interface_set`, explicit task dependencies, and discovered patch conflicts.
4. **Integrate** — create an isolated integration candidate in deterministic topological order; conflicting candidates become explicit conflict tasks rather than manual hidden edits.
5. **Snapshot** — run C6-required gates, emit an immutable synchronization snapshot, and create a checkpoint proposal.

C0 may assemble an integration candidate but cannot mark it canonical without the existing deterministic/canonical promotion boundary.

## 14. Conflict model

Conflicts are first-class records, not chat prose.

Conflict classes:

- `PATH_WRITE_CONFLICT`
- `INTERFACE_CONTRACT_CONFLICT`
- `DEPENDENCY_VERSION_CONFLICT`
- `STALE_BASE_CONFLICT`
- `SEMANTIC_DECISION_CONFLICT`
- `VERIFICATION_CONFLICT`
- `PRIVACY_POLICY_CONFLICT`

Every conflict has a content-addressed resolution receipt.

### 14.1 Conflict budget

Each epoch records:

- candidate count;
- clean integration count;
- conflicting candidate count;
- stale candidate count;
- duplicate-work count;
- rework count;
- integration latency.

The first adaptation signal is:

`conflict_rate = conflicting_candidates / max(candidate_count, 1)`.

Initial policy:

- `< 0.10`: concurrency may increase within the hard maximum;
- `0.10–0.25`: hold concurrency;
- `> 0.25`: reduce producer concurrency or repartition task ownership.

This is a routing signal, not a truth metric.

## 15. Blind and redundant work

True blinded redundancy cannot rely on shared ChatGPT Project memory, because project chats may reference other chats in the same project.

Therefore:

- ordinary same-project chats may perform non-blind parallel specialization;
- a `REDUNDANT` task requiring real blindness SHOULD use isolated machine workers or separate project/context boundaries;
- sibling candidate summaries are not exposed through the federation API until the blind group closes;
- C0 does not release comparative results before closure.

This preserves independent evidence where independence materially matters.

## 16. Persistence model

Supabase remains the sole canonical mutable ledger. Stage D.6 proposes a private-schema federation subsystem; final DDL is deferred to the implementation plan/migration review.

Logical entities:

- `federated_epoch`
- `federated_slot`
- `federated_session`
- `federated_role_genome`
- `federated_task`
- `federated_assignment`
- `federated_candidate_receipt`
- `federated_conflict_event`
- `federated_integration_decision`
- `federated_sync_snapshot`
- `federated_role_outcome`

Existing `chat_capsule_checkpoint` remains the canonical checkpoint chain. Federation tables reference checkpoint IDs; they do not replace the checkpoint system.

All exposed write paths MUST be narrow RPC/tool actions rather than arbitrary SQL. RLS/private-schema fail-closed policy remains mandatory.

## 17. Artifact topology

Logical truth remains split by responsibility:

- **Supabase:** federation coordination, epochs, assignments, receipts, integration decisions, checkpoint references;
- **Git:** source commits, worktrees, diffs, integration candidates;
- **R2:** content-addressed large artifacts/capsules/logs when deployed;
- **Drive:** human-readable recovery replicas;
- **Create State:** semantic handoff/decision memory;
- **PostHog:** privacy-minimized development telemetry.

No replica may become a second canonical promotion authority.

## 18. MCP / tool surface

Stage D.6 adds a narrow federation capability surface. Proposed operations:

Read-oriented:

- `federation_status`
- `slot_catalog`
- `session_status`
- `epoch_status`
- `task_get`
- `task_dependencies`
- `candidate_status`
- `conflict_status`
- `sync_snapshot_get`

Guarded writes:

- `federation_register`
- `session_release`
- `task_claim`
- `task_progress`
- `candidate_submit`
- `review_submit`
- `conflict_submit`
- `integration_propose`
- `sync_snapshot_publish`

Not exposed:

- arbitrary SQL;
- arbitrary canonical file writes;
- direct checkpoint promotion;
- champion mutation;
- role authority mutation;
- verifier bypass;
- secret retrieval.

## 19. ChatGPT Project usage

A single ChatGPT Project with project-only memory is the recommended optional UI shell when available because it can keep common project files/instructions and allow project chats to reference project context.

However:

- project memory is ambient context only;
- federation state from MCP/Supabase overrides remembered prose;
- role instructions explicitly tell each chat to ignore sibling decisions unless they are present as approved federation artifacts;
- high-value blinded redundancy uses isolated contexts instead of same-project chats.

Stage D.6 remains portable outside Projects: any ordinary chat with the CONTROL capsule and federation tool can register.

## 20. Failure and recovery behavior

### Chat lost

Reclaim slot, increment `lease_generation`, restore from current epoch/task state. No project state is lost with the conversation.

### Synchronizer lost

Create a new C0 session. It reconstructs state from open epoch, receipts, conflict graph, integration decisions, and last synchronization snapshot.

### Two chats claim one role

Unique slot ownership/CAS permits one generation. The loser receives an assignment conflict and requests another eligible slot.

### Stale candidate arrives

Store as `STALE_FENCED`; never integrate automatically.

### Supabase unavailable

Chats may continue local isolated work against their pinned TaskEnvelope but cannot acquire new authoritative assignments or publish integration-eligible receipts. Local outbox replay is allowed after recovery.

### R2/Git unavailable

Receipt remains incomplete until required digest-addressed artifacts are durable. No canonical proposal is emitted.

### MCP unavailable

CONTROL capsule permits offline work, but federation state is frozen and multi-chat coordination is suspended.

## 21. Security and privacy

- No service-role or database secret enters a chat transcript or capsule.
- MCP identity authenticates the user; `session_id` is not treated as a credential.
- P3 remains local-only under the existing privacy policy.
- Task projections obey Stage C external privacy rules.
- Role genomes cannot raise their own privacy ceiling.
- All mutable coordination actions record actor/session/epoch/task identifiers and receipt hashes.
- Fencing tokens prevent replay of stale session authority.
- C0 does not gain a canonical bypass merely because it is the synchronizer.

## 22. Adaptation model

Stage D.6 adapts two things separately.

### 22.1 Operational adaptation — allowed automatically inside bounds

- producer concurrency;
- preferred task-to-slot routing;
- machine-worker preferences below each chat;
- review pairing;
- exploration fraction;
- soft capability weights.

Inputs may include acceptance rate, verifier success, regression rate, conflict rate, rework, latency, and benchmark outcomes.

### 22.2 Structural adaptation — proposal only

The following require explicit benchmarked policy change:

- changing the hard eight-slot count;
- changing hard role ownership;
- granting new authority;
- changing mandatory review relationships;
- changing promotion rules;
- changing privacy ceilings.

## 23. Telemetry and measurements

The federation must make its claimed speed/quality benefit measurable.

Per epoch record at minimum:

- wall-clock integration duration;
- task throughput;
- active slot count;
- clean merge rate;
- conflict rate;
- stale work rate;
- duplicate work rate;
- rework rate;
- verification pass rate;
- post-integration regression rate;
- human intervention count;
- artifact/compute cost when observable;
- benchmark score deltas.

Stage F will use these outcomes to learn routing priors. Stage D.6 itself does not claim a fixed speedup factor.

## 24. Deterministic verification requirements

Before Stage D.6 is development-ready, local tests must prove:

1. exactly eight logical slot definitions exist;
2. duplicate active ownership is rejected;
3. reassignment increments fencing generation;
4. stale-generation receipt cannot integrate;
5. TaskEnvelope role/epoch metadata participates in hashing;
6. Role Genome hard fields cannot soft-adapt;
7. candidate submission cannot mutate canonical source;
8. conflict graph detects overlapping write/interface sets;
9. C0 integration order is deterministic for the same dependency graph;
10. C6 review requirement cannot be bypassed for configured risk classes;
11. project-memory absence does not prevent bootstrap;
12. synchronizer recovery reconstructs the same synchronization snapshot;
13. federation capsule excludes secrets/runtime leases;
14. existing Stage A–D tests and lineage invariants remain green.

Supabase migrations additionally require branch or transaction-safe validation before canonical DDL application.

## 25. Success criteria

Stage D.6 is complete when:

1. one CONTROL capsule can bootstrap all eight roles;
2. eight logical slots are defined and versioned;
3. multiple ordinary chats can register without duplicate active slot ownership;
4. sessions can be replaced without stale-result corruption;
5. tasks are pinned to epochs/checkpoints/role genomes;
6. chats submit isolated content-addressed candidates rather than shared mutable edits;
7. C0 can deterministically reconstruct and integrate a compatible candidate set;
8. C6 can independently verify integration policy;
9. a new C0 chat can recover synchronization state without relying on prior C0 conversation memory;
10. concurrency adapts within fixed bounds from conflict/outcome data;
11. Supabase remains the only canonical mutable authority;
12. no direct promotion path is added;
13. the portable capsule remains deterministic and secret-free;
14. measured federation telemetry is sufficient for later Stage F/G comparison against single-chat development.

## 26. Non-goals

Stage D.6 does not:

- programmatically spawn ChatGPT UI conversations;
- guarantee unattended background execution of ordinary chats;
- make project memory canonical;
- allow every chat to write the same branch/database state;
- replace machine agents with more UI chats;
- claim that eight chats are always better than fewer chats;
- change the canonical champion or promote a new release;
- close the existing Python/Node external toolchain certification blockers;
- require all eight chats to be active for every epoch.

## 27. Implementation sequencing after approval

The implementation plan should split Stage D.6 into independently verifiable phases:

- **D6-A — Federation contracts:** role catalog, Role Genome, epoch/session/task/candidate schemas, hashing.
- **D6-B — Local federation simulator:** slot registration, fencing, assignment, conflict graph, synchronizer recovery.
- **D6-C — Portable chat bootstrap:** common capsule, role activation instructions, offline behavior, CLI/status.
- **D6-D — Supabase federation ledger:** reviewed migration, CAS/RPC operations, RLS/private-schema security.
- **D6-E — MCP federation surface:** registration, task, candidate, conflict and sync tools without arbitrary mutation.
- **D6-F — Multi-chat integration gate:** run a controlled epoch with multiple sessions and deterministic synchronization.
- **D6-G — Adaptive specialization telemetry:** conflict-budget concurrency and soft Role Genome outcome updates.

No phase may silently change champion/promotion authority.
