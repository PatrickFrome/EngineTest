# Metaengine Portable Multi-Agent Development Fabric — Design Specification

**Date:** 2026-08-12  
**Status:** APPROVED_ARCHITECTURE / WRITTEN_SPEC_REVIEW_GATE  
**Target:** Destruktion 4.0 METAENGINE 16X 2.3.0-alpha.1  
**Source artifact SHA-256:** `8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0`  
**Canonical cloud authority:** Supabase project `gzrbxoiuenkksualgpvp`  
**Design principle:** Local-first + Cloud Swarm, zero-spend, capability-based routing, competitive multi-agent coding, deterministic promotion gates.

## 1. Purpose

Create a portable development environment that allows Metaengine to be developed from an ordinary AI chat while distributing work across the strongest available free local tools, AI coding agents, cloud services, CI systems, databases, observability platforms, and artifact stores.

The environment must continue to function when individual external services are unavailable, quotas are exhausted, authentication is absent, or a provider changes its product. No external service except the existing canonical Supabase ledger may become a hidden source of truth.

## 2. Success criteria

The environment is successful when all of the following hold:

1. A fresh machine can restore a usable development control plane from a portable CONTROL capsule without embedded secrets.
2. Offline mode can inspect, modify, test, verify, package, and propose a checkpoint without any cloud service.
3. Free-cloud mode can dispatch independent coding/review/testing tasks to multiple providers through capability adapters.
4. Exhausting a free quota causes a fail-closed or fallback routing decision, never an automatic paid overage.
5. Every significant code change can be traced from TaskEnvelope -> candidate implementation(s) -> deterministic verification -> independent review -> promotion proposal.
6. No AI agent or external service can directly change the canonical champion, verifier, truth rules, promotion gate, or immutable lineage bytes.
7. A provider can be replaced without changing the core task schema or the Metaengine reasoning architecture.
8. A new ordinary chat can recover current project state from portable artifacts plus canonical cloud state without relying on conversation memory.
9. The full immutable lineage vault remains independently verifiable.
10. All writes with canonical significance are content-addressed and append-only or compare-and-swap guarded.

## 3. Non-goals

This phase does not:

- make external AI services epistemic authorities;
- allow executable self-modification outside reviewed patches;
- create a second canonical database;
- automatically spend money after a free quota is exhausted;
- claim frontier-model parity from internal benchmarks;
- require GitHub, Cloudflare, Replit, Neon, Linear, PostHog, Google services, or any single provider for basic operation;
- copy canonical production data into disposable sandboxes by default.

## 4. Immutable architectural invariants

The existing 2.3 boundary remains in force:

- only declarative architecture policy may evolve autonomously under the existing generation-frozen promotion protocol;
- executable code, verifier logic, holdout material, permissions, source firewall, truth invariants, and promotion rules never self-update;
- all 16 lineage originals remain byte-preserved;
- majority vote is not truth;
- biographies and provider performance histories are routing priors, never truth weights;
- structural novelty is diagnostic, not a promotion objective;
- missing external evidence cannot be converted into success;
- canonical promotion authority remains Supabase.

The development fabric adds one new invariant:

> **External intelligence may propose, test, criticize, and rank patches; only deterministic gates plus the canonical promotion protocol may authorize a canonical state change.**

## 5. Top-level architecture

The fabric is split into eight independently replaceable planes.

### 5.1 Chat Orchestrator Plane

Primary interactive controller: ChatGPT / GPT-5.6 Sol.

Responsibilities:

- interpret user intent;
- decompose work into bounded TaskEnvelopes;
- choose risk/privacy class;
- select capabilities rather than specific vendors;
- launch parallel candidate worlds when useful;
- synthesize receipts and explain decisions;
- never bypass deterministic gates.

The chat is an orchestrator, not a persistence layer.

### 5.2 Portable Local Control Plane

Mandatory local components:

- Python >= 3.11;
- `uv` for Python environment and lockfile management;
- Git for local source history and worktrees;
- SQLite for the local session journal/outbox;
- pytest + Hypothesis for executable verification;
- Ruff + mypy for static checks;
- Semgrep Community Edition + pip-audit for security/dependency checks;
- project-native doctor/integrity tools;
- optional Ollama/OpenCode for unlimited local model-backed coding when local hardware permits.

This plane must be sufficient for OFFLINE mode.

### 5.3 AI Worker Plane

Workers are selected through capabilities, never hard-coded provider names.

Initial worker classes:

