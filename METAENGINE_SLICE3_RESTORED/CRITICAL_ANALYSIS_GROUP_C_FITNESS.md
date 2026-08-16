# Critical Analysis — Group C: Fitness & Recursive Modules

**Reviewer:** Z.ai Code (sub-agent `crit-C-fitness`)
**Scope:** 8 modules, 3,594 LOC implementation + 1,928 LOC tests
**Method:** Full source read of all 8 modules + targeted test runs + dependency-graph scan

## Executive Summary

| # | Module | LOC | Test LOC | Impl (1-10) | Tests (1-10) | Verdict |
|---|---|---|---|---|---|---|
| 1 | `tiered_fitness.py` | 724 | 274 | 7 | 8 | Solid; one global-RNG bug |
| 2 | `real_recursive.py` | 493 | 187 | 6 | 5 | State-leak across runs; tests unmocked+slow |
| 3 | `amplify_distill.py` | 642 | 349 | 8 | 8 | Best of group; clean IDA + persistence |
| 4 | `pbt_fitness_wiring.py` | 142 | 220 | 7 | 8 | Thin, correct; reaches into private attrs |
| 5 | `real_fitness.py` | 442 | 313 | 5 | 7 | **Critical bug**: orchestrator ignores theta |
| 6 | `event_publisher.py` | 187 | **0** | 6 | 0 | **No tests**; singleton root-resolution bug |
| 7 | `state_bus.py` | 374 | 263 | 7 | 8 | **Not thread-safe** despite "shared bus" role |
| 8 | `multi_model_router.py` | 590 | 322 | 8 | 8 | Best-in-class router; minor cost-aware quirks |
| **Avg** | — | 449 | 241 | **6.75** | **6.5** | — |

Total: 8 modules / 3,594 impl LOC / 1,928 test LOC / test-to-impl ratio 0.54

---

## Per-Module Analysis

### 1. `tiered_fitness.py` (724 LOC, 274 test LOC)

**Purpose.** 3-tier fitness adapter (L0 surrogate → L1 constitution → L2 real-LLM) for PBT/ES. Surrogate learns an online linear residual correction from L2 observations (I5). UCB1 acquisition (R5.2) selects under-explored thetas for L2. PER-style prioritized replay (R6.4). 12-task L2 bank with execution verification (R3.3) and corrected scoring formula (R2.1).

**Quality: 7/10.** Architecture is principled (cites Wu 2021, Yu 2024). Surrogate/UCB/PER are real research-grade mechanisms. Result hashing via `canonical_hash` is consistent. Blending weights (0.2·L0 + 0.3·L1 + 0.5·L2) are documented and deterministic.

**Coverage: 8/10.** 274 LOC tests exercise L0/L1/L2 paths, caching, budget enforcement, mock L2 (correct/wrong/error), determinism, constitution invariants. Tests pass in ~5s.

**Connectivity.** Imports `canonical_hash` from `.util`; consumed by `pbt_fitness_wiring`, `real_recursive`; optional `router` param accepts `MultiModelRouter`; publishes `fitness.evaluated` and `fitness.l2_fallback` events via `event_publisher`.

**Weak spots — specific bugs:**

1. **Global RNG pollution (line 131-132).** `deterministic_l2=True` calls `random.seed(42)` — this is the *process-global* RNG, affecting every other module that uses `random`. Two adapter instances, or any other code using `random`, breaks the "deterministic L2 task selection" contract. Should use `random.Random(42)` instance attribute.
2. **Unbounded `effective_l1_threshold` (line 594).** `effective_l1_threshold = self.l1_threshold - ucb_bonus - mae_adjustment` is not clamped to `[0,1]`. With default `ucb_exploration=0.3` and few evals, `ucb_bonus ≈ 0.35`, `mae_adjustment` up to `+0.1`, so threshold can go *negative* → L2 fires whenever budget is available, defeating the L1 gate.
3. **Frozen-dataclass mutation hack (lines 666-667).** `TieredFitnessResult(**{**result.__dict__, "result_hash": h})` — relies on `__dict__` existing on a `frozen=True` dataclass (no `slots=True`). Works today but is fragile; `dataclasses.replace(result, result_hash=h)` is idiomatic.
4. **Cache eviction is FIFO, not LRU (line 670-676).** Evicts oldest by insertion order; an L2 result is as easily evicted as an L0. With `cache_size=50` and 4 PBT members × 3 generations, this is fine, but a high-value L2 result could be dropped.
5. **Diversity penalty double-counts with UCB (lines 330-338 vs 178-197).** L0 applies a `-0.01 * eval_count` penalty for re-evaluated thetas; UCB separately adds an exploration bonus. Both target the same goal (diversity) and can cancel out or over-correct.

