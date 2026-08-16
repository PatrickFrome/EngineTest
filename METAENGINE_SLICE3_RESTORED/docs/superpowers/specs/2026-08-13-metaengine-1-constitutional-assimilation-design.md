# METAENGINE-1 Constitutional Kernel, OrganizationPolicy, and Architectural Assimilation Foundation

**Status:** APPROVED DESIGN — user-approved direction with mandatory continuous development review requirement

**Stage ID:** `METAENGINE-1`

**Alias:** `METAENGINE-KERNEL-1`

**Parent implementation HEAD:** `b6473241c7cbb522a5d950f5f3f88ad0fbc2d010`

**Parent stage:** `D6-G1 PASS_ADAPTATION_SHADOW_READY`

## 1. Purpose

METAENGINE-1 turns the project's existing constitutional ideas, architecture-policy evolution, federation evidence, and prior architectural influences into a single model-independent foundation for discovering, testing, preserving, and assimilating ways of organizing intelligence.

The stage does **not** make MetaEngine self-modifying, does **not** activate D6-G2 Role Genome adaptation, does **not** promote a new canonical champion, and does **not** vendor arbitrary external model repositories into Core.

The stage establishes four durable primitives:

1. a compiled and hash-bound Constitutional Kernel;
2. a provider/model-independent `OrganizationPolicy v1` abstraction;
3. a content-addressed Architecture Source and Mechanism Library;
4. a mandatory Development Evolution Review Gate that runs after every completed development step before the next step may begin.

## 2. North-star identity

MetaEngine is a model-independent experimental operating system for organizing intelligence.

Its persistent purpose is to improve at least one of:

- **ABILITY TO ORGANIZE INTELLIGENCE**;
- **ABILITY TO LEARN HOW TO ORGANIZE INTELLIGENCE**;

without hidden weakening of:

- evidence;
- reproducibility;
- integrity;
- portability;

and without unjustified growth of:

- complexity;
- cost;
- lock-in.

Models, chats, agents, federation topologies, MCP transports, Supabase, Cloudflare, and the current 16 engine lineages are resources or implementations, not the permanent identity of MetaEngine.

## 3. Existing state and gaps

METAENGINE-1 preserves the useful properties of the current system rather than replacing them.

### 3.1 Existing constitutional fragments

Current constitutional semantics are spread across several places:

- `metaengine/security.py` defines `IMMUTABLE_GUARDRAILS`;
- `metaengine/architecture_policy.py` binds architecture policies to `IMMUTABLE_GUARDRAIL_HASH` and forbids mutation of verifier/benchmark/truth/tool-permission fields;
- `config/evolution_policy_2_3.json` separately defines immutable policy fields, promotion constraints, rollback, and `self_modifying_code_allowed = false`;
- DevFabric rules define no-canonical-authority, patch-only, credential, deterministic-gate, and deployment boundaries;
- federation protocols define privacy, fencing, review, immutable finalization, and shadow adaptation boundaries.

These rules are directionally consistent but do not yet derive from one machine-readable constitutional authority.

### 3.2 Concrete guardrail verification gap

`metaengine/security.py` currently defines six immutable guardrails but `verify_handoff()` validates only `IMMUTABLE_GUARDRAILS[:5]`.

Therefore the rule:

`SELF_UPDATE_CANNOT_MUTATE_VERIFIERS_OR_SAFETY_BOUNDARY`

contributes to `IMMUTABLE_GUARDRAIL_HASH` but is not currently required in a handoff payload.

METAENGINE-1 must close this with a RED-first regression test. This is a concrete example of why constitutional semantics must become compiled and centrally testable rather than duplicated by convention.

### 3.3 ArchitecturePolicy is a legacy-specific policy

`ArchitecturePolicy` currently encodes:

- `engine_01` ... `engine_16`;
- fixed dialectic operators;
- 16X-specific waves;
- 16X-specific mutation limits.