- `CODE_GENERATOR`
- `CODE_REPAIR`
- `ARCHITECTURE_CRITIC`
- `TEST_GENERATOR`
- `SECURITY_REVIEWER`
- `PERFORMANCE_REVIEWER`
- `DOC_REVIEWER`
- `COUNTEREXAMPLE_GENERATOR`
- `BENCHMARK_DESIGNER`
- `INDEPENDENT_ADJUDICATOR`

Initial providers and intended use:

- **Ollama + OpenCode:** default bulk local generation, repair, test generation, cheap parallel worlds;
- **Google Antigravity CLI:** independent multi-agent/subagent implementation and architectural criticism;
- **Replit Agent:** remote independent implementation, reproduction, smoke testing, small hosted prototypes within free credits;
- **GitHub Copilot Free / CLI:** opportunistic specialized review/fix once a repository is connected and quota permits;
- **Cloudflare Workers AI:** small edge inference, classification, routing assistance, and lightweight independent checks within the daily free allocation;
- future providers may join by implementing the same adapter contract.

No worker receives direct canonical database credentials.

### 5.4 Deterministic Verification Plane

Every candidate passes deterministic local verification before AI opinions are considered.

Minimum gate:

1. content hash verification;
2. affected unit tests;
3. full test suite when risk policy requires it;
4. Ruff;
5. mypy for typed surfaces;
6. Semgrep CE;
7. pip-audit for dependency changes;
8. project-native invariant checks;
9. lineage lock verification when relevant;
10. reproducibility/clean-worktree check.

Optional domain gates:

- differential benchmark;
- property-based tests;
- mutation testing;
- SQL migration verification;
- performance regression test;
- source/citation entailment check.

AI review can reject a deterministically passing patch, but it cannot make a deterministic failure pass.

### 5.5 Canonical Evidence and State Plane

**Supabase remains the sole canonical mutable ledger and promotion authority.**

Canonical responsibilities:

- champion pointer;
- architecture policies;
- frozen generation/evolution evidence;
- external outcomes;
- checkpoint chain;
- promotion/rollback records;
- canonical development receipts that have crossed the promotion boundary.

The new development fabric may add append-only development receipt tables in a future migration, but only after schema design and migration review.

### 5.6 Sandbox and Experimental Data Plane

Neon is allowed only as a **non-canonical disposable laboratory**.

Permitted uses:

- schema migration rehearsal;
- query tuning;
- isolated branch-per-experiment SQL tests;
- synthetic or explicitly exported non-sensitive fixtures;
- destructive migration simulation.

Forbidden by default:

- production reads/writes from Metaengine runtime;
- mirroring canonical champion state as an authority;
- treating Neon branch success as canonical evidence by itself;
- copying sensitive canonical data without a separately reviewed export policy.

This preserves the existing 2.3 statement that Neon is retired from canonical reads/writes while still exploiting its branch model for isolated experiments.

Cloudflare D1 may hold only ephemeral router metadata such as leases, quota snapshots, task pointers, and worker health. It cannot duplicate canonical policy/champion state.

### 5.7 Artifact, Recovery, and Memory Plane

Responsibilities are deliberately split:

- **Local FULL vault:** immutable lineage bytes and complete forensic recovery;
- **Portable CONTROL capsule:** chat development state, schemas, manifests, adapter configuration, task receipts, hashes, and bootstrap logic without secrets;
- **Cloudflare R2:** content-addressed artifact replication when configured within free-tier guardrails;
- **Google Drive:** human-accessible recovery/handoff artifacts and signed/hash manifests;
- **Create State:** semantic project memory, architecture decisions, session handoffs, and code knowledge; never canonical evidence;
- **Git repository:** source history, branches, patches, and CI once a durable repository exists.

Every replicated object is addressed by digest. Replicas may disappear without changing canonical state.

### 5.8 Observability and Human Coordination Plane

**PostHog** receives privacy-minimized development telemetry, especially AI/LLM execution traces where appropriate:

- provider/model class;
- task class;
- latency;
- token/compute estimates if exposed;
- success/failure;
- test delta;
- patch size;
- verifier outcome;
- promotion outcome;
- quota/fallback behavior.

Raw project secrets, private source content, unrestricted prompts, and canonical database credentials are not telemetry fields.

**Linear** is the human-readable task/project projection:

- project roadmap;
- issue status;
- review gates;
- milestones;
- release notes.

Linear issues are projections of TaskEnvelope state, not the machine source of truth.

## 6. Capability adapter contract

Every external provider adapter exposes a common logical interface.

Required fields:

