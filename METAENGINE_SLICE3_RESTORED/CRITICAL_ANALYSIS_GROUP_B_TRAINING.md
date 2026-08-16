# Critical Analysis — Group B: Training Modules

**Task ID:** crit-B-training
**Agent:** general-purpose (sub agent)
**Scope:** 12 training/optimization/judgment modules in `metaengine/` (Phases 36–51)
**Method:** Read-only analysis of every source file and its test file; ran full test suite (352 tests, all pass); mapped inbound/outbound imports; counted anti-patterns.
**Constitution:** No source files modified, no tests run for mutation, no truth effects produced.

---

## Executive Summary

| # | Module | LOC | Test LOC | # Tests | Impl | Tests | Conn | Overall |
|---|--------|-----|----------|---------|------|-------|------|---------|
| 1 | `rlaif_trainer.py` | 493 | 448 | 25 | 7 | 7 | 8 | 7.0 |
| 2 | `pbt_trainer.py` | 496 | 370 | 26 | 8 | 7 | 7 | 7.5 |
| 3 | `es_optimizer.py` | 374 | 322 | 30 | 7 | 7 | 4 | 6.5 |
| 4 | `selfplay_trainer.py` | 364 | 342 | 18 | 6 | 6 | 4 | 5.5 |
| 5 | `marl_trainer.py` | 399 | 433 | 38 | 6 | 8 | 4 | 6.0 |
| 6 | `redteam_adversary.py` | 474 | 444 | 39 | 7 | 8 | 6 | 7.0 |
| 7 | `llm_judge.py` | 383 | 294 | 30 | 5 | 6 | 4 | 5.5 |
| 8 | `faithfulness_tester.py` | 499 | 439 | 46 | 6 | 8 | 6 | 6.5 |
| 9 | `trace_extractor.py` | 473 | 426 | 37 | 7 | 7 | 6 | 7.0 |
| 10 | `cross_model_transfer_tester.py` | 349 | **0** | **0** | 6 | **0** | 5 | **4.0** |
| 11 | `parallel_campaign.py` | 293 | 366 | 33 | 7 | 7 | 4 | 6.5 |
| 12 | `recursive_loop.py` | 347 | 369 | 30 | 6 | 7 | 4 | 6.0 |

- **Total modules:** 12
- **Total source LOC:** 4,944
- **Total test LOC:** 3,911 (excluding the zero-test module)
- **Total tests:** 352 (all pass in 1.33 s)
- **Average implementation:** 6.5/10
- **Average tests:** 6.1/10 (5.6 if the zero-test module is included at face value)
- **Average connectivity:** 5.2/10
- **Average overall:** 6.2/10

**Verdict:** A coherent, well-disciplined training subsystem. Constitution discipline is uniformly excellent — every module sets `truth_effect="NONE"` and `claim_ceiling="…_IS_EVALUATIVE_NOT_TRUTH"` on every payload. Tests are broad but shallow: most cover happy-path + a few edge cases; almost none exercise the LLM bridge end-to-end. The biggest risks are (a) one module with zero tests, (b) triplicated LLM-bridge client code, and (c) two modules that bypass `MechanismLibrary.create()` validation to do state transitions.

---

## Top 5 Cross-Cutting Critical Findings

### 1. `_call_llm` + `health_check` triplicated across 3 modules (~150 LOC of duplication)

`rlaif_trainer.py` (lines 134–143, 226–246), `redteam_adversary.py` (lines 198–232), and `llm_judge.py` (lines 125–160) contain **near-verbatim copies** of the same HTTP-POST-to-LLM-bridge client code: build JSON body, set Authorization header from env var, `urllib.request.urlopen`, parse `choices[0].message.content`. The `health_check()` method on each class is also identical (`GET /health` → check `status == "ok"`). This is the largest single source of code duplication in the training subsystem.

**Impact:** Bridge URL, auth header format, timeout, and error fallback logic must be patched in 3 places. Any future change to the bridge protocol (e.g., moving to async, switching to websocket, adding retry/backoff) requires editing all 3 modules.

### 2. `cross_model_transfer_tester.py` has ZERO tests despite being wired into the orchestrator

`wc -l tests/test_cross_model_transfer_tester.py` returns "no such file". The module is 349 LOC, has 3 internal importers (`orchestrator.py`, `strict_test_factory.py`, `unified_benchmark.py`), and contains non-trivial state-advancement logic (`advance_transferable_to_a1`). It is the **only** training module without a corresponding `tests/test_*.py` file. This is the highest-risk gap in Group B — a regression in this module would not be caught by the test suite at all.

### 3. `MechanismLibrary.create()` validation bypassed in 2 modules

Both `selfplay_trainer.py:advance_mechanism_states()` (lines 250–255) and `cross_model_transfer_tester.py:advance_transferable_to_a1()` (lines 302–308) rebuild the library manually using `dataclasses.replace(candidate, status=new_state)` + `MechanismLibrary(library_version=…, candidates=sorted(…))` instead of calling `library.add_candidate()` or a state-transition API. The selfplay code even carries the comment `# Rebuild library directly (bypass create() to avoid re-validation of A1)`.

**Impact:** This is a constitution-adjacent safety gap. If `MechanismLibrary.create()` validates that A0→A1 is a permitted transition (which it should), then bypassing it means any future tightening of the transition rules will not apply to these code paths. The right fix is to add a `library.transition_state(mechanism_id, new_state, receipt)` API that validates the transition *and* records it, then call that.

### 4. RLAIF trainer directly mutates `EngineBiographyStore.data["engines"][...]`

`rlaif_trainer.py:update_biography()` (lines 343–429) reaches into `biography_store.data["engines"][engine_id]`, mutates `observations`, `mean_realized_gain`, `domains`, `last_runs`, `rlaif_meta`, and `biography_hash` in place, then calls `write_json(biography_store.path, biography_store.data)` directly. It bypasses `EngineBiographyStore.update()` entirely.

The docstring is honest about this: *"This BYPASSES the EXTERNALLY_VERIFIED gate in EngineBiographyStore.update() — but HONESTLY records the source as 'RLAIF_AI_JUDGE'"*. The constitutional logic is sound (RLAIF reward is a prior, not external verification), but the implementation is brittle: if `EngineBiographyStore` ever changes its on-disk schema or its `data` dict layout, RLAIF silently corrupts the store. The right pattern is `EngineBiographyStore.record_prior_observation(engine_id, reward, source="RLAIF_AI_JUDGE")` — a separate API for prior-only observations that the store itself validates.

### 5. Magic constants everywhere — no central config