This remains a valid legacy policy format for the current engine ecology, but it is not sufficiently general to represent:

- one model;
- one model plus deterministic verifier;
- heterogeneous model families;
- a deterministic pipeline;
- temporary specialists;
- dynamic sparse routing;
- development/scientific federations;
- human/AI hybrid organizations.

METAENGINE-1 therefore introduces `OrganizationPolicy v1` above the legacy `ArchitecturePolicy`, with a deterministic legacy adapter instead of a destructive rewrite.

### 3.4 Architectural assimilation is currently informal

The project already contains architectural influences and bounded mechanisms inspired by external systems, but there is no first-class registry that distinguishes:

- source fact from inference;
- public/open code from restricted/reference-only material;
- an observed behavior from a mechanism hypothesis;
- a hypothesis from a transferred mechanism;
- a transferred mechanism from an assimilated principle.

METAENGINE-1 creates that boundary.

## 4. Three constitutional layers

The prior Core Constitution is retained as a design corpus, but its rules are compiled into three distinct authority levels rather than one monolithic immutable document.

### 4.1 K0 — Constitutional Invariants

K0 contains only semantics that ordinary experiments, organization policies, role adaptation, architecture search, and model outputs cannot mutate.

Initial K0 invariants:

1. **PROVENANCE_PRIMARY_EVIDENCE** — derived context never silently replaces primary evidence.
2. **CANONICAL_NOT_SCIENTIFIC_TRUTH** — canonical integrity does not itself establish scientific truth.
3. **NO_TRUTH_FROM_RANKING_OR_VOTING** — ranking, majority, reward, or popularity cannot promote a claim to truth by themselves.
4. **PRESERVE_ABSTENTION** — missing/unknown/abstained evidence cannot be silently converted to success, failure, or zero.
5. **MUTATION_REQUIRES_RECEIPT** — persistent mutation requires content-addressed provenance/evidence.
6. **SEPARATE_GENERATION_AND_PROMOTION** — a generator cannot be its sole promotion authority.
7. **FROZEN_EVALUATION_CONTRACT** — an experiment cannot mutate its own verifier/evaluator contract after execution starts.
8. **NO_NORMAL_KERNEL_SELF_MUTATION** — normal architecture/policy evolution cannot modify K0 semantics.
9. **NO_EXECUTABLE_SELF_MODIFICATION** — normal policy evolution cannot self-modify executable code.
10. **PRIVACY_PERMISSION_FAIL_CLOSED** — secrets, privacy, permissions, and authority boundaries fail closed.
11. **IMMUTABLE_HISTORY_WITH_SUPERSESSION** — historical lineage/evidence is not rewritten; later claims may supersede, narrow, contradict, or retract it.
12. **ROLLBACK_RECOVERY_REQUIRED** — canonical promotion requires a defined recovery/rollback path.

K0 is serialized canonically and content-addressed by `constitution_hash`.

### 4.2 K1 — Research Governance

K1 contains strong research policy that may evolve only through a dedicated constitutional-amendment process with independent evidence.

Initial K1 topics include:

- resource normalization;
- minimum sufficient organization;
- complexity tax;
- scientific versus development federation;
- replication definitions;
- evidence confidence levels;
- external sealed benchmark requirements;
- architecture assimilation rules;
- development evolution review procedure;
- provider/model independence requirements;
- promotion evidence ceilings.

K1 is not mutable through ordinary `OrganizationPolicy` evolution.

### 4.3 K2 — Organization Policy

K2 is the normal evidence-gated evolution surface.

It may describe:

- worker/resources;
- topology;
- routing;
- memory;
- tool access;
- information boundaries;
- review topology;
- budgets;
- termination;
- recovery;
- exploration policies;
- task-region specialization.

A K2 policy has no authority to relax K0 or K1.

## 5. Constitutional binding

The constitutional hash becomes a first-class lineage anchor.