- `provider_id`
- `adapter_version`
- `capabilities[]`
- `availability`
- `privacy_classes_supported[]`
- `execution_modes[]`
- `free_quota_policy`
- `concurrency_hint`
- `max_payload_hint`
- `health_check()`
- `quota_snapshot()`
- `execute(TaskEnvelope) -> CandidateReceipt`
- `cancel(task_id)` where supported

Provider-specific authentication remains outside the portable capsule.

Adapter output is data, never executable authority.

## 7. Core exchange objects

### 7.1 TaskEnvelope

A TaskEnvelope is immutable after dispatch and includes:

- `task_id`
- `parent_task_id` if decomposed
- `source_checkpoint_id`
- `source_tree_hash`
- `objective`
- `acceptance_tests`
- `allowed_paths`
- `forbidden_paths`
- `capabilities_required`
- `risk_class`
- `privacy_class`
- `network_policy`
- `time_budget`
- `compute_budget`
- `zero_spend = true`
- `max_parallel_candidates`
- `deterministic_gate_profile`
- `artifact_return_contract`

### 7.2 CandidateReceipt

A worker returns:

- `candidate_id`
- `task_id`
- `provider_id`
- `base_tree_hash`
- `patch_hash`
- `artifact_hashes[]`
- `changed_paths[]`
- `worker_summary`
- `self_reported_checks[]`
- `execution_metadata`

Self-reported checks are informative only until independently repeated.

### 7.3 VerificationReceipt

A verifier returns:

- candidate hash;
- verifier identity/version;
- exact commands or verifier profile;
- exit statuses;
- test counts;
- security findings;
- invariant findings;
- benchmark deltas when applicable;
- artifact hashes;
- verdict: `PASS`, `FAIL`, or `INCONCLUSIVE`.

### 7.4 PromotionProposal

A promotion proposal contains only verified content-addressed inputs and never performs promotion itself.

It references:

- source checkpoint;
- winning candidate;
- all verification receipts;
- dissenting AI reviews;
- benchmark receipts;
- risk classification;
- expected canonical mutations;
- rollback target.

## 8. Routing policy

Routing is capability-first and outcome-informed.

The router chooses workers using:

1. required capability;
2. privacy eligibility;
3. current health;
4. remaining free quota;
5. task risk;
6. historical task-class effectiveness;
7. independence/diversity value;
8. latency and compute cost;
9. concurrency availability.

Historical effectiveness may improve routing but cannot become an epistemic truth weight.

### Parallel-world policy

Suggested default candidate counts:

- trivial deterministic edit: 1 implementation + 1 verifier;
- normal feature/bugfix: 2 independent implementations + deterministic verification + 1 independent AI review;
- high-risk architecture/security/database change: 3-4 independent candidate/critic worlds + deterministic gates + differential benchmark where applicable;
- evolution/benchmark methodology changes: isolated design review before any implementation dispatch.

The router may reduce parallelism when quota or local resources are constrained.

## 9. Zero-spend policy

`zero_spend` is a hard execution invariant for the default profile.

Rules:

- providers with explicit hard free limits are allowed only while their free allowance is available;
- providers capable of paid overage require an explicit external budget guard configured to stop usage at zero paid spend, or they remain disabled in `FREE_CLOUD`;
- quota uncertainty routes to another provider or local execution;
- free quota exhaustion is recorded as `QUOTA_EXHAUSTED`, not as task failure;
- no adapter may silently upgrade a plan, attach a payment method, or turn on pay-as-you-go;
- billing configuration is never stored in the portable capsule.

Current official constraints relevant to the initial design:

- Cloudflare Workers Free: 100,000 requests/day;
- Cloudflare Workers AI: 10,000 free neurons/day, after which free-plan operations require upgrade rather than automatic paid inference;
- Cloudflare D1 Free: 5M rows read/day, 100k written/day, 5 GB total storage; limits fail closed;
- Cloudflare R2 Standard free tier: 10 GB-month storage, 1M Class A, 10M Class B operations/month, free egress;
- Cloudflare Workflows Free: 3,000 steps/day;
- Replit Starter: free daily Agent credits with a monthly cap;
- Ollama local execution: unlimited on local hardware;
- GitHub Free: 2,000 Actions minutes/month and 120 Codespaces core-hours/month for personal accounts;
- Linear Free: 2 teams and 250 issues;
- PostHog free tiers include 1M analytics events/month and 1M feature-flag requests/month;
- Neon Free currently provides up to 10 projects and branch-based experimentation subject to its Free resource allowances.

All quotas are runtime-discovered or treated as configuration hints because vendors may change them.

## 10. Privacy classes

Every task is classified before dispatch.

### P0 — Public

May be sent to any healthy free provider.

### P1 — Project-internal non-secret