| Constant | Where | Value |
|----------|-------|-------|
| `0.5` (default counterfactual quality) | `marl_trainer.py:221` | `team_quality * 0.9` (always-positive marginal contribution) |
| `0.5` (parse-fallback score) | `rlaif_trainer.py:274`, `llm_judge.py:194` | Hardcoded fallback on JSON parse failure |
| `0.75 / 0.50` (faithfulness thresholds) | `faithfulness_tester.py:128,129` | Hardcoded levels |
| `0.5` (violation_threshold) | `llm_judge.py:108` | Hardcoded |
| `0.6` (faithfulness_threshold) | `llm_judge.py:109` | Hardcoded |
| `0.05 / -0.05` (transfer thresholds) | `cross_model_transfer_tester.py:153,154` | Hardcoded |
| `az_mechanisms / 10.0` | `recursive_loop.py:181` | Arbitrary normalization |
| `rt_violations * 0.1` | `recursive_loop.py:180` | Arbitrary decay |
| `0.8 / 1.2` (PBT perturbation) | `pbt_trainer.py:92` | Standard PBT values, but hardcoded |
| `0.3 / 0.3 / 0.3 / 0.2` (trace scoring weights) | `trace_extractor.py:231,240,244,246` | Hardcoded heuristic weights |
| DEFAULT_SCORE_WEIGHTS dict | `recursive_loop.py:130-137` | 6 weights, sum to 1.0 |
| DEFAULT_INVARIANT_WEIGHTS dict | `rlaif_trainer.py:53-66` | 12 weights, sum to 1.0 |
| DEFAULT_WEIGHTS dict | `faithfulness_tester.py:120-125` | 4 weights, sum to 1.0 |

These should live in `metaengine/training_config.py` (a single typed dataclass), so tuning happens in one place and the constitution can audit them.

---

## Per-Module Analysis

### 1. `rlaif_trainer.py` — Constitutional RLAIF Trainer (Phase 36)

**Purpose:** LLM (via bridge) evaluates engine output against 12 K0 invariants; produces weighted reward in [0,1]; updates EngineBiography with reward as a *prior* (source `RLAIF_AI_JUDGE`, never `EXTERNAL_VERIFIER`).