Objects created under METAENGINE-1 must either directly contain `constitution_hash` or be transitively and unambiguously bound to an object that contains it.

Target bindings:

- `ResourceDescriptor`;
- `OrganizationPolicy`;
- `ExperimentContract`;
- `ExecutionReceipt`;
- `EvidenceReceipt`;
- `AdaptationReceipt`;
- `PromotionDecision`;
- `RecoveryCut`;
- `DevelopmentEvolutionReviewReceipt`.

Existing historical objects are not rewritten. They remain governed by their original guardrail/evolution hashes and are connected through legacy compatibility receipts.

## 6. Mandatory Development Evolution Review Gate

### 6.1 New permanent development law

After **every completed development step**, MetaEngine must perform a review cycle over:

1. the Constitution;
2. the Architecture/Mechanism Library;
3. current architecture/research/evolution policies;
4. the just-completed code/architecture change;
5. the best available alternative mechanisms and integrations;

and may begin the next development step only after a content-addressed review receipt exists.

This requirement applies to METAENGINE-1 itself and every later stage.

### 6.2 Definition of a development step

A `DevelopmentStep` is the smallest **complete, committed/reviewer-gated unit** with its own deterministic verification evidence.

An incomplete TDD state such as RED without GREEN is not a completed development step and therefore does not trigger the gate. The gate runs after the full atomic test/implementation/verification unit, before the next reviewer-gated task begins.

This definition preserves TDD atomicity while satisfying the requirement that no completed development advance bypasses constitutional and architectural reflection.

### 6.3 Review cycle

For completed step `S_n`:

```text
S_n COMPLETE
  ↓
VERIFY STEP EVIDENCE
  ↓
CONSTITUTION REVIEW
  ↓
ARCHITECTURE LIBRARY REVIEW
  ↓
POLICY REVIEW
  ↓
GENERATE ALTERNATIVES
  ↓
COMPARE CURRENT / LIBRARY-DERIVED / MINIMAL BASELINE
  ↓
SELECT ACCEPT / REVISE / REVERT / DEFER
  ↓
DEVELOPMENT EVOLUTION REVIEW RECEIPT
  ↓
ONLY THEN PLAN S_(n+1)
```

### 6.4 Constitution review

The review checks:

- whether the step violates K0;
- whether it silently changes K1 semantics;
- whether it expands authority, privacy, truth, or promotion semantics;
- whether a newly discovered failure requires a constitutional amendment candidate;
- whether the step made a constitutional rule unenforced or duplicated inconsistently.

K0 conflict yields `BLOCK_NEXT_STEP_CONSTITUTION`.

### 6.5 Architecture/Mechanism Library review

The review checks:

- mechanisms already registered and relevant to the just-completed problem;
- newly discovered mechanisms or source updates;
- whether the completed solution duplicates a known mechanism under another name;
- whether a simpler or better-supported implementation exists;
- whether multiple compatible mechanisms should be tested in an architecture tournament;
- whether the current solution should be generalized into a reusable mechanism candidate;
- whether new external architecture material should be ingested before the next step.

Library evidence may suggest alternatives but cannot override deterministic failure or K0.

### 6.6 Policy review

The review evaluates the completed change against:

- `OrganizationPolicy` contracts;
- legacy `ArchitecturePolicy` behavior;
- D6 federation/adaptation policies;
- evolution policy constraints;
- evidence/promotion contracts;
- complexity/resource budgets;
- current task-region assumptions.

The review explicitly asks whether the completed implementation should remain:

- Core;
- plugin/adapter;
- experimental mechanism;
- task-region-specific policy;
- deprecated/superseded path.

### 6.7 Alternative generation and comparison

Every review must include at least these alternatives when meaningful:

- **CURRENT** — retain the just-completed design;
- **MINIMAL** — a simpler organization or implementation;
- **LIBRARY** — the best relevant mechanism from the Architecture Library;
- **SYNTHESIS** — a compatible combination if evidence supports composition.