**Recommendations.**
- Replace `random.seed(42)` with `self._rng = random.Random(42)` and `self._rng.choice(self.L2_TASKS)`.
- Clamp `effective_l1_threshold = max(0.0, min(1.0, ...))`.
- Use `dataclasses.replace()` for hash-backfill everywhere (also applies to real_recursive, amplify_distill, real_fitness).
- Consider LRU cache (e.g., `collections.OrderedDict` with move-to-end on hit).

**Replacement alternatives.** Optuna's `TPESampler` or `CMA-ES` for hyperparameter search; `botorch` for true Bayesian-Opt surrogate (Gaussian Process instead of linear residual). For L2 verification, switch to `bigcode-evaluation-harness` style ground-truth tasks.

---

### 2. `real_recursive.py` (493 LOC, 187 test LOC)

**Purpose.** Orchestrates the recursive improvement flywheel: amplify (IDA) → run PBT with tiered fitness → distill → compare. Adds reject-sampling filter (R1.1), convergence early-stop (R1.2), champion carry-forward with amplify-guided mutation (R6.2).

**Quality: 6/10.** Conceptually sound flywheel, but several real bugs compromise its premise (state loss, value conflation).

**Coverage: 5/10.** 19 tests, but every test that calls `runner.run()` makes real HTTP calls to `localhost:3031` (30s timeout each). Running the full file exceeded the 2-minute tool budget; only 4 of 19 tests completed in 30s. **No mock injection** for the bridge/router — tests assume a live LLM endpoint.

**Connectivity.** Wires `ThreeTierFitnessAdapter` + `AmplifyDistillCycle` + `PBTPopulationTrainer` + `create_default_router`. Publishes `recursive.converged` and `distill.low_confidence` events. Reads `accumulated_state.json`.

**Weak spots — specific bugs:**

1. **Adapter/router recreated per `run()` call (lines 192-209).** `MultiModelRouter` and `ThreeTierFitnessAdapter` are instantiated inside `run()`, not `__init__`. Calling `run()` twice creates fresh instances, **discarding all surrogate weights, UCB counts, and cache**. The flywheel's claim of "accumulates insights" is broken across `run()` invocations.
2. **Value conflation: `0.0` treated as missing (lines 247-251).** `acc_metrics.get('marl_foe_mean', 0.0) or (0.02 if ... else 0.05)` — Python's `or` falls through when the left operand is falsy, so a *legitimate* `0.0` measurement is replaced by a heuristic. Same pattern for `faithfulness_mean` (falls to 0.61/0.65) and `transfer_rate` (falls to 0.57/0.60). This conflates "missing" with "measured zero" and silently injects hardcoded priors the module claims to have removed (see comment line 346: "no more hardcoded 0.02 / 0.61 / 0.57").
3. **`amplification` may be undefined (line 276).** `amplified_config = amplification.amplified_config if prev_mean_fitness is not None else {}` — but `amplification` is bound inside the `if prev_mean_fitness is not None` block (line 252). Currently safe only because `prev_champions` is also empty on the first generation; fragile to refactor.
4. **`hasattr` defensive pattern hides trainer API drift (line 282, 327).** `trainer.population.members if hasattr(trainer.population, 'members') else []` — if the PBT API changes, this silently does nothing instead of failing fast.
5. **Champion extraction uses `getattr(m, 'fitness', 0.0)` (line 329).** If PBT members don't have a `fitness` attribute, all champions get fitness=0.0 and are sorted arbitrarily. No assertion that the attribute exists.

**Recommendations.**
- Move `router` and `adapter` instantiation to `__init__`; persist `self.adapter` across `run()` calls. Accept router injection for tests.
- Replace `acc_metrics.get(k, 0.0) or <fallback>` with explicit missingness check: `v = acc_metrics.get(k); v = fallback if v is None else v`.
- Inject a `mock_llm` or `probe_fn` into tests so they don't require a live bridge.