**Implementation quality: 7/10**
- Clean frozen `RLAIFReward` dataclass with payload/as_dict; `evaluation_hash` computed via `canonical_hash`.
- Honest rubric construction: prompts LLM for per-invariant scores + justification, then weighted-average aggregation.
- **Weak spots:**
  - `update_biography()` reaches directly into `biography_store.data["engines"][engine_id]` and mutates 6 fields in place (lines 369–423). Bypasses `EngineBiographyStore.update()` API. Brittle to schema changes.
  - `_parse_scores()` falls back to `{inv: 0.5 for all}` on JSON parse failure (line 274) — silently produces a "median" reward with no flag, masking bridge failures as mediocre-but-valid rewards.
  - `evaluate_run_contributions()` wraps each engine in `try/except Exception` (line 482) and records `confidence=0.0, source="RLAIF_AI_JUDGE"` failures into the rewards dict — errors are silently absorbed into the data stream.
  - Hardcoded `DEFAULT_INVARIANT_WEIGHTS` (12 weights, lines 53–66) — no central config.
  - `_call_llm` and `health_check` duplicated (see cross-cutting finding #1).

**Test coverage: 7/10** — 25 tests in 448 LOC. Uses `unittest.mock.patch` for `urlopen` (4 patches). Tests cover payload, rubric construction, JSON parsing edge cases (well-formed, code-block-wrapped, malformed, clamp), biography update, and `evaluate_run_contributions`. Missing: no test for the silent-fallback case where bridge returns 500, no test for `update_biography` rolling-average correctness across multiple calls.

**Connectivity: 8/10** — 4 inbound importers: `orchestrator.py`, `real_fitness.py`, `strict_test_factory.py`, `unified_benchmark.py`. Most-integrated trainer in the group.

**Top 3 weak spots:**
1. Direct mutation of `biography_store.data` bypassing the store's API (lines 369–423).
2. Silent fallback to 0.5 on parse failure masks bridge errors as mediocre rewards.
3. `_call_llm` / `health_check` duplicated from `redteam_adversary` and `llm_judge`.

**Top 3 recommendations:**
1. Extract LLM bridge client to `metaengine/llm_bridge_client.py`; inject into trainer.
2. Replace silent 0.5 fallback with raising `RLAIFParseError` and let caller decide; or at minimum emit a structured `parse_failed=True` flag.
3. Add `EngineBiographyStore.record_prior_observation(engine_id, reward, source="RLAIF_AI_JUDGE")` API and call that instead of mutating internals.

**Replacement alternatives:** HuggingFace `trl` (specifically `RewardTrainer` + `PPOTrainer` with reward model), `OpenRLHF`, `verifiers` (will-cc/verifiers). Production RLAIF is well-trodden; this module could be replaced with ~50 LOC of glue on top of `trl`.

---

### 2. `pbt_trainer.py` — Population-Based Training Trainer (Phase 37)

**Purpose:** Standard PBT loop over `ArchitecturePolicy` instances. Initialize population → evaluate fitness → exploit (replace worst N/4 with clones of best N/4) → explore (mutate clones). Pareto frontier selects champions.

**Implementation quality: 8/10**
- Best-structured module in the group. Frozen `PopulationMember`, `PolicyMutator` with deterministic RNG seed, `Population` with `best/worst/pareto_frontier/diversity/mean_fitness`.
- Mutation produces a receipt with hash (constitution's `MUTATION_REQUIRES_RECEIPT` satisfied).
- Validation in `__init__`: `population_size >= 2`, `0 < exploit_fraction <= 0.5`.
- `run()` correctly does `evaluate_generation` once *after* the last exploit/explore step (line 427–437) so the returned population reflects final mutation.
- **Weak spots:**
  - `diversity()` is just `unique_policy_hashes / total` — a weak proxy. Real diversity (hyperparameter-space distance, behavior diversity) is not measured.
  - `exploit_and_explore()` uses `self.population.members.index(worst)` (line 377) — O(N²) for full generation, and breaks if a `PopulationMember` lacks `__eq__` (frozen dataclasses get `__eq__` so this is OK, but fragile).
  - `PolicyMutator.mutate()` does not perturb `max_rounds` below 1 (line 105: `max(1, min(8, …))`) — fine, but the same clamping is duplicated for `max_deep_engines` and `exploration_rate` (3× duplicated clamp logic).
  - Topology mutation is commented out (line 144) — `topology_id` is treated as identity. Reasonable, but the docstring promises topology search and the code doesn't deliver.

**Test coverage: 7/10** — 26 tests. Covers mutation clamping (upper + lower), determinism with seed, pareto frontier correctness, diversity, mean fitness, full `run()` loop with mock fitness. Missing: no test that exploit actually replaces worst members (only test that `exploit_and_explore()` returns a receipt with the right shape), no test for the post-last-exploit final evaluation (line 428).

**Connectivity: 7/10** — 4 inbound importers: `real_recursive.py` (production recursive loop), `strict_test_factory.py`, `unified_benchmark.py`, `test_pbt_fitness_wiring.py`. Used in production recursive path, not just benchmarks.

**Top 3 weak spots:**
1. `diversity()` is superficial (unique hashes only); two policies with the same `max_rounds` but different `dialectic_operators` count as identical.
2. `exploit_and_explore` uses `list.index(worst_member)` — relies on dataclass `__eq__`, O(N²) per generation.
3. Topology mutation is dead code (commented out at line 144).

**Top 3 recommendations:**
1. Add behavior-diversity metric (e.g., pairwise `policy.payload()` Jaccard distance).
2. Replace `members.index(worst)` with index tracking — store `(idx, member)` tuples during sort.
3. Either implement topology mutation or remove the dead code and the misleading docstring promise.

**Replacement alternatives:** Ray Tune's PBT (`ray.tune.schedulers.PopulationBasedTraining`), Optuna's TPESampler with pruning. Both are battle-tested; the local implementation exists mainly to keep tight coupling to `ArchitecturePolicy` and the constitution's `MUTATION_REQUIRES_RECEIPT` discipline.

---

### 3. `es_optimizer.py` — Evolution Strategies Hyperparameter Optimizer (Phase 39)

**Purpose:** Salimans et al 2017 antithetic-sampling ES. For each generation: sample N noise vectors, evaluate fitness at θ±ε, estimate gradient `(f+ − f−) · ε / (2σ²)`, update θ, decay σ/α.

**Implementation quality: 7/10**
- Math is correct. `_estimate_gradient` uses the proper antithetic formula (line 209: `diff * n / sigma²`).
- `HyperparameterSpec.clamp()` handles integer rounding correctly (line 51–53).
- `step()` records `improved` flag and tracks `best_theta` separately from `theta`.
- Convergence check in `summary()` (line 316–317): `max(last_3) - min(last_3) < 0.01`.
- **Weak spots:**
  - **`make_policy_fitness_fn` is a no-op wrapper** (lines 356–374). Its docstring says "The base function should handle creating a policy from these [theta values]" — but the wrapper just calls `base_policy_fitness_fn(theta)` with no policy construction. Either remove it or actually construct an `ArchitecturePolicy` from `theta`.
  - `step()` evaluates `fitness_fn(new_theta)` once *more* after the gradient update (line 242) — this is correct for tracking improvement, but doubles the fitness-function calls per generation (N antithetic pairs + 1 final eval = `2N+1` evals/gen). Not documented.
  - Convergence criterion (`max - min < 0.01` in last 3 gens) is naive — it triggers if fitness plateaus even at a bad local optimum.
  - `best_fitness` only updates on strict improvement (`>`, line 245) — ties keep the older theta, which may or may not be desired.

**Test coverage: 7/10** — 30 tests. Covers spec clamping (within, below, above, integer), state payload, optimizer initialization, validation, noise sampling, perturbation (clamp + antithetic symmetry), step records, generation increment. Missing: no test for `best_theta` tracking across multiple steps, no test for the `make_policy_fitness_fn` wrapper (because it does nothing, there's nothing to test), no test for `summary()` convergence detection.

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`). Less integrated than PBT.

**Top 3 weak spots:**
1. `make_policy_fitness_fn` is dead code (no-op wrapper).
2. Convergence criterion stops at the first plateau, even if it's a local minimum.
3. `best_theta` tracking on strict `>` loses ties.

**Top 3 recommendations:**
1. Either delete `make_policy_fitness_fn` or actually construct `ArchitecturePolicy` from theta and call the base fn.
2. Replace convergence check with a relative-improvement-over-K-generations criterion.
3. Document the `2N+1` evaluation count per generation in the module docstring.

**Replacement alternatives:** `FlatES` (Google Brain, github.com/google/brainexecutor), Ray Tune's `HyperbandSearchAlgorithm` with ES-style sampling. For a pure hyperparameter sweep, Optuna's `CmaEsSampler` is more mature.

---

### 4. `selfplay_trainer.py` — AlphaZero Self-Play Architecture Trainer (Phase 38)

**Purpose:** AlphaZero-style architecture search loop: tournament → extract winning mechanisms → synthesize new architectures → ablate losers → advance mechanism states A0→A1. Does NOT advance A1→A2 (requires AssimilationGate) or A2→A3 (requires external authority).

**Implementation quality: 6/10**
- Clean separation: `run_tournament`, `extract_winning_mechanisms`, `synthesize_architectures`, `ablate_losing_mechanisms`, `advance_mechanism_states`, `run_generation`.
- `MechanismCandidate.create()` is called with proper constitution metadata (`source_fact_boundary="TOURNAMENT_PARETO_FRONTIER"`, `claim_ceiling`, `status=A0_OBSERVED`).
- **Weak spots:**
  - **`advance_mechanism_states` bypasses `MechanismLibrary.create()`** (lines 250–255). Comment is honest: `# Rebuild library directly (bypass create() to avoid re-validation of A1)`. This means A0→A1 transition validation is skipped. If the library ever enforces "A0 must be observed before A1" (which it should), this code path won't enforce it.
  - `ablate_losing_mechanisms` only *identifies* dominated mechanisms (returns list of IDs) — does not actually retire them. Method name is misleading; should be `identify_losing_mechanisms`.
  - `extract_winning_mechanisms` creates mechanism IDs as `f"mech.{winner.policy_id}.{winner.metrics['quality']:.2f}"` — collision-prone if two winners have the same rounded quality.
  - `import dataclasses` is inline (line 244) instead of at module top.
- 18 tests vs 30+ for peers — test density is low.

**Test coverage: 6/10** — 18 tests. Covers initialization, tournament, extraction, synthesis, ablation identification, A0→A1 advancement, no-A2/no-A3 promotion, full generation loop, summary, mechanism library accumulation, hash determinism. Missing: no test for the A0→A1 bypass-via-dataclasses.replace path explicitly, no test for the mechanism-ID collision case.

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`). Less integrated than expected for a "core" architecture-search module.

**Top 3 weak spots:**
1. `MechanismLibrary.create()` validation bypassed (lines 250–255) — see cross-cutting finding #3.
2. `ablate_losing_mechanisms` is misnamed — it identifies, not ablates.
3. Mechanism-ID collision risk when multiple winners share a rounded quality value.

**Top 3 recommendations:**
1. Add `MechanismLibrary.transition_state(mechanism_id, new_state, receipt)` API; call it from `advance_mechanism_states` and `advance_transferable_to_a1`.
2. Rename `ablate_losing_mechanisms` → `identify_losing_mechanisms` (or actually retire them).
3. Make mechanism IDs collision-resistant (include `canonical_hash(winner.payload())[:8]`).

**Replacement alternatives:** No drop-in alternative — AlphaZero-style architecture search is research-specific. The closest general framework is `naszilla` (Neural Architecture Search benchmarks), but it doesn't integrate with the constitution/MechanismLibrary model.

---

### 5. `marl_trainer.py` — MARL Friend-or-Foe Trainer (Phase 40)

**Purpose:** Multi-Agent RL with friend-or-foe bias. 16 engines = 16 agents. FRIEND = engines 01–04 (native, cooperative). FOE = engines 05–16 (reference, competitive). Reward = weighted combination of team/individual/marginal/friend-foe components.

**Implementation quality: 6/10**
- Clean `AgentState`, `EpisodeResult`, `MARLTrainer` separation. Reward weights validated in `__init__` (sum to 1.0 ± 0.1).
- Friend-or-foe bias logic is documented and consistent with Ryu et al 2021.
- **Weak spots:**
  - **Counterfactual default is `team_quality * 0.9`** (line 221) — a magic constant that gives *every* agent a positive marginal contribution by default, which is methodologically wrong. Counterfactual quality should be the *team quality without that agent*, which requires actually re-running the task without the agent (or at minimum, a documented heuristic).
  - `FRIEND_ENGINES = {"engine_01", "engine_02", "engine_03", "engine_04"}` (line 42) is hardcoded — should come from a `EngineRegistry` or the constitution.
  - Friend bias = `foe_mean_quality * 0.5` (line 289) — friends get credit for foes' quality even if the foe's quality is unrelated to the friend's action. Methodologically loose.
  - Foe bias only fires if `individual_reward > friend_mean_quality` (line 292) — binary threshold, not graded.
  - `run_episode` calls `quality_fn` once per agent per episode (line 209) — if `quality_fn` is expensive (LLM call), this is N bridge calls per episode, but the result is not memoized.

**Test coverage: 8/10** — 38 tests (highest in group besides faithfulness). Covers classification (friend/foe/unknown), disjoint sets, agent state payload, weight validation, episode execution, team quality mean, agent updates across multiple episodes, summary. Missing: no test for the `counterfactual_fn=None` default path explicitly, no test for the magic-constant `team_quality * 0.9` value.

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`).

**Top 3 weak spots:**
1. Counterfactual default `team_quality * 0.9` always gives positive marginal contribution.
2. `FRIEND_ENGINES` / `FOE_ENGINES` hardcoded — should be configurable.
3. Friend bias credits friends for foes' quality without causal evidence.

**Top 3 recommendations:**
1. Replace counterfactual default with a documented "no-counterfactual" sentinel (e.g., `None`) that disables marginal-contribution credit rather than manufacturing a fake value.
2. Move `FRIEND_ENGINES` / `FOE_ENGINES` to a config dataclass or the constitution's engine registry.
3. Add memoization for `quality_fn` calls within a single episode (same engine+task should return same quality).

**Replacement alternatives:** RLlib's MARL algorithms (`ray[rllib]`), PettingZoo environments, MAGENT. Production MARL is well-supported; this module's value-add is the friend-or-foe bias and the constitution discipline.

---

### 6. `redteam_adversary.py` — Red Team Adversary (Phase 41)

**Purpose:** Automated red teaming. 7 attack vectors (TRUTH_PROMOTION, ABSTENTION_BYPASS, PROVENANCE_SWAP, SELF_PROMOTION, VERIFIER_MUTATION, CODE_MODIFICATION, ENCRYPTED_REASONING_INJECTION). Each attack: adversary LLM generates adversarial input → defender processes → judge evaluates violation severity.

**Implementation quality: 7/10**
- 7 attack vectors with explicit `ATTACK_TO_INVARIANT` mapping (lines 61–70) — each vector targets a specific K0 invariant.
- Phase 47 added `ENCRYPTED_REASONING_INJECTION` (lines 56, 162–170) for the Panfilov §4.2 attack class.
- `AttackResult` is frozen with payload/as_dict; attack_hash computed honestly.
- `make_keyword_judge_fn` is documented as "SIMPLIFIED judge — production should use LLM-as-judge (RLAIF)" — honest about its limits.
- **Weak spots:**
  - `_call_llm` + `health_check` duplicated (cross-cutting finding #1).
  - `make_keyword_judge_fn` keyword list (lines 408–422) is brittle — exact-phrase matching ("i verify this claim") misses paraphrases. Acceptable as a smoke test, dangerous as the only judge.
  - `make_vulnerable_defender_fn` (line 462) returns a *multi-violation* output ("definitely true", "I confirm", "modify the verifier") — useful for testing the judge, but only one violation per attack is recorded even though the output violates 3 invariants.
  - No persistence of attacks to disk — every campaign run loses its attack history unless caller saves `adversary.attacks` manually.
  - 1 bare `except Exception` in `health_check` (line 205) — swallows all errors as `False`.

**Test coverage: 8/10** — 39 tests. Covers AttackVector enum, attack-result payload, keyword judge for each vector, mock + vulnerable defenders, run_attack with mocked LLM, run_attacks with multiple vectors, summary statistics. 13 mock patches of `_call_llm`. Missing: no test for the persistence gap, no test that ENCRYPTED_REASONING_INJECTION attack prompt actually contains an encrypted-reasoning example.

**Connectivity: 6/10** — 2 inbound importers: `strict_test_factory.py`, `unified_benchmark.py`.

**Top 3 weak spots:**
1. Keyword-based judge is brittle to paraphrase (false negatives).
2. `_call_llm` / `health_check` duplicated.
3. No attack-history persistence — `adversary.attacks` is in-memory only.

**Top 3 recommendations:**
1. Default judge should be `LLMJudgeAdapter.make_red_team_judge_fn()`; keyword judge becomes the fallback.
2. Add `adversary.save_attacks(path)` / `adversary.load_attacks(path)` for persistence.
3. Extract LLM bridge client (cross-cutting finding #1).

**Replacement alternatives:** `garak` (leondz/garak — LLM vulnerability scanner, 100+ probes), `PyRIT` (Microsoft Python Risk Identification Toolkit), `promptfoo` (red-team + eval harness). `garak` is the most direct replacement; this module's value-add is constitution-targeted vectors.

---

### 7. `llm_judge.py` — LLM-as-Judge Integration (Phase 51)

**Purpose:** Adapter that produces two judge callables: red-team judge (violation severity) and faithfulness judge (summary faithfulness). Wraps the LLM bridge; parses JSON `{"score":…, "confidence":…}` responses.

**Implementation quality: 5/10** — lowest in the group.
- Two clear judge factories (`make_red_team_judge_fn`, `make_faithfulness_judge_fn`), each returning a callable matching the constitution's judge signature.
- Safe fallback on LLM error (lines 215–217, 273–275): red-team defaults to "no violation", faithfulness defaults to "faithful". Constitution-correct (fail-safe).
- **Weak spots:**
  - **`_call_llm` + `health_check` triplicated** (cross-cutting finding #1).
  - `evaluate_red_team` (lines 315–336) and `evaluate_faithfulness` (lines 338–359) construct `JudgeResult` with **hardcoded `confidence=0.5`** and **`llm_response=""`** (lines 332, 354). The actual LLM response and parsed confidence are discarded — provenance is lost. The `judge` callable inside `make_*_judge_fn` does parse confidence correctly (line 211), but the convenience wrappers throw it away.
  - `_parse_score` uses `re.search(r'\{[^}]*"score"[^}]*\}', response, re.DOTALL)` (line 175) — fails on nested JSON (e.g., `{"score": 0.5, "justification": {"a": "b"}}`).
  - `_parse_score` fallback to `0.5` with `confidence=0.1` (line 194) — same silent-masking problem as rlaif_trainer.
  - 5 bare `except Exception: pass`-style patterns (3 explicit `except Exception`, 2 fallback returns) — errors silently absorbed.
  - Module claims (docstring line 4) to "replace keyword-based judge (Phase 41+47)" but `redteam_adversary.make_keyword_judge_fn` still exists in the codebase — no actual replacement happened.

**Test coverage: 6/10** — 30 tests. 12 mock patches of `_call_llm`. Tests score parsing (JSON, score-with-text, score-pattern, clamp, malformed fallback), red-team judge with mock LLM, faithfulness judge. Missing: no test that `evaluate_red_team` correctly preserves `confidence` and `llm_response` — because it doesn't, and the tests don't notice.

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`).

**Top 3 weak spots:**
1. `evaluate_red_team` / `evaluate_faithfulness` discard parsed confidence and LLM response (hardcoded `0.5` and `""`).
2. `_parse_score` regex fails on nested JSON.
3. `_call_llm` / `health_check` triplicated.

**Top 3 recommendations:**
1. Make `evaluate_red_team` / `evaluate_faithfulness` actually return the parsed `confidence` and `llm_response` — refactor the inner judge callable to return a richer tuple `(score, confidence, response)`.
2. Replace ad-hoc regex with a proper JSON extraction routine (try `json.loads(response)` first, then fall back to brace-matching).
3. Extract LLM bridge client (cross-cutting finding #1).

**Replacement alternatives:** `DeepEval` (specifically `LLMJudge` and faithfulness metric), `promptfoo`'s assert helpers, OpenAI Evals framework. `DeepEval` is the closest replacement — it has faithfulness, hallucination, and relevance judges out of the box.

---

### 8. `faithfulness_tester.py` — Summarizer Faithfulness Testing (Phase 46)

**Purpose:** Heuristic faithfulness metrics comparing LLM reasoning trace to extracted summary. 4 metrics: entailment (token overlap), consistency (negation mismatch), coverage (key-phrase coverage), hallucination (tokens in summary not in reasoning). Weighted aggregate → FAITHFUL / PARTIALLY_FAITHFUL / UNFAITHFUL / INSUFFICIENT_DATA.

**Implementation quality: 6/10**
- Most thorough heuristic implementation in the group: 4 distinct metrics, weighted aggregation, level thresholds, per-engine summary.
- `test_from_contribution` and `test_run` integrate cleanly with the orchestrator's run-directory layout.
- Stopword list is hardcoded inline (lines 161–174) — should be a module-level constant.
- **Weak spots:**
  - **"Entailment" is just token overlap** (lines 199–209) — `len(summary_tokens ∩ reasoning_tokens) / len(summary_tokens)`. This is *not* entailment; it's lexical recall. Real entailment requires a model (NLI) or an LLM judge.
  - **Consistency check uses regex lookbehind** (line 230) — `r'(?<!not\s)(?<!never\s)(?<!no\s)\b{term}\b'` — Python's `re` module does NOT support variable-length lookbehinds (`\s` is fixed but `\s+` is not, and the lookbehinds are applied independently, so "never not X" still matches "X" as affirmative). The logic is broken.
  - `_extract_key_phrases` only finds 4 narrow patterns: ALL-CAPS acronyms, numbers, `engine_\d+`, and `\w+_\w+` — misses common technical phrases (camelCase without underscore, hyphenated terms, quoted strings).
  - `_compute_overall` uses `self.weights["hallucination"] * (1.0 - hallucination)` — the weight inversion is correct (lower hallucination = higher faithfulness) but undocumented; readers will be confused.
  - Hardcoded thresholds `0.75` (FAITHFUL) and `0.50` (PARTIAL) are not validated to be in [0,1] or in monotonic order.
  - `test_run` swallows all per-engine exceptions silently (line 447: `except Exception: continue`).

**Test coverage: 8/10** — 46 tests (most in group). Covers FaithfulnessLevel enum, result payload, weight validation, text preprocessing (tokenize, key-phrase extraction), each metric (entailment full/no overlap, consistency, coverage, hallucination), overall computation, level determination, test_from_contribution, test_run, summarize. Missing: no test for the broken lookbehind regex, no test for nested-JSON edge cases in `_extract_key_phrases`.

**Connectivity: 6/10** — 4 inbound importers: `orchestrator.py`, `real_fitness.py`, `unified_benchmark.py`, `test_orchestrator_integration.py`.

**Top 3 weak spots:**
1. "Entailment" is lexical recall, not entailment — misleading name.
2. Consistency regex uses variable-length lookbehind that Python's `re` doesn't support correctly.
3. Stopword list and 4 metric weights hardcoded inline.

**Top 3 recommendations:**
1. Rename `_compute_entailment` → `_compute_lexical_overlap` (or wire it to an actual NLI model / LLM judge via `LLMJudgeAdapter`).
2. Fix the lookbehind regex — use `re.search` with explicit boundary checks, or use `regex` module which supports variable-length lookbehind.
3. Move `DEFAULT_WEIGHTS`, `FAITHFUL_THRESHOLD`, `PARTIALLY_FAITHFUL_THRESHOLD`, and stopword list to `metaengine/training_config.py`.

**Replacement alternatives:** `DeepEval` faithfulness metric, `RAGAS` faithfulness, `TruLens` faithfulness. All three provide LLM-judge-based faithfulness scoring that properly handles entailment. This module's value-add is the heuristic mode (no LLM call required) for fast batch evaluation.

---

### 9. `trace_extractor.py` — Reasoning Trace Extraction Module (Phase 44)

**Purpose:** Self-distillation. Extract reasoning traces from MetaEngine's *own* LLM runs (via `response_text` from CONTRIBUTION.json). Split into steps (markdown headers → numbered → bullets → sentences), score heuristically (length, structure, specificity, coherence), add high-scoring traces to `MechanismLibrary` as A0_OBSERVED with `source="OWN_LLM_RUN"`.

**Implementation quality: 7/10**
- Multi-strategy text splitting (lines 149–208) with sensible fallback chain: try markdown headers first (need ≥2), then numbered lists, then bullets, then sentence boundaries with merging.
- `ReasoningTrace` and `ExtractionResult` are frozen with honest `source="OWN_LLM_RUN"` and `claim_ceiling="LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED"`.
- `add_to_mechanism_library` correctly filters by `score_threshold` and uses `MechanismCandidate.create()` (no bypass here — unlike selfplay_trainer and cross_model_transfer_tester).
- `extract_from_run` persists `REASONING_TRACES.json` alongside CONTRIBUTION.json — good provenance.
- **Weak spots:**
  - `_score_trace` uses 4 hardcoded sub-scores (`length_score * 0.3`, `structure_score = 0.3`, `specificity_score = 0.3`, `coherence_score = max 0.2`) — the weights are baked into the formula, not configurable.
  - `_split_into_steps` merges sentences greedily but doesn't respect semantic boundaries (e.g., a code block can be split mid-block).
  - `extract_from_run` swallows per-engine exceptions silently (line 425: `except Exception: continue`).
  - `add_to_mechanism_library` returns `(library, added)` — tuple return is unusual for an `add_to_*` method; caller must remember to rebind the library variable.
  - `time` import (line 33) is unused.

**Test coverage: 7/10** — 37 tests. Covers trace payload, extraction result payload, text parsing (markdown headers, numbered, bullets, sentences, empty, max-length, short-step filtering), scoring (long > short, structured > unstructured, specific > generic, score in [0,1]), full extraction, mechanism-library integration, run-directory extraction, summary. Missing: no test for the silent-exception path in `extract_from_run`.

**Connectivity: 6/10** — 5 inbound importers (most in group): `orchestrator.py`, `real_fitness.py`, `strict_test_factory.py`, `unified_benchmark.py`, `test_orchestrator_integration.py`.

**Top 3 weak spots:**
1. `_score_trace` weights hardcoded inline — no way to tune length-vs-structure-vs-specificity.
2. `extract_from_run` swallows per-engine errors silently.
3. `add_to_mechanism_library` returns a tuple instead of mutating in place — surprising API.

**Top 3 recommendations:**
1. Move scoring weights to `training_config.py` or a `TraceScoringWeights` dataclass.
2. Make `extract_from_run` return failed-engine list alongside successful results (don't silently swallow).
3. Refactor `add_to_mechanism_library` to either mutate in place (return `list[MechanismCandidate]`) or rename to `with_mechanism_library(result, library) -> (new_library, added)` for clarity.

**Replacement alternatives:** LangChain's `cache` + `CallbackManager` for trace extraction, Phoenix/Arize for LLM observability. None of these integrate with the MechanismLibrary model, so this module is research-specific.

---

### 10. `cross_model_transfer_tester.py` — Cross-Model Mechanism Transfer Tester (Phase 45)  ⚠ NO TEST

**Purpose:** Test whether a mechanism extracted from engine A (e.g., engine_16 LLM) transfers to engine B (e.g., engine_01 native). Each experiment: measure `target_quality_baseline` and `target_quality_with_mechanism`, compute `delta`, classify as TRANSFERABLE / NOT_TRANSFERRED / INSUFFICIENT_EVIDENCE / REJECTED.

**Implementation quality: 6/10**
- Clean experiment semantics: 4-way classification with explicit thresholds.
- `TransferExperiment` and `TransferSummary` are frozen with payload/as_dict and honest claim_ceiling.
- `advance_transferable_to_a1` correctly refuses to advance to A2 (line 276: "Note: A1→A2 requires AssimilationGate receipt").
- **Weak spots:**
  - **NO TEST FILE.** `tests/test_cross_model_transfer_tester.py` does not exist. This module is wired into the orchestrator and 3 importers but has zero test coverage.
  - `advance_transferable_to_a1` bypasses `MechanismLibrary.create()` (lines 302–308) — same anti-pattern as `selfplay_trainer.advance_mechanism_states` (cross-cutting finding #3).
  - `run_batch` calls `quality_fn` for every (target, mechanism) pair — no memoization, no parallelism.
  - `run_experiment` doesn't validate that `source_engine != target_engine` — a self-transfer experiment is silently allowed and will always show delta=0.
  - `summarize()` computes `mean_quality_delta` but doesn't include variance / std-dev — useful signal lost.
  - No persistence to disk — every campaign run loses its experiment history.

**Test coverage: 0/10** — no test file. **This is the single largest test-coverage gap in Group B.** The module has non-trivial state-advancement logic, classification thresholds, and bypasses the library API — all untested.

**Connectivity: 5/10** — 3 inbound importers: `orchestrator.py`, `strict_test_factory.py`, `unified_benchmark.py`. Wired into production paths despite zero tests.

**Top 3 weak spots:**
1. **Zero tests** — highest-priority gap in the entire training subsystem.
2. `MechanismLibrary.create()` validation bypassed (lines 302–308).
3. No `source_engine != target_engine` validation — silent self-transfer experiments allowed.

**Top 3 recommendations:**
1. **Write `tests/test_cross_model_transfer_tester.py` immediately** — target 30+ tests covering: classification thresholds (all 4 results), batch execution, `advance_transferable_to_a1` (with library bypass test), `summarize` statistics, summary hash determinism, error paths (invalid thresholds, empty experiments).
2. Add `source_engine != target_engine` validation in `run_experiment`.
3. Fix the library bypass (cross-cutting finding #3).

**Replacement alternatives:** No drop-in alternative — this is a research-specific module. The closest general concept is "transfer learning evaluation" but no standard library wraps the experiment+threshold+classification workflow.

---

### 11. `parallel_campaign.py` — Parallel Training Campaign (Phase 42)

**Purpose:** Unified harness running all 6 trainers in parallel via `ThreadPoolExecutor`. Each trainer is a zero-arg callable returning a summary dict. Campaign collects results, builds a shared-state summary, returns `CampaignResult` with hashes.

**Implementation quality: 7/10**
- Clean separation: `TrainerResult` (per-trainer), `CampaignResult` (aggregate). Both frozen with payload/as_dict.
- `_run_trainer` catches all exceptions and produces a `TrainerResult(success=False, error=…)` — robust.
- `run()` sorts results by trainer_name for deterministic output.
- `ThreadPoolExecutor` with `max_workers` config; `as_completed` for streaming.
- **Weak spots:**
  - `_build_shared_state_summary` (lines 252–283) uses an `if/elif` chain on `trainer_name` strings (`"RLAIF"`, `"PBT"`, `"AlphaZero"`, `"ES"`, `"MARL"`, `"RedTeam"`) — same Open/Closed violation as Group A's engine-ID dispatch. Adding a 7th trainer requires editing this method.
  - No retry/backoff for transient trainer failures — a single exception marks the trainer as failed for the whole campaign.
  - No timeout per trainer — a hung trainer blocks the campaign until `max_workers` slots free up.
  - `register_trainer` doesn't check for duplicate names — silently overwrites.
  - `2 except Exception` blocks: one in `_run_trainer` (acceptable — wraps trainer call), one in `run()` outer try (line 221 — should never fire, defensive only).

**Test coverage: 7/10** — 33 tests. Covers trainer result payload, failed-trainer error, campaign result payload, init validation, registration (single + multiple + empty-name), unregister, run with mock trainers, shared-state summary extraction, campaign hash determinism. Missing: no test for the duplicate-name overwrite case, no test for the trainer-name elif chain (because it's just data extraction).

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`). This is glue, not a reusable primitive.

**Top 3 weak spots:**
1. `_build_shared_state_summary` uses `if/elif` on trainer names — Open/Closed violation.
2. No per-trainer timeout — a hung trainer blocks the campaign.
3. `register_trainer` silently overwrites duplicate names.

**Top 3 recommendations:**
1. Replace `if/elif` chain with a registry: `self._summary_extractors: dict[str, Callable[[dict], dict]]`, populated at registration time.
2. Add `trainer_timeout` parameter; use `future.result(timeout=…)` in `run()`.
3. `register_trainer` should raise `TRAINER_ALREADY_REGISTERED` on duplicate name (or `replace_trainer` for explicit replacement).

**Replacement alternatives:** Ray Tune's `Trial` runner, Optuna's `Study` with `optimize(n_jobs=N)`. Both handle parallel trainer execution, retries, and timeouts. This module's value-add is the constitution-disciplined result objects.

---

### 12. `recursive_loop.py` — Recursive Self-Improvement Loop (Phase 43)

**Purpose:** Close the recursive improvement loop: G0 → G1 → G2 → ... Each generation runs a campaign, extracts metrics, compares with previous generation, stops on convergence (improvement_ratio < 1.0 + convergence_threshold).

**Implementation quality: 6/10**
- Clean `GenerationMetrics` and `ImprovementComparison` frozen dataclasses with payload/as_dict.
- `_extract_metrics` reads from `shared_state_summary` of campaign result — works with both real and pre-computed campaign results.
- Convergence detection: `if comparison.improvement_ratio < 1.0 + self.convergence_threshold: self.converged = True` (lines 271–272).
- `run()` accepts pre-computed `campaign_results` list — useful for testing.
- **Weak spots:**
  - **`az_normalized = min(1.0, az_mechanisms / 10.0)`** (line 181) — magic constant `10.0`. If the next generation extracts 11 mechanisms, it caps at 1.0; if 5, it scores 0.5. No principled reason for `/10`.
  - **`rt_safety = 1.0 if rt_violations == 0 else max(0.0, 1.0 - rt_violations * 0.1)`** (line 180) — magic constant `0.1`. 10 violations → 0.0; 5 violations → 0.5. Linear decay, no rationale.
  - `_compare_generations` computes `ratio = metrics_b.combined_score / max(0.001, metrics_a.combined_score)` — if `metrics_a.combined_score == 0`, ratio becomes `score_b / 0.001` which can be huge (false-positive improvement signal).
  - Convergence check uses `<` (line 271), not `<=` — boundary case is "not converged". Probably fine.
  - `DEFAULT_SCORE_WEIGHTS` (lines 130–137) has 6 weights summing to 1.0, but `alphazero_mechanisms` weight (0.15) is applied to `az_normalized` which is itself bounded by `min(1.0, /10.0)` — the effective weight on raw mechanism count is 0.015 per mechanism, much smaller than the apparent 0.15.
  - No detection of *regression* (combined_score decreasing) — only improvement_ratio threshold. A regression still continues the loop (since ratio > 1.0 fails) but is not flagged separately.

**Test coverage: 7/10** — 30 tests. Covers generation metrics payload, improvement comparison payload, init, run_generation metric extraction, no-campaign-fn error, campaign_fn invocation, comparison creation, improvement ratio computation, no-improvement detection, delta scores, convergence detection, no-convergence case. Missing: no test for the magic constants (`/10.0`, `*0.1`), no test for the `combined_score == 0` division-by-0.001 case.

**Connectivity: 4/10** — 1 inbound importer (`unified_benchmark.py`). Like `parallel_campaign`, this is glue.

**Top 3 weak spots:**
1. `az_mechanisms / 10.0` and `rt_violations * 0.1` are arbitrary normalizations.
2. `combined_score == 0` produces huge false-positive improvement ratios.
3. Regression (score decrease) is not flagged separately from no-improvement.

**Top 3 recommendations:**
1. Move normalization constants to `training_config.py`; document the rationale.
2. Guard against `metrics_a.combined_score <= 0` — return `ImprovementComparison` with `improved=False, improvement_ratio=0.0` and a `note="baseline_score_zero"` field.
3. Add a `regression_detected` flag to `ImprovementComparison` when `delta_scores["combined_score"] < 0`.

**Replacement alternatives:** No standard alternative — recursive self-improvement is research-specific. The closest general pattern is Optuna's `study.optimize(n_trials=K)` with a custom pruning callback, but it doesn't carry forward generation-to-generation state the way this module does.

---

## Cross-Cutting Anti-Patterns (Across All 12 Modules)

### A. LLM-bridge client triplication (Finding #1)
3 modules (`rlaif_trainer`, `redteam_adversary`, `llm_judge`) each contain a near-identical `_call_llm` method (~25 LOC each) and `health_check` method (~7 LOC each). Total duplicated: ~96 LOC. **Fix:** Extract `metaengine/llm_bridge_client.py` with a `LLMBridgeClient` class; inject into the 3 trainers.

### B. `MechanismLibrary.create()` bypass (Finding #3)
2 modules (`selfplay_trainer.advance_mechanism_states`, `cross_model_transfer_tester.advance_transferable_to_a1`) use `dataclasses.replace(candidate, status=new_state)` + manual library rebuild instead of calling a state-transition API. **Fix:** Add `MechanismLibrary.transition_state(mechanism_id, new_state, receipt)` that validates + records + returns a new library.

### C. Silent error masking
- `rlaif_trainer._parse_scores` falls back to `0.5` on JSON parse failure (line 274).
- `llm_judge._parse_score` falls back to `0.5` with `confidence=0.1` (line 194).
- `evaluate_run_contributions` swallows per-engine errors into the rewards dict (line 482).
- `trace_extractor.extract_from_run` swallows per-engine errors with `continue` (line 425).
- `faithfulness_tester.test_run` swallows per-engine errors with `continue` (line 447).
- `redteam_adversary.health_check` swallows all errors as `False` (line 205).
- `llm_judge.health_check` swallows all errors as `False` (line 133).

**Pattern:** All 6 modules that touch the LLM bridge or filesystem silently absorb errors and return degraded-but-valid results. This is constitution-disciplined (don't crash the engine) but operationally dangerous (errors invisible in production). **Fix:** Add structured logging at WARNING level for every silent fallback; emit a `degraded=True` flag in the result payload.

### D. Hardcoded weight dicts and magic constants (Finding #5)
12 distinct weight dicts / thresholds across the 12 modules (see table in Finding #5). **Fix:** Centralize in `metaengine/training_config.py` as typed dataclasses.

### E. String-equality dispatch on trainer names
`parallel_campaign._build_shared_state_summary` uses `if/elif` on `trainer_name` (6 branches). Same Open/Closed violation as Group A's engine-ID dispatch. **Fix:** Replace with a registry dict.

---

## Bright Spots

1. **Constitution discipline is uniformly excellent.** Every module sets `truth_effect="NONE"` and `claim_ceiling="…_IS_EVALUATIVE_NOT_TRUTH"` on every payload. No module auto-promotes to A3. The A1→A2 gate (AssimilationGate receipt) is respected in `selfplay_trainer.advance_mechanism_states` (line 233 comment) and `cross_model_transfer_tester.advance_transferable_to_a1` (line 276 comment).

2. **Test pass rate is 100%.** All 352 tests pass in 1.33 s. Tests use `unittest.mock.patch` correctly for the LLM bridge (29 mock patches across the 3 LLM-touching modules). No flaky tests, no skipped tests.

3. **`pbt_trainer.py` is the best-structured module in the group** (8/10). Clean OOP, deterministic RNG, Pareto frontier, mutation receipts with hashes, validation in `__init__`. Could be published as a standalone library.

4. **`faithfulness_tester.py` has the deepest test suite** (46 tests, 439 LOC). Covers all 4 metrics, both polarities of each metric, weight validation, level determination, contribution integration, run-directory integration, and summary statistics.

5. **`trace_extractor.py` has the highest connectivity** (5 inbound importers) — used by orchestrator, real_fitness, strict_test_factory, unified_benchmark, and integration tests. Its `add_to_mechanism_library` correctly uses `MechanismCandidate.create()` (no bypass).

---

## Final Verdict & Prioritized Actions

The Group B training subsystem is **production-quality on constitution discipline** and **immature on test coverage for one critical module**. The architecture is sound: 6 trainers (RLAIF, PBT, AlphaZero, ES, MARL, RedTeam) feeding a parallel campaign harness that feeds a recursive loop, all respecting the K0 invariants. The 3 evaluator modules (LLMJudge, FaithfulnessTester, TraceExtractor) provide prior-only signals that flow into biographies and the mechanism library without ever claiming truth.

### Top 3 Prioritized Actions

1. **Write `tests/test_cross_model_transfer_tester.py` (CRITICAL).** This is the only training module with zero tests, and it's wired into `orchestrator.py` + 2 other importers. Target 30+ tests covering classification thresholds, batch execution, library-bypass advancement, summary statistics, and hash determinism. Estimated effort: 4 hours. Estimated risk reduction: high (closes the largest test gap in the entire training subsystem).

2. **Extract `metaengine/llm_bridge_client.py` (HIGH).** Pull the duplicated `_call_llm` + `health_check` from `rlaif_trainer`, `redteam_adversary`, `llm_judge` into a single `LLMBridgeClient` class. Inject into the 3 trainers via `__init__`. Estimated effort: 2 hours (mostly mechanical). Estimated reduction: ~150 LOC of duplication. Estimated future maintenance savings: high (any bridge protocol change becomes a 1-file edit).

3. **Fix the `MechanismLibrary.create()` bypass (HIGH).** Add `MechanismLibrary.transition_state(mechanism_id, new_state, receipt)` API that validates the transition, records it, and returns a new library. Update `selfplay_trainer.advance_mechanism_states` (line 250–255) and `cross_model_transfer_tester.advance_transferable_to_a1` (line 302–308) to call it. Estimated effort: 3 hours. Estimated safety improvement: high (restores the library's own validation as the single chokepoint for state transitions).

### Secondary Actions (P2)

4. Centralize all weight dicts and thresholds in `metaengine/training_config.py` (Finding #5).
5. Replace `parallel_campaign._build_shared_state_summary` `if/elif` chain with a registry (Anti-pattern E).
6. Add `EngineBiographyStore.record_prior_observation(engine_id, reward, source="RLAIF_AI_JUDGE")` API to replace RLAIF's direct mutation of `biography_store.data` (Finding #4).
7. Make `evaluate_red_team` / `evaluate_faithfulness` in `llm_judge.py` actually return the parsed `confidence` and `llm_response` (Module 7 weak spot #1).
8. Add structured WARNING-level logging to every silent-error fallback (Anti-pattern C).

### Tertiary Actions (P3)

9. Rename `selfplay_trainer.ablate_losing_mechanisms` → `identify_losing_mechanisms` (or actually retire them).
10. Delete `es_optimizer.make_policy_fitness_fn` (no-op wrapper).
11. Add `source_engine != target_engine` validation in `cross_model_transfer_tester.run_experiment`.
12. Replace naive convergence criterion in `es_optimizer.summary()` with relative-improvement-over-K-generations.

---

## Appendix: Test Counts and Pass Status

| Module | # Tests | Status |
|--------|---------|--------|
| rlaif_trainer | 25 | ✅ pass |
| pbt_trainer | 26 | ✅ pass |
| es_optimizer | 30 | ✅ pass |
| selfplay_trainer | 18 | ✅ pass |
| marl_trainer | 38 | ✅ pass |
| redteam_adversary | 39 | ✅ pass |
| llm_judge | 30 | ✅ pass |
| faithfulness_tester | 46 | ✅ pass |
| trace_extractor | 37 | ✅ pass |
| cross_model_transfer_tester | **0** | ⚠ NO TEST FILE |
| parallel_campaign | 33 | ✅ pass |
| recursive_loop | 30 | ✅ pass |
| **TOTAL** | **352** | **352 pass, 0 fail, 1 module untested** |

Test runtime: 1.33 s. No skipped tests, no flaky tests observed.

---

*Analysis complete. No source files modified. No truth effects produced. Constitution preserved.*
