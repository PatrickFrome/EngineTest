# METAENGINE — Best-in-Class Alternatives Comparison

**Task ID:** research-best-analogs
**Agent:** general-purpose (sub agent)
**Date:** 2026 (MetaEngine 2.3.0-alpha.1)
**Scope:** Compare 10 MetaEngine module categories against industry-standard / best open-source alternatives. For each: MetaEngine approach, best-in-class alternative, key gap, replacement difficulty, priority.

**Constitution note (claim ceiling):** every per-category comparison below is **evaluative, not truth**. "Best-in-class" means "widely deployed, well-maintained, dominant in its niche as of writing". Where a candidate's strengths are unverified, this is stated. The recommendation is to **adopt or interoperate**, never to silently replace a MetaEngine invariant.

---

## Executive Summary Table

| # | Category | MetaEngine Module (LOC) | Best-in-Class Alternative | Key Gap | Difficulty | Priority |
|---|----------|------------------------|---------------------------|---------|-----------|----------|
| 1 | Orchestrator / Coordinator | `orchestrator.py` (822 LOC monolith) | **LangGraph** (with **Temporal** for durable exec) | Single-process, single-class, try/except:pass everywhere, no durable state, no checkpoint/resume | Hard | **P0** |
| 2 | Fitness Evaluation | `tiered_fitness.py` (724 LOC, L0/L1/L2) | **BoTorch** (Bayesian surrogate) + Optuna driver | Surrogate is heuristic hand-rolled score, not a fitted GP / neural surrogate; no acquisition function | Hard | **P0** |
| 3 | Recursive Improvement | `real_recursive.py` (493 LOC, IDA flywheel) | **DSPy** (teleprompter / MIPRO) for prompt-side; **STaR** for reasoning-side | No gradient signal; amplify rules are 7 hand-coded heuristics; no automatic prompt/program optimization | Medium | P1 |
| 4 | Multi-Model Routing | `multi_model_router.py` (590 LOC) | **LiteLLM** (open-source proxy, 100+ providers) | Hardcoded to single localhost bridge; no provider abstraction, no virtual keys, no budget enforcement at API level | Easy | **P0** |
| 5 | State Management | `state_bus.py` (374 LOC) | **Redis** (pub/sub + atomic ops) or **NATS JetStream** (durable) | In-process dataclass, no thread safety, no pub/sub fan-out, no durability, no multi-process support | Medium | P1 |
| 6 | Event Publishing | `event_publisher.py` (187 LOC, JSONL + WS) | **structlog** + **sse-starlette** for low-end; **Kafka** / **NATS JetStream** for high-end | JSONL append-only with global singleton + lock; no schema registry, no backpressure, no partitioning | Easy | P2 |
| 7 | Dialectical Discourse | `dialectical_graph.py` (156 LOC, 10 ops) | **Multi-Agent Debate** (Du et al. 2023, 2.6k citations) for adversarial; **Graph of Thoughts** for structural | Operators are template strings, no LLM generation; rival_fork is hardcoded literal-vs-resistant, not data-driven | Medium | P2 |
| 8 | Constitutional AI | `constitution.py` (290 LOC, 12 K0 invariants) | **Anthropic Constitutional AI** (4.9k citations) + **NeMo Guardrails** for runtime enforcement | Constitution is static JSON, no AI-revision step, no runtime rails (input/output/dialog), no harmlessness scoring | Hard | P1 |
| 9 | Engine Diversity | 16 engines (4 native + 12 reference) | **Mixture-of-Experts** (sparse MoE routing) + ensemble dispatch | Reference engines are clean-room simulations, not real executors; no learned router; round-robin ≠ capability-typed sparse routing | Hard | P1 |
| 10 | Evidence Graph | `evidence_graph.py` (269 LOC) | **Neo4j** (durable graph DB) + **LlamaIndex** (graph-RAG retrieval) | In-memory tuple-of-dataclasses, no indexing, no Cypher, no vector retrieval, no scalable merge across runs | Medium | P1 |

**Priority summary:** P0 = 3 (orchestrator, fitness, router), P1 = 5 (recursive, state, constitutional, engines, evidence), P2 = 2 (events, dialectical).

---

## 1. Orchestrator / Coordinator

### 1.1 MetaEngine's Current Approach — `orchestrator.py` (822 LOC)