Alternatives are compared using a vector, not one scalar score:

- expected capability gain;
- evidence strength;
- information gain;
- complexity tax;
- resource cost;
- reversibility;
- blast radius;
- portability;
- provider/model independence;
- security/privacy impact;
- license/source risk;
- integration coupling;
- testability/reproducibility.

If evidence cannot distinguish alternatives, the result is `DEFER_EXPERIMENT_REQUIRED`, not an invented winner.

### 6.8 DevelopmentEvolutionReviewReceipt

Conceptual fields:

```text
review_protocol_version
completed_step_id
completed_step_commit
completed_step_evidence_hashes
constitution_hash
architecture_library_snapshot_hash
policy_snapshot_hash
relevant_mechanism_ids
alternatives_considered
decision
rationale
complexity_delta
capability_hypothesis
required_followup_experiment
constitutional_findings
library_findings
policy_findings
next_step_allowed
receipt_hash
```

Allowed decisions:

- `ACCEPT_CONTINUE`;
- `ACCEPT_WITH_FOLLOWUP_EXPERIMENT`;
- `REVISE_BEFORE_CONTINUE`;
- `REVERT_BEFORE_CONTINUE`;
- `DEFER_EXPERIMENT_REQUIRED`;
- `BLOCK_CONSTITUTIONAL_CONFLICT`.

`next_step_allowed = true` only for an explicitly admissible decision.

### 6.9 Hard transition invariant

No gate-bearing implementation task `S_(n+1)` may start unless the immediately preceding completed task `S_n` has a valid `DevelopmentEvolutionReviewReceipt` whose:

- commit/evidence hashes match the completed state;
- constitution/library/policy snapshot hashes are valid;
- `next_step_allowed` is true.

This becomes a deterministic development gate, not a prose checklist.

## 7. OrganizationPolicy v1

### 7.1 Purpose

`OrganizationPolicy` becomes the primary evolvable representation of how available intelligence is organized.

It is not tied to a model provider, chat UI, fixed number of agents, Supabase, Cloudflare, or the 16X engine identifiers.

### 7.2 Conceptual schema

An organization policy contains:

- `policy_version`;
- `constitution_hash`;
- `parent_policy_hash`;
- `resource_requirements`;
- `worker_roles`;
- `topology`;
- `routing`;
- `memory_policy`;
- `tool_policy`;
- `information_boundaries`;
- `review_policy`;
- `resource_budget`;
- `termination_policy`;
- `recovery_policy`;
- `evaluation_contract_ref`;
- `status`;
- `lineage`;
- `policy_hash`.

### 7.3 Supported initial organizations

The type must be able to express at least:

- `ONE_RESOURCE`;
- `RESOURCE_PLUS_VERIFIER`;
- `SEQUENTIAL_PIPELINE`;
- `PARALLEL_ENSEMBLE`;
- `SPECIALIST_ROUTING`;
- `HIERARCHICAL_FEDERATION`;
- `REDUNDANT_REPLICATION`;
- the current C0–C7 federation through a legacy adapter.

### 7.4 Legacy ArchitecturePolicy adapter

`ArchitecturePolicy` remains intact as a 2.3 representation.

A deterministic adapter maps it into `OrganizationPolicy` without claiming semantic features that are not present in the legacy policy.

The current canonical active/champion architecture policy is not changed by METAENGINE-1.

## 8. ResourceDescriptor v1

All intelligence sources are described as resources rather than hardcoded model/provider types.

Conceptual fields:

- resource identity/runtime identity;
- capability descriptors;
- context characteristics;
- tool capabilities;
- cost observations;
- latency observations;
- reliability observations;
- determinism class;
- privacy/security class;
- provider/runtime adapter reference;
- evidence confidence per property.

Missing observations remain `UNOBSERVED` rather than defaulting to zero or success.

The same abstraction must support, in principle:

