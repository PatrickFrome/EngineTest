# Critical Analysis — Group F: Architecture Modules

**Task ID:** crit-F-arch
**Agent:** general-purpose (sub-agent)
**Scope:** 16 architecture & reentry modules in METAENGINE_SLICE3_RESTORED.
**Mode:** Read-only critical analysis. No source files modified, no canonical state touched, no truth effects produced.

---

## Executive Summary

| # | Module | Impl LOC | Test LOC | Tests | Impl | Tests | Conn | Notes |
|---|--------|---------:|---------:|------:|-----:|------:|-----:|-------|
| 1 | architecture_policy.py | 281 | 225 | 20 | 9 | 9 | 10 | Spine — I1 backward-compat, CAS champion promotion |
| 2 | architecture_search.py | 184 | 0 | 0 | 7 | 0 | 4 | 4-strategy generator, deterministic seed=42 |
| 3 | architecture_synthesis.py | 121 | 0 | 0 | 7 | 0 | 6 | itertools.combinations(2,3), 5 importers |
| 4 | architecture_evolution.py | 37 | 0 | 0 | 6 | 0 | 8 | DENSE one-liner, 5 magic thresholds |
| 5 | organization_policy.py | 456 | 191 | 8 | 9 | 8 | 7 | Excellent validation cascade |
| 6 | organization_tournament.py | 228 | 105 | 7 | 7 | 8 | 6 | Pairwise + Pareto, 6dp rounding tie risk |
| 7 | organization_legacy.py | 172 | 139 | 6 | 8 | 8 | 2 | Test-only — 0 production importers |
| 8 | task_conditional_selector.py | 115 | 0 | 0 | 5 | 0 | 4 | `self._experience` not persisted |
| 9 | curriculum_generator.py | 144 | 0 | 0 | 7 | 0 | 4 | Deterministic seed=42 = fixed curriculum |
| 10 | autonomous_loop.py | 122 | 0 | 0 | 7 | 0 | 6 | ONLY module with cross-run persistence |
| 11 | recursive_improvement.py | 89 | 0 | 0 | 5 | 0 | 4 | Hardcoded g0_acc=0.5 + `'actual_q' in dir()` |
| 12 | depth_budget.py | 80 | 0 | 0 | 7 | 0 | 6 | 11 magic thresholds, 6-component gain |
| 13 | frontier_control_plane.py | 598 | 0 | 0 | 8 | 0 | 7 | Largest module — Anthropic+Magentic+AlphaEvolve+DSPy patterns |
| 14 | polycentric_reentry.py | 281 | 60 | 4 | 6 | 3 | 1 | DEAD CODE — never instantiated |
| 15 | core4_reentry.py | 292 | 0 | 0 | 6 | 0 | 2 | DEAD CODE — only helpers imported |
| 16 | native_reentry_compiler.py | 127 | 0 | 0 | 7 | 0 | 8 | Wired as `self.compiler` |
| **Total / Avg** | **3,227** | **720** | **45** | **6.81** | **2.25** | **5.31** | Test ratio 0.22 |

**Existing tests:** 45 tests across 5 dedicated suites, ALL PASS (~0.5s).

---

## Per-Module Analysis

### 1. architecture_policy.py (281 LOC, 225 test LOC, 20 tests, 22 importers)

**Purpose:** Defines `ArchitecturePolicy` frozen dataclass — the declarative architecture contract: generation lineage, topology_id, waves (engine grouping), dialectic_operators, mutable hyperparameters (max_rounds, max_deep_engines, exploration_rate, temperature), and immutable guardrail/verifier/benchmark hashes. Provides `PolicyStore` with append-only records + compare-and-swap champion promotion + atomic rollback.

**Implementation quality: 9/10.**
- `MUTABLE_FIELDS` / `FORBIDDEN_FIELDS` frozensets enforce the constitutional boundary between evolvable hyperparameters and immutable safety anchors.
- `PolicyStore.promote()` uses `os.replace(temporary, active_path)` — atomic compare-and-swap on the active policy pointer; rejects if `expected_champion_hash` does not match current.
- `from_dict()` implements graceful I1 backward-compat: injects `temperature=0.4` default for legacy policies, then verifies hash; if hash still mismatches, re-tries against the temperature-stripped payload before raising `POLICY_HASH_MISMATCH`. This is the model pattern for schema-version-tolerant deserialization.
- `mutate_policy()` uses `dict.fromkeys(parent.dialectic_operators + operators)` to dedupe while preserving order — clean algebraic merge.
- `validate()` checks bounds on every field, rejects unknown engines/operators/duplicates.

**Test coverage: 9/10.** 20 tests across 225 LOC. Covers validation errors, hash determinism, CAS promotion failure, rollback, mutation receipt chaining. Missing: concurrent-promotion race test (though `os.replace` makes this safe in practice).

**Connectivity: 10/10.** 22 importers — the architectural spine. Imported by orchestrator, organization_legacy, organization_tournament (transitive), frontier_control_plane (via orchestrator state), and most Group B/C trainers.

**Weak spots:**
1. `verifier_hash = "EXTERNAL_VERIFIER_PINNED_BY_CAMPAIGN"` and `benchmark_hash = "SEALED_BY_CAMPAIGN"` are placeholder strings, not real hashes — the FORBIDDEN_FIELDS guard prevents mutation but the values themselves are non-canonical.
2. `initial_policy()` hardcodes the 4-wave 16-engine decomposition — no parameterization for smaller/larger engine pools.
3. `rollback()` does NOT use the atomic `os.replace` pattern that `promote()` uses — direct `write_json(self.active_path, ...)`. Inconsistent atomicity guarantee.

**Recommendations:**
1. Replace `verifier_hash` / `benchmark_hash` placeholders with real canonical hashes (or load from `security.py` constants).
2. Make `rollback()` use the same `.json.tmp` + `os.replace` pattern as `promote()`.
3. Parameterize `initial_policy()` to accept an engine pool argument (default to `ENGINE_ARCHITECTURE_MIX`).

---

### 2. architecture_search.py (184 LOC, NO test)

**Purpose:** Phase 13 — generates novel `ArchitectureCandidate` records from mechanism library + biography priors + tournament-dominated-config avoidance. 4 strategies: RECOMBINATION, BIOGRAPHY_GUIDED, NOVELTY, ADVERSARIAL.

**Implementation quality: 7/10.**
- Clean strategy decomposition. Deduplication via `seen: set[tuple[str, ...]]` is correct.
- `predicted_quality = sum(priors.get(m, 0.5) for m in combo) / len(combo)` — silent 0.5 fallback for unknown mechanisms.
- `novelty_score = 1.0 - (len(set(combo) & champion) / max(1, len(combo)))` — clean novelty metric.
- `_rng = random.Random(seed)` — deterministic seed=42.
- Uses `**{**c.__dict__, "candidate_hash": h}` dataclass-rebuild pattern to inject hash after construction. This is the SAME anti-pattern flagged in Group B (mechanism_library bypass). It works because `ArchitectureCandidate` is frozen, but it bypasses any future `__post_init__` validation.

**Test coverage: 0/10.** NO dedicated test file. Generator is exercised end-to-end only via orchestrator's `try: ... except: pass` block (orchestrator.py:149-161).

**Connectivity: 4/10.** 2 importers: orchestrator (instantiates with seed=42, writes `ARCHITECTURE_SEARCH_CANDIDATES.json`) + tests/test_selfplay_trainer.py (imports but only as transitive). Output is write-only — no downstream consumer reads the candidates.