May be sent only to providers explicitly enabled for project source processing.

### P2 — Sensitive project data

Local-only by default. External dispatch requires a provider-specific policy override.

### P3 — Secrets / credentials / canonical privileged material

Never placed in an AI prompt, portable artifact, telemetry event, or third-party task. Access occurs through managed OAuth, secret stores, or narrow server-side bindings only.

## 11. Portability profiles

### OFFLINE

Requires only local toolchain and project bytes.

Provides:

- edit/build/test/static/security checks;
- local AI if Ollama is installed;
- local SQLite task journal;
- patch and checkpoint proposal generation;
- full integrity verification when FULL vault is present.

### FREE_CLOUD

Adds any healthy zero-cost adapters:

- Supabase canonical reads/approved writes;
- Antigravity CLI;
- Replit;
- Cloudflare Free surfaces;
- Neon disposable branches;
- PostHog;
- Linear;
- Drive;
- Create State;
- GitHub if repository access becomes available.

### MAX_SWARM

Uses the largest safe parallel ensemble allowed by current free quotas and local compute. It never changes the canonical promotion rules and never relaxes privacy policy.

## 12. Portable filesystem model

Target control-plane layout:

```text
metaengine-dev/
  metaenv.toml
  TOOLCHAIN.lock
  uv.lock
  package-lock.json
  profiles/
    offline.toml
    free-cloud.toml
    max-swarm.toml
  router/
    capabilities/
    policies/
    quotas/
    dispatch/
  adapters/
    supabase/
    neon/
    cloudflare/
    linear/
    posthog/
    replit/
    github/
    drive/
    create_state/
    ollama/
    antigravity/
  mcp/
    gateway/
    schemas/
  verification/
    tests/
    static/
    security/
    differential/
  state/
    session.sqlite
    receipts/
    outbox/
  artifacts/
    manifests/
    patches/
    reports/
  bootstrap/
    linux.sh
    macos.sh
    windows-wsl.sh
  scripts/
    doctor
    dispatch
    verify
    checkpoint
    recover
```

Generated state is separable from source so the capsule can be rebuilt deterministically.

## 13. MCP gateway design

The fabric exposes a narrow MCP gateway rather than giving chat agents raw infrastructure access.

Initial MCP tool groups:

- project state/read-only inspection;
- task creation and status;
- candidate artifact listing;
- deterministic verification invocation;
- quota/health status;
- checkpoint proposal creation;
- canonical promotion request only through an explicit guarded tool.

Cloudflare Workers is the preferred remote MCP transport because it is lightweight and can use Workers bindings. Noodle Seed is an alternative deployment adapter for a governed hosted MCP endpoint. Neither becomes canonical state.

Authentication must be OAuth or managed identity where possible. Static long-lived data-plane credentials are forbidden in portable files.

## 14. Failure handling

### Provider failure

Mark provider unhealthy for a bounded cooldown and reroute. Preserve the original TaskEnvelope and all partial receipts.

### Quota exhaustion

Emit `QUOTA_EXHAUSTED`, update quota snapshot, reroute locally or to another free provider.

### Conflicting AI candidates

Run deterministic gates independently. If multiple pass, use benchmark evidence and independent review. If evidence remains insufficient, preserve multiple candidates and return `INCONCLUSIVE`; do not force a winner.

### Verification failure

Candidate is rejected or returned to a repair worker with the exact failing receipt. A repair is a new candidate with a new hash.

### Canonical cloud unavailable

Continue local development and append to local outbox. Canonical promotion is blocked until Supabase is reachable and the source checkpoint still matches.

### Recovery after chat loss

A new chat loads:

1. CONTROL capsule;
2. project state manifest;
3. current local task/outbox receipts if provided;
4. canonical checkpoint/champion from Supabase;
5. semantic handoff from Create State when available;
6. replicated artifacts from Drive/R2 only when required.

## 15. Git and source history

The current uploaded project archive has no `.git` directory. Therefore Git initialization must be an explicit implementation step rather than an assumed property of the archive.

The implementation plan must create a durable baseline in a way that preserves the source artifact binding:

- record the source archive SHA-256;
- create an initial immutable baseline commit or imported history strategy;
- exclude generated secrets/cache/runtime state;
- retain content-addressed release manifests;
- use worktrees or equivalent isolated directories for competing candidate worlds.

A remote GitHub repository is optional. Local Git remains mandatory for candidate isolation.

## 16. Testing strategy for the fabric itself

The development fabric must test itself.

Required test families:

1. adapter contract tests with fake providers;
2. quota fail-closed tests;
3. zero-spend policy tests;
4. privacy routing tests;
5. task immutability/hash tests;
6. candidate receipt validation;
7. deterministic gate precedence over AI opinion;
8. offline recovery test;
9. cloud outage/outbox replay test;
10. provider replacement test;
11. checkpoint CAS conflict test;
12. portable CONTROL capsule extraction + doctor test;
13. FULL lineage verification test;
14. no-secret-in-capsule scan;
15. cross-platform bootstrap smoke tests.

## 17. Rollout decomposition

Implementation is intentionally decomposed so every stage leaves a usable system.

### Stage A — Portable local kernel

- establish Git baseline;
- create `metaenv.toml` and toolchain lock;
- local SQLite task/receipt journal;
- TaskEnvelope/CandidateReceipt/VerificationReceipt schemas;
- capability registry extension;
- provider-independent router;
- deterministic verifier profiles;
- bootstrap + doctor;
- OFFLINE profile.

### Stage B — Local AI swarm

- Ollama adapter;
- OpenCode adapter/launcher;
- competitive candidate worktrees;
- local critic/reviewer workers;
- outcome-aware but non-authoritative worker routing.

### Stage C — Connected existing services

- Supabase guarded canonical adapter;
- Create State memory adapter;
- Google Drive artifact/recovery adapter;
- Linear projection adapter;
- PostHog privacy-minimized telemetry adapter;
- Neon disposable branch adapter;
- Replit independent worker adapter.

### Stage D — Remote edge fabric

- Cloudflare Worker MCP gateway;
- D1 ephemeral router state if needed;
- R2 artifact replication;
- Workflows for durable free-tier orchestration where step CPU constraints fit;
- Workers AI lightweight worker;
- Noodle Seed alternative MCP deployment profile.

### Stage E — GitHub/CI plane

When repository access exists:

- GitHub remote;
- PR projection;
- Actions verification;
- optional Copilot/CodeRabbit/Sonar review surfaces where free-plan/privacy policy permits.

### Stage F — Metaengine development intelligence

- provider outcome telemetry;
- routing effectiveness model;
- task-class specialization memory;
- differential benchmark scheduling;
- automatic recommendation of candidate ensemble size while preserving deterministic promotion rules.

## 18. Design decisions and rejected alternatives

### Rejected: cloud-first canonical control plane

Reason: makes chat development dependent on service availability and weakens portability.

### Rejected: GitHub as sole execution bus

Reason: current connector has no repository access and repository availability must not be required for recovery.

### Rejected: multiple canonical databases

Reason: creates split-brain champion/evidence state.

### Rejected: direct provider-specific calls throughout Metaengine core

Reason: produces vendor lock-in and makes quota/failure policy impossible to centralize.

### Rejected: AI majority vote for patch selection

Reason: conflicts with existing Metaengine truth invariants and provides correlated confidence rather than evidence.

### Rejected: automatic pay-as-you-go fallback

Reason: violates zero-spend requirement and makes routing costs unpredictable.

## 19. External facts verified for this design

Verified against official vendor sources on 2026-08-12:

- Google announced the consumer transition from Gemini CLI to Antigravity CLI, with free/individual Gemini CLI service ending 2026-06-18 and Antigravity positioned for multi-agent workflows.
- Cloudflare documents Workers Free limits, Workers AI's 10,000 free neurons/day, D1 free limits, R2 free tier, and Workflows free step allocation.
- Replit documents a Starter plan with daily Agent credits that reset daily subject to a monthly cap.
- Ollama states local model execution on the user's own hardware is unlimited.
- GitHub documents 2,000 Actions minutes and 120 Codespaces core-hours per month for GitHub Free personal accounts.
- Linear documents 2 teams and 250 issues on Free plus Agent Platform/MCP availability.
- PostHog documents generous monthly free tiers including 1M product analytics events and 1M feature-flag requests.
- Neon documents its free plan and branching model suitable for disposable test worlds.

Vendor limits are not hard-coded as truth: adapters must treat them as refreshable quota policy data.

## 20. Acceptance gate for implementation planning

Before implementation planning begins, the written specification must be reviewed for:

- placeholders/TODOs: none permitted;
- conflicts with Metaengine 2.3 invariants: none permitted;
- accidental second canonical authority: none permitted;
- hidden paid fallback: none permitted;
- provider lock-in at core interfaces: none permitted;
- secret material in portable files: none permitted;
- ambiguity about Neon canonical status: none permitted;
- ambiguity about AI authority: none permitted.

After written-spec approval, the next artifact is a detailed implementation plan, not direct ad-hoc coding.