**Replacement alternatives.** Ray Tune's `PopulationBasedTraining` (RAY) for the PBT loop; `stable-baselines3` for the RL framing; `nevergrad` for the surrogate + acquisition layer.

---

### 3. `amplify_distill.py` (642 LOC, 349 test LOC)

**Purpose.** IDA cycle: amplify (7 rules → config changes) → distill (extract insights + improved trainers) → compare. N5 adds ML-based rule weighting (policy-gradient update with bounded weights). N4 adds idempotent JSON persistence of distillation history.

**Quality: 8/10.** Cleanest module in the group. Rule application is table-driven; weights are bounded `[0.1, 3.0]`; persistence is atomic via `write_json` (tmp+rename); deduplication by `distillation_hash`. Constitution compliance is enforced structurally (no `promote()`/`modify_code()` methods).

**Coverage: 8/10.** 349 LOC tests cover each of the 7 amplify rules, distill detection of improvements/decreases/convergence, persistence load/save, rule-weight updates, idempotency, determinism. Tests pass in ~5s.

**Connectivity.** Standalone; only depends on `canonical_hash, write_json, load_json` from `.util`. Consumed by `real_recursive`.

**Weak spots:**

1. **Rule thresholds fire too aggressively (line 235).** `if pbt_fitness < 0.7` — the heuristic L0 caps at ~0.85 (rarely hit), so this rule fires on essentially every generation. Combined with rule 5 (`if not es_converged`, which is always true by default), the system is constantly amplifying.
2. **Rule-weight update is unbounded in spirit (line 441-458).** Improvement is clipped to `[-0.5, 0.5]`, weight is bounded `[0.1, 3.0]`, but a rule that fires every generation will saturate at 3.0 after ~5 positive improvements (lr=0.1, +0.1/gen). No decay or regularization toward 1.0.
3. **`max_config_change` declared but never enforced (line 159).** The constructor accepts it but no `amplify()` code path checks it. Dead parameter.
4. **Integer-field rule scaling is lossy (line 307-308).** `mr_delta = (base_new_mr - old_mr) * w` then `round(mr_delta)`. For `w=0.5` and `base_new_mr - old_mr = 1`, `mr_delta = 0.5`, `round(0.5) = 0` (banker's rounding) → no change. Rule appears to fire but does nothing.
5. **`previous_metrics` semantics inconsistent.** `distill()` accepts `previous_metrics` but `run_cycle()` passes `previous_metrics` to both `amplify()` (as `previous_config`!) and `distill()` (as `previous_metrics`). Type confusion — `previous_metrics` is a metrics dict, not a config dict.

**Recommendations.**
- Enforce `max_config_change` by clamping the cumulative fractional change per generation.
- Add weight decay toward 1.0 (e.g., `new_w = 0.99 * old_w + 0.01 * 1.0 + lr * improvement`) to prevent saturation.
- Fix `run_cycle()` to pass `previous_config` (config dict) to `amplify()` and `previous_metrics` to `distill()` separately.

**Replacement alternatives.** `optuna.pruners` for rule-based termination; `hyperopt`'s `Trials` for persistence; an explicit `pipeline.Pipeline` (sklearn) for rule composition.

---

### 4. `pbt_fitness_wiring.py` (142 LOC, 220 test LOC)

**Purpose.** Thin adapter: `ArchitecturePolicy → theta dict → TieredFitnessResult → PBT-compatible dict`. Also provides ES-compatible fitness function and a default-adapter factory.

**Quality: 7/10.** Minimal and focused. The adapter is correctly read-only (no policy mutation). State-bus publishing is best-effort with `try/except` swallow.

**Coverage: 8/10.** 220 LOC tests cover reward/tier metadata, determinism, ES variant, PBT integration, constitution compliance.

**Connectivity.** Consumes `ThreeTierFitnessAdapter` + `ArchitecturePolicy`. Consumed by `real_recursive` and PBT/ES trainers.

**Weak spots:**

1. **Reaches into adapter private state (line 71-72).** `adapter._generation` and `adapter._l2_calls_this_gen` — private attributes, no public accessor. Fragile coupling; renaming either breaks this module silently.
2. **`mean_fitness=result.fitness` is misnamed (line 70).** Publishes the *last* evaluation's fitness as `mean_fitness`, not an actual mean. Subscribers reading `tiered_fitness_mean` will see a noisy last-value, not a mean.
3. **`cost` is always 1.0 (line 83).** Comment says "normalized cost (tiered adapter doesn't track cost)" — but PBT uses `cost` to compute cost-aware exploitation. Hardcoding 1.0 defeats cost-aware PBT.
4. **`temperature` extracted via `getattr` fallback (line 56).** `getattr(policy, "temperature", 0.4)` — if `ArchitecturePolicy` ever drops `temperature`, this silently uses 0.4. Should be a hard attribute access.

**Recommendations.**
- Add public `adapter.generation` and `adapter.l2_calls_this_gen` properties (or `adapter.stats()`).
- Maintain a running mean inside the adapter; expose `adapter.mean_fitness_this_gen`.
- Track per-tier cost (L0≈0.0, L1≈0.001, L2≈1.0) and return it as `cost`.

**Replacement alternatives.** None — this is the right abstraction boundary. Keep.

---

### 5. `real_fitness.py` (442 LOC, 313 test LOC)

**Purpose.** `RealFitnessFunctionFactory` — runs the full MetaOrchestrator per theta, then evaluates via RLAIF (if bridge available) or heuristic fallback. Caches per-theta, rate-limits, publishes to state bus.

**Quality: 5/10.** The architecture is sound, but **the central claim — "real fitness = real measurement" — is broken by the orchestrator override bug** (below).

**Coverage: 7/10.** 313 LOC tests exercise caching, rate limiting, bus publishing, clamping, constitution compliance. But no test verifies that varying `max_rounds` in theta *actually changes the orchestrator's behavior* — because it doesn't.

**Connectivity.** Imports `MetaOrchestrator`, `ArchitecturePolicy`, `ConstitutionalRLAIFTrainer`, `ReasoningTraceExtractor`, `SummarizerFaithfulnessTester`. Publishes via `bus.publish_rlaif`.

**Weak spots — specific bugs:**

1. **CRITICAL — Orchestrator ignores theta (lines 348-359).** `orch.run(..., experiment_policy={"max_rounds": 1, "max_deep_engines": 2, ...})` hard-codes `max_rounds=1, max_deep_engines=2`. Verified against `orchestrator.py` line 204: `max_rounds=int(experiment_policy.get('max_rounds', active_policy.max_rounds))` — the experiment_policy overrides the active_policy. The carefully constructed `policy` object (lines 326-340) with theta-derived `max_rounds`/`max_deep_engines` is passed via `architecture_policy` key but **never used for these two fields**. Fitness is effectively insensitive to two of the four theta dimensions.
2. **`enable_rlaif` inverted control (line 357).** `experiment_policy["enable_rlaif"] = use_rlaif` — but the orchestrator's RLAIF path requires the bridge; the factory's own `_rlaif_fitness` (line 212) *also* runs RLAIF independently. Double evaluation or wasted work depending on bridge state.
3. **`run_dir` cleanup race (line 344-346).** `if run_dir.exists(): shutil.rmtree(run_dir)` then `orch.run(... out_dir=run_dir ...)`. If two concurrent calls (PBT with `max_workers>1`) hit the same theta, they'll rmtree each other's runs. No lock.
4. **Rate limit blocks the call thread (line 139-145).** `time.sleep(rate_limit_delay - elapsed)` — default 2.0s. With PBT population=8 × 3 generations = 24 calls = 48s of pure sleep. Should use a token bucket or async.
5. **`FitnessResult.source` ambiguity (line 364).** `"RLAIF"` if reward is not None, else `"HEURISTIC"`. But `_rlaif_fitness` returns heuristic fitness when RLAIF fails (line 272), so `source="RLAIF"` even when RLAIF didn't actually run. Misleading.
6. **Cache stores full result including `latency` (line 129).** Re-serving a cached result returns the original latency, not 0.0 (unlike `tiered_fitness` which correctly returns `elapsed_ms=0.0` for cache hits).

**Recommendations.**
- **Fix the orchestrator override**: either remove the hard-coded `max_rounds`/`max_deep_engines` from `experiment_policy`, or pass `params["max_rounds"]`, `params["max_deep_engines"]` explicitly.
- Add a test that varies `max_rounds` and asserts the orchestrator's run output changes.
- Use a file lock (`fcntl.flock` or `filelock` lib) around `run_dir` creation.
- Track `source` separately: `source = "RLAIF" if rlaif_reward is not None else ("HEURISTIC" if use_rlaif else "HEURISTIC_NO_RLAIF")`.

**Replacement alternatives.** For real fitness evaluation, use `lm-evaluation-harness` (Eleuther) or `bigcode-evaluation-harness` — both provide standardized, reproducible benchmarks with ground-truth scoring.

---

### 6. `event_publisher.py` (187 LOC, **NO TEST FILE**)

**Purpose.** Singleton JSONL event log (`storage/events.log`) for WebSocket real-time push. Provides `publish_event`, `read_events_since`, `get_event_count`, `reset_event_log`, `publisher_state`.

**Quality: 6/10.** Simple and works, but two real bugs and zero tests.

**Coverage: 0/10.** **No `tests/test_event_publisher.py` file exists.** The module is exercised indirectly by `test_real_recursive`, `test_api_server`, etc., but no test directly asserts event ordering, dedup, byte-offset semantics, or singleton behavior.

**Connectivity.** Consumed by `tiered_fitness` (fitness.evaluated, fitness.l2_fallback), `real_recursive` (recursive.converged, distill.low_confidence), `api_server` (api.rate_limited, recursive.generation, recursive.summary). Read by `api_server` for the `/events` SSE endpoint.

**Weak spots — specific bugs:**

1. **Singleton ignores `root` changes (lines 51-69).** `_init_event_log(root)` caches `_event_log_path` on first call. Subsequent calls with a *different* `root` (e.g., tests using `tmp_path`) return the *original* path. This makes the module untestable in isolation — tests must call `reset_event_log(root=tmp_path)` *before* any other code has touched the singleton, or they'll pollute the real `storage/events.log`.
2. **`event_hash` collision risk (lines 103-107).** Hash is `canonical_hash({type, timestamp, payload})` where `timestamp` has 1-second resolution. Two identical events published in the same second get the same hash. Docstring says "dedup by event_hash is the client's responsibility" — but a server-side sequence number would be trivial and eliminate the risk.
3. **`read_events_since` loads entire file (line 134).** `log_path.read_bytes()` — O(n) memory per read. For long-running systems, `events.log` can grow unbounded. No rotation, no size cap.
4. **`default=str` silently coerces (line 108).** `json.dumps(event, default=str)` — non-serializable payloads (e.g., `Path`, `datetime`, custom objects) are silently stringified via `str()`. This hides type bugs in event payloads.
5. **No line-length cap.** A payload with a multi-MB string produces a single JSONL line. Most JSONL parsers (including `read_events_since`) buffer whole lines → OOM risk.
6. **`reset_event_log` is not atomic with respect to readers (line 165).** `log_path.write_text("")` truncates the file; concurrent `read_events_since` may see a partial/empty read.

**Recommendations.**
- **Add `tests/test_event_publisher.py`** covering: publish/read round-trip, byte-offset semantics, dedup-by-hash, root-override, large-payload handling, concurrent publish (threading).
- Replace singleton with a class or context manager; pass `root` explicitly. Drop the module-level `_event_log_path`.
- Add a monotonic `event_seq: int` field (process-local counter) to eliminate hash collisions.
- Use `io.BufferedWriter` with line-buffered writes; add log rotation at e.g. 100 MB.

**Replacement alternatives.** `structlog` + `python-json-logger` for structured logging; Redis Streams or NATS JetStream for a real event bus; `watchfiles` (Rust-backed) for tailing instead of byte-offset polling.

---

### 7. `state_bus.py` (374 LOC, 263 test LOC)

**Purpose.** Shared mutable dataclass holding state from all trainers (RLAIF, PBT, AlphaZero, ES, MARL, RedTeam, Faithfulness, Traces, Transfer, TieredFitness). Provides `publish_*` / `get_*` methods, `save`/`load`, `summary`.

**Quality: 7/10.** Clean dataclass-based design; comprehensive publisher/subscriber coverage; good summary stats.

**Coverage: 8/10.** 263 LOC tests cover every publish/get pair, hash determinism, save/load, idempotency, constitution compliance.

**Connectivity.** Consumed by `real_fitness` (`publish_rlaif`), `pbt_fitness_wiring` (`publish_tiered_fitness`), and indirectly by all trainers.

**Weak spots — specific bugs:**

1. **NOT THREAD-SAFE.** `TrainingStateBus` is a mutable `@dataclass` with no lock. The docstring says "Connects all trainers via a shared state object" — PBT runs with `max_workers=4`, MARL has multiple agents, the orchestrator runs deep engines concurrently. Any concurrent `publish_*` / `get_*` pair can race (e.g., dict mutation during iteration → `RuntimeError: dictionary changed size during iteration`). This is a **design flaw**, not just a bug.
2. **`load()` is lossy (lines 304-337).** `payload()` saves `pbt_champions_count`, `alphazero_architectures_count`, `redteam_vulnerabilities_count` (counts only), but `load()` doesn't restore the actual lists. So `bus.pbt_champions` is empty after load — AlphaZero tournament would have no participants. Same for `redteam_vulnerabilities`, `transferable_mechanisms`, `marl_agent_rewards`.
3. **`publish_pbt` overwrites `pbt_champions` (line 112).** `self.pbt_champions = champions` — replaces, not appends. If two PBT trainers publish, the second overwrites the first. No merge semantics.
4. **`compute_hash` is non-comprehensive (lines 238-255).** Only includes a subset of fields (rlaif_rewards, pbt_best_fitness, es_best_fitness, marl_friend_mean, redteam_violation_rate, faithfulness_mean, transfer_rate, counts). Two bus states with different `pbt_champions` (but same count) produce the same hash. Subscribers detecting change via hash would miss champion swaps.
5. **`@dataclass` (not `frozen=True`) with mutable defaults (line 55, 60, 61, 69, 74, 78, 82, 85, 93, 94).** `field(default_factory=...)` is used correctly, so instantiation is safe — but the class is wide-open to external mutation. No `read_only()` view.
6. **`summary()["publishers"]["es"]` heuristic (line 347).** `1 if self.es_best_fitness > 0 else 0` — an ES that converged at fitness=0.0 (rare but possible) shows as "no ES publisher". Should be `1 if self.es_best_theta else 0` or a separate `es_published: bool` flag.

**Recommendations.**
- Add a `threading.RLock` and guard every `publish_*` / `get_*` / `compute_hash` / `payload` / `save` method.
- Make `load()` round-trip-lossless: serialize the full lists (with size cap if needed) or document that load is "summary-only".
- Replace `pbt_champions = champions` with append+dedup or version-stamped snapshot.
- Include all fields in `compute_hash` (or document the intentional subset).

**Replacement alternatives.** `pydantic` BaseModel for validation + `model_dump()`; Redis pub/sub for true multi-process state; `kafka` for event sourcing. For single-process, a `dataclasses.dataclass(frozen=True)` + copy-on-write is safer.

---

### 8. `multi_model_router.py` (590 LOC, 322 test LOC)

**Purpose.** Multi-backend LLM router: round-robin or cost-aware selection, automatic failover on 429/500, health tracking with cooldown, background reaper thread (N2), cost-aware routing (N3) preferring cheap backends for simple tasks.

**Quality: 8/10.** Best-in-class module. Clean separation of `ModelBackend`/`RoutedResult`/`MultiModelRouter`. Injectable `probe_fn` for testing. Daemon thread with proper stop semantics. Cost-aware routing is a real optimization.

**Coverage: 8/10.** 322 LOC tests cover add/remove, round-robin, failover on 429, all-backends-fail, health recovery, cost-aware selection, summary, constitution compliance. Tests use `mock_llm_response` fixture (HTTP mocking).

**Connectivity.** Consumed by `tiered_fitness` (optional `router` param), `real_recursive` (`create_default_router()`), `orchestrator`. Uses `urllib.request` for HTTP.

**Weak spots:**

1. **Cost-aware complex-task heuristic is inverted (line 250).** `pool = sorted(complex_tier, key=lambda b: -b.cost_score)` — for complex tasks, prefers the MOST EXPENSIVE backend. Comment says "higher cost = more capable" but this is an assumption; for cost *optimization*, complex tasks should still prefer the *cheapest capable* backend. As written, complex tasks always pick the priciest model.
2. **`avg_latency_ms` update is buggy (lines 346-349).** `backend.avg_latency_ms = (backend.avg_latency_ms * (backend.total_requests - 1) + latency_ms) / backend.total_requests` — but `total_requests` is incremented on line 345 *before* this line, so the formula divides by N but multiplies by N-1, which is correct only if the previous average was over N-1 requests. On the first request: `total_requests=1`, formula = `(0 * 0 + latency) / 1 = latency` ✓. On second: `total_requests=2`, formula = `(latency1 * 1 + latency2) / 2` ✓. OK, it's correct. Withdrawn — but the inline arithmetic is opaque; use `statistics.mean` or a deque.
3. **Round-robin counter shared across pools (line 255-256).** `self._round_robin_index` is global; when cost-aware routing switches between simple and complex pools, the same counter indexes into different-sized pools → uneven distribution. E.g., simple pool has 2 backends, complex has 3; calls alternate between pools: index 0 (simple[0]), 1 (complex[1]), 2 (simple[0]), 3 (complex[0]) — distribution skews.
4. **`health_check` hard-codes `localhost:3031` (line 502).** Not parameterized by `backends[0].endpoint`. If backends use a different host/port, `health_check` checks the wrong URL.
5. **Reaper thread keeps running after router GC (line 477-482).** Daemon thread; if `MultiModelRouter` is collected without `stop_reaper()`, the thread continues probing until process exit. No `__del__` or context manager.
6. **No request-level deduplication.** If two callers request the same prompt concurrently, both hit the backend. A response cache (keyed by prompt+model+temp) would halve LLM cost for repeated prompts.
7. **`urllib` not `requests`/`httpx`.** No connection pooling, no retry-with-backoff, no HTTP/2. For high-throughput, this is a bottleneck.

**Recommendations.**
- For complex tasks, sort by `cost_score / capability_score` (cheapest per capability unit) instead of `-cost_score`.
- Use per-pool round-robin counters (or a single counter with consistent hashing).
- Add `__enter__`/`__exit__` to support `with MultiModelRouter() as r:` and auto-stop reaper.
- Add `health_check(endpoint=...)` parameter.
- Add a `response_cache: dict[str, RoutedResult]` keyed by `(prompt, model, temperature, max_tokens)`.

**Replacement alternatives.** `litellm` (drop-in multi-provider router with 100+ backends, built-in failover, cost tracking); `openai.AsyncOpenAI` with `tenacity` for retries; `httpx` for connection pooling.

---

## Top 5 Findings (Cross-Cutting)

1. **`real_fitness.py` orchestrator override defeats theta-sensitivity (CRITICAL).** Lines 348-359 hard-code `max_rounds=1, max_deep_engines=2` in `experiment_policy`, which the orchestrator prefers over the theta-derived `ArchitecturePolicy`. Two of four theta dimensions have zero effect on fitness. Every test passes because tests only assert range/determinism, not theta-sensitivity.

2. **`real_recursive.py` discards surrogate/UCB state across `run()` calls.** Adapter + router are instantiated inside `run()`, so calling `run()` twice creates fresh state. The flywheel's "accumulates insights across runs" claim is broken at the adapter level.

3. **`event_publisher.py` has no tests and a singleton root-resolution bug.** The module-level `_event_log_path` ignores subsequent `root` arguments, making it untestable in isolation. The `default=str` JSON fallback silently coerces non-serializable payloads. Hash collisions are possible at 1-second timestamp resolution.

4. **`state_bus.py` is not thread-safe despite its "shared bus" role.** PBT runs with `max_workers=4`; concurrent `publish_*`/`get_*` calls can race. `load()` is lossy (drops `pbt_champions`, `redteam_vulnerabilities`, `transferable_mechanisms`). `compute_hash` misses field-level changes.

5. **Value conflation in `real_recursive.py`: `0.0` treated as "missing".** The `acc_metrics.get(k, 0.0) or <fallback>` pattern (lines 247-251) replaces legitimate zero measurements with hardcoded heuristics (0.02, 0.61, 0.57) — the very hardcoded values the I4 comment claims to have removed.

## Top 3 Recommendations

1. **Fix `real_fitness.py` orchestrator override (Finding #1).** Either delete `max_rounds`/`max_deep_engines` from the `experiment_policy` dict (let the orchestrator fall back to `active_policy`), or pass `params["max_rounds"]`, `params["max_deep_engines"]` explicitly. Add a regression test that varies `max_rounds ∈ {1, 4, 8}` and asserts the orchestrator's run output (e.g., biography count, trace count) changes accordingly. *Effort: 2 hours.*

2. **Move adapter/router instantiation to `RealRecursiveRunner.__init__` (Finding #2).** Persist `self.adapter` and `self.router` across `run()` calls so surrogate weights, UCB counts, and the L2 cache accumulate. Accept router injection (`router: MultiModelRouter | None = None`) for testability. *Effort: 1 hour.*

3. **Add `tests/test_event_publisher.py` and fix the singleton root bug (Finding #3).** Replace the module-level `_event_log_path` singleton with either a class (`EventPublisher(root=...)`) or a context manager. Add tests for: round-trip, byte-offset, dedup-by-hash, root-override, concurrent publish, large payload. Add a monotonic `event_seq` field to eliminate hash collisions. *Effort: 3 hours.*

## Module Dependency Graph

```
                          ┌─────────────────┐
                          │ architecture_   │
                          │     policy      │
                          └────────┬────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
   ┌─────────────────┐   ┌──────────────────┐    ┌────────────────────┐
   │  tiered_fitness │◄──┤ pbt_fitness_     │    │   real_fitness     │
   │  (L0/L1/L2,    │   │   wiring         │    │  (orchestrator+     │
   │   surrogate,UCB)│   │  (PBT↔tiered)   │    │   RLAIF eval)       │
   └────────┬────────┘   └──────────────────┘    └─────────┬──────────┘
            │                                               │
            │  router                                      │ bus
            ▼                                              ▼
   ┌─────────────────┐   ┌──────────────────┐    ┌────────────────────┐
   │ multi_model_   │   │   real_recursive │───►│     state_bus      │
   │    router      │   │  (flywheel: amp→ │    │  (shared mutable   │
   │  (failover,    │   │   PBT→distill→   │    │   state, NOT       │
   │   cost-aware)  │   │   compare)       │    │   thread-safe)     │
   └────────────────┘   └────────┬─────────┘    └────────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ amplify_distill  │
                        │ (IDA, ML rules,  │
                        │  persistence)    │
                        └──────────────────┘

   Cross-cutting: event_publisher ← (tiered_fitness, real_recursive, api_server)
```

## Test Execution Summary

| Module | Tests | Status |
|---|---|---|
| `test_tiered_fitness.py` | 33 | ✅ pass (~5s) |
| `test_amplify_distill.py` | 30 | ✅ pass (~5s) |
| `test_state_bus.py` | 25 | ✅ pass (~2s) |
| `test_multi_model_router.py` | 28 | ✅ pass (~5s) |
| `test_pbt_fitness_wiring.py` | 16 | ✅ pass (~3s) |
| `test_real_fitness.py` | 28 | ✅ pass (~5s) |
| `test_real_recursive.py` | 19 | ⚠️ slow (>30s for full file; each `runner.run()` makes real HTTP calls to `localhost:3031` with 30s timeout; no mock injection) |
| `test_event_publisher.py` | **0** | ❌ does not exist |

---

## Replacement Strategy (if greenfield)

If rebuilding Group C from scratch, the minimal viable stack would be:

- **Surrogate + acquisition**: `botorch` (Bayesian Optimization with Gaussian Processes) — replaces the linear-residual surrogate in `tiered_fitness` with a proper GP, giving calibrated uncertainty estimates.
- **PBT loop**: `ray.tune.schedulers.PopulationBasedTraining` — replaces `real_recursive`'s hand-rolled flywheel.
- **IDA cycle**: keep `amplify_distill.py`'s design but externalize rules to a `YAML` config; replace ML rule weighting with `optuna.pruners.HyperbandPruner`.
- **Router**: `litellm.Router` — drop-in multi-provider router with built-in failover, cost tracking, caching.
- **State bus**: `redis` (or `nats`) — true multi-process pub/sub with TTL, persistence, and atomic ops.
- **Event publisher**: `structlog` + `python-json-logger` for structured logs; `sse-starlette` for the WebSocket/SSE bridge; or `kafka` for a real event log.

This would shrink Group C from 3,594 LOC to ~800 LOC of glue code, with the complex logic delegated to battle-tested libraries.

---

*End of Group C critical analysis.*