**Weak spots:**
1. Hardcoded magic numbers: `max_candidates // 3` (strategy split), `novelty < 0.5` skip threshold, `predicted_cost = 1.0 + 0.1 * len(combo)`, biography `predicted_cost=1.2`, novelty `predicted_cost=0.8`, adversarial `predicted_cost=1.5`.
2. `organization_type` hardcoded per strategy (`SPECIALIST_ROUTING`, `RESOURCE_PLUS_VERIFIER`, `ONE_RESOURCE`, `PARALLEL_ENSEMBLE`) — no rationale for the mapping.
3. Deterministic `seed=42` in orchestrator means every run produces IDENTICAL candidates for the same mechanism library — kills the "novelty pressure" claim.
4. Output JSON is written but never read back by any subsequent run — search results do not accumulate.

**Recommendations:**
1. Add `tests/test_architecture_search.py` — ~10 tests covering: empty mechanism_ids, all-dominated configs, biography-guided path, novelty<0.5 skip, deduplication, hash determinism, seed reproducibility.
2. Replace `seed=42` in orchestrator with `seed=int(time.time()) % 2**31` or accept a run_id-derived seed.
3. Persist generated candidates to `storage/architecture_search_history.jsonl` and feed them back as `dominated_configs` on the next run.
4. Extract magic numbers to a `SearchConfig` dataclass.

---

### 3. architecture_synthesis.py (121 LOC, NO test)

**Purpose:** Phase 20 — combines winning mechanisms from tournament worlds into `SynthesizedArchitecture` candidates. Explicitly does NOT assume positive sum: `claim_ceiling = "SYNTHESIS_RESULT_DOES_NOT_ASSUME_POSITIVE_SUM"`.

