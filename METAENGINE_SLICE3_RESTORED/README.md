# Destruktion 4.0 METAENGINE 16X — 2.3.0-alpha.1

A controlled policy-evolution and hermeneutic reasoning ecology over sixteen immutable engine lineages.

Version 2.3 closes the most important learning-integrity gaps in 2.2. Architecture changes are declarative, hash-addressed and evaluated only after a generation-wide freeze barrier. A candidate can become champion only through an outcome verifier, paired uncertainty bounds, suite-level non-inferiority, immutable safety gates and compare-and-swap promotion. Ordinary unverified runs cannot train biographies or promote policies.

The release does **not** claim parity with frontier foundation models. Four engines have native local executors; engines 5–16 remain explicitly labelled reference simulations. Structural depth and internal nonlinearity are diagnostics, never evidence of truth or external superiority.

## 2.3 controlled evolution

- **Generation barrier** — sibling worlds use one frozen champion and cannot influence each other before all artifacts are sealed.
- **Successive halving** — 24 declarative candidates are screened as 24 → 8 → 3 on disjoint case slices.
- **Outcome gate** — missing external/oracle evidence produces `INSUFFICIENT_EXTERNAL_EVIDENCE`; promotion is impossible.
- **Atomic promotion and rollback** — an append-only receipt and compare-and-swap champion pointer prevent split-brain updates.
- **Immutable safety kernel** — evolution cannot change truth invariants, verifier identity, holdout, permissions or promotion rules.
- **Actual-output provenance** — transformations must resolve to spans in real executor output; the static `TYPE_MAP` learning path is removed.
- **Typed handoff integrity** — objective, complete guardrails and handoff hash reach every selected deep execution without pressure truncation.
- **Dialectical graph** — ten typed operators preserve source readings, rival interpretations, falsifiers and residual tensions.
- **Auditable synthesis** — unresolved claims and defensible rivals survive synthesis instead of being erased by a scalar winner.
- **Hash-chained telemetry and replication outbox** — missing token/USD data stays missing; secrets are redacted and cloud writes are retryable.

The controlled 2.3 campaign executed **7,200 isolated worlds** across three generations. Two candidates passed the configured internal oracle gate; the third generation retained the champion. This validates the evolution mechanism, not general reasoning superiority. See `METAENGINE_2.3_IMPLEMENTATION_REPORT_RU.md` and `RELEASE_VALIDATION_2_3.md`.

Version 2.2 introduced the breadth-first evidence-control plane retained beneath the new 2.3 verifier and evolution layers. **These mechanisms organize computation and evaluation; they cannot vote a claim into truth or mutate an immutable native lineage.**

## Runtime

```text
16 × LIGHTWEIGHT DIAGNOSTIC PRIMARY
  ↓
PRIMARY MESH + CLAIM/DISAGREEMENT STATE
  ↓
TASK LEDGER: FACTS / ASSUMPTIONS / UNKNOWNS / WORKSTREAMS
  ↓
EXPECTED EPISTEMIC GAIN SCHEDULER
  ↓
TYPED HANDOFFS + TEMPORARY COALITIONS + TOPOLOGY
  ↓
SPARSE NATIVE RE-ENTRY
  ↓
TRANSFORMATION GRAPH + CANDIDATE ARCHIVE
  ↓
EVALUATOR ENSEMBLE + PARETO / TOURNAMENT SIGNALS
  ↓
PROGRESS LEDGER → CONTINUE / REPLAN / STOP
  ↓
16 × CROSS-ENGINE REVIEW → ARBITRATION → FUSION WITHOUT ERASURE
```

## New 2.2 mechanisms