- an LLM;
- a deterministic Python worker;
- a SQL/formal verifier;
- a search system;
- a human worker;
- a remote agent runtime.

## 9. Architecture Source Registry

### 9.1 Purpose

External model/system architectures are research sources, not automatically trusted dependencies.

Every source is pinned and classified before any code or mechanism can influence MetaEngine.

### 9.2 Source classes

Three source classes are mandatory:

#### `PERMISSIVE_CODE`

Official source code whose license permits the intended analysis/reference/reimplementation use.

Examples may include MIT/Apache-licensed official projects after license verification.

#### `RESTRICTED_REFERENCE`

Source/weights/code available under a custom or restrictive license. These may be studied and referenced subject to their terms but are not copied into Core by default.

#### `CLOSED_BEHAVIORAL_ONLY`

Public papers, system cards, documentation, or observable behavior are available, but internal architecture/code is not.

Claims about hidden implementation remain hypotheses, never source facts.

### 9.3 Source record

Each ingested source records:

```text
source_id
publisher
system_name
version
source_class
official_source_locator
exact_commit_or_release
retrieved_at
source_sha256
license_name
license_sha256
allowed_use
architecture_claims
retained_reference_paths
mechanism_candidates
```

No source enters the library without an explicit license/source classification.

### 9.4 Reference vault boundary

Large external source trees are kept outside MetaEngine Core and outside the ordinary CONTROL capsule.

Suggested boundary:

```text
research/architecture_library/      # small tracked metadata/cards/receipts
reference-vault/                    # external content-addressed source snapshots
```

The tracked project stores hashes, provenance, license metadata, architecture cards, and extracted mechanism hypotheses.

It does not create direct runtime dependencies on foreign repositories unless a later evidence-gated integration explicitly requires one.

## 10. Mechanism Library

### 10.1 Unit of assimilation

MetaEngine assimilates **mechanisms**, not brands, model weights, or whole foreign architectures.

A mechanism is an abstract, independently implementable hypothesis about a causal organization or computation strategy.

### 10.2 Mechanism states

- `A0_OBSERVED` — an interesting property/behavior is observed.
- `A1_MECHANISM_HYPOTHESIS` — a plausible abstract mechanism has been identified.
- `A2_TRANSFERABLE` — independent MetaEngine implementation reproduces the effect and survives ablation.
- `A3_ASSIMILATED` — the mechanism transfers across multiple task/resource regimes and may influence organization generation/search.

Only A3 mechanisms may automatically influence future organization-policy generation.

### 10.3 Mechanism record

```text
mechanism_id
semantic_definition
origin_source_ids
source_fact_boundary
hypothesized_effect
task_scope
prerequisites
resource_cost
complexity_cost
known_incompatibilities
known_failures
implementation_variants
experiment_receipts
ablation_receipts
transfer_receipts
confidence
status
```

### 10.4 Initial mechanism-candidate families

The initial registry should include mechanism hypotheses previously identified from public/open architecture research, including:

- sparse conditional routing;
- hybrid compressed-state/full-attention organization;
- latent/context compression;
- sparse evidence attention/retrieval;
- speculative multi-action/multi-plan proposal;
- adaptive reasoning budget;
- parallel hypothesis generation and critique;
- constitution-derived testing;
- residual organization paths;
- dynamic specialist/swarm instantiation;
- preserved structured state;
- objective-neutral load balancing.

These entries begin at A0/A1 unless MetaEngine already has independent experimental evidence sufficient for a higher status.

Existing 2.2/2.3 architecture influences must be retrospectively registered rather than reimplemented under new names.

## 11. Assimilation Loop

The permanent external-architecture assimilation loop is:

```text
EXTERNAL SYSTEM
  ↓
SOURCE / BEHAVIOR CHARACTERIZATION
  ↓
BEHAVIORAL / ARCHITECTURAL FINGERPRINT
  ↓
COMPETING MECHANISM HYPOTHESES
  ↓
ABSTRACT MECHANISM
  ↓
INDEPENDENT METAENGINE IMPLEMENTATION
  ↓
CONTROLLED EXPERIMENT
  ↓
ABLATION
  ↓
TRANSFER TEST
  ↓
ORGANIZATION TOURNAMENT
  ↓
REJECT / CONTEXTUAL / TRANSFERABLE / ASSIMILATED
```

A strong external model is evidence that a capability exists, not proof that MetaEngine knows the mechanism that causes it.

## 12. Constitution-derived testing

The Constitutional Kernel is executable in the testing sense.

For every K0 invariant the implementation must provide:

- deterministic positive conformance tests;
- deterministic negative/adversarial tests;
- generated boundary cases where useful;
- a stable error/failure code;
- coverage mapping from invariant → enforcement point → test.

A machine-readable `Constitution Conformance Matrix` becomes a required artifact.

The first required regression is the current handoff 5-of-6 guardrail gap.

## 13. Architecture Library as a development input, not authority

The library does not automatically modify code.

For every development step the Development Evolution Review may produce:

- `REUSE_EXISTING_MECHANISM`;
- `TEST_ALTERNATIVE_MECHANISM`;
- `REGISTER_NEW_MECHANISM_CANDIDATE`;
- `GENERALIZE_IMPLEMENTATION`;
- `KEEP_LOCAL_SPECIALIZATION`;
- `REJECT_LIBRARY_ALTERNATIVE`.

Every decision is preserved with rationale/evidence so the project learns not only which mechanisms worked, but which alternatives were considered and rejected.

## 14. Interaction with D6-G1 and future D6-G1O/D6-G1E

METAENGINE-1 does not invalidate D6-G1.

D6-G1 remains `PASS_ADAPTATION_SHADOW_READY`, with no automatic Role Genome materialization.

Future Outcome Receipt v2 and Evidence Campaign work should be expressed under the new constitutional and organization-policy contracts rather than becoming a parallel conceptual stack.

Before beginning those later implementation steps, the mandatory Development Evolution Review Gate must re-analyze:

- K0/K1;
- Mechanism Library;
- OrganizationPolicy/evolution policy;
- the best alternatives for richer outcome evidence and evidence campaigns.

This explicitly implements the requirement that every subsequent development step is preceded by a fresh architecture/constitution/policy selection cycle.

## 15. Initial external architecture research set

The first source-ingestion wave should prioritize sources with high architectural information value and clear official provenance.

### Permissive-code candidates, subject to exact license verification

- DeepSeek open inference/model repositories;
- Qwen open model/reference repositories;
- permissively licensed Moonshot/Kimi research components such as Kimi-Linear where confirmed;
- Apache/MIT-compatible Mistral/GLM implementation/reference material where confirmed.

### Restricted/reference candidates

- Llama-family material under Meta community licenses;
- Kimi releases with custom model licenses where applicable.

### Closed/behavioral/document-only candidates

- OpenAI frontier model system cards/research descriptions;
- Anthropic Claude/Constitutional AI public research where model internals are closed;
- Google Gemini/Deep Think public research where model internals are closed.

The ingestion implementation must verify the exact current official license and source before downloading or retaining code.

## 16. No cargo-cult integration rule

A foreign architectural feature cannot be integrated merely because a strong model uses it.

At minimum, a proposed assimilation must answer:

- What current MetaEngine inability does the mechanism address?
- What is the competing simpler explanation?
- Can the mechanism be implemented independently of the source model?
- What baseline and challenger isolate the effect?
- What resource normalization is required?
- What ablation would falsify the mechanism claim?
- Does the effect transfer across another resource/model/task regime?
- Does complexity tax erase the gain?

If these cannot be answered, the correct state is A0/A1, not code integration.

## 17. Model/provider independence gate

Core-domain code introduced by METAENGINE-1 must be expressible without business logic tied to particular providers such as:

- OpenAI;
- ChatGPT;
- Claude;
- Gemini;
- Supabase;
- Cloudflare;
- C0–C7;
- engine_01 ... engine_16.

Provider/runtime names belong in adapters, resource descriptors, source registry records, or legacy adapters.

A static dependency/conformance check should verify this boundary for the new Core package.

## 18. Storage/canonical authority

METAENGINE-1 does not decentralize canonical authority and does not change the existing Supabase canonical project.

Core semantics target a `CanonicalStore` contract based on required properties such as:

- ACID transactions;
- compare-and-swap/fencing;
- immutability constraints;
- content-addressed receipts;
- auditability.

Supabase/PostgreSQL remains the current implementation.

## 19. Security and license boundaries

External source ingestion must never:

- fetch or persist credentials;
- execute downloaded code merely because it was downloaded;
- add foreign dependencies to runtime automatically;
- copy restricted code into permissive Core;
- treat model weights as source code mechanisms;
- infer hidden architecture as fact from behavior;
- bypass existing P3/network restrictions;
- expand the 18-tool federation MCP surface implicitly.

Downloaded reference material is inert research input until separately validated.

## 20. Implementation slices

METAENGINE-1 should be implemented in this order because the mandatory review law must govern the stage itself.

### Slice 0 — Development Evolution Review Gate

Build the receipt/protocol and a **METAENGINE-1-local transition checker** first. This local checker must already be capable of blocking Slice 1 if Slice 0 lacks its own verified review receipt.

After Slice 0 passes, every subsequent slice must produce a Development Evolution Review Receipt before the next slice starts.

### Slice 1 — Constitutional Kernel v1

- canonical K0 representation;
- constitution hash;
- conformance matrix;
- 5-of-6 handoff regression fix;
- legacy guardrail compatibility;
- amendment boundary skeleton without amendment authority.

Then run the Development Evolution Review Gate.

### Slice 2 — OrganizationPolicy v1 + ResourceDescriptor v1

- provider-independent types;
- validation;
- hashing/lineage;
- legacy ArchitecturePolicy adapter;
- no canonical champion mutation.

Then run the Development Evolution Review Gate.

### Slice 3 — Architecture Source Registry

- source records;
- license/source classification;
- content hashes;
- reference-vault index;
- no runtime dependency.

Then run the Development Evolution Review Gate.

### Slice 4 — Mechanism Library and Assimilation Receipts

- A0–A3 states;
- mechanism cards;
- evidence/ablation/transfer references;
- registration of existing MetaEngine architecture influences;
- initial external-source mechanism hypotheses.

Then run the Development Evolution Review Gate.

### Slice 5 — Constitutional/Library/Policy Development Gate Global Integration

- promote the already-used METAENGINE-1-local checker into the permanent project-wide development transition gate;
- enforce review receipts at future implementation-plan task/stage transitions;
- add stage gate summary;
- produce deterministic METAENGINE-1 CONTROL/handoff evidence.

Only then may the next project stage begin.

## 21. Testing strategy

Implementation must be RED-first.

Required categories:

### Constitution

- missing any K0 invariant fails;
- mutation of K0-bound field fails;
- complete handoff including all current guardrails passes;
- historical legacy guardrail hashes remain readable without retroactive rewriting.

### Development review gate

- next step without receipt fails;
- stale receipt/commit mismatch fails;
- stale constitution/library/policy snapshot fails;
- blocking decision cannot advance;
- valid `ACCEPT_CONTINUE` advances exactly one transition.

### OrganizationPolicy

- canonical hash deterministic;
- semantically equivalent unordered inputs canonicalize deterministically where specified;
- unknown resource/role identities fail where contracts require pinning;
- legacy ArchitecturePolicy mapping stable;
- K0/K1 mutation attempts fail.

### Source registry