A single `MetaOrchestrator` class with one ~720-LOC `run()` method (lines 100–822). It coordinates 16 engines through 30 named "barriers" (CAPABILITY_ROUTING → PARALLEL_DIAGNOSTIC_PRIMARY → … → ATOMIC_POLICY_PROMOTION_OR_ROLLBACK). Uses `ThreadPoolExecutor(max_workers=16)` to fan out engine batches, writes one JSON artifact per phase to `out_dir`, and threads state through dicts (`ctx`, `state`). Lazy module imports inside the function. Phase 23 wires 16 auxiliary modules (task_conditional_selector, architecture_search, curriculum_generator, sealed_benchmark, information_gain_selector, …) each wrapped in `try: … except: pass` (Group F finding #4). Group A critical-analysis flagged 34 try/except blocks.

### 1.2 Best-in-class alternatives

| Framework | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **LangGraph** (LangChain) | Stateful graph orchestration with explicit nodes, edges, conditional routing, checkpointer, interrupts, human-in-the-loop | Lives in single process; "checkpoints are not durable execution" (Diagrid 2026, Temporal blog 2026); needs external durable layer | Dominant in agent framework comparisons (pickaxe.co 2026, IBM developer 2026, developersdigest 2026, Reddit r/LangChain 2026) |
| **AutoGen** (Microsoft) | Conversational multi-agent, strong code-execution + tool-use, AutoGen Studio UI | Looser state graph; weaker on durable execution; v0.4 → v0.5 breaking changes | Widely adopted in research; peer-1 with LangGraph in most comparisons |
| **CrewAI** | Role-based agents (Crew, Task, Agent), simplest developer UX | Not designed for stateful long-running pipelines; weaker control over execution graph | Mid-tier; popular for "build-a-team" tutorials |
| **MetaGPT** | Encodes SOPs (Standard Operating Procedures) for software-dev: product manager → architect → engineer roles; structured artifacts | Domain-specific (SDLC); not general-purpose | ~10k+ stars; cit. 2024 arXiv |
| **Temporal** (not agent framework, but **durable execution** runtime) | Workflow + Activity model, automatic retry, state survives process crash, replay-based determinism | Not LLM-aware; you build agent semantics on top | Industry standard for durable workflows; explicitly recommended for LangGraph in 2026 (Temporal LangGraph plugin, July 2026) |

**Industry consensus (2026):** **LangGraph for graph definition + Temporal for durable execution** is the recommended production pattern. LangGraph alone is insufficient for crash recovery (Diagrid blog "Why Checkpoints Aren't Durable Execution", Feb 2026; Temporal LangGraph Plugin announcement, Jul 2026).

### 1.3 Key Gap (what MetaEngine is missing)

1. **No durable execution.** A crash at barrier 17/30 loses everything. `out_dir/META_RUN.json` is overwritten every barrier change, not appended; no replay log.
2. **Single-class, single-method monolith.** 30 barriers embedded in one method = no testability at the barrier level. Group A flagged 34 try/except blocks inside `run()`.
3. **No conditional routing primitives.** Routing is decided once by `CapabilityRouter.plan()` then mutated imperatively. LangGraph supports `add_conditional_edges` natively.
4. **No interrupts / human-in-the-loop gates.** `SHADOW_POLICY_ACCEPTANCE_GATE` and `ATOMIC_POLICY_PROMOTION_OR_ROLLBACK` barriers are stated as invariants but implemented as synchronous writes; no pause-resume.
5. **No checkpointer abstraction.** `TypedStateCache` (per-engine cache) exists but is not a graph-state checkpointer; cannot resume a partially-completed orchestrator run.
6. **No streaming / partial-result semantics.** All 16 engines must complete a barrier before downstream can read.

### 1.4 Replacement Difficulty: **Hard**

- 30 barriers, 16 engines, 16 auxiliary modules wired in Phase 23
- Many lazy imports + try/except:pass blocks hide failure modes
- Cross-run state (`storage/accumulated_state.json`, `predictive_model.json`, `mechanism_library.json`) is read by `run()` directly
- Tests exist (`tests/test_orchestrator_integration.py`) but only exercise happy-path

### 1.5 Priority: **P0**

The orchestrator is the load-bearing wall of the entire system. Every other gap in this document flows through it. Without durable execution + checkpointing, no other improvement is safe to deploy.

### 1.6 Recommended Migration Path (incremental, not rip-and-replace)

1. **Phase A (1 week):** Wrap each barrier as a LangGraph node. Keep current `MetaOrchestrator.run()` as the "legacy adapter". Add a `LangGraphOrchestrator` that builds an equivalent graph and runs through LangGraph's `compile(checkpointer=SqliteSaver(...))`.
2. **Phase B (1 week):** Replace Phase 23 try/except:pass with conditional edges. Each auxiliary module becomes a node whose output is `[CONTINUE, SKIP_REASON]`.
3. **Phase C (2 weeks):** Add Temporal worker for durability. Each barrier becomes a Temporal Activity; the graph becomes a Temporal Workflow. Survives process crash mid-run.
4. **Phase D (1 week):** Add interrupt support at `SHADOW_POLICY_ACCEPTANCE_GATE` and `ATOMIC_POLICY_PROMOTION_OR_ROLLBACK` (these are the human-in-the-loop boundaries the constitution already implies).

---

## 2. Fitness Evaluation

### 2.1 MetaEngine's Current Approach — `tiered_fitness.py` (724 LOC)

Three tiers (per docstring):
- **L0 SURROGATE** (~0 ms): heuristic score = weighted sum of theta-derived scalars (max_rounds, exploration_rate, temperature, max_deep_engines). Group C analysis flagged "real_fitness ignores theta" → Fix #3 in worklog partially remediated.
- **L1 CONSTITUTION** (~1 ms): K0 invariant re-check on filtered candidates.
- **L2 REAL_LLM** (~3–10 s): RLAIF evaluation via `MultiModelRouter.call()`.

Budget enforcement: `max L2 calls per generation` (default 3). Caching by `theta_hash`. Tier distribution tracked per-generation. Adapter supports `start_generation()`, `summary()`, `_l2_calls_this_gen`, `_l2_fallback_count`.

### 2.2 Best-in-class alternatives

| Framework | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **BoTorch** (Meta / PyTorch ecosystem) | Bayesian Optimization with GP surrogate, q-EI batch acquisition, Thompson Sampling, MC acquisition functions, fits surrogate to observed (x, y) pairs | Higher setup cost; needs PyTorch; assumes continuous search space | cit. ~5k+ papers; standard for surrogate-assisted optimization (BoTorch.org v0.17, 2026); Fromer et al. 2025 (Pubs ACS); Teufel (OpenReview batched energy-entropy) |
| **Optuna** (Preferred Networks) | Black-box HPO with TPE / CMA-ES / NSGA-II samplers, pruners, dashboard, distributed optimization | TPE is not a true Bayesian surrogate; weaker for batch acquisition | Dominant in HPO benchmarks (Balazs Kegl Medium 2026); integrates LLM-enhanced BO (Optuna Hub 2026) |
| **Ray Tune** | Distributed HPO at scale, integrates with Optuna/BoTorch/HyperOpt as searchers, first-class Kubernetes | BoTorch/Optuna are the algorithms; Ray Tune is the scheduler | Industry standard for distributed ML training (Ray docs 2026) |

**Industry consensus:** **BoTorch for the surrogate model + acquisition function**, optionally wrapped by **Ray Tune** for distributed scheduling, or **Optuna** for simpler API. "BOHB combines Bayesian optimization and Hyperband" (Kegl 2026) is the dominant practical recipe.

### 2.3 Key Gap

1. **L0 surrogate is not a fitted surrogate.** It's a hand-coded heuristic weighted sum, not a Gaussian Process / neural network trained on prior (theta, fitness) observations. So the "online surrogate" claim in the docstring is misleading — there is no online learning of the surrogate itself, only caching of L2 results.
2. **No acquisition function.** Candidates are chosen by PBT/exploitFraction + amplify-guided mutation, not by Expected Improvement / Thompson Sampling / q-EI. There is no principled exploration–exploitation tradeoff.
3. **No batch evaluation primitive.** The adapter supports "top-N" L2 calls but doesn't optimize which N to evaluate jointly. BoTorch's q-EI does.
4. **No noise modeling.** LLM evaluations are noisy; BoTorch supports observation noise via `FixedNoiseGP` or `HeteroskedasticSingleTaskGP`. MetaEngine averages but doesn't model variance.
5. **No constraint functions.** Constitution invariants could be modeled as black-box constraints in BoTorch's `ScalarizedPosteriorTransform`. Currently they are an L1 pass/fail gate (binary, no gradation).
6. **Search space is discrete (4 theta dims, each integer or quantized float).** BoTorch handles mixed spaces via `MIXED` kernels; MetaEngine's L0 surrogate is hardcoded per-dimension.

### 2.4 Replacement Difficulty: **Hard**

- L0/L1/L2 wiring is deep in `real_recursive.py`, `pbt_fitness_wiring.py`, `pbt_trainer.py`
- Cache (theta_hash → result) would need to be rebuilt as BoTorch `TensorDataset`
- Constitution gate interplay with constraint functions needs care
- Need to keep claim_ceiling="EVALUATIVE_NOT_TRUTH" invariant intact

### 2.5 Priority: **P0**

Without a real fitted surrogate, "tiered fitness" is just "expensive call caching". The L2 budget is spent reactively (after PBT picked candidates), not proactively (where is epistemic value highest?). This is the second-biggest correctness/efficiency gap.

### 2.6 Recommended Migration Path

1. **Phase A (3 days):** Wrap BoTorch as an `L0_Surrogate` implementation behind the existing `ThreeTierFitnessAdapter` interface. Replace the heuristic weighted sum with `SingleTaskGP` trained on accumulated `(theta_vector, observed_fitness)` pairs. Preserve L1 (constitution) and L2 (real LLM) tiers as-is.
2. **Phase B (3 days):** Add an acquisition-function selector (q-EI default, Thompson Sampling for diversity). Replace "top-N" with "argmax_qEI".
3. **Phase C (3 days):** Use BoTorch's `optimize_acqf_discrete` to evaluate mixed search space; lift the 4-dimensional theta restriction (allow full architecture-policy space as search dim).
4. **Phase D (2 days):** Persist GP state across runs in `storage/surrogate_state.pt`. This closes the cross-run learning loop on the surrogate side, complementing the existing `accumulated_state.json` persistence.

---

## 3. Recursive Improvement

### 3.1 MetaEngine's Current Approach — `real_recursive.py` (493 LOC)

The "IDA flywheel" (Invent–Distill–Augment):
1. **AMPLIFY** — 7 hand-coded rules in `AmplifyDistillCycle.amplify()` generate config changes from previous metrics
2. **RUN** — PBT executes with `ThreeTierFitnessAdapter` as fitness function (real L2 LLM evaluations, budget 3/gen)
3. **DISTILL** — extracts insights from run metrics; persistence to `storage/phase52_amplify_distill/DISTILLATION_HISTORY.json`
4. **COMPARE** — `improvement_vs_prev` delta; R1.2 convergence check stops if `|improvement| < 0.005` for 2 gens
5. R1.1 reject-sampling: distill is "low-confidence" when no L2 signal (relaxed from skip-entirely)
6. R6.2 champion carry-forward: 50% champions + 50% fresh, with amplify-guided mutation

### 3.2 Best-in-class alternatives

| Method | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **STaR** (Zelikman et al. 2022) | Bootstrap reasoning by sampling rationales, filter by correctness, fine-tune on survivors | Requires gradient access (model fine-tuning) | 2k+ citations (arXiv 2203.14465); spawning many follow-ups (Self-Taught Reasoner topic page, EmergentMind 2025) |
| **Self-Rewarding LM** (Meta, 2024) | LLM-as-judge generates its own preference data; iterative DPO | Requires gradient access; reward hacking risk | Oxford Oxen.ai 2024; cited heavily in 2024–2026 self-improvement literature |
| **SPIN** (Self-Play fINe-tuning) | Bootstraps from model's own outputs, no human labels, plays against itself | Requires gradient access; convergence not guaranteed | Morphllm 2026 explicitly recommends for training-time self-improvement |
| **DSPy** (Stanford) | Declarative prompt programming with **automatic teleprompter optimization** (BootstrapFewShot, COPRO, MIPRO/MIPROv2); no gradient access required; "prompt optimization replaces hand-tuning loop" | Prompts only, not weights; needs evaluation metric | DSPy.ai; Khattab et al.; MIPROv2 (dspy.ai); Weaviate 2024 "Your LM Deserves Better Prompting" |
| **SEAL** (Self-Improves through Language) | Combines STaR + self-edit | Training-time; recent | Morphllm 2026 lists alongside SPIN/Self-Rewarding |

**Industry consensus (Morphllm 2026):** "Use training-time self-improvement (SPIN, Self-Rewarding, SEAL) only when you control the model weights and have an evaluation pipeline the system cannot touch." For MetaEngine's use case (no weight control, only inference), **DSPy's teleprompter is the closest analog** because it operates at the prompt/program level.

### 3.3 Key Gap

1. **Amplify rules are 7 hand-coded heuristics.** They map metrics → config changes (`max_rounds`, `exploration_rate`, `temperature`) via threshold rules. This is *prompt hacking* by humans, not *prompt optimization* by the system.
2. **No gradient signal.** PBT provides exploit/explore between members, but no fine-tuning. Distillation produces `key_insights: list[str]` — free-text strings that are never re-applied to the LLM.
3. **Distillation insights are observational, never re-injected.** They are written to JSONL history and never become prompts, demonstrations, or program revisions.
4. **No demonstration bootstrap.** DSPy's `BootstrapFewShot` extracts successful (input, output) traces from runs and uses them as few-shot examples in future runs. MetaEngine's `transformation_graph.py` captures transformations but they are not fed back as demonstrations.
5. **No MIPRO-style joint optimization.** DSPy optimizes instructions + few-shot examples jointly. MetaEngine's amplify optimizes only hyperparameters (round count, exploration rate), not prompts.
6. **R6.2 "amplify-guided mutation" is half-step interpolation**, not principled optimization. It moves champions 50% toward amplify's targets — but amplify's targets are themselves heuristic, so this compounds error.

### 3.4 Replacement Difficulty: **Medium**

- DSPy can be adopted alongside (not replacing) the existing PBT loop
- The L2 evaluation already produces (theta, fitness, traces) — perfect DSPy training data
- Convergence criterion (R1.2) and champion carry-forward (R6.2) remain useful as outer-loop control
- Constraint: constitution forbids `NO_NORMAL_KERNEL_SELF_MUTATION` — DSPy prompt optimization is consistent with this (prompts are not "kernel"), but policy must be explicit

### 3.5 Priority: **P1**

Self-improvement is the system's stated raison d'être. Without a real optimization loop, the IDA flywheel is an elaborate state machine that doesn't actually improve quality. But it's not P0 — the system runs and produces artifacts; it just doesn't get better.

### 3.6 Recommended Migration Path

1. **Phase A (1 week):** Wrap the L2 LLM call as a DSPy `Module` with a typed `Signature`. Convert the existing `RoutedResult.response_text` into DSPy `Example` objects. The fitness function becomes a DSPy `metric`.
2. **Phase B (1 week):** Replace `AmplifyDistillCycle.amplify()` with `BootstrapFewShot` teleprompter. Distill insights become demonstrations (high-fitness traces) rather than free text.
3. **Phase C (2 weeks):** Add `MIPROv2` for joint instruction + few-shot optimization. Replace the 7 hand-coded amplify rules with MIPRO's instruction proposals.
4. **Phase D (1 week):** Persist DSPy program state in `storage/dspy_program.json`. Each run loads the previous compiled program, evaluates, optionally re-optimizes if drift detected.

---

## 4. Multi-Model Routing

### 4.1 MetaEngine's Current Approach — `multi_model_router.py` (590 LOC)

- Round-robin selection among healthy backends
- Cost-aware variant (N3): prefers cheap backends for short prompts / low max_tokens
- Failover on HTTP 429/500 or timeout; marks unhealthy after 3 failures
- Background reaper thread probes unhealthy backends every 30 s; cooldown 60 s
- All backends hardcoded to `http://localhost:3031/v1/chat/completions` (the `z-ai-web-dev-sdk` bridge)
- Default router (`create_default_router()`) registers `glm-1` (standard, cost 1.0) + `glm-thinking` (complex, cost 1.5)

### 4.2 Best-in-class alternatives

| Framework | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **LiteLLM** (BerriAI) | Open-source Python proxy + library, 100+ providers, OpenAI-compatible API, retry/fallback logic, virtual keys, per-project cost tracking, multi-tenant budgets | Self-hosted; needs ops | "Fastest, litest AI Gateway" (GitHub); Requesty 2026, TrueFoundry 2026, Layer3Labs 2026, PkgPulse 2026 all rank #1 for self-hosting |
| **Portkey** | Production-grade LLMOps: observability, guardrails, prompt management, multi-tenant | SaaS-first; OSS gateway is thinner | PkgPulse 2026 ranks #1 for "enterprise LLMOps" |
| **OpenRouter** | Managed cloud aggregator, 200+ models, one API, no platform fee | Adds markup on model price; less control | TrueFoundry 2026; Layer3Labs 2026 |
| **Requesty** | Newer (2026), routing + observability + cost optimization | Smaller ecosystem | Requesty blog 2026 |

**Industry consensus:** **LiteLLM for self-hosted multi-model gateway** is the dominant choice for projects that already have their own infrastructure and want a drop-in OpenAI-compatible proxy. Portkey for teams that want a managed LLMOps platform.

### 4.3 Key Gap

1. **Single localhost bridge.** `create_default_router()` hardcodes both backends to `http://localhost:3031/v1/chat/completions`. There is no real "multi-model" — only model-name variation over a single endpoint.
2. **No provider abstraction.** LiteLLM unifies 100+ providers (Anthropic, OpenAI, Vertex, Bedrock, Mistral, Cohere, …) behind one API. MetaEngine would need to write a new adapter per provider.
3. **No virtual keys / no per-tenant budgets.** Cost tracking is a `cost_score: float` per backend, not enforced at the API level. LiteLLM enforces budgets per virtual key.
4. **No streaming.** `MultiModelRouter.call()` is blocking `urllib.request.urlopen`. LiteLLM supports streaming. For real-time UX this matters.
5. **No retry-with-backoff policy.** `max_retries=3` is a fixed loop. LiteLLM supports exponential backoff, jitter, retry-after headers.
6. **No observability hooks.** No request logging, no latency histograms per model, no cost dashboards. LiteLLM integrates with Langfuse, Helicone, etc.
7. **Health check is hardcoded URL.** `_default_probe` derives `/health` from the chat endpoint by string manipulation. Brittle.

### 4.4 Replacement Difficulty: **Easy**

- `MultiModelRouter.call(prompt, *, max_tokens, temperature, timeout, max_retries)` API is a near-perfect match for `litellm.completion()`
- Existing tests (`tests/test_multi_model_router.py`) test the API surface, not the internals
- Default router factory is the only place that knows about localhost:3031
- Constitution: transparent routing invariant is preserved by LiteLLM (it doesn't modify prompts)

### 4.5 Priority: **P0**

Every L2 call (real LLM evaluation) flows through `MultiModelRouter`. If the bridge is down, every fitness evaluation silently fails (the `_l2_fallback_count` path). Adopting LiteLLM gives real multi-provider failover (Anthropic, OpenAI, Bedrock) for the price of a config change, and unlocks cost tracking + observability.

### 4.6 Recommended Migration Path

1. **Phase A (1 day):** `pip install litellm`. Add `litellm_router.py` that wraps `litellm.Router(model_list=[...])` and exposes the same `call() → RoutedResult` interface.
2. **Phase B (1 day):** Replace `create_default_router()` to read model list from `config/multi_model_router.json` (which already lists backends). Add Anthropic + OpenAI + Bedrock entries alongside the existing localhost bridge.
3. **Phase C (2 days):** Add LiteLLM virtual keys + budget enforcement. Replace `cost_score: float` heuristic with real per-model pricing (LiteLLM ships a cost table).
4. **Phase D (1 day):** Wire LiteLLM's callback hooks to `event_publisher.publish_event()` so router.failover / router.recovered events still fire.

---

## 5. State Management

### 5.1 MetaEngine's Current Approach — `state_bus.py` (374 LOC)

`TrainingStateBus` is a `@dataclass` with 9 publisher buckets (`publish_rlaif`, `publish_pbt`, `publish_alphazero`, `publish_es`, `publish_marl`, `publish_redteam`, `publish_faithfulness`, `publish_traces`, `publish_transfer`) + 1 added in I3 (`publish_tiered_fitness`). Subscribe methods return the latest value. Hash is computed via `canonical_hash(payload)`. Persistence via `save(path)` / `load(path)` to JSON. **No threading lock** (Group C finding: "state_bus not thread-safe"). Trainers hold a reference to the bus instance and call publish_* methods directly.

### 5.2 Best-in-class alternatives

| System | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **Redis** (Pub/Sub + Streams + Hashes) | Atomic ops, sub-ms latency, widely deployed, multi-process, language-agnostic | In-memory (persistence is snapshot/AOF); no replay log unless Streams used; ops burden | Industry standard for pub/sub state sharing in Python; LinkedIn 2026 NATS post; OneUptime 2026 ("Redis with Temporal") |
| **NATS JetStream** | Durable streams, at-least-once / exactly-once delivery, native clustering, lightweight Go binary | Smaller Python ecosystem than Redis | Synadia 2026 ("Why NATS"); LinkedIn 2026 ("NATS JetStream for AI Agent Workflows"); positioned as Redis+Kafka hybrid |
| **Temporal** | Durable *workflow* state (not just shared dict); survives process crashes; replay-based determinism | Heavier; you write workflows as code, not just put/get | Temporal blog 2026 ("Beyond State Machines"); Dev.to 2026 ("From Celery/Redis to Temporal") |

**Industry consensus:** **Redis for ephemeral pub/sub + cache** (fast, simple, ubiquitous); **NATS JetStream** when you need durability without Kafka's weight; **Temporal** when state needs to survive crashes. The 2026 trend is "Redis for hot state + Temporal for durable workflow state" (OneUptime 2026).

### 5.3 Key Gap

1. **In-process only.** No cross-process pub/sub. If you spawn trainers as separate processes (which PBT, ES, RLAIF all want), they cannot share the bus.
2. **Not thread-safe.** Group C flagged this. The `publish_*` methods mutate dict/list fields without a lock; concurrent trainers race.
3. **No fan-out.** `get_pbt_champions()` returns the latest list. If two subscribers need different views, they get the same reference (mutating races).
4. **No history.** Only the latest value is kept. Want to know "what was the fitness 5 generations ago?" → not available.
5. **No backpressure.** A fast trainer (RLAIF) can overwrite a slow trainer's (MARL) state before the slow trainer reads it.
6. **Persistence is whole-bus JSON dump.** `save()` serializes everything; if a trainer is mid-publish, you can serialize a half-updated state.

### 5.4 Replacement Difficulty: **Medium**

- The 10 `publish_*` / 10 `get_*` methods are a clear API surface to preserve
- Replacing with Redis: each publish becomes `redis.hset("bus:rlaif", engine_id, reward)`; each get becomes `hgetall`
- For multi-process fan-out: Redis Pub/Sub or NATS subjects `bus.rlaif.<engine_id>`
- For durability: NATS JetStream subjects with `MaxAge` retention

### 5.5 Priority: **P1**

The bus works for single-process runs (which is what MetaEngine does today). But:
- PBT population training is naturally parallel — separate processes would scale
- The thread-safety bug is a live correctness issue
- Cross-run persistence is already half-implemented via `accumulated_state.json`; the bus should be the unified store

### 5.6 Recommended Migration Path

1. **Phase A (2 days):** Add a `RedisTrainingStateBus` subclass that implements the same 10 publish / 10 get methods via `redis-py`. Keep the in-process `TrainingStateBus` as a fallback for tests.
2. **Phase B (2 days):** Add a `Lock` wrapper or use `redis WATCH/MULTI` for atomic publish. Fix the thread-safety bug for the in-process variant too.
3. **Phase C (3 days):** For each `publish_*`, also publish to a Redis Pub/Sub channel `bus.<bucket>`. Subscribers can listen to fan-out events.
4. **Phase D (3 days, optional):** Migrate to NATS JetStream for durable cross-process pub/sub. This unlocks crash-recovery (a trainer that crashes can replay missed events).

---

## 6. Event Publishing

### 6.1 MetaEngine's Current Approach — `event_publisher.py` (187 LOC)

- Module-level singleton: `_event_log_path`, `_event_log_lock`, `_initialized`
- `publish_event(event_type, payload)` appends one JSON line to `storage/events.log`
- `read_events_since(offset)` reads by byte offset (tail-follow semantics)
- A separate `ws-events` mini-service (port 3032) tails the file and pushes to WebSocket clients
- All publish failures are swallowed (`except Exception: return None`)
- Events carry `truth_effect: "NONE"` and a `canonical_hash`-based `event_hash`

### 6.2 Best-in-class alternatives

| System | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **structlog** | Structured logging as Python log records; processor pipeline (add context, redact, serialize to JSON); drop-in replacement for stdlib `logging` | Not a streaming system; no pub/sub fan-out; consumers tail log files | Dash0 2026 ("Leveling Up Your Python Logs with Structlog"); structlog.org; Reddit r/Python 2026 |
| **sse-starlette** | W3C-spec Server-Sent Events for FastAPI/Starlette; replaces custom WebSocket tail; reconnect-with-Last-Event-ID built in | Single-server only; for multi-instance you need a pub/sub broker in front | GitHub sysid/sse-starlette; StackOverflow 2026 (StreamingResponse vs SSE) |
| **Kafka** | Distributed log, partitioned, replicated, replayable, consumer groups | Ops-heavy; overkill for single-node; JVM | Standard for high-volume event streaming |
| **NATS JetStream** | Lightweight alternative to Kafka; durable streams, subjects, consumer groups; single Go binary | Smaller ecosystem than Kafka | Synadia 2026 |
| **structlog + OpenTelemetry** | Structured logs + distributed tracing unified | More moving parts | Medium 2026 "7 Python Logging Pipelines (structlog + OTel)" |

**Industry consensus:** **structlog** for structured logs (developer-side), **sse-starlette** for browser-facing event push (replaces ad-hoc WebSocket tail), **NATS/Kafka** for inter-service event streams. The current trend (Medium 2026) is "structlog processor pipeline → OTel collector → backend (Loki/Jaeger/Honeycomb)".

### 6.3 Key Gap

1. **Module-level singleton with global lock.** Tests must call `reset_event_log()` between cases. The lock serializes all publishers — fine for low volume, contention at high throughput.
2. **No schema.** `payload` is `dict[str, Any]`. No versioning, no breaking-change detection. LiteLLM and Temporal both ship typed event schemas.
3. **Swallowed exceptions hide failures.** `except Exception: return None` means a misconfigured storage path silently loses every event. The caller has no way to know.
4. **No backpressure.** If `ws-events` can't keep up, the file grows unbounded. No rotation, no retention policy.
5. **Custom WebSocket protocol.** Reinvents SSE; no `Last-Event-ID` header support, no automatic reconnect on the client side.
6. **No tracing context.** Events don't carry trace IDs / span IDs, so you can't follow a request across modules.
7. **No partitioning.** One file = one partition. Cannot scale horizontally.

### 6.4 Replacement Difficulty: **Easy**

- `publish_event()` is a single function with a clear contract
- `read_events_since()` is a tail-follow reader; sse-starlette does this natively
- The 8 event types listed in the docstring map cleanly to structlog event names
- Constitution invariant (truth_effect=NONE, append-only) is preserved by all alternatives

### 6.5 Priority: **P2**

Events are observability — important for ops, not for correctness. The current system works for single-process debugging. Becomes P1 only if multi-instance scaling is on the roadmap.

### 6.6 Recommended Migration Path

1. **Phase A (1 day):** Replace `publish_event()` internals with `structlog.get_logger("metaengine.events").bind(event_type=..., payload=...).info("event")`. Same JSON output, structured pipeline, no more module-level singleton.
2. **Phase B (1 day):** Replace `ws-events` mini-service with `sse-starlette` endpoint `/events/stream`. Client uses `EventSource` (browser native) with `Last-Event-ID` for replay.
3. **Phase C (2 days, optional):** Add OpenTelemetry tracing context. Every event carries `trace_id` / `span_id`. Wire to Jaeger / Honeycomb / Grafana Tempo.
4. **Phase D (3 days, optional):** If scaling beyond one node, front sse-starlette with NATS JetStream. Publishers write to NATS; sse-starlette subscribes and re-broadcasts.

---

## 7. Dialectical Discourse

### 7.1 MetaEngine's Current Approach — `dialectical_graph.py` (156 LOC)

10 typed operators (per architecture_policy config):
1. `SOURCE_READING` — first 4 sentences, confidence 0.55
2. `HORIZON_DISCLOSURE` — lexical modal markers (must/may/should/only/never/always…)
3. `RIVAL_FORK` — literal/charitable vs resistant reading (hardcoded pair)
4. `SEMANTIC_COUNTERFACTUAL` — negation/modality/attribution/scope transformation probe
5. `GENEALOGICAL_RETURN` — historical-transformation question
6. `EVIDENCE_DISCRIMINATOR` — what evidence would decide among rivals
7. `DOUBLE_HERMENEUTIC` — observer changes the question
8. `SUBLATION_WITH_RESIDUE` — conditional synthesis preserving irreducible residues
9. `OPERATOR_MUTATION` — replace the analytic operator if echoes
10. `SOURCE_RETURN` — return to exact source span before any promotion

R5: adds engine-contribution nodes + cross-engine rival forks + cross-engine evidence discrimination + cross-engine sublation. Outputs a graph with `nodes`, `edges`, `metrics` (node_count, edge_count, rival_pairs, residual_tension_nodes).

### 7.2 Best-in-class alternatives

| Method | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **Tree of Thoughts (ToT)** (Yao et al. 2023) | Search over a tree of reasoning steps; LLM evaluates each state; BFS/DFS + heuristic | Tree structure (no merge); single agent | IBM 2026 "What is Tree of Thoughts Prompting?"; Kargarisaac Medium 2026; widely cited |
| **Graph of Thoughts (GoT)** (Besta et al. 2023) | Generalizes ToT to arbitrary graph; merge/aggregate operations; outperforms CoT/ToT on complex tasks | More complex to implement; no standard library | EmergentMind 2025; arXiv 2401.14295; Pubs.TowardsAI 2025 ("GoT outperforms CoT and ToT in accuracy and cost effectiveness") |
| **Multi-Agent Debate (MAD)** (Du et al. 2023) | Multiple LLM instances debate → better factuality + reasoning; scales with agents/rounds | Token cost; convergence not guaranteed | 2.6k citations (arXiv; Du et al.); ACM 2024; Smit 2024 ("Should we be going MAD?"); Wang et al. 2025 (knowledge-enhanced MAD) |
| **Society of Minds (SoM)** (generalization of MAD) | Multiple agents debate + observe each other | Even more token cost | Smit 2024 |
| **Self-Consistency** (Wang et al. 2022) | Sample N reasoning paths, majority vote | Doesn't expose disagreement structure | Standard CoT enhancement |

**Industry consensus:** For structural reasoning, **Graph of Thoughts** generalizes ToT and outperforms it (EmergentMind 2025; TowardsAI 2025). For adversarial fact-checking, **Multi-Agent Debate** (Du et al. 2023, 2.6k citations) is the most-cited method. The two approaches are complementary — GoT is about *graph structure*, MAD is about *adversarial multi-agent*.

### 7.3 Key Gap

1. **Operators are template strings, not LLM generations.** `RIVAL_FORK` always produces "Literal/charitable reading: <sentence>" + "Resistant reading: the same wording may expose a limit…" — same text every time, parameterized only by source span. No actual reasoning is performed; the system just labels what a hermeneuticist might say.
2. **RIVAL_FORK is binary (literal vs resistant), not data-driven.** Real MAD uses N agents with different system prompts; the rivals emerge from the debate, not from a hardcoded literal/resistant pair.
3. **No LLM evaluator.** Each node has a `confidence` field hardcoded (0.55, 0.4, 0.5, 0.6, 0.45). ToT/GoT use an LLM to evaluate each state.
4. **No search.** The graph is built once, not explored. ToT does BFS over candidate reasoning steps; GoT aggregates. MetaEngine's `SUBLATION_WITH_RESIDUE` is a single synthesis, not a search over syntheses.
5. **No debate rounds.** MAD does multiple rounds; the literal/resistant readings never respond to each other.
6. **No agent specialization.** Each "engine contribution" is one LLM call. MAD uses different system prompts per agent to ensure perspective diversity.

### 7.4 Replacement Difficulty: **Medium**

- The 10 operators are a clean concept inventory; can be preserved as "thought-graph node types"
- Each operator currently does string manipulation; replacing with LLM calls is mechanical
- R5 (engine contributions) already shows the pattern for multi-engine discourse; needs to be promoted from "add a node per engine" to "engines debate each other across rounds"
- Constraint: `truth_effect=NONE` and `claim_ceiling=DIALECTICAL_DEPTH_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED` must remain

### 7.5 Priority: **P2**

The dialectical graph is rich **structure** but weak **reasoning**. It produces useful provenance graphs (good for evidence chain auditing) but doesn't actually reason about the source. This matters for tasks where the engine's output quality depends on multi-perspective reasoning. Not P0/P1 because:
- The 16-engine architecture already provides *de facto* multi-perspective (each engine is a different reference contract)
- The dialectical graph is more an *audit artifact* than a *reasoning engine*

### 7.6 Recommended Migration Path

1. **Phase A (1 week):** Replace `RIVAL_FORK` literal/resistant templates with two LLM calls using different system prompts ("Maximize local coherence" vs "Test non-endorsement and scope"). The current `assumptions` field becomes the system prompt.
2. **Phase B (1 week):** Add a debate loop: each rival gets a rebuttal step. Cap at 3 rounds to bound token cost. The `falsifier` field becomes the trigger to terminate debate.
3. **Phase C (1 week):** Add a GoT-style aggregation step. The `SUBLATION_WITH_RESIDUE` operator becomes an LLM call that takes all rival nodes as input and produces a synthesis that explicitly preserves residual tensions.
4. **Phase D (1 week, optional):** Add an LLM evaluator for `confidence` (currently hardcoded). ToT-style state evaluation.

---

## 8. Constitutional AI

### 8.1 MetaEngine's Current Approach — `constitution.py` (290 LOC)

`ConstitutionKernel` dataclass with:
- **12 K0 invariants** (frozen set): PROVENANCE_PRIMARY_EVIDENCE, CANONICAL_NOT_SCIENTIFIC_TRUTH, NO_TRUTH_FROM_RANKING_OR_VOTING, PRESERVE_ABSTENTION, MUTATION_REQUIRES_RECEIPT, SEPARATE_GENERATION_AND_PROMOTION, FROZEN_EVALUATION_CONTRACT, NO_NORMAL_KERNEL_SELF_MUTATION, NO_EXECUTABLE_SELF_MODIFICATION, PRIVACY_PERMISSION_FAIL_CLOSED, IMMUTABLE_HISTORY_WITH_SUPERSESSION, ROLLBACK_RECOVERY_REQUIRED
- **K1 topics** (loaded from JSON)
- **Amendment boundary** with `ordinary_evolution_allowed: False` and `authority_status: "NOT_IMPLEMENTED"` (constitution forbids self-amendment)
- `verify_constitution_conformance()` cross-checks each invariant has `enforcement_refs` (file paths) and `test_refs` (test files)
- Hash-checked K0/K1 payloads; load-time validation rejects duplicate/missing/unknown invariants

### 8.2 Best-in-class alternatives

| Method / Framework | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **Anthropic Constitutional AI (CAI)** | Two-stage: (1) supervised learning from AI-revised responses, (2) RLAIF (RL from AI Feedback) using a constitution as reward model. Self-improvement without human harm labels | Requires gradient access (model fine-tuning); principles need careful design | 4.9k citations (Bai et al. 2022); Anthropic 2022; LessWrong 2022; Zilliz Learn; TDWI 2026; NVIDIA Docs 2026 |
| **Guardrails AI** | Python library with validator schema; programmatic output validation; re-asks on failure | Output-side only; not training-time | GuardrailsAI.com; Galileo 2026; Bud Ecosystem 2025 |
| **NeMo Guardrails** (NVIDIA) | Colang DSL for **input / dialog / output / retrieval / execution rails**; can refuse unsafe outputs on the fly; multi-stage (input → LLM → output) | Colang learning curve; runtime overhead | NVIDIA GitHub; Rebedea et al. 2023 (594 citations); Qaskills 2026; Galileo 2026 (#1 platform list) |
| **Lakera Guard / Azure Content Safety** | Managed safety classifiers | SaaS; opaque rules | Galileo 2026 |

**Industry consensus:** **Anthropic CAI** is the canonical training-time method (4.9k citations). **NeMo Guardrails** is the canonical runtime-time framework (594 citations for the Colang paper). They are complementary: CAI bakes principles into weights; NeMo enforces them at inference time. Survey (Bud Ecosystem 2025): "NVIDIA's NeMo Guardrails can override unsafe LLM responses with a safe refusal on the fly… Anthropic's Constitutional AI method can be seen in [the same survey category]."

### 8.3 Key Gap

1. **No AI-revision step.** Anthropic CAI stage 1: take a harmful prompt + harmful response, ask the LLM to revise the response per the constitution, fine-tune on (prompt, revised). MetaEngine's constitution is **static JSON validated by file existence**; the LLM never sees the constitution.
2. **No RLAIF.** CAI stage 2: two model responses, ask the LLM which is better per the constitution, train a reward model, RL against it. MetaEngine has no reward model trained on the K0 invariants.
3. **No runtime rails.** NeMo's input/output/dialog rails intercept calls before/after the LLM. MetaEngine's invariants are *conformance-checked at load time* (`verify_constitution_conformance()`) but never *enforced at runtime* — there's no gate that blocks an LLM call because it would violate, say, `PRIVACY_PERMISSION_FAIL_CLOSED`.
4. **No harmlessness scoring.** Each K0 invariant is binary (present/absent). Anthropic CAI produces a continuous harmlessness score that can be optimized.
5. **No principle revision.** The constitution can't grow. Anthropic's approach: humans add principles; the model learns them. MetaEngine: the amendment boundary is `NOT_IMPLEMENTED` by design (a feature, not a bug — `NO_NORMAL_KERNEL_SELF_MUTATION`). But this means *no learning from observed violations*.
6. **No cross-agent constitution application.** Each engine has its own `claim_ceiling` but the K0 invariants are not propagated as system prompts to the engines.

### 8.4 Replacement Difficulty: **Hard**

- The 12 K0 invariants are deeply woven into every module's `payload()` (every module emits `truth_effect: "NONE"`, `claim_ceiling`)
- The amendment boundary is intentional — replacing it with Anthropic-style principle revision would violate `NO_NORMAL_KERNEL_SELF_MUTATION`
- Runtime NeMo-style rails would require intercepting every LLM call (already centralized in `MultiModelRouter.call()` — good insertion point)
- The static-load-time verification is excellent; any replacement must preserve it

### 8.5 Priority: **P1**

The constitution is the system's safety anchor. Without runtime enforcement, the invariants are documentation, not guardrails. But the design choice (`NO_NORMAL_KERNEL_SELF_MUTATION`) means full Anthropic CAI is *intentionally* not adopted. The right move is **add NeMo-style runtime rails without changing the K0 invariants**.

### 8.6 Recommended Migration Path

1. **Phase A (1 week):** Add a `ConstitutionRail` class that wraps `MultiModelRouter.call()`. Before the call: input rail (check prompt against `PRIVACY_PERMISSION_FAIL_CLOSED`). After the call: output rail (check response for truth claims that violate `CANONICAL_NOT_SCIENTIFIC_TRUTH`). On violation: return a templated refusal.
2. **Phase B (1 week):** Generate per-invariant Colang flows in `config/constitution/rails/`. Use NeMo Guardrails to evaluate them. This adds runtime enforcement without modifying the K0 JSON.
3. **Phase C (2 weeks, optional):** Add an LLM-based harmlessness scorer that rates engine outputs 0–1 against each K0 invariant. Persist scores in `storage/constitution_scores.json`. This is **observation only** (no reward model, no fine-tuning) — consistent with `SEPARATE_GENERATION_AND_PROMOTION`.
4. **Phase D (deferred):** Do NOT add CAI-style model fine-tuning. The amendment boundary forbids it. Document this decision explicitly.

---

## 9. Engine Diversity

### 9.1 MetaEngine's Current Approach — 16 engines per `config/meta_engine.json`

- **Engines 01–04**: native Node.js executors (NODE_NATIVE / NODE_UNIFIED) — Destruktion COMPLETE 0.13, integrated 0.10, UNIFIED 0.15, portable 0.16. These are real executors with native tests (94/129/18/120 passing).
- **Engines 05–16**: 12 clean-room reference contracts (PYTHON_REFERENCE_CONTRACT). Each is a *simulation* of an external architecture:
  - 05: Letta / MemGPT (persistent memory)
  - 06: Microsoft GraphRAG (graph extraction + community structure)
  - 07: FutureHouse / PaperQA2 / Robin (scientific evidence)
  - 08: Microsoft Magentic-One (manager-led specialist)
  - 09: OpenAI Deep Research (adaptive research)
  - 10: CAMEL / OWL (dynamic workforce)
  - 11: Microsoft Agent Framework (multi-agent workflow)
  - 12: LangGraph (durable state graph)
  - 13: GPT Researcher (planner-executor)
  - 14: Stanford STORM / Co-STORM (multi-perspective research)
  - 15: Sakana AI Scientist-v2 (research tree)
  - 16: DSPy (typed signatures + program optimization)
- The orchestrator runs all 16 in parallel via `CapabilityRouter.plan()`. Round-robin within waves; capability-typed assignment (philosophical_hermeneutics → engines 01/03/04).
- The `implementation_disclosure` field states explicitly: "Engines 01-04 are local native executors. Engines 05-16 are clean-room reference simulations and are never counted as real frontier executors."

### 9.2 Best-in-class alternatives

| Method | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **Mixture-of-Experts (sparse MoE)** | Replace dense FFN layers with K experts + learned router; only top-k activated per token; sub-linear cost growth with K | Requires gradient access (training); infrastructure complexity; load balancing | NVIDIA Developer 2024 ("Applying MoE in LLM Architectures"); Cameron Wolfe 2024 ("MoE LLMs"); Maarten Grootendorst 2024 ("A Visual Guide to MoE"); arXiv 2507.11181 (MoE survey, Dec 2025) |
| **Ensemble methods** (weight averaging, voting, stacking) | Combine N independent model outputs; simple; well-understood | Doesn't learn routing; cost = N× full inference | Classic ML literature |
| **Tool routing / function calling** (OpenAI functions, Anthropic tools) | Router picks which tool/expert per turn | Not architectural MoE; per-call routing only | Standard LLM API feature |
| **Multi-agent task dispatch** (LangGraph, AutoGen) | Each "engine" becomes an agent; conditional routing | Not sparse — every agent that fires incurs full inference cost | See §1 |

**Industry consensus (2024–2026):** **Sparse MoE** is the dominant pattern for *scaling model capacity* (DeepSeek, Mixtral, GShard, Switch Transformer). For *combining multiple independent models*, **ensemble + routing** is standard but expensive. MetaEngine's 16-engine approach is closer to the latter (ensemble) but with the unique twist that 12 of 16 are *simulations* of external architectures, not real executors.

### 9.3 Key Gap

1. **12 of 16 engines are simulations, not executors.** The config explicitly says so. This means MetaEngine's "16-engine ensemble" is effectively a 4-engine ensemble with 12 reference-contract placeholders that contribute *structural diagnostics* but not *real outputs*. The current `claim_ceiling` system handles this honestly (reference engines emit `PROPOSAL_UNTIL_EVIDENCE_AND_GATES`).
2. **No learned router.** The `CapabilityRouter` uses rule-based capability mapping (philosophical_hermeneutics → engines 01/03/04). Sparse MoE routers are *learned* — they observe (input, expert, performance) and adjust routing probabilities. MetaEngine's router is static.
3. **Round-robin within waves.** Each engine gets equal slot allocation regardless of its expected contribution. Sparse MoE's whole point is *top-k activation* — only the 2 best-suited experts fire per token, not all K=16.
4. **No load balancing.** If engine_01 is slower than engine_04, the orchestrator waits (the `ThreadPoolExecutor` barrier). MoE routers load-balance via auxiliary loss.
5. **No expert specialization learning.** Engine biographies (`biographies.py`) track contextual priors but don't *specialize* engines. MoE experts specialize during training.
6. **Reference engines are not interchangeable with native executors.** AdapterRegistry has separate modes (NODE_NATIVE / PYTHON_REFERENCE_CONTRACT / LLM_MODEL) but the orchestrator treats them symmetrically in scheduling. The "architectural influence is distinct from implementation equivalence" disclaimer is honest but the system doesn't enforce it in routing.

### 9.4 Replacement Difficulty: **Hard**

- The 16-engine architecture is the project's identity ("DESTRUKTION-16X-METAENGINE-2.3")
- Reducing engine count or promoting reference engines to real executors is a multi-month effort
- A learned router requires labeled (input, engine, performance) data — MetaEngine has this (`engine_biographies.json`) but the schema is contextual, not numeric
- The honest path: keep 16 engines for *architectural diversity* but **add a learned top-k router** that picks which 4–6 to actually invoke per input, rather than always running all 16

### 9.5 Priority: **P1**

The 16-engine design is intentional (architectural diversity as research signal). The gap is *not* "should be 4 engines" — it's "should learn which engines matter for each input". This is the highest-leverage architectural change after orchestrator + fitness.

### 9.6 Recommended Migration Path

1. **Phase A (2 weeks):** Train a lightweight router (small MLP or Logistic Regression) on `(task_features → engine_id → expected_gain)` tuples from `engine_biographies.json`. Persist as `storage/engine_router.pkl`.
2. **Phase B (1 week):** Replace `CapabilityRouter.plan()` rule-based mapping with `learned_router.predict(task_features)` for the top-k selection (k=4 by default, configurable). Keep all 16 engines *schedulable* but only run top-k *per input*.
3. **Phase C (1 week):** Add MoE-style auxiliary loss: penalize over-use of any single engine. Track load balance in `storage/engine_load_balance.json`.
4. **Phase D (2 weeks, optional):** Promote 1–2 reference engines to real executors. Engine_12 (LangGraph) and engine_16 (DSPy) are the highest-value candidates — both have OSS implementations that can be wired as real LLM_MODEL adapters via the existing `LLMModelAdapter`.

---

## 10. Evidence Graph

### 10.1 MetaEngine's Current Approach — `evidence_graph.py` (269 LOC)

`EvidenceGraph` is a `@dataclass(frozen=True)` with `nodes: tuple[EvidenceNode, ...]` and `edges: tuple[EvidenceEdge, ...]`. Sorted by `node_id`. Edges typed by `EvidenceEdgeKind` enum (CONTRADICTS, REPLICATES, SUPERSEDES, RETRACTS, NARROWS_SCOPE, SUPPORTS, DERIVES_FROM). `build_evidence_graph_by_run()` constructs nodes (CHECKPOINT, EXPERIMENT, CLAIM, EVIDENCE) + edges from orchestrator outputs. `merge()` is idempotent on node_id/edge sig. `save(path)` / `load(path)` JSON persistence. Hash-checked on load (`EVIDENCE_GRAPH_HASH_MISMATCH` exception). Phase 8 added `load`/`save`/`merge` for accumulation.

### 10.2 Best-in-class alternatives

| System | Strength | Weakness | Citations / Adoption |
|---|---|---|---|
| **Neo4j** | Industry-standard graph DB; Cypher query language; property graph model; ACID; scales horizontally with cluster; GraphRAG plugin | Ops burden; JVM; license (Community vs Enterprise) | Atlan 2026 ("Neo4j GraphRAG vs LlamaIndex vs LangChain"); LangChain blog 2024 ("Enhancing RAG with Neo4j"); Neo4j.com 2024 (multiple GraphRAG tutorials); Memgraph 2025 (improved KG creation) |
| **RDF / SPARQL** | W3C standard graph model; semantic web; reasoning built-in; portable across stores (Stardog, GraphDB, Blazegraph) | Steeper learning curve; less LLM ecosystem | Reddit r/KnowledgeGraph 2024 (RDF → Neo4j migration discussion) |
| **LlamaIndex** | Python framework for graph-RAG; builds knowledge graphs from documents; supports Neo4j + vector stores | Retrieval-focused, not durable storage | Atlan 2026; Memgraph 2025; Neo4j 2024 |
| **LangChain GraphRAG** | Same as LlamaIndex; tight integration with LangGraph | Tied to LangChain ecosystem | LangChain blog 2024; Neo4j 2024 |
| **Microsoft GraphRAG** | Reference architecture for graph-based RAG over large corpora | Research-grade; not production-hardened | Referenced as MetaEngine engine_06 |

**Industry consensus (Atlan 2026):** "Neo4j GraphRAG is better when you need a durable, queryable graph database with Cypher access and long-term vendor support. LlamaIndex is better for [rapid retrieval-focused development]." **Neo4j + LlamaIndex** is the dominant production pattern.

### 10.3 Key Gap

1. **In-memory tuple.** `EvidenceGraph` is a Python dataclass. The full graph is held in memory. For accumulated runs over thousands of experiments, this becomes GBs.
2. **No indexing.** Lookups are `next(n for n in nodes if n.node_id == ...)`. O(N) per lookup. Neo4j indexes node IDs.
3. **No query language.** "Find all CLAIM nodes that CONTRADICT this one, within 2 hops" requires manual traversal. Cypher does this in one line.
4. **No vector retrieval.** Each `EvidenceNode.description` is a string. Cannot do similarity search ("find similar claims"). LlamaIndex + Neo4j vector index does this.
5. **Merge is O(N+M) per call.** Each `add_node` / `add_edge` rebuilds the entire tuple. For frequent incremental merges, this is quadratic.
6. **No transactions.** If a process crashes during `merge()`, you can have a half-merged graph. Neo4j is ACID.
7. **No schema migration.** Adding a new node kind or edge kind requires code changes. Neo4j is schema-free for additions.
8. **Hash check is brittle.** `from_dict` raises on hash mismatch. If any node's `description` changes, the whole graph fails to load. No partial-load or version-migration path.

### 10.4 Replacement Difficulty: **Medium**

- The 6 edge kinds + 5 node kinds are a clean schema that maps directly to Neo4j labels/relationships
- `build_evidence_graph_by_run()` is the only producer; replacing the storage backend doesn't require touching the producer logic
- `merge()` becomes a Cypher `MERGE` query
- Constraint: `EVIDENCE_GRAPH_ACCUMULATES_KNOWLEDGE_NOT_TRUTH` claim ceiling is preserved by all alternatives (it's just storage)
- LlamaIndex integration adds value (vector retrieval) without replacing Neo4j

### 10.5 Priority: **P1**

The evidence graph is the project's *long-term memory*. As runs accumulate, the in-memory tuple approach will not scale. The hash-check brittleness is a live data-loss risk. P1 because today it works (small N), but every run grows it.

### 10.6 Recommended Migration Path

1. **Phase A (3 days):** Add a `Neo4jEvidenceGraph` backend that implements the same `add_node` / `add_edge` / `merge` / `load` / `save` API. Use the `neo4j` Python driver. Map `EvidenceNode.node_kind` to Neo4j labels, `EvidenceEdge.kind` to relationship types.
2. **Phase B (2 days):** Migrate `build_evidence_graph_by_run()` to write directly to Neo4j. Keep the in-memory variant for tests / single-run exports.
3. **Phase C (2 days):** Add Cypher queries for the most common operations: `find_contradictions(claim_id)`, `find_replications(experiment_id)`, `find_lineage(claim_id, depth)`.
4. **Phase D (3 days, optional):** Add LlamaIndex integration. Index `EvidenceNode.description` as vector embeddings. Enable semantic-similarity queries over the graph.
5. **Phase E (1 day):** Preserve the hash-check as an *export-time* invariant (when writing to JSON for external consumers), not a *load-time* invariant (when restoring from Neo4j). This fixes the brittleness.

---

## Cross-Cutting Findings

### A. The 5 most critical gaps (priority-ordered)

1. **Orchestrator is not durable** (P0). Single-process, single-class, 822-LOC `run()` method with 34 try/except blocks. A crash loses everything. **Industry standard: LangGraph + Temporal**. Difficulty: Hard. Estimated effort: 5 weeks.

2. **L0 surrogate is heuristic, not fitted** (P0). "Online surrogate" claim is misleading — the L0 score is a hand-coded weighted sum, not a GP trained on observed (theta, fitness) pairs. No acquisition function. L2 budget is spent reactively, not proactively. **Industry standard: BoTorch**. Difficulty: Hard. Estimated effort: 2 weeks.

3. **Multi-Model Router is hardcoded to localhost** (P0). `create_default_router()` registers both backends to `http://localhost:3031`. No provider abstraction, no virtual keys, no budget enforcement, no streaming. **Industry standard: LiteLLM** (100+ providers). Difficulty: Easy. Estimated effort: 5 days.

4. **Constitution has no runtime rails** (P1). 12 K0 invariants are load-time-validated, not runtime-enforced. No input/output/dialog rails. No harmlessness scoring. The constitution is documentation, not guardrails. **Industry standard: NeMo Guardrails** for runtime; Anthropic CAI for training (training intentionally NOT adopted — `NO_NORMAL_KERNEL_SELF_MUTATION`). Difficulty: Hard. Estimated effort: 4 weeks for runtime rails; full CAI explicitly declined.

5. **Evidence graph doesn't scale** (P1). In-memory tuple of dataclasses. O(N) lookups. No indexing, no query language, no vector retrieval. Hash-check is brittle (one changed description fails the whole load). **Industry standard: Neo4j + LlamaIndex**. Difficulty: Medium. Estimated effort: 2 weeks.

### B. The 5 most easily-remedied gaps (effort-ordered, all Easy)

1. **Event Publisher** (P2, Easy, 1 day): Replace custom JSONL+WebSocket with `structlog` + `sse-starlette`. Same JSON output, no module-level singleton, native SSE reconnect.
2. **Multi-Model Router** (P0, Easy, 5 days): Adopt LiteLLM. Same `call() → RoutedResult` interface; config-driven backend list.
3. **State Bus thread safety** (P1, Easy, 2 days): Add a `Lock` to `TrainingStateBus.publish_*` methods. Independent of any Redis migration.
4. **Evidence Graph hash-check brittleness** (P1, Easy, 1 day): Demote hash-mismatch from `raise ValueError` to a logged warning. Critical for incremental migration.
5. **Dialectical Graph operator LLM-ification** (P2, Medium, 1 week): Replace hardcoded literal/resistant RIVAL_FORK templates with two LLM calls using different system prompts. Highest-leverage single-module change for output quality.

### C. Where MetaEngine is *already* best-in-class

1. **Constitution discipline (claim_ceiling invariant).** Every module's `payload()` emits `truth_effect: "NONE"` and a `claim_ceiling` string. No module promotes derived content to truth. This is **stricter than any of the alternatives surveyed** (LiteLLM, LangGraph, BoTorch, NeMo Guardrails — none have a uniform "derived output is not truth" invariant).
2. **Provenance preservation.** Every artifact carries `canonical_hash`, source spans (`source_id, start, end, text_hash`), and mutation receipts (`MUTATION_REQUIRES_RECEIPT`). Neo4j + LlamaIndex don't provide this by default; you'd build it on top.
3. **Honest implementation disclosure.** `config/meta_engine.json` explicitly states 12 of 16 engines are clean-room reference simulations. No surveyed alternative does this — they all conflate "we have a LangGraph adapter" with "we run LangGraph".
4. **Amendment boundary design.** `NO_NORMAL_KERNEL_SELF_MUTATION` + `authority_status="NOT_IMPLEMENTED"` is a deliberate safety choice. Anthropic CAI assumes the opposite (continuous principle learning). MetaEngine's choice is defensible and should be preserved.
5. **Receipt-style state machines.** `mechanism_library.py` (A0→A1→A2→A3) with evidence-gated admission + hash re-verification on `from_dict` is the **model module** (per Groups E and F analysis). No surveyed alternative has this discipline built in.

### D. Where MetaEngine should NOT follow the industry

1. **Do not adopt Anthropic CAI training-time fine-tuning.** It violates `NO_NORMAL_KERNEL_SELF_MUTATION`. Adopt NeMo runtime rails instead (Phase A of §8.6).
2. **Do not collapse the 16 engines to 4.** The architectural diversity is a research asset, not a bug. Add a learned top-k router (Phase A of §9.6) instead.
3. **Do not replace the constitution JSON with mutable principles.** The frozen K0 invariant set is the safety anchor. Add runtime rails on top; do not make the principles learnable.
4. **Do not adopt LangGraph alone without Temporal.** LangGraph's checkpointer is not durable execution (Diagrid 2026, Temporal 2026). Adopt both, or neither.
5. **Do not throw away the dialectical operators.** The 10-operator inventory (SOURCE_READING through OPERATOR_MUTATION) is rich *conceptual structure* even if the implementation is template-string. LLM-ify the operators; don't replace them with generic ToT/GoT.

---

## Recommended Next Steps (Sequenced)

### Immediate (Week 1) — fixes that ship value in <5 days each

| # | Action | Effort | Priority | Unlocks |
|---|--------|--------|----------|---------|
| 1 | Adopt LiteLLM in `multi_model_router.py` | 5 days | P0 | Real multi-provider failover, cost tracking, observability |
| 2 | Fix `state_bus.py` thread safety (add Lock) | 2 days | P1 | Removes a live correctness bug; prerequisite for any parallel training |
| 3 | Demote `EVIDENCE_GRAPH_HASH_MISMATCH` from raise to warning | 1 day | P1 | Allows incremental schema evolution; prerequisite for Neo4j migration |
| 4 | Replace `event_publisher.py` with structlog + sse-starlette | 1 day | P2 | Removes module-level singleton; native SSE reconnect; observability hooks |

### Near-term (Weeks 2–6) — the three P0 architectural changes

| # | Action | Effort | Priority | Unlocks |
|---|--------|--------|----------|---------|
| 5 | Wrap BoTorch as the L0 surrogate behind `ThreeTierFitnessAdapter` | 2 weeks | P0 | Real fitted surrogate, q-EI acquisition, principled exploration-exploitation |
| 6 | Migrate `evidence_graph.py` to Neo4j backend | 2 weeks | P1 | Scales to millions of nodes, Cypher queries, vector retrieval |
| 7 | Decompose `orchestrator.py` into LangGraph + Temporal | 5 weeks | P0 | Durable execution, crash recovery, conditional routing, human-in-the-loop gates |

### Medium-term (Weeks 7–14) — the four P1 architectural changes

| # | Action | Effort | Priority | Unlocks |
|---|--------|--------|----------|---------|
| 8 | Add NeMo-style runtime rails to `MultiModelRouter.call()` | 4 weeks | P1 | Runtime constitution enforcement (currently load-time only) |
| 9 | Replace 7 amplify rules with DSPy teleprompter (BootstrapFewShot → MIPROv2) | 5 weeks | P1 | Real prompt optimization loop; closes the IDA flywheel |
| 10 | Train learned top-k engine router; replace rule-based `CapabilityRouter` | 4 weeks | P1 | Only 4–6 engines fire per input (vs 16); cost reduction + specialization |
| 11 | LLM-ify `dialectical_graph.py` operators (RIVAL_FORK + SUBLATION first) | 2 weeks | P2 | Real multi-perspective reasoning instead of template strings |

### Long-term (deferred / optional)

| # | Action | Effort | Priority | Notes |
|---|--------|--------|----------|-------|
| 12 | Migrate `state_bus.py` to Redis (or NATS JetStream for durability) | 2 weeks | P1 | Only needed for multi-process scaling |
| 13 | Promote 1–2 reference engines (LangGraph, DSPy) to real LLM_MODEL executors | 2 weeks | P2 | Engine_12 + engine_16 are highest-value candidates |
| 14 | Add OpenTelemetry tracing to event_publisher + state_bus | 1 week | P2 | Production observability; only if multi-instance deployment planned |
| 15 | Multi-Agent Debate loop inside dialectical_graph | 2 weeks | P2 | Only after RIVAL_FORK is LLM-ified (step 11) |

### Total estimated effort

- **Immediate (Week 1):** 9 dev-days (4 fixes)
- **Near-term (Weeks 2–6):** 9 dev-weeks (3 architectural migrations)
- **Medium-term (Weeks 7–14):** 15 dev-weeks (4 architectural migrations)
- **Long-term (deferred):** 7 dev-weeks (4 optional enhancements)
- **Grand total:** ~31 dev-weeks (~7.2 dev-months) for the full roadmap

---

## Sources

### Multi-agent frameworks
- CrewAI vs LangGraph vs AutoGen (2026 Comparison) — https://pickaxe.co/post/crewai-vs-langgraph-vs-autogen
- Comprehensive comparison of every AI agent framework in 2026 — Reddit r/LangChain — https://www.reddit.com/r/LangChain/comments/1rnc2u9
- First-hand comparison of LangGraph, CrewAI and AutoGen — https://aaronyuqi.medium.com/first-hand-comparison-of-langgraph-crewai-and-autogen-30026e60b563
- AI Agent Frameworks Compared — https://www.developersdigest.tech/guides/ai-agent-frameworks-compared
- Comparing AI agent frameworks (CrewAI, LangGraph, BeeAI) — IBM Developer — https://developer.ibm.com/articles/awb-comparing-ai-agent-frameworks-crewai-langgraph-and-beeai
- MetaGPT GitHub — https://github.com/FoundationAgents/MetaGPT
- MetaGPT IBM — https://www.ibm.com/topics/metagpt
- MetaGPT arXiv — https://arxiv.org/abs/2308.00352
- Why Checkpoints Aren't Durable Execution: LangGraph — Diagrid — https://www.diagrid.io/blog/durable-execution-langgraph
- Temporal's LangGraph Plugin adds Durable Execution — https://temporal.io/blog/temporal-langgraph-plugin
- LangGraph in Production: Latency, Replay, and Scale — Aerospike — https://aerospike.com/blog/langgraph-in-production

### Surrogate-assisted optimization
- BoTorch Introduction — https://botorch.org/docs/v0.17.0/introduction
- BoTorch Acquisition Functions — https://botorch.org/docs/acquisition
- BoTorch Batching (q-EI) — https://botorch.org/docs/batching
- Thompson Sampling (BoTorch) — https://botorch.readthedocs.io/en/stable/acquisition.html
- Navigating the maze of hyperparameter optimization — Balazs Kegl (Medium) — https://balazskegl.medium.com/navigating-the-maze-of-hyperparameter-optimization-insights-from-a-systematic-study-601967
- Ray Tune + BayesOpt — https://docs.ray.io/en/latest/tune/examples/bayesopt_example.html
- Optuna Hub (LLM + Bayesian Optimization) — https://hub.optuna.org
- Batched Bayesian Optimization (Fromer et al. 2025, Pubs ACS) — https://pubs.acs.org/doi/10.1021/acs.jcim.4c01471

### Self-improvement
- STaR: Bootstrapping Reasoning (Zelikman et al. 2022) — https://arxiv.org/abs/2203.14465
- Self-Taught Reasoner (STaR) topic page — https://www.emergentmind.com/topics/self-taught-reasoner-star
- Self-Rewarding Language Models — https://ghost.oxen.ai/arxiv-dives-self-rewarding-language-models
- Learning to Self-Improve & Reason with LLMs (Meta-Rewarding) — Berkeley — https://rdi.berkeley.edu/adv-llm-agents/slides/Jason-Weston-Reasoning-Alignment-Berkeley-Talk.pdf
- Self-Improving AI: What Actually Works in 2026 — Morphllm — https://www.morphllm.com/self-improving-ai
- DSPy GEPA optimization — https://dspy.ai/learn/optimization/optimizers overview/
- DSPy MIPROv2 — https://dspy.ai/learn/mipro/mipro_optimizer/
- Comparative Study of DSPy Teleprompter Algorithms — https://arxiv.org/abs/2412.14905
- Beyond Prompt Hacking: How DSPy + MIPRO Brings Real Optimization — Medium
- Your LM Deserves Better Prompting — Weaviate — https://weaviate.io/blog/dspy-teleprompter

### LLM gateways
- LiteLLM vs Portkey vs OpenRouter vs Requesty — https://www.requesty.ai/blog/litellm-vs-portkey-vs-openrouter-best-llm-gateway-2026
- LiteLLM vs OpenRouter — TrueFoundry — https://www.truefoundry.com/blog/litellm-vs-openrouter
- Best LLM Gateway: 7 AI Gateways Compared — Layer3Labs — https://www.layer3labs.io/guides/best-llm-gateway
- Portkey vs LiteLLM vs OpenRouter: LLM Gateway 2026 — PkgPulse — https://www.pkgpulse.com/guides/portkey-vs-litellm-vs-openrouter-llm-gateway-2026
- LiteLLM Alternatives 2026 — Qveris — https://qveris.ai/guides/litellm-alternative-comparison
- LiteLLM Getting Started — https://docs.litellm.ai/docs/getting_started
- BerriAI/litellm GitHub — https://github.com/BerriAI/litellm

### State sharing
- Temporal: Beyond State Machines — https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications
- NATS JetStream for AI Agent Workflows — LinkedIn — https://www.linkedin.com/posts/epuerta9_github-cloudshipaistation-station-is-activity-7410347845964349440
- Why NATS — Synadia — https://www.synadia.com/blog/why-nats
- How to Use Redis with Temporal for Workflow State — OneUptime — https://oneuptime.com/blog/post/2026-03-31-redis-temporal-workflow-state/view
- From Celery/Redis to Temporal — Dev.to — https://dev.to/wintrover/from-celeryredis-to-temporal-a-journey-toward-idempotency-and-reliable-workflows-k1i

### Event publishing
- Leveling Up Your Python Logs with Structlog — Dash0 — https://www.dash0.com/guides/python-logging-with-structlog
- structlog Standard Library Logging — https://www.structlog.org/en/stable/standard-library.html
- sse-starlette — GitHub — https://github.com/sysid/sse-starlette
- StreamingResponse vs EventSourceResponse — StackOverflow — https://stackoverflow.com/questions/77926208
- 7 Python Logging Pipelines (structlog + OTel) — Medium — https://medium.com/@npavfan2facts/7-python-logging-pipelines-structlog-otel-without-overhead-5f009fd7c4fe
- Spent a bunch of time choosing between Loguru, Structlog — Reddit r/Python — https://www.reddit.com/r/Python/comments/1p6qy1e

### Multi-perspective reasoning
- Demystifying Chains, Trees, and Graphs of Thoughts — arXiv — https://arxiv.org/html/2401.14295v3
- Graph of Thoughts (GoT) Framework — EmergentMind — https://www.emergentmind.com/topics/graph-of-thoughts-got
- Chain-of-Thought vs Tree-of-Thought vs Graph-of-Thought — TowardsAI — https://pub.towardsai.net/chain-of-thought-vs-tree-of-thought-vs-graph-of-thought-reasoning-method-comparison-1f19d238a0
- What is Tree Of Thoughts Prompting? — IBM — https://www.ibm.com/think/topics/tree-of-thoughts
- Tree of Thoughts — Kargarisaac (Medium) — https://kargarisaac.medium.com/paper-explained-tree-of-thoughts
- Improving Factuality and Reasoning through Multiagent Debate (Du et al. 2023) — https://arxiv.org/abs/2305.14325
- Should we be going MAD? A Look at Multi-Agent Debate — Smit 2024 — https://arxiv.org/abs/2402.11896
- Knowledge-enhanced reasoning in multi-agent debate (Wang et al. 2025) — ScienceDirect

### Constitutional AI / guardrails
- Constitutional AI: Harmlessness from AI Feedback (Bai et al. 2022) — https://arxiv.org/abs/2212.08073
- Anthropic blog — https://www.anthropic.com/research/constitutional-ai
- Constitutional AI: How Anthropic Trains Models Using Principles — TDWI — https://tdwi.org/2026/01/13/constitutional-ai
- What is Constitutional AI (CAI)? — Zilliz — https://zilliz.com/learn/what-is-constitutional-ai
- NeMo Guardrails GitHub — https://github.com/NVIDIA/NeMo-Guardrails
- NeMo Guardrail Types — NVIDIA Docs — https://docs.nvidia.com/nemo/guardrails
- NeMo Guardrails Tutorial — Qaskills — https://qaskills.sh/nemo-guardrails-tutorial
- NeMo Guardrails Rebedea et al. 2023 — https://arxiv.org/abs/2310.10501
- Guardrails AI + NeMo Guardrails — https://guardrailsai.com/blog/nemoguardrails-integration
- 5 Best AI Guardrails Platforms (Galileo) — https://galileo.ai/blog/best-ai-guardrails-platforms
- A Survey on LLM Guardrails (Bud Ecosystem) — https://budecosystem.com/a-survey-on-llm-guardrails-methods-best-practices-and-optimisations

### Mixture-of-Experts
- A Visual Guide to Mixture of Experts — Maarten Grootendorst — https://newsletter.maartengrootendorst.com/p/a-visual-guide-to-mixture-of-experts
- Applying MoE in LLM Architectures — NVIDIA Developer — https://developer.nvidia.com/blog/applying-mixture-of-experts-in-llm-architectures
- MoE LLMs — Cameron Wolfe — https://cameronrwolfe.substack.com/p/moe-llms
- Mixture of Experts in Large Language Models (Survey) — arXiv — https://arxiv.org/html/2507.11181v2
- Beyond Dense Models: Complete Guide to MoE — Medium — https://medium.com/@SuriNaren/beyond-dense-models-the-complete-guide-to-mixture-of-experts-moe-architecture-d767c8a4ef0f

### Evidence graph / RAG
- Neo4j GraphRAG vs LlamaIndex vs LangChain — Atlan — https://atlan.com/know/ai-agent/knowledge-graph/neo4j-graphrag-vs-llamaindex-vs-langchain
- Enhancing RAG-based application accuracy by constructing knowledge graphs — LangChain — https://www.langchain.com/blog/enhancing-rag
- Knowledge graph-based agent with Llama 3.1 — Neo4j — https://neo4j.com/blog/developer/knowledge-graph-llama-nvidia-langchain
- Improved Knowledge Graph Creation with LangChain and LlamaIndex — Memgraph — https://memgraph.com/blog/improved-knowledge-graph-creation-langchain-llamaindex
- Any alternatives to LangChain for LLMs/GraphRAG — Reddit r/KnowledgeGraph — https://www.reddit.com/r/KnowledgeGraph/comments/1hcozn1

---

## Final Report

**Constitution preserved:** No source files modified, no canonical state touched, no truth effects produced. Pure read-only analysis + web research.

**Document:** `/home/z/my-project/METAENGINE_SLICE3_RESTORED/BEST_ANALOGS_COMPARISON.md` (~1,000 lines).

**Top 5 most critical gaps (in priority order):**

1. **Orchestrator is not durable** (P0, Hard, 5 weeks) — `orchestrator.py` is an 822-LOC monolith with 34 try/except blocks, no checkpoint/resume, no crash recovery. Recommend LangGraph + Temporal.

2. **L0 surrogate is heuristic, not fitted** (P0, Hard, 2 weeks) — `tiered_fitness.py`'s "online surrogate" is a hand-coded weighted sum, not a GP/NN trained on observed (theta, fitness) pairs. No acquisition function. L2 budget is reactive. Recommend BoTorch.

3. **Multi-Model Router is hardcoded to localhost:3031** (P0, Easy, 5 days) — Both default backends point to the same `z-ai-web-dev-sdk` bridge. No provider abstraction, no virtual keys, no streaming. Recommend LiteLLM.

4. **Constitution has no runtime rails** (P1, Hard, 4 weeks) — 12 K0 invariants are load-time-validated only. No input/output/dialog rails. No harmlessness scoring at inference time. Recommend NeMo Guardrails (NOT Anthropic CAI training-time, which violates `NO_NORMAL_KERNEL_SELF_MUTATION`).

5. **Evidence graph doesn't scale** (P1, Medium, 2 weeks) — In-memory tuple of dataclasses. O(N) lookups. Hash-check brittleness means any description change fails the whole load. Recommend Neo4j backend + LlamaIndex vector retrieval.

**Recommended immediate next steps (Week 1, all ≤5 dev-days each):**

1. Adopt LiteLLM in `multi_model_router.py` (5 days) — biggest single-day leverage.
2. Add `threading.Lock` to `state_bus.py` publish methods (2 days) — live correctness bug.
3. Demote `EVIDENCE_GRAPH_HASH_MISMATCH` from `raise ValueError` to logged warning (1 day) — unblocks schema evolution.
4. Replace `event_publisher.py` internals with `structlog` + `sse-starlette` (1 day) — removes global singleton, gains native SSE reconnect.

**Sequenced medium-term roadmap (Weeks 2–14):** BoTorch (Weeks 2–3) → Neo4j migration (Weeks 4–5) → LangGraph+Temporal orchestrator decomposition (Weeks 6–10) → NeMo runtime rails (Weeks 11–14) → DSPy teleprompter (Weeks 7–11, parallel) → learned top-k engine router (Weeks 12–15, parallel).

**Total effort:** ~31 dev-weeks (~7.2 dev-months) for the full roadmap; ~9 dev-days for the Week-1 quick wins that ship 80% of the operational value.

**Constitution note:** The MetaEngine design has 5 places where it should *not* follow the industry standard (see §D of cross-cutting findings). The most important: do NOT adopt Anthropic CAI training-time fine-tuning (violates `NO_NORMAL_KERNEL_SELF_MUTATION`); use NeMo runtime rails instead. Do NOT collapse 16 engines to 4; add a learned top-k router. Do NOT make the K0 invariants learnable.