- **Breadth-first workstreams** — independent domains receive parallel first-pass ownership before evidence-gated depth.
- **Task Ledger** — facts, routing assumptions and unresolved unknowns are never collapsed into one plan narrative.
- **Typed Handoffs** — every delegated deep execution receives a hash-bound objective, input references, budget and guardrails.
- **Progress Ledger** — stalled transformation traces can trigger topology replanning.
- **Evaluator Ensemble** — grounding-contract, novelty, independent-challenge, cost, integrity and abstention signals are kept separate.
- **Pareto Candidate Archive** — diverse non-dominated candidates survive instead of a scalar-score winner erasing alternatives.
- **Shadow Policy Evolution** — trace-derived router/topology mutations are proposals only and require an external acceptance gate.

The architectural source analysis and exact integration map are in `FRONTIER_ARCHITECTURE_INTEGRATION_REPORT_RU.md`.

## New 2.0 mechanisms

- **Native Re-entry Compiler** — compiles derived pressure back into native engine tasks while preserving the original-source firewall.
- **Expected Epistemic Gain Scheduler** — allocates deep budget by context-specific expected gain, cost, independence, tension and biography priors.
- **Engine Biographies** — empirical context-sensitive specialization memory, never authority weights.
- **Temporary Coalitions** — problem-specific groups with no truth authority.
- **Productive Topology Library + Architecture Evolution** — topology can be retained, mutated, quarantined or retired.
- **Transformation Graph** — records typed causal changes of question, interpretation, operator, parse, evidence, workflow, memory and hypothesis space.
- **Depth Budget Controller** — continuation must purchase itself with causal marginal gain.
- **Hash-bound Typed State Cache** — exact reuse only; no semantic-equivalence guessing.

## Core-4 native emphasis

- Engine 1: native interrogative induction; schema-valid abstention is preserved as a valid outcome.
- Engine 2: native micro-local operator ecology / source-resistance re-analysis; mutation is not fabricated without a valid source-born delta.
- Engine 3: native shared semantic-boundary / semantic-role execution.
- Engine 4: native semantic/scope/counterfactual gate execution.

## Controlled 1.4 → 2.0 A/B

Across five task classes:

- median local runtime: **3.25 s → 2.53 s** (~**1.28×** median speedup);
- deep executions: **200 → 62** (**69% reduction**);
- mean 2.0 typed causal depth: **8.0**;
- architecture mutations: **5**;
- native claim-node delta: **0**;
- native position delta: **0**;
- derived truth-promotion violations: **0**.

Exact warm rerun of the hermeneutic case: **3.32 s → 1.14 s** with **9/9** deep states reused by exact hash identity.

See `SELF_REORGANIZING_2.0_REPORT.md` and `AB_BENCHMARK_1.4_VS_2.0.json`. Runtime numbers are local controlled measurements, not external performance guarantees.

## Run and evolve

```bash
cd Destruktion_4.0_METAENGINE_16X_2.3.0-alpha.1
python -m metaengine.cli run path/to/source.md --out runs/example
python -m metaengine.cli active-policy
python -m metaengine.cli evolve --out runs/evolution --generations 3 --world-workers 8
python -m metaengine.cli rollback-policy POLICY_HASH --reason "canary regression"
```

`evolve` may promote only when a configured oracle/verifier supplies valid outcomes. A normal `run` deliberately records an unverified result and cannot modify the active policy.

Useful inspection commands:

```bash
python -m metaengine.cli biographies
python -m metaengine.cli topologies
python -m metaengine.cli route path/to/source.md
python -m metaengine.cli frontier-patterns
```


## Parallel Experimental Ecology 2.1

2.1 adds an outer bounded-concurrency fabric above the 2.0 self-organizing runtime. Experimental worlds read a frozen biography snapshot, cold worlds use isolated caches, and no cross-world comparison is allowed before the freeze barrier.

Commands:

```bash
python -m metaengine.cli parallel-benchmark file1.md file2.md --out runs/bench --world-workers 4 --inner-workers 2
python -m metaengine.cli parallel-worlds source.md --worlds 24 --out runs/worlds --world-workers 4 --inner-workers 2
python -m metaengine.cli parallel-ablation source.md --order 1 --out runs/ablate --world-workers 4 --inner-workers 2
python -m metaengine.cli parallel-topologies source.md --repeats 4 --out runs/topologies --world-workers 4 --inner-workers 2
```

Release-stage validation now contains **281,204 completed checks/executions**, including **117 full-native worlds**. The original 64,320-test campaign remains preserved, and the extended campaign adds 131,072 cache-key checks, 65,536 router perturbations, 16,384 topology screens, 1,820 order-4 frozen ablations, 2,048 additional randomized subsets and 24 full-native topology×task worlds. See `release-evidence/2.1/PARALLEL_EXPERIMENTAL_ECOLOGY_REPORT.md`.

## Persistence

Local JSON/JSONL remains the portable source record. Supabase project `gzrbxoiuenkksualgpvp` is the **single canonical cloud ledger and promotion authority**. Neon is retired from reads and writes; its project is retained only to avoid destructive deletion without explicit authorization. The 2.3 migration is applied to Supabase.

## Claim ceiling

`CONTROLLED_SELF_REORGANIZING_ARCHITECTURAL_PERFORMANCE_CAUSAL_DEPTH_AND_SPARSE_EXECUTION_GAIN_WITH_NATIVE_TRUTH_POSITION_INVARIANCE; NOT_EXTERNAL_PHILOSOPHICAL_SEMANTIC_OR_GENERAL_REASONING_SUPERIORITY_VALIDATION`

For 2.3 this ceiling is further constrained by: `REFERENCE_SIMULATIONS_PRESENT; EXTERNAL_FRONTIER_PARITY_NOT_ESTABLISHED`.


### Extended campaign

The 2.1 parallel ecology has now executed **281,204** controlled release-stage checks/executions, including **117 full-native worlds**. High-volume matrices include 131,072 cache-key checks (0 collisions), 65,536 router perturbations, 16,384 topology screens, 1,820 order-4 ablations and 2,048 additional randomized subset tests. A 24-world full-native topology×task matrix completed 24/24 with no native-position inflation or derived truth promotion.

The larger campaign also confirms two unresolved design pressures: **router-resolution saturation** (45 coarse fingerprints despite 65,536 perturbations) and **topology-selector concentration** (14,523 / 16,384 selections on `DYNAMIC_GAIN_TOPOLOGY`). These are explicit targets for the next stage.

## Portable Development Fabric — Stage A

Stage A adds an **additive local development control plane** under `metaengine/devfabric/` and `devfabric/`. It does not change the existing `destruktion-meta16` command or canonical Supabase authority.

Core commands after the locked development environment is available:

```bash
metaengine-dev doctor --profile offline --json
metaengine-dev task-create --objective "..." --source-checkpoint cp001 --source-tree-hash <sha> --capability CODE_GENERATOR
metaengine-dev journal-verify --json
metaengine-dev verify --profile normal --candidate-dir .
metaengine-dev capsule-build --out dist/METAENGINE_DEVFABRIC_CONTROL.zip --json
metaengine-dev recover-test --control-capsule dist/METAENGINE_DEVFABRIC_CONTROL.zip --json
```

The OFFLINE doctor is fail-closed: missing `uv.lock`, unresolved required tools, source-binding mismatch, Git-baseline failure, or modified protected lineage bytes block Stage A certification. Cloud credentials are never consulted by the OFFLINE profile.

The CONTROL capsule omits immutable lineage bytes and carries `devfabric/LINEAGE_LOCK_SHA256.txt` instead. Full lineage bytes remain in the Local FULL vault. The external Stage A gate receipt attests to the capsule SHA-256 without being embedded in the capsule, avoiding a self-referential hash cycle.

`zero_spend=true` is enforced by the router. P3 tasks are local-only, and paid-capable providers with unknown free quota are denied rather than assumed safe.