- source without license classification fails;
- hash mismatch fails;
- restricted source cannot be marked permissive without an explicit reviewed classification;
- downloaded content remains outside runtime import paths.

### Mechanism library

- A1 cannot be treated as A3;
- assimilation requires referenced transfer/ablation evidence;
- closed-model architectural hypotheses are marked as hypotheses, not facts;
- rejected mechanism remains in history.

### Regression

- D6 finalization remains immutable;
- D6-G1 remains shadow-only;
- 18-tool MCP surface unchanged;
- current active policy/champion/cp001 unchanged;
- lineage lock remains valid.

## 22. Stage completion criteria

METAENGINE-1 is complete only if all of the following are true:

1. `constitution_hash` is deterministic and enforced.
2. All K0 invariants map to enforcement and tests.
3. The existing handoff 5-of-6 gap is closed.
4. `OrganizationPolicy v1` represents legacy 16X and non-16X organizations without provider-specific Core logic.
5. `ResourceDescriptor v1` can describe at least one model-like and one deterministic worker without Core changes.
6. Architecture Source Registry records official source/version/hash/license class.
7. Mechanism Library distinguishes A0/A1/A2/A3 and prevents hypothesis-as-fact promotion.
8. The initial source wave has source/architecture cards for every explicitly targeted family: OpenAI GPT-5.6-class public material, Anthropic Claude/Constitutional AI, Google Gemini/Deep Think, DeepSeek V3/V3.2, Qwen3-Next/Qwen3.5-class open material, Moonshot/Kimi K2.5/K3 plus permissive Kimi research components, GLM, Mistral, and Llama 4. Closed or restricted systems remain document/reference-only as required by source and license boundaries.
9. For each source classified `PERMISSIVE_CODE`, the relevant official architecture/reference code (excluding model weights and unnecessary large artifacts) is content-addressed in the external reference vault when license verification and runtime budget permit; any blocked download is recorded as an explicit source-ingestion blocker rather than silently omitted.
10. Existing MetaEngine architectural influences are registered without duplicate implementation.
11. Every METAENGINE-1 slice after Slice 0 has a valid Development Evolution Review Receipt.
12. A deterministic checker prevents the next stage from starting without the latest valid review receipt.
13. D6-G1 adaptation remains shadow-only and canonical authority is unchanged.
14. 18-tool federation MCP surface remains unchanged.
15. Full regression, lineage, CONTROL determinism, Git portability, and secret scans pass.

Terminal status:

`PASS_METAENGINE_1_CONSTITUTIONAL_ASSIMILATION_FOUNDATION`

## 23. Explicit non-goals

METAENGINE-1 does not:

- activate D6-G2;
- automatically mutate Role Genomes;
- run an external sealed benchmark yet;
- automatically deploy Federation MCP;
- decentralize canonical truth;
- vendor large foreign repositories into Core;
- copy model weights;
- claim hidden architecture of closed models;
- enable executable self-modification;
- allow the Architecture Library to override Constitution or evidence gates;
- create new canonical champion/promotion records.

## 24. Design decision summary

The project adopts the following permanent development pattern:

```text
IMPLEMENT VERIFIED STEP
        ↓
CONSTITUTION ANALYSIS
        ↓
ARCHITECTURE / MECHANISM LIBRARY ANALYSIS
        ↓
POLICY ANALYSIS
        ↓
GENERATE AND COMPARE BEST ALTERNATIVES
        ↓
SELECT / REVISE / DEFER / REVERT
        ↓
CONTENT-ADDRESSED REVIEW RECEIPT
        ↓
ONLY THEN NEXT DEVELOPMENT STEP
```

This is not an optional retrospective. It is a required part of the architecture and the learning process of MetaEngine itself.

The purpose is to ensure that future development is not merely cumulative. Every step must reconsider whether the newest constitutional knowledge, external architectural knowledge, internal evidence, and current policy imply a better code or architecture decision before the project is allowed to move forward.