**Implementation quality: 7/10.**
- `itertools.combinations(winning_mechanisms, 2)` + `combinations(..., 3)` — exhaustive enumeration, then `self._rng.shuffle` + `[:max_combinations]`.
- Empty-result branch (fewer than 2 mechanisms) correctly computes `result_hash` on the empty result.
- `novelty_score = len(combo_sorted) / max(2, len(winning_mechanisms))` — questionable: a 3-mechanism combo from a 3-mechanism pool gets novelty=1.0, same as a 2-mechanism combo from a 2-mechanism pool. The metric conflates combo size with pool size.
- Same `**{**result.__dict__, "result_hash": h}` dataclass-rebuild pattern.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 6/10.** 5 importers: orchestrator (instantiates per run), selfplay_trainer.py (instantiates as `self.synthesizer` — properly persisted across the trainer's lifetime), synthesis_bridge.py, plus 2 test files. selfplay_trainer is the only production consumer that actually USES the synthesized architectures (for mechanism recombination).

**Weak spots:**
1. `novelty_score` formula is semantically weak (see above).
2. Comment `# Check if this combination has been tested before (in experience); For now, all syntheses are novel` — TODO admitted in source. No memory of prior syntheses.
3. `self._rng.shuffle(all_combos)` — non-deterministic across runs unless seed is fixed; orchestrator uses seed=42, so same shuffle every run.
4. No tracking of which syntheses were later falsified — the "does not assume positive sum" claim has no enforcement mechanism.

**Recommendations:**
1. Add `tests/test_architecture_synthesis.py` — ~8 tests covering: <2 mechanisms empty result, pairs-only path, pairs+triples path, max_combinations truncation, hash determinism, shuffle reproducibility.
2. Replace `novelty_score` with `1.0 - (prior_test_count(combo) / total_test_count)` — actual novelty against history.
3. Accept a `tested_combos: set[tuple[str, ...]]` parameter and skip already-tested combinations.
4. Wire `synthesis_bridge.py` output back as `tested_combos` on the next run.

---

### 4. architecture_evolution.py (37 LOC, NO test)

**Purpose:** Selects topology from `topology_library.candidates()` based on routing, disagreements, scheduler plan, and previous round's outcome. Magentic-One-style frontier replanning + disagreement-triggered topology mutation.

**Implementation quality: 6/10.**
- DENSE one-liner formatting (37 LOC on ~6 effective lines). Almost unreadable.
- 5 magic thresholds: `0.28` (frontier replan utility floor), `0.22` (disagreement mutation floor), `0.08` (retire threshold), and implicit `0` (eligible[0] fallback).
- String-equality dispatch for mutation label (`'FRONTIER_REPLAN_TOPOLOGY'`, `'RETAIN_TOPOLOGY'`, `'MUTATE_TOPOLOGY_UNDER_DISAGREEMENT'`, `'MUTATE_TOPOLOGY_FOR_EXPECTED_GAIN'`, `'INITIAL_TOPOLOGY_BIRTH'`).
- `eligible = [c for c in cands if c['topology_id'] not in excluded] or cands` — fallback to full candidate list if all are excluded, which silently re-admits quarantined/retired topologies.
- `selected = eligible[0]` — assumes `cands` is pre-sorted by `expected_utility`; if the library does not guarantee this, the fallback is silently wrong.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 8/10.** 3 importers: orchestrator.py:71 instantiates `self.evolution = ArchitectureEvolutionEngine(self.topologies)`, called at orchestrator.py:215 (`select`) and orchestrator.py:280 (`adjudicate_after_round`). Deeply wired into the round loop.

**Weak spots:**
1. `eligible[0]` fallback — silent dependence on candidate ordering.
2. `or cands` fallback re-admits excluded topologies — defeats the quarantine/retire mechanism.
3. `adjudicate_after_round` uses `observed_outcome < .08` as retire threshold — magic number with no calibration.
4. No persistence of `quarantined`/`retired` across runs — `previous` is in-memory only.

**Recommendations:**
1. Add `tests/test_architecture_evolution.py` — ~10 tests covering: initial birth, retain, frontier replan, disagreement mutation, false_confidence quarantine, retire-on-no-outcome, retire-on-low-outcome, all-excluded fallback, hash determinism.
2. Replace `or cands` with explicit `raise ValueError("ALL_CANDIDATES_EXHAUSTED")` — surface the failure.
3. Extract magic thresholds to a config dataclass.
4. Reformat from one-liners to multi-line for readability.

---

### 5. organization_policy.py (456 LOC, 191 test LOC, 8 tests, 5 importers)

**Purpose:** Defines `OrganizationPolicy` — the resource-aware organizational contract: resource_requirements, worker_roles, execution_groups, topology_edges (FLOW/ROUTE/DELEGATE/REVIEW/SYNCHRONIZE/REDUNDANT), 9 policy tuples (routing, memory, tool, information_boundaries, review, resource_budget, termination, recovery, lineage). 7 organization types with type-specific validation rules.

**Implementation quality: 9/10.**
- Excellent validation cascade: duplicate requirement_id/role_id detection, hex-hash format check (64-char), execution_group role coverage (every role must be in exactly one group), topology edge endpoints must exist as roles.
- Type-specific edge requirements enforced in `validate()`: RESOURCE_PLUS_VERIFIER requires REVIEW edge, SPECIALIST_ROUTING requires ROUTE edge, HIERARCHICAL_FEDERATION requires DELEGATE or SYNCHRONIZE, REDUNDANT_REPLICATION requires REDUNDANT edge. This is the model for invariant-as-code.
- `_pairs()` helper rejects duplicate keys with different values — catches schema drift.
- `payload()` calls `self.validate()` on every serialization — defensive double-check.
- `from_dict()` re-verifies `policy_hash` against recomputed hash.

**Test coverage: 8/10.** 8 tests across 191 LOC. Covers create/validate/from_dict/hash-mismatch/organization-type-specific edge requirements. Missing: concurrent-modification test, full `creation_fields()` round-trip test.

**Connectivity: 7/10.** 5 importers: organization_legacy.py (adapter), organization_tournament.py (transitive — PolicyResult references policy_id), cli.py, plus 2 test files.

**Weak spots:**
1. `OrganizationType.ONE_RESOURCE` requires exactly 1 role but does NOT require zero topology edges — a self-loop is rejected but extra edges to nonexistent roles are caught only by the generic edge-endpoint check.
2. `creation_fields()` returns a dict with dataclass objects (not their payload) — inconsistent with `payload()` which serializes. Confusing API surface.
3. `_pairs()` sorts by key — but `routing`/`memory_policy`/etc. are semantically unordered maps; the sort is canonical but loses insertion-order provenance.
4. No `OrganizationPolicyStore` equivalent to `PolicyStore` — no persistence/champion-promotion pattern for organizations.

**Recommendations:**
1. Add `OrganizationPolicyStore` mirroring `PolicyStore` (append-only + CAS promotion).
2. Add tests for `creation_fields()` round-trip and ONE_RESOURCE edge constraint.
3. Document that `_pairs()` sort is canonicalization, not ordering.

---

### 6. organization_tournament.py (228 LOC, 105 test LOC, 7 tests, 5 importers)

**Purpose:** Phase 4 — pairwise comparison of organization policies on a task suite with Pareto frontier analysis. 5 dimensions: quality, cost, latency, reproducibility, resource_efficiency.

**Implementation quality: 7/10.**
- `_dominates(a, b)` is strict — requires `a` to be ≥ on all 3 dimensions AND strictly > on at least one. Correct Pareto semantics.
- Pairwise loop is O(n² × m) over policies × tasks — fine for small N (≤10 policies), no scaling guard.
- `mean_metrics[pid]` rounds each metric to 6 decimal places BEFORE the Pareto comparison — could cause false-tie at the 6th decimal (two policies with quality 0.5000001 vs 0.5000002 would both round to 0.5 and neither dominates).
- `dominance` map built from pairwise winners — but `dominance.setdefault(p.winner, []).append(...)` uses `p.policy_b if p.winner == p.policy_a else p.policy_a` which is incorrect when `winner == "TIE"` (already guarded by `if p.winner != "TIE"`, but the ternary is still semantically fragile).
- `TournamentResult.tournament_hash` is computed via `**{**result.__dict__, "tournament_hash": h}` — same dataclass-rebuild pattern.

**Test coverage: 8/10.** 7 tests across 105 LOC. Covers dominance, pairwise, Pareto, hash determinism.

**Connectivity: 6/10.** 5 importers: orchestrator.py (builds synthetic PolicyResults from biography priors — NOT real policy executions), plus test files.

**Weak spots:**
1. 6dp rounding before Pareto — false-tie risk.
2. `next((r for r in results_list if r.policy_id == pa and r.task_id == tid), None)` — O(n) scan inside O(n²) loop = O(n³). Should build a `(policy_id, task_id) → result` dict.
3. Orchestrator builds SYNTHETIC PolicyResults from biography priors (orchestrator.py:534-542) — `cost=1.0, latency=0.5, reproducibility=1.0, resource_efficiency=0.5` are all hardcoded. The tournament is comparing priors, not measured outcomes.
4. No ablation support despite the docstring claiming it.

**Recommendations:**
1. Round only at the FINAL `payload()` step, not in `mean_metrics`.
2. Build a lookup dict before the pairwise loop.
3. Add `ablation: tuple[str, ...]` parameter to skip specified policies.
4. Replace orchestrator's synthetic PolicyResults with real measured outcomes from `META_RUN.json`.

---

### 7. organization_legacy.py (172 LOC, 139 test LOC, 6 tests, 1 importer)

**Purpose:** Adapter functions projecting legacy `ArchitecturePolicy` (16X) and D6 role genomes into `OrganizationPolicy` v1. Loss-aware: architecture operators remain routing metadata, not capabilities.

**Implementation quality: 8/10.**
- `organization_from_architecture_policy()` validates the source policy, checks engine coverage (`set(flattened) == expected`), requires ≥2 waves, then projects waves→execution_groups, engines→roles, operators→routing tuples.
- `organization_from_role_genomes()` loads the pinned C0-C7 catalogue via `load_role_genome()`, builds REVIEW edges from `mandatory_reviewers`, adds SYNCHRONIZE edges from C0 to all other slots.
- Lineage preservation is thorough: 7-8 lineage tuples recording source_kind, source_policy_hash, source_policy_version, source_generation, source_status, source_guardrail_hash, source_verifier_hash, source_parent_policy_hash.
- `_load_federation_protocol()` validates `slot_ids` catalog and `synchronizer_slot == C0`.

**Test coverage: 8/10.** 6 tests across 139 LOC. Covers both adapter functions, hash determinism, error paths.

**Connectivity: 2/10.** **1 importer — test file only.** This module is NOT called by orchestrator or any production code. It is a migration/compatibility adapter that exists solely for the test suite. 172 LOC of test-only production code.

**Weak spots:**
1. **Zero production consumers** — the adapter is orphaned. Either it should be called from a migration CLI (`metaengine migrate-legacy-policy`) or it should be deleted.
2. `organization_type=OrganizationType.SEQUENTIAL_PIPELINE` is hardcoded for the architecture-policy projection — but `ArchitecturePolicy.waves` is a 4-wave 16-engine decomposition, which is closer to PARALLEL_ENSEMBLE.
3. `_compact_json()` is defined but never used in the module.
4. `allowed_security_classes = tuple(ResourceSecurityClass)` — grants ALL security classes to legacy engines, which defeats the security-class purpose.

**Recommendations:**
1. Either wire `organization_from_architecture_policy()` into a CLI migration command, or move the module to `metaengine/legacy/` and mark it as deprecated.
2. Restrict `allowed_security_classes` to a subset relevant to legacy engines.
3. Remove unused `_compact_json()`.

---

### 8. task_conditional_selector.py (115 LOC, NO test, 2 importers)

**Purpose:** Phase 19 — selects organization policies based on task features (complexity, uncertainty, context_length). 4 deterministic rules + biography-prior fallback.

**Implementation quality: 5/10.**
- Rule logic is clean: `uncertainty > 0.7 → MODEL_PLUS_VERIFIER`, `complexity < 0.3 → SINGLE_MODEL`, `complexity > 0.7 and uncertainty < 0.3 → FEDERATION`, else biography-prior fallback.
- **CRITICAL:** `self._experience: dict[str, list[float]] = {}` is in-memory only — never persisted. orchestrator.py:137 instantiates `TaskConditionalSelector()` PER RUN, so `self._experience` is reset to `{}` every run. The "online adaptation" claim in the docstring is FALSE.
- `if selected is None or selected not in available_policies` — the `selected not in available_policies` check is dead code because `selected` is only set to values already checked against `available_policies`.
- `available_policies` is passed as `[active_policy.policy_hash[:16]]` by orchestrator (orchestrator.py:141) — a SINGLE policy. So the rules never fire (they check `"MODEL_PLUS_VERIFIER" in available_policies` etc., which is always False). The selector always falls through to the biography-prior default.
- Hardcoded thresholds: 0.7, 0.3, 0.85, 0.8, 0.7 (confidence), 0.5 (bio weight), 0.5 (exp weight).

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 4/10.** 2 importers: orchestrator (instantiates per run) + tests. Output `TASK_CONDITIONAL_SELECTION.json` is write-only — no downstream consumer.

**Weak spots:**
1. `self._experience` not persisted — defeats online learning.
2. Orchestrator passes only 1 policy — all rules dead, always falls to default.
3. `selected not in available_policies` dead branch.
4. Policy names `"MODEL_PLUS_VERIFIER"`, `"SINGLE_MODEL"`, `"FEDERATION"` do NOT match `OrganizationType` enum values (`RESOURCE_PLUS_VERIFIER`, `ONE_RESOURCE`, `HIERARCHICAL_FEDERATION`). Naming mismatch means even if multiple policies were passed, the rules would never match.

**Recommendations:**
1. Add `tests/test_task_conditional_selector.py` — ~10 tests covering: each rule fires correctly, fallback path, experience accumulation, hash determinism.
2. Fix policy name mismatch: use `OrganizationType` enum values.
3. Persist `self._experience` to `storage/task_conditional_experience.json` (mirror AutonomousExperimentLoop pattern).
4. Pass real `available_policies` list from `OrganizationPolicyStore` (once it exists).

---

### 9. curriculum_generator.py (144 LOC, NO test, 2 importers)

**Purpose:** Phase 14 — generates discriminative benchmark tasks. 4 difficulty levels × 3 templates × 8 contexts = 96 possible tasks. Progressive mode sorts EASY → ADVERSARIAL.

**Implementation quality: 7/10.**
- Clean template-based generation. `_CAPABILITY_DOMAINS` is a 10-element tuple covering REASONING/PLANNING/EVIDENCE/TOOL_USE/MEMORY/CREATIVITY/ANALYSIS/SYNTHESIS/CRITIQUE/RETRIEVAL.
- `_rng = random.Random(seed)` with seed=42 — deterministic. orchestrator.py:165 uses seed=42, so EVERY RUN produces the IDENTICAL 3-task curriculum. The "progressive difficulty" claim is true, but the curriculum is FIXED across all runs.
- Same `**{**task.__dict__, "task_hash": h}` rebuild pattern — but here the rebuild is redundant: the second `CurriculumTask(...)` constructor call could be replaced with `dataclasses.replace(task, task_hash=h)`.
- Progressive distribution: `levels[min(i * len(levels) // max(1, count), len(levels) - 1)]` — for count=3, produces indices [0, 1, 2] → EASY, MEDIUM, HARD (skips ADVERSARIAL). For count=5, produces [0, 1, 2, 3, 3] → duplicates HARD.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 4/10.** 2 importers: orchestrator (instantiates per run) + tests. Output `CURRICULUM_TASKS.json` is write-only — generated tasks are never executed by any benchmark runner.

**Weak spots:**
1. Deterministic seed=42 in orchestrator → fixed curriculum across all runs.
2. Progressive distribution has off-by-one for count=3 (skips ADVERSARIAL) and duplicates for count=5.
3. Generated tasks are never executed — `CURRICULUM_TASKS.json` is a dead artifact.
4. Only 8 hardcoded contexts — limited diversity.

**Recommendations:**
1. Add `tests/test_curriculum_generator.py` — ~8 tests covering: progressive distribution, difficulty choice, capability sampling, hash determinism, seed reproducibility, empty count.
2. Fix progressive distribution formula.
3. Wire generated tasks into `unified_benchmark.py` or `strict_test_factory.py`.
4. Vary seed per run or accept a `run_id`-derived seed.

---

### 10. autonomous_loop.py (122 LOC, NO test, 2 importers)

**Purpose:** Phase 28 — closed-loop self-improvement: hypothesize → select experiment → execute → record outcome → adjust → repeat.

**Implementation quality: 7/10.**
- **ONLY module in Group F with proper cross-run state persistence.** orchestrator.py:619-647 reads `storage/autonomous_loop.json`, replays prior outcomes via `record_outcome()`, records the current run's outcome, generates the next hypothesis, and persists the updated outcomes list. This is the model pattern that the other 5 "learning" modules should follow.
- `generate_hypothesis()` uses `mechanism_library_ids[:2]` — takes the FIRST 2 mechanisms, not the top-quality or random. Silent dependence on caller-side ordering.
- `select_experiment()` uses `experiment_id.startswith(c["id"][:3])` — fragile 3-character prefix match for "similar experiments". Two experiments with IDs `exp-001-abc` and `exp-002-def` would NOT match, but `exp-001-abc` and `exp-001-xyz` would.
- `c_adj["expected_gain"] = 0.5 * c.get("expected_gain", 0.5) + 0.5 * avg_q` — silent 0.5 fallback for missing expected_gain.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 6/10.** 2 importers: orchestrator (deeply wired with persistence) + tests.

**Weak spots:**
1. `mechanism_library_ids[:2]` — silent ordering dependence.
2. `startswith(c["id"][:3])` — fragile similarity heuristic.
3. `loop_hash()` is computed on `payload()` which does NOT include `_outcomes` — so the hash is constant across runs. Misleading: the "loop hash" does not reflect loop state.
4. No bound on `_outcomes` list — grows unboundedly across runs.

**Weak spots → Recommendations:**
1. Add `tests/test_autonomous_loop.py` — ~10 tests covering: hypothesis generation, experiment selection with/without matching outcomes, record_outcome, payload hash, cross-run persistence round-trip.
2. Replace `[:2]` with explicit top-k selection (accept a `top_k: int = 2` parameter).
3. Replace prefix match with explicit `experiment_kind` field on outcomes.
4. Include `_outcomes` count (not contents) in `payload()` so `loop_hash` reflects state.
5. Cap `_outcomes` at e.g. 1000 entries with FIFO eviction.

---

### 11. recursive_improvement.py (89 LOC, NO test, 3 importers)

**Purpose:** Phase 16 — compares researcher generations (G0 vs G1) to measure recursive self-improvement.

**Implementation quality: 5/10.**
- `compare()` is a 15-line pure function: `g0_acc = g0_correct / max(1, g0_experiments)`, `g1_acc = g1_correct / max(1, g1_experiments)`, `improvement = g1_acc / max(0.01, g0_acc)`.
- `max(0.01, g0_acc)` guards against division by zero — but if `g0_acc = 0.0`, `improvement = g1_acc / 0.01 = 100 * g1_acc`, which is semantically meaningless (100× improvement from 0 baseline).
- `efficiency = g1_better and exp_reduction > 0` — boolean, no nuance for "G1 slightly better but used 10× more experiments".

**orchestrator.py:580-592 usage is broken:**
```python
g0_acc = 0.5  # baseline
g1_acc = actual_q if 'actual_q' in dir() else 0.5
gen_result = comparator.compare(
    g0_experiments=10, g0_correct_predictions=int(g0_acc * 10),
    g1_experiments=1, g1_correct_predictions=1 if g1_acc > g0_acc else 0,
)
```
- `g0_acc = 0.5` is a HARDCODED baseline, not a measured G0.
- `'actual_q' in dir()` — name-based scope lookup. If `actual_q` is not defined in the local scope (e.g., if the run failed before measuring quality), this silently falls back to 0.5. This is the same anti-pattern as `0.0 or fallback` flagged in Group C.
- `g1_experiments=1, g1_correct_predictions=1 if g1_acc > g0_acc else 0` — single-experiment "generation" with binary correctness. The improvement_ratio is either `g1_acc / 0.5` (≈2× if better) or `0 / 0.5` (0× if worse). No granularity.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 4/10.** 3 importers: orchestrator (broken usage above) + 2 test files (test_synthesis_bridge, test_phases_17_22).

**Weak spots:**
1. `max(0.01, g0_acc)` division-by-zero guard produces meaningless 100× ratios.
2. Orchestrator's `'actual_q' in dir()` scope lookup is brittle.
3. Hardcoded `g0_experiments=10` baseline.
4. Single-experiment G1 has no statistical power.

**Recommendations:**
1. Add `tests/test_recursive_improvement.py` — ~8 tests covering: zero-baseline, equal-accuracy, G1-better, G1-worse, efficiency-improved, hash determinism.
2. Replace `'actual_q' in dir()` with explicit `actual_q: float | None = None` parameter.
3. Persist G0 baseline to `storage/g0_baseline.json` instead of hardcoding 0.5.
4. Require `g1_experiments >= 10` for statistical validity.

---

### 12. depth_budget.py (80 LOC, NO test, 3 importers)

**Purpose:** Adaptive deep-compute budget controller. Budget is a safety ceiling — epistemic stopping (proliferation/echo/marginal-gain) has priority over hard budget exhaustion.

**Implementation quality: 7/10.**
- `total = round(12.0 + 9.0 * c, 2)` — budget scales with complexity (12-21 units).
- `next_budget()` caps per round: `{1: 6.4, 2: 4.4, 3: 2.8, 4: 1.8}` — magic numbers.
- `evaluate()` computes 6-component gain: `new_types`, `new_peer_pairs`, `causal_depth_gain`, `tension_reduction`, `topology_change`, `productive_reground` — each normalized to [0, 1] with hardcoded denominators (4, 8, 2, 2, 1, 4).
- Weighted sum: `0.24*new_types + 0.16*new_peer_pairs + 0.28*causal_depth_gain + 0.14*tension_reduction + 0.10*topology_change + 0.08*productive_reground` — weights sum to 1.00 (good).
- 4 stop conditions with 4 magic thresholds: `proliferation` (node_count > 220 and gain < 0.18), `echo` (gain < 0.075), `marginal` (gain < 0.20 or efficiency < 0.055), `budget_exhausted` (remaining < 0.75).
- `eligible_for_policy_learning: False` is hardcoded — the controller never admits learning eligibility.
- `policy` field is a 200-character string constant — verbose, no parameterization.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 6/10.** 3 importers: orchestrator (used for stop decisions) + 2 test files.

**Weak spots:**
1. 11 magic thresholds with no calibration rationale.
2. `eligible_for_policy_learning: False` hardcoded — defeats the "policy learning" claim.
3. DENSE one-liner formatting — unreadable.
4. `productive_reground = min(1.0, reg/4) * (1.0 if (nt or np or depth_delta or tension or topo) else .15)` — complex conditional with magic 0.15 multiplier.

**Recommendations:**
1. Add `tests/test_depth_budget.py` — ~10 tests covering: complexity clamping, per-round caps, consume + remaining, each stop condition, low_gain_streak, proliferation, echo, marginal, budget_exhausted, continue.
2. Extract thresholds to a `DepthBudgetConfig` dataclass.
3. Make `eligible_for_policy_learning` a computed field based on gain + streak.
4. Reformat to multi-line.

---

### 13. frontier_control_plane.py (598 LOC, NO test, 4 importers)

**Purpose:** Phase 22 — evidence-control overlay implementing 6 frontier patterns: Anthropic BREADTH_FIRST_ORCHESTRATOR_WORKERS, Microsoft Magentic-One TASK_LEDGER_PROGRESS_LEDGER_REPLAN, Google AI Co-Scientist GENERATION_REFLECTION_RANKING, AlphaEvolve CANDIDATE_ARCHIVE_EVALUATOR_ENSEMBLE, DSPy TRACE_DRIVEN_REFLECTIVE_POLICY_EVOLUTION, OpenAI TYPED_HANDOFFS_GUARDRAILS_TRACING.

**Implementation quality: 8/10.**
- `_hash_record(record, field)` strips the hash field before computing the hash — self-reference-safe pattern (same as signed_provenance.py Group D bright spot).
- `create_task_ledger()` builds facts/assumptions/unknowns (Magentic-One pattern) with provenance references.
- `plan_round()` builds typed handoffs with hash-bound `input_refs` (original_source_hash, task_ledger_hash, scheduler_plan_hash, architecture_hash) and 6 guardrails.
- `_candidate()` computes 6-dim evaluator_scores with `EVALUATOR_WEIGHTS` (0.30+0.20+0.25+0.10+0.10+0.05 = 1.00).
- `_pareto_ids()` — O(n²) Pareto frontier over 6 dimensions.
- `_tournament()` — pairwise wins/losses/ties with 0.01 delta threshold.
- `_policy_candidate()` — 4 mutation triggers: REQUIRE_EXTERNAL_OUTCOME, TOPOLOGY_DIVERSITY_FLOOR, ROUTER_HIGH_RESOLUTION_TASK_STATE, BREADTH_FIRST_WORKSTREAM_REDECOMPOSITION.
- `evaluate_round()` tracks `_seen_transformation_types` across rounds — only the controller that maintains cross-round state.

**Test coverage: 0/10.** NO dedicated test file. 598 LOC is the LARGEST untested module in Group F.

**Connectivity: 7/10.** 4 importers: orchestrator.py (deeply wired — `create_task_ledger`, `plan_round`, `evaluate_round`, `artifact`), replication.py, cli.py, + test_frontier_control_plane_2_2.py (exists but is integration-level, not unit).

**Weak spots:**
1. 598 LOC with NO dedicated unit tests — highest-risk untested module in the group.
2. `EVALUATOR_WEIGHTS` hardcoded — no calibration mechanism.
3. `successful_states = {"COMPLETE", "DEGRADED", "REFERENCE_SIMULATION_COMPLETE", "ABSTAIN", "UNRESOLVED"}` — magic set.
4. `_tournament()` uses `delta > 0.01` threshold — magic.
5. `proliferation` threshold `node_count > 220` — magic.
6. `pressure_lines()` is a static method that returns 4 hardcoded lines.

**Recommendations:**
1. Add `tests/test_frontier_control_plane.py` — ~20 tests covering: task_ledger creation, required_engines, plan_round handoff hashes, _candidate scoring, _pareto_ids, _tournament, _policy_candidate triggers, evaluate_round stop conditions, artifact hash, cross-round transformation-type tracking. ~3 hours.
2. Extract `EVALUATOR_WEIGHTS` and thresholds to a `FrontierConfig` dataclass.
3. Move `pressure_lines` to a constants module.

---

### 14. polycentric_reentry.py (281 LOC, 60 test LOC, 4 tests, 1 importer)

**Purpose:** 16-engine recursive reentry with PEER_TARGETS adjacency matrix (16×5 = 80 directed peer edges). Adaptive 3-round stop based on novelty_threshold=0.22 + round3_engine_threshold=0.30.

**Implementation quality: 6/10.**
- `PEER_TARGETS` is a hand-curated 16-entry adjacency dict — semantic graph of which engines should consume each other's outputs. Well-designed but undocumented.
- `_project_other()` dispatches on engine_id with 12 branches (engine_05 through engine_16), each generating 2-3 `_polypos()` generative positions with claim_type, anchors, primitive, peer_sources.
- `_round_novelty()` computes 3-component novelty: type_novelty (35%), lexical_novelty (35%), peer_uptake (30%).
- `_downgrade()` correctly sets `evidence_strength = min(float(q.get('evidence_strength', 0.0)), 0.18)` — caps derived evidence strength below the 0.20 primary-source threshold.
- DENSE one-liner formatting throughout — `_project_other` is 60 lines of one-liner if/elif branches.

**CRITICAL: `PolycentricRecursiveReentry` class is NEVER INSTANTIATED.** Grep confirms only 1 reference (the class definition itself). 281 LOC of dead code. The orchestrator uses `NativeReentryCompiler` (not this class) for reentry.

**Test coverage: 3/10.** 4 tests across 60 LOC for 281 LOC of source. Tests exist but cover only the helper functions (`_peer_positions`, `_project`, `_round_novelty`), NOT the `PolycentricRecursiveReentry` class itself (which is dead code).

**Connectivity: 1/10.** 1 importer — test file only. The main class is dead.

**Weak spots:**
1. **281 LOC of dead code** — `PolycentricRecursiveReentry` is never called by orchestrator or any production module.
2. DENSE one-liner formatting — `_project_other` is unreadable.
3. Magic thresholds: 0.22 (novelty_threshold), 0.30 (round3_engine_threshold), 0.18 (evidence_strength cap).
4. Code duplication with `core4_reentry.py` — both have `_downgrade`, `_dossier`, `run_round`, `run` with near-identical structure.

**Recommendations:**
1. **Either wire `PolycentricRecursiveReentry` into the orchestrator's deep-engine pipeline** (as an alternative to `NativeReentryCompiler` for full 16-engine reentry), **OR delete the main class** and keep only the helper functions (extracted to a shared `reentry_projections.py` module that both `core4_reentry` and `polycentric_reentry` import).
2. Add ~15 tests for `PolycentricRecursiveReentry.run_round` and `run` (mocking the adapter factory).
3. Extract `_downgrade` and `_dossier` to a shared `reentry_common.py` to eliminate duplication with `core4_reentry.py`.
4. Reformat one-liners.

---

### 15. core4_reentry.py (292 LOC, NO test, 2 importers)

**Purpose:** 4-engine (engine_01-04) recursive reentry. Builds DERIVED_REENTRY_DOSSIER with provenance firewall, runs native adapters, downgrades outputs to SECOND_ORDER_GENERATIVE.

**Implementation quality: 6/10.**
- `_project_core4()` dispatches on engine_id with 4 branches, each generating 4-8 `_gpos()` generative positions with claim_type, anchors, lineage_primitive.
- `_downgrade()` correctly sets `evidence_strength = min(float(q.get('evidence_strength', 0.0)), 0.20)` — caps at 0.20 (slightly higher than polycentric's 0.18).
- `_dossier()` builds a markdown dossier with PROVENANCE FIREWALL header, ORIGINAL_SOURCE block, HYBRID_AGENDA, DISAGREEMENTS, PRIOR_CORE4_RETURNS, REQUIRED_REENTRY_BEHAVIOR sections.
- `run_round()` uses `ThreadPoolExecutor(max_workers=max_workers)` to run 4 engines in parallel.
- `run()` builds a hermeneutic return graph with REGROUND_REQUIRED edges back to ORIGINAL_SOURCE — the cycle closes only as a reground requirement, never as self-certification.
- DENSE one-liner formatting throughout.

**CRITICAL: `Core4RecursiveReentry` class is NEVER INSTANTIATED.** Only its helper functions (`_project_core4`, `_gpos`, `_tokens`, `_salient_terms`, `_sentences`, `_entropy`) are imported by `polycentric_reentry.py`. 292 LOC of source, ~140 LOC (the class itself) is dead code.

**Test coverage: 0/10.** NO dedicated test file.

**Connectivity: 2/10.** 2 importers: polycentric_reentry.py (imports helpers only) + test_epistemic_core.py. The main `Core4RecursiveReentry` class is dead.

**Weak spots:**
1. **~140 LOC of dead code** — `Core4RecursiveReentry` class is never instantiated.
2. `__import__('json').loads(...)` at line 115 — anti-pattern, should be `import json` at top.
3. `except Exception as e: raw = EngineContribution(eid, 'FAILED', {}, {'claims':[]}, repr(e))` — silent failure-to-EngineContribution conversion; adapter errors are swallowed into the artifact.
4. `try: import json; bd = json.loads(...)` at line 203 — local import inside try block, redundant with the top-level `import math, re` (json is NOT imported at top).
5. Code duplication with `polycentric_reentry.py` (see above).

**Recommendations:**
1. **Either wire `Core4RecursiveReentry` into the orchestrator** (as a Core-4-specific deep reentry path, perhaps triggered when `engine_id in {'engine_01', 'engine_02', 'engine_03', 'engine_04'}`), **OR delete the main class** and extract the helpers to `reentry_projections.py`.
2. Add `tests/test_core4_reentry.py` — ~15 tests covering helpers + (if kept) the main class.
3. Fix the `__import__('json')` anti-pattern.
4. Move `import json` to top-level.

---

### 16. native_reentry_compiler.py (127 LOC, NO test, 4 importers)

**Purpose:** Compiles a reentry dossier + typed handoff, runs the native adapter AND (for engine_01/02/03/04) a specialized native subcommand in parallel, extracts transformations, emits a hash-verified receipt.

**Implementation quality: 7/10.**
- `execute()` calls `verify_handoff(handoff)` — proper security gate before execution.
- `verify_release_file(self.root, pkgroot/'package.json')` + `verify_release_file(self.root, pkgroot/cmd[1])` — verifies the specialized binary against the release manifest before running.
- `run_sandboxed(cmd, cwd=pkgroot, timeout=180)` — proper sandboxed execution.
- `redact_secrets(cp.stdout[-6000:])` — output truncation + secret redaction.
- `_engine2_hypothesis_bank()` builds a frequency-based hypothesis bank with stopword filtering.
- Hash-stripped receipt pattern: `receipt['receipt_hash'] = canonical_hash({k: v for k, v in receipt.items() if k != 'receipt_hash'})`.
- `_specialized()` dispatches on engine_id with hardcoded paths: `Destruktion_4.0_UNIFIED_0.15.0-alpha.1` for engine_03.
- `except Exception as e: return {'mode': 'SPECIALIZED_NATIVE_SUBCOMMAND', 'exit_code': 2, 'error': repr(e)}` — specialized failures are recorded but do not fail the whole execute().

**Test coverage: 0/10.** NO dedicated test file. 127 LOC wired into orchestrator as `self.compiler` (orchestrator.py:71) — most critical untested module by importance.

**Connectivity: 8/10.** 4 importers: orchestrator.py (instantiated as `self.compiler`), test_controlled_learning_2_3.py, test_self_organizing_2_0.py, test_epistemic_core.py.

**Weak spots:**
1. Hardcoded package paths (`Destruktion_4.0_UNIFIED_0.15.0-alpha.1`) — version-pinned in source.
2. `else: return None` in `_specialized()` — engines other than 01/02/03/04 silently return None, no logging.
3. `specialized_mode = 'NATIVE_OPERATOR_PRESSURE_REANALYSIS' if engine_id=='engine_02' and (spec or {}).get('exit_code')==3 else ...` — magic exit code 3, magic engine_id.
4. `evidence_strength=0.25 if refs else 0.0` — magic 0.25 for transformations with source spans.
5. `extract_transformations(raw.canonical or {}, raw.native or {}, source, context['input_hash'])` — assumes `context` dict has `input_hash` key; KeyError if missing.

**Recommendations:**
1. Add `tests/test_native_reentry_compiler.py` — ~12 tests covering: handoff verification, dossier compilation, specialized subcommand dispatch, transformation extraction, receipt hash, parallel execution, error handling. Requires mocking `adapter_factory` and `run_sandboxed`.
2. Extract hardcoded package paths to a config.
3. Replace `context['input_hash']` with `context.get('input_hash', '')` — defensive.
4. Log `else: return None` cases.

---

## Cross-Cutting Findings

### Top 5 Cross-Cutting Critical Findings

1. **573 LOC of dead reentry code + 172 LOC of test-only adapter code = 745 LOC disconnected from production.**
   - `PolycentricRecursiveReentry` (polycentric_reentry.py:182, 281 LOC) is NEVER instantiated.
   - `Core4RecursiveReentry` (core4_reentry.py:106, ~140 LOC of the 292 LOC file) is NEVER instantiated — only its helper functions are imported.
   - `organization_from_architecture_policy()` and `organization_from_role_genomes()` (organization_legacy.py, 172 LOC) are called ONLY from tests.
   - Combined: 745 LOC of source code (23% of Group F's 3,227 LOC) that is either dead or test-only. The orchestrator uses ONLY `NativeReentryCompiler` for reentry and does not call any organization-legacy adapter.

2. **11 of 16 modules have NO dedicated test file** (1,914 LOC of source with zero direct tests):
   - architecture_search (184), architecture_synthesis (121), architecture_evolution (37), task_conditional_selector (115), curriculum_generator (144), autonomous_loop (122), recursive_improvement (89), depth_budget (80), frontier_control_plane (598), core4_reentry (292), native_reentry_compiler (127).
   - Test ratio drops from 0.22 (already low) to 0.00 for these 11 modules.
   - **Priority:** frontier_control_plane (598 LOC, largest untested), core4_reentry (292 LOC), native_reentry_compiler (127 LOC, most-critical untested — wired as `self.compiler`).

3. **Cross-run learning loop is OPEN for 5 of 6 "learning" modules.** Only `AutonomousExperimentLoop` persists state across runs (`storage/autonomous_loop.json`). The other 5 are instantiated PER RUN in orchestrator.py:137-165, 522, 582 with `seed=42`:
   - `TaskConditionalSelector()` — `self._experience` reset every run.
   - `ArchitectureSearchGenerator(seed=42)` — deterministic candidates every run.
   - `CurriculumGenerator(seed=42)` — deterministic curriculum every run.
   - `ArchitectureSynthesizer(seed=42)` — deterministic synthesis every run.
   - `GenerationComparator()` — no persistence; orchestrator hardcodes `g0_acc=0.5` baseline and uses `'actual_q' in dir() else 0.5` name-based scope lookup.
   - This repeats the Group D "cross-run loop open" anti-pattern (cross_run_accumulator, meta_learning, uncertainty_calibration, local_outcome_oracle) — the orchestrator treats stateful modules as ephemeral.

4. **Silent failure masking in orchestrator Phase 23.** All 16 module calls in orchestrator.py:134-650 are wrapped in `try: ... except: pass` or `except Exception:` — failures are silently swallowed and the run continues without those artifacts. Specifically:
   - `recursive_improvement` uses `actual_q if 'actual_q' in dir() else 0.5` — if `actual_q` is undefined (e.g., run failed before quality measurement), silently falls back to 0.5 baseline.
   - `task_conditional_selector` is passed `[active_policy.policy_hash[:16]]` as `available_policies` — a SINGLE policy, so all 4 rules silently fail (they check `"MODEL_PLUS_VERIFIER" in available_policies` etc.) and fall through to the biography-prior default. The selector is effectively a no-op.
   - Plus the policy-name mismatch: rules check `"MODEL_PLUS_VERIFIER"`, `"SINGLE_MODEL"`, `"FEDERATION"` but `OrganizationType` enum values are `RESOURCE_PLUS_VERIFIER`, `ONE_RESOURCE`, `HIERARCHICAL_FEDERATION`. Even with multiple policies, no rule would match.

5. **Dense one-liner formatting + magic constants + dataclass-rebuild anti-pattern.** The same trio flagged in Groups B/C/E recurs:
   - Dense one-liners: architecture_evolution.py (37 LOC on ~6 lines), depth_budget.py (80 LOC on ~10 lines, 11 magic thresholds), polycentric_reentry.py / core4_reentry.py (573 LOC combined, dense throughout).
   - Magic constants: ~40 across the group (frontier_control_plane EVALUATOR_WEIGHTS + 5 thresholds, depth_budget 11 thresholds, architecture_evolution 5 thresholds, task_conditional_selector 6 thresholds, autonomous_loop 2 magic numbers, recursive_improvement 0.01/0.5, native_reentry_compiler 0.25/3).
   - `**{**result.__dict__, "result_hash": h}` dataclass-rebuild pattern in 8 modules (architecture_search, architecture_synthesis, organization_tournament, autonomous_loop, recursive_improvement, task_conditional_selector, curriculum_generator, plus polycentric/core4 reentry). Should use `dataclasses.replace()`.

### Cross-Cutting Anti-Patterns

- **(A) Dead code by disconnection:** 745 LOC across 3 modules (polycentric_reentry main class, core4_reentry main class, organization_legacy functions) exists in the codebase but is never called by production code. The orchestrator imports `NativeReentryCompiler` for reentry but ignores both `PolycentricRecursiveReentry` and `Core4RecursiveReentry`. This is the architecture-group analog of the Group D "accumulation modules treated as ephemeral" finding — but worse, because these are entirely unused, not just mis-wired.
- **(B) Cross-run loop open:** 5 of 6 "learning" modules (search, curriculum, synthesis, selector, comparator) are instantiated per-run with no state persistence. Only AutonomousExperimentLoop persists. Same root cause as Group D.
- **(C) Silent failure masking:** `try: ... except: pass` in orchestrator Phase 23 + `'actual_q' in dir() else 0.5` scope lookup + `0.5` fallbacks in 6 modules. Same anti-pattern as Group B (silent error masking in 6 modules) and Group E (strict_test_factory SKIP-as-PASS).
- **(D) Magic constants pervasive:** ~40 hardcoded thresholds across 8 modules with no central config. Same as Group B (12 weight dicts) and Group E (16 engine costs + 21 thresholds).
- **(E) Dense one-liner formatting:** architecture_evolution.py, depth_budget.py, polycentric_reentry.py, core4_reentry.py — same as Group B (transformation_graph, nonlinearity, epistemic_gain). Unreadable, untestable, magic constants buried in one-liners.

### Bright Spots

- **architecture_policy.py (9/9/10)** is the model module for Group F — frozen dataclass with MUTABLE/FORBIDDEN field separation, atomic CAS promotion, I1 backward-compat hash fallback, hash re-verification on from_dict. The `PolicyStore` is the only persistent store in the group besides `AutonomousExperimentLoop`'s outcomes file.
- **organization_policy.py (9/8/7)** has the most thorough validation cascade in the group — type-specific edge requirements (REVIEW/ROUTE/DELEGATE/SYNCHRONIZE/REDUNDANT) enforced in `validate()`, called on every `payload()`. The `_pairs()` duplicate-key detection is a model for schema-drift prevention.
- **autonomous_loop.py (7/0/6)** is the ONLY module in Group F with proper cross-run state persistence. The orchestrator reads `storage/autonomous_loop.json`, replays prior outcomes, records the current outcome, generates the next hypothesis, and persists. This is the pattern the other 5 "learning" modules should follow.
- **native_reentry_compiler.py (7/0/8)** is properly security-gated: `verify_handoff()` before execution, `verify_release_file()` on the specialized binary, `run_sandboxed()` with timeout, `redact_secrets()` on output. Model for sandboxed-execution modules.
- **Constitution discipline uniformly excellent:** every module sets `truth_effect="NONE"` and a `claim_ceiling` string on every payload. No module promotes derived content to truth. The claim ceilings are specific and epistemically honest (e.g., `"SYNTHESIS_RESULT_DOES_NOT_ASSUME_POSITIVE_SUM"`, `"NATIVE_REENTRY_CAN_REORGANIZE_ANALYSIS_BUT_CANNOT_PROMOTE_DERIVED_CONTEXT"`).

---

## Final Verdict

Group F is the architecture-and-reentry subsystem. It contains 2 model modules (architecture_policy, organization_policy), 1 properly-wired learning module (autonomous_loop), and 13 modules with significant gaps — 11 with zero tests, 3 with dead main classes, 5 with broken cross-run persistence, and 1 (task_conditional_selector) that is effectively a no-op due to a naming mismatch.

The group's central architectural problem is **disconnection**: the orchestrator wires up 16 modules in Phase 23, but 3 are entirely dead, 5 are stateless-when-they-should-be-stateful, and 1 is silently a no-op. The result is a subsystem that APPEARS to implement closed-loop self-improvement but actually implements 16 fire-and-forget JSON writers.

### Top 3 Prioritized Recommendations

1. **Delete or wire up the 3 dead-code modules** (polycentric_reentry + core4_reentry main classes = ~420 LOC; organization_legacy functions = 172 LOC; total ~592 LOC).
   - Option A (wire up): Integrate `PolycentricRecursiveReentry` into the orchestrator's deep-engine pipeline as an alternative to `NativeReentryCompiler` for full 16-engine reentry. Integrate `Core4RecursiveReentry` as a Core-4-specific path. Call `organization_from_architecture_policy()` from a CLI migration command.
   - Option B (delete): Remove the main classes, extract the helper functions (`_project_core4`, `_project_other`, `_gpos`, `_polypos`, `_peer_positions`, `_round_novelty`, `_lexical_divergence`) to a shared `reentry_projections.py` module that both files import. Delete `organization_legacy.py` or move to `metaengine/legacy/`.
   - **Estimated effort:** 3 hours. Eliminates 592 LOC of dead/disconnected code.

2. **Write 11 missing dedicated test files** (~120 tests, ~18 hours). Priority order:
   - test_frontier_control_plane.py (~20 tests, 3h — 598 LOC is the largest untested module in the group).
   - test_native_reentry_compiler.py (~12 tests, 2h — most-critical untested, wired as `self.compiler`; requires adapter mocking).
   - test_core4_reentry.py (~15 tests, 2h — covers helpers + main class if kept).
   - test_depth_budget.py (~10 tests, 1.5h).
   - test_autonomous_loop.py (~10 tests, 1.5h — cross-run persistence round-trip is the key test).
   - test_task_conditional_selector.py (~10 tests, 1.5h).
   - test_architecture_search.py (~10 tests, 1.5h).
   - test_recursive_improvement.py (~8 tests, 1h).
   - test_curriculum_generator.py (~8 tests, 1h).
   - test_architecture_synthesis.py (~8 tests, 1h).
   - test_architecture_evolution.py (~10 tests, 1.5h).
   - **Lifts test-coverage average from 2.25/10 to ~6.5/10.**

3. **Fix cross-run persistence for the 5 "learning" modules + fix the silent-failure masking in orchestrator Phase 23.**
   - Mirror `AutonomousExperimentLoop`'s `storage/autonomous_loop.json` pattern for `TaskConditionalSelector._experience`, `ArchitectureSearchGenerator` history, `CurriculumGenerator` history, `ArchitectureSynthesizer` tested-combos, `GenerationComparator` G0 baseline.
   - Replace `seed=42` with run_id-derived seeds where determinism is not required.
   - Fix `task_conditional_selector.py` policy-name mismatch: replace `"MODEL_PLUS_VERIFIER"` / `"SINGLE_MODEL"` / `"FEDERATION"` with `OrganizationType.RESOURCE_PLUS_VERIFIER.value` / `OrganizationType.ONE_RESOURCE.value` / `OrganizationType.HIERARCHICAL_FEDERATION.value`.
   - Pass real `available_policies` list (not `[active_policy.policy_hash[:16]]`).
   - Replace `try: ... except: pass` in Phase 23 with `try: ... except Exception as exc: ledger.append(run_id, 'PHASE_23_MODULE_FAILED', {'module': ..., 'error': repr(exc)[:200]})`.
   - Replace `'actual_q' in dir() else 0.5` with explicit `actual_q: float | None = None` parameter.
   - **Estimated effort:** 6 hours. Closes the cross-run learning loop for 5 modules + surfaces 16 silent failure modes.

### Secondary Recommendations (5)

4. Extract magic constants to central config files: `frontier_config.py` (EVALUATOR_WEIGHTS + 5 thresholds), `depth_budget_config.py` (11 thresholds), `evolution_config.py` (5 thresholds), `reentry_config.py` (novelty/evidence thresholds). ~3 hours.
5. Replace `**{**result.__dict__, "hash": h}` dataclass-rebuild pattern with `dataclasses.replace(result, hash=h)` in 8 modules. ~1 hour.
6. Reformat dense one-liners in architecture_evolution.py, depth_budget.py, polycentric_reentry.py, core4_reentry.py to multi-line. ~2 hours.
7. Extract `_downgrade` and `_dossier` from polycentric_reentry.py and core4_reentry.py to a shared `reentry_common.py`. ~1.5 hours.
8. Fix `organization_tournament.py` 6dp-rounding-before-Pareto bug + O(n³) pairwise lookup. ~1 hour.

### Tertiary Recommendations (4)

9. Add `OrganizationPolicyStore` mirroring `PolicyStore` (append-only + CAS promotion).
10. Replace `recursive_improvement`'s `max(0.01, g0_acc)` division guard with explicit zero-baseline handling.
11. Make `depth_budget.eligible_for_policy_learning` a computed field based on gain + streak.
12. Cap `AutonomousExperimentLoop._outcomes` at 1000 entries with FIFO eviction.

---

## Reportable Numbers

- **Total modules:** 16
- **Total impl LOC:** 3,227
- **Total dedicated test LOC:** 720
- **Test ratio:** 0.22
- **Average implementation quality:** 6.81/10
- **Average test coverage:** 2.25/10
- **Average connectivity:** 5.31/10
- **Modules with NO dedicated test file:** 11 of 16 (68.75%) — architecture_search, architecture_synthesis, architecture_evolution, task_conditional_selector, curriculum_generator, autonomous_loop, recursive_improvement, depth_budget, frontier_control_plane, core4_reentry, native_reentry_compiler
- **Modules with dead main classes (never instantiated):** 2 (polycentric_reentry, core4_reentry)
- **Modules with test-only production code (zero production importers):** 1 (organization_legacy)
- **Modules with broken cross-run persistence:** 5 (task_conditional_selector, architecture_search, curriculum_generator, architecture_synthesis, recursive_improvement)
- **Modules with proper cross-run persistence:** 1 (autonomous_loop)
- **Existing tests passing:** 45 tests across 5 dedicated suites, ALL PASS (~0.5s). No regressions.
- **Constitution preserved:** no source files modified, no canonical state touched, no truth effects produced. Pure read-only critical analysis.
