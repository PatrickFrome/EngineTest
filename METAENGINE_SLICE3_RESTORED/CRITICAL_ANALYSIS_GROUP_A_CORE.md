# CRITICAL ANALYSIS — Group A: Core Engine

**Agent:** general-purpose (sub agent) — `crit-A-core`
**Scope:** 14 core modules of `metaengine/` (orchestrator, routing, fusion, claims, disagreement, arbitration, hybrid_mesh, synthesis, adapters/{base,node_native,reference,registry}, cli, constitution, security, storage, util)
**Method:** direct source read of every module + cross-reference of `tests/` directory + import-graph inspection
**Date:** 2026-08-14
**Verdict tone:** brutally honest

---

## Executive Summary

| # | Module | LOC | Impl | Tests | Conn | Value | Avg |
|---|---|---|---|---|---|---|---|
| 1 | orchestrator.py | 810 | 3/10 | 2/10 | 1/10 | 5/10 | **2.8** |
| 2 | routing.py | 132 | 7/10 | 2/10 | 6/10 | 7/10 | **5.5** |
| 3 | fusion.py | 23 | 2/10 | 1/10 | 4/10 | 2/10 | **2.3** |
| 4 | claims.py | 125 | 6/10 | 3/10 | 7/10 | 7/10 | **5.8** |
| 5 | disagreement.py | 48 | 7/10 | 2/10 | 6/10 | 7/10 | **5.5** |
| 6 | arbitration.py | 61 | 7/10 | 2/10 | 5/10 | 7/10 | **5.3** |
| 7 | hybrid_mesh.py | 321 | 6/10 | 3/10 | 6/10 | 7/10 | **5.5** |
| 8 | synthesis.py | 45 | 3/10 | 2/10 | 5/10 | 4/10 | **3.5** |
| 9 | adapters/base.py | 64 | 5/10 | 1/10 | 7/10 | 6/10 | **4.8** |
| 10 | adapters/node_native.py | 56 | 4/10 | 1/10 | 5/10 | 6/10 | **4.0** |
| 11 | adapters/reference.py | 58 | 4/10 | 1/10 | 5/10 | 6/10 | **4.0** |
| 12 | adapters/registry.py | 57 | 6/10 | 1/10 | 6/10 | 6/10 | **4.8** |
| 13 | cli.py | 325 | 4/10 | 1/10 | 6/10 | 5/10 | **4.0** |
| 14 | constitution.py | 290 | 9/10 | 7/10 | 6/10 | 9/10 | **7.8** |
| 15 | security.py | 164 | 7/10 | 5/10 | 8/10 | 8/10 | **7.0** |
| 16 | storage.py | 16 | 5/10 | 0/10 | 3/10 | 4/10 | **3.0** |
| 17 | util.py | 16 | 8/10 | 6/10 | 10/10 | 8/10 | **8.0** |

**Total modules analyzed:** 17 (counting each adapter file separately; the task listed them as item 9 with 4 sub-files).
**Average scores:** Implementation 5.5 · Tests 2.4 · Connectivity 5.7 · Overall value 6.0.
**Average LOC per module:** ~155 (skewed by orchestrator's 810).

### Top 5 Critical Findings (cross-cutting)

1. **`orchestrator.py` is an anti-pattern monument.** One class, one 700-LOC `run()` method, 63 imports, 34 `try/except Exception` blocks (17 of them ending with bare `pass`), hardcoded constitution hash string `'1b6311bd…'`, and a fallback idiom `if 'actual_q' in dir()` to check whether a local variable was bound in a previous `try` block. This is the *hub of the entire system* and it is untestable in unit form. The integration tests (`test_orchestrator_integration.py`) mostly do `assert 'Phase 48' in source` — they are string-scanning the file, not exercising behavior.

2. **`fusion.py` is a 23-line lie.** It is named "fusion" but performs no fusion. It returns a status inventory (`Counter` of statuses + dict of `{engine_id: canonical}` passthrough). The "FUSION_WITHOUT_ERASURE" string is a label, not an algorithm. Every consumer that calls `fuse(contribs)` and expects merged output is silently receiving raw passthrough.

3. **Zero direct unit tests for 14 of the 17 modules.** No `tests/test_routing.py`, `tests/test_fusion.py`, `tests/test_claims.py`, `tests/test_disagreement.py`, `tests/test_arbitration.py`, `tests/test_synthesis.py`, `tests/test_constitution.py`, `tests/test_security.py`, `tests/test_storage.py`, `tests/test_util.py`, `tests/test_cli.py`, or any `tests/adapters/test_*.py`. Coverage exists only indirectly through integration tests (`test_epistemic_coordination.py`, `test_epistemic_core.py`, `test_synthesis_bridge.py`, `test_constitution_kernel.py`, `test_hybrid_mesh.py`). Of these, only `test_hybrid_mesh.py` (53 LOC of tests for 321 LOC source = 17% ratio) and `test_constitution_kernel.py` are real unit tests; the rest are string-scanning or one-assertion sanity checks.

4. **Constitution hash is hardcoded as a magic string in orchestrator.py** (`'1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d'` on lines 439, 564). If the actual `k0_v1.json` constitution file is ever amended (which `constitution.py` correctly forbids), the orchestrator will silently keep using the stale hash. This is a **liveness/safety hazard**.

5. **Adapters dispatch on `engine_id` string equality 12 times in `hybrid_mesh._signals_from_contribution` and 12 more times in `adapters/reference.py`.** Adding `engine_17` requires editing ~24 elif branches across two files. This is a textbook Open/Closed violation and a maintenance trap.

---

## Module-by-Module Analysis

### 1. `orchestrator.py` — 810 LOC, 63 imports

**Purpose:** The single entry point (`MetaOrchestrator.run()`) that wires together routing, mesh, claims, disagreement, arbitration, dialectical graph, evidence graph, frontier control plane, tiered fitness, RLAIF, federation bridge, adaptation bridge, signed provenance, mechanism library, predictive model, causal attribution, uncertainty calibration, failure taxonomy, architecture synthesis, organization tournament, policy generator, cross-world transfer, recursive improvement, cross-run verification, assimilation loop, autonomous loop, cross-model validation, meta-learning, trace extraction, faithfulness testing, and tiered fitness.

**Implementation quality — 3/10.**
- Single 700-line method body. No decomposition into testable units.
- 34 `try/except Exception` blocks. 17 use bare `pass`. Errors are logged to a ledger then swallowed; the caller cannot tell which subsystem failed.
- `if 'actual_q' in dir()` (lines 493, 585, 607, 625, 685) — uses `dir()` to probe local variable bindings across `try` blocks. This is fragile, slow, and unreadable.
- Hardcoded constitution hash `'1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d'` appears twice (lines 439, 563) — drift hazard.
- `except Exception: pass  # predictive model is diagnostic, not blocking` is the pattern repeated ~15 times. The "diagnostic, not blocking" excuse is plausible once, dangerous 15 times.
- Multi-statement one-liners (`a=b if c else d; e=f(g,h); write_json(...)`) everywhere.

**Test coverage — 2/10.** Two test files reference it:
- `tests/test_metaengine.py` (11 LOC, 3 asserts): checks the config file has 16 engines and an invariant flag — does NOT exercise the orchestrator.
- `tests/test_orchestrator_integration.py` (241 LOC, 11 tests): mostly `assert 'Phase 48' in source` and `assert 'REASONING_TRACE_EXTRACTION' in source` — string-scanning, not behavior. The fault-tolerance tests monkey-patch methods to raise, then assert the orchestrator survives. They never assert *correctness* of output.

**Connectivity — 1/10.** Hub module: imports 63 internal modules. Imported by `cli.py`, `parallel_ecology.py`, `real_fitness.py`. Any change here can break the whole system; any failure here takes the whole system down.

**Top 3 weak spots:**
1. The 700-line `run()` method. Untestable, unmaintainable, single point of failure.
2. 17 silent `pass`-on-exception blocks mask every "diagnostic" subsystem failure. A real bug in `MechanismLibrary.load()` would be invisible.
3. The `if 'actual_q' in dir()` idiom — a code smell that signals the author couldn't track local variable scope across `try` blocks. Should be `actual_q = None` initialization at top, then `if actual_q is not None`.

**Top 3 improvements:**
1. **Decompose `run()` into phases** (RoutePhase, PrimaryPhase, InterweavePhase, DeepRoundPhase, ReviewPhase, SynthesisPhase, DiagnosticPhase). Each phase is a class with `execute(state) -> state`. This unlocks unit testing per phase.
2. **Replace `except Exception: pass` with `except Exception as e: ledger.append(run_id, 'SUBSYSTEM_FAILED', {'name': ..., 'error': repr(e)[:200]})`** and a module-level decorator. Stop using `pass`.
3. **Read the constitution hash from disk** (`constitution.constitution_hash(self.root)`) instead of hardcoding `'1b6311bd…'`. Add a startup assertion that the hardcoded value matches the loaded one.

**Replacement alternative:** The orchestrator is a workflow engine. Real options: **Prefect**, **Dagster**, **Apache Airflow**, or **Temporal**. Each supports retries, observability, and per-step testing. The current `run()` is a poor man's DAG that none of the team can reason about.

---

### 2. `routing.py` — 132 LOC

**Purpose:** `CapabilityRouter.plan(input_path, mode) -> routing_plan`. Reads the input text, fingerprints it against 9 domain signals (PHILOSOPHICAL_HERMENEUTICS, EVIDENCE_RESEARCH, etc.), scores each of 16 engines, and assigns a role (CORE / SPECIALIST / CHALLENGER / RESERVE_REVIEW) — *never* drops an engine in FULL_16X mode.

**Implementation quality — 7/10.**
- Clean separation: fingerprint → score → role. Deterministic and reproducible.
- `ROLE_THRESHOLDS = ((0.58,'CORE'),(0.36,'SPECIALIST'),(0.20,'CHALLENGER'),(-1.0,'RESERVE_REVIEW'))` and the `next(role for threshold,role in ROLE_THRESHOLDS if score>=threshold)` idiom is fine because `-1.0` is the catch-all. But it would raise `StopIteration` if all thresholds were positive — fragile.
- `_engine_score` mixes domain coverage, lineage bonus (+0.12 for `engine_01..04`), and reproducibility penalty (×0.88 for failed native tests) into a single number. Magic weights, no calibration.
- `routing_version='16X-FRONTIER-EVIDENCE-CONTROL-2.2'` is a string literal that must match consumers' expectations.

**Test coverage — 2/10.** Only `test_epistemic_coordination.py` touches it, and only via the orchestrator. No unit test for `fingerprint`, `_engine_score`, or `plan`. Boundary cases (empty input, all-zero scores, 10000-token input) are untested.

**Connectivity — 6/10.** Leaf-ish. Imported by `orchestrator.py`, `cli.py`, `experiment_routing_bridge.py`. No internal imports except `.util`.

**Top 3 weak spots:**
1. Magic constants: `0.58`, `0.36`, `0.20`, `0.12`, `0.88`, `0.34`, `0.18`, `0.08`, `0.07`, `0.55`, `2500`, `1200`. None are named or calibrated. Behavior is opaque.
2. `DOMAIN_SIGNALS` keyword lists are English-only (with a few Heidegger-German loanwords like `sein`, `beyng`). Russian negation handling lives in `claims._base_key`, not here — inconsistent.
3. Hardcoded `engine_01..engine_04` list on line 85 ("Native Destruktion lineages are always relevant as epistemic challengers"). Adding engine_17 would require editing this file plus `hybrid_mesh.ENGINE_PRIMITIVES` plus 6 other files.

**Top 3 improvements:**
1. Extract thresholds and bonuses to a `routing_config.json` so they can be tuned without code changes.
2. Add `tests/test_routing.py` with at least: empty input, single-domain input, all-engine-failed-native-test input, and a property-based test that `len(assignments)==16` always.
3. Replace the `engine_01..04` magic list with a `is_core_challenger` flag in `config/meta_engine.json`.

**Replacement alternative:** **LangChain's RouterChain** or **LlamaIndex's RouterQueryEngine** for LLM-aware routing; **durable-rules** or **python-rule-engine** for declarative rule scoring. The current implementation is fine for a research project but would not scale to a production router.

---

### 3. `fusion.py` — 23 LOC

**Purpose:** `fuse(contribs) -> dict`. Supposedly fuses engine contributions without erasing native positions.

**Implementation quality — 2/10.**
- The function does NOT fuse anything. It returns a status inventory:
  - `complete_engines`, `degraded_engines`, `failed_engines`, `reference_simulation_engines`, `real_executor_engines` (all lists of engine_ids)
  - `complementary = {engine_id: c.canonical}` — a passthrough dict, NOT a merge
  - `conflicts` is `[]` unless any engine failed/degraded, in which case it's a single dict `{'dimension':'execution_status','resolution':'UNRESOLVED_OPERATIONAL_DIFFERENCE'}`
- The `'FUSION_WITHOUT_ERASURE'` policy is a string label, not an algorithm.
- `defaultdict` imported but unused.
- `Counter` is the only collection actually exercised.

**Test coverage — 1/10.** `tests/test_epistemic_core.py` references it; no direct unit test.

**Connectivity — 4/10.** Imported by `orchestrator.py` (twice — for primary and final fusion) and `test_epistemic_core.py`. Internal imports: only `Counter, defaultdict` from stdlib.

**Top 3 weak spots:**
1. **The function does not perform fusion.** Despite the name and the elaborate `claim_ceiling` string, it returns passthrough data. Callers that expect merged content are silently getting nothing.
2. `complementary = {c.engine_id: c.canonical for c in contribs}` will overwrite if the same engine_id appears twice (e.g. from primary + deep rounds). Last-write-wins by accident, not by design.
3. The single conflict entry `'UNRESOLVED_OPERATIONAL_DIFFERENCE'` is the only "fusion logic". No actual resolution is attempted.

**Top 3 improvements:**
1. Either rename to `inventory.py` and document that it produces a status inventory (not a fusion), OR implement actual fusion: union of claims, conflict detection per-proposition, evidence-strength aggregation per source_ref.
2. If keeping it as inventory, drop `defaultdict` import and the misleading `complementary` name.
3. Add `tests/test_fusion.py` covering: all-COMPLETE input, mixed-status input, duplicate engine_ids, empty contribs.

**Replacement alternative:** If actual fusion is needed: **ensemble methods** (voting/weighted), **retrieval-augmented answer synthesis** (RAG fusion), or **Debate-style RLHF** methods. The current stub is none of these.

---

### 4. `claims.py` — 125 LOC

**Purpose:** `extract_positions(contrib)` extracts claim dicts from an engine contribution (handling claims, graph edges, research trees, perspectives, research questions, gaps, workflow plans). `ClaimGraphBuilder.build(contributions, hybrid_mesh)` groups positions by `proposition_key` and links them by shared `source_ref`.

**Implementation quality — 6/10.**
- Good defensive coding: `_claim` returns `None` on empty text, the build pipeline filters `None`.
- `_base_key` does conservative negation normalization — strips `not/no/never/cannot/can't/не/нет/никогда/нельзя` then takes first 48 tokens. This is purely lexical; "X is good" and "X is not bad" will NOT be grouped.
- Representative selection: `max(ps, key=lambda p:(len(p['source_refs']), p['evidence_strength'], len(p['proposition'])))` — arbitrary tiebreaker.
- Engine-specific fallback chain (graph edges → research trees → perspectives → questions → gaps → workflow plans) is well-commented but hardcoded.
- Edge construction: shared `source_ref` only. No semantic similarity, no embedding-based grouping.

**Test coverage — 3/10.** Two integration test files (`test_epistemic_coordination.py`, `test_epistemic_core.py`) exercise it through the orchestrator. No direct unit test of `_base_key`, `_claim`, or `extract_positions`.

**Connectivity — 7/10.** Imported by `orchestrator.py`, `hybrid_mesh.py`, `test_epistemic_coordination.py`, `test_epistemic_core.py`. Internal imports: `.util`.

**Top 3 weak spots:**
1. Lexical-only proposition keying. "The cat is on the mat" and "A feline sits on a rug" will never group even if semantically identical.
2. Russian-negation handling is in `_base_key` but no other language's negation. English + Russian only.
3. The 6-branch fallback in `extract_positions` (graph → tree → perspectives → questions → gaps → plan) is a priority chain with no configuration. If a contribution has both graph edges AND research questions, only graph edges survive.

**Top 3 improvements:**
1. Add embedding-based proposition keying as an optional secondary grouping pass: hash the embedding (e.g. MiniLM) of the proposition to a 16-char key, and merge groups whose embeddings are within cosine 0.85.
2. Extract the fallback priority chain to a config so it can be reordered per-experiment.
3. Add `tests/test_claims.py` with cases for: empty contribution, contribution with all 6 fallback types, two contributions with same proposition but different stance, propositions with shared source_ref.

**Replacement alternative:** **arg-mapping libraries** (e.g. AMF, Argkit) for argumentation theory; **sentence-transformers** + faiss for semantic proposition clustering. Current lexical approach is from the 1990s.

---

### 5. `disagreement.py` — 48 LOC

**Purpose:** `DisagreementEngine.analyze(claim_graph, routing_plan, hybrid_mesh)` finds nodes with both POSITIVE and NEGATIVE stances (material conflict) or POSITIVE/NEGATIVE + UNCERTAIN (assertion uncertainty), and assigns a tension score.

**Implementation quality — 7/10.**
- Compact and focused. The tension formula `0.50*severity + 0.28*breadth + 0.12*(1-source_density) + 0.10*core_challenger` is at least documented by the variable names.
- `_side` maps stance → side. Re-defines `POS` and `NEG` sets that are also defined in `arbitration.py` and `claims.py` — duplication.
- Returns sorted conflicts by `(-tension_score, disagreement_id)` — deterministic, good.

**Test coverage — 2/10.** Only integration tests. No unit tests of the tension formula, the threshold `0.72`/`0.5` for HIGH/MEDIUM/LOW priority, or the `material` vs `uncertainty` classification.

**Connectivity — 6/10.** Imported by `orchestrator.py`, `test_epistemic_coordination.py`, `test_epistemic_core.py`. Internal imports: `.util`.

**Top 3 weak spots:**
1. Magic coefficients `0.50, 0.28, 0.12, 0.10` and thresholds `0.72, 0.5`. No calibration, no justification.
2. `POS`/`NEG` set duplicated across `disagreement.py`, `arbitration.py`, `claims.py`. If you add a stance to one, you must remember the others.
3. `breadth = min(1.0, len(engines)/4)` — `4` is a magic constant. A conflict involving 5 engines is "max breadth".

**Top 3 improvements:**
1. Move `POS`/`NEG`/`UNCERTAIN` to a shared `stances.py` module; import everywhere.
2. Move coefficients to `config/disagreement_weights.json` so they can be tuned per-experiment without code changes.
3. Add `tests/test_disagreement.py` with cases: zero conflicts, pure material conflict, pure uncertainty conflict, mixed, high-tension (>0.72), low-tension (<0.5).

**Replacement alternative:** **Abstract Argumentation Framework** (Dung 1995) — `argparse`, `aspartix`, `pyarg`. The current tension score is a hand-rolled heuristic; AAF has a real theory of acceptability.

---

### 6. `arbitration.py` — 61 LOC

**Purpose:** `AdaptiveArbitrator.arbitrate(claim_graph, disagreements, routing_plan, reviews, hybrid_mesh)` produces a `state` per claim node from a 7-branch decision tree: UNRESOLVED_RESEARCH_PRIORITY / QUALIFIED_UNRESOLVED / GENERATIVE_ONLY / PROVISIONALLY_SUPPORTED / SUPPORTED_BUT_REVIEW_REQUIRED / INSUFFICIENT_EVIDENCE / ABSTAIN.

**Implementation quality — 7/10.**
- Clean decision tree, well-named states.
- `majority_vote_used: False` is hardcoded on every decision — explicit constitution compliance.
- Follow-up portfolio routes HIGH-priority conflicts to challenger engines. Good design.
- `evidence >= 0.65` threshold is magic.
- `generative_only = bool(ps) and not truth_positions` — clean.
- `c['disagreement_id'] if c else None` — defensive against missing conflicts_by_claim.

**Test coverage — 2/10.** Integration tests only. None of the 7 state branches has a unit test.

**Connectivity — 5/10.** Imported by `orchestrator.py`, `test_epistemic_coordination.py`, `test_epistemic_core.py`. Internal imports: `.util`.

**Top 3 weak spots:**
1. `evidence >= 0.65` is the single threshold separating PROVISIONALLY_SUPPORTED from SUPPORTED_BUT_REVIEW_REQUIRED. No calibration.
2. `high = [c for c in disagreements.get('conflicts',[]) if c['research_priority']=='HIGH']` and then `candidates[:6]` — picks top 6 engines by review_priority. Magic `6`.
3. No way to override the arbitration policy per-domain. A philosophical-hermeneutics claim and an evidence-research claim get the same threshold.

**Top 3 improvements:**
1. Make `0.65` configurable in `config/arbitration_policy.json` with per-domain overrides.
2. Add `tests/test_arbitration.py` with 7 cases, one per state branch.
3. Document the relationship between `arbitration.decisions[].state` and `synthesis.arbitrated_supported_claims` — currently `synthesis.py` filters on `{'PROVISIONALLY_SUPPORTED', 'SUPPORTED_BUT_REVIEW_REQUIRED'}` which is a duplicated constant.

**Replacement alternative:** **Toulmin model** implementations; **defeasible reasoning** libraries (e.g. `defeasible`). The current state machine is a reasonable hand-rolled approximation.

---

### 7. `hybrid_mesh.py` — 321 LOC, 53 test LOC

**Purpose:** `ArchitectureInterweave.weave(contributions, routing_plan, source_text, preserve_agenda)` produces a typed signal bus, a complete 16×15=240 directed bridge matrix, 6 overlapping hybrid organs, a research agenda, and cross-architecture traces.

**Implementation quality — 6/10.**
- Most-tested module in this group: 4 unit tests in `test_hybrid_mesh.py` (still only 53 LOC of tests for 321 LOC source = 17% ratio — woefully low).
- `ENGINE_PRIMITIVES` (16 engines × 4 primitives = 64) and `HYBRID_ORGANS` (6 organs) are hardcoded module-level dicts. Adding `engine_17` requires editing this file plus routing.py plus 5 others.
- `_signals_from_contribution` has 12 elif branches on `eid == 'engine_05'`, `'engine_06'`, …, `'engine_16'`. Textbook Open/Closed violation.
- `_bridge_mode` returns `('DIRECT_TYPED_REUSE', direct)` or `('CONTEXT_OR_CRITIQUE_PROJECTION', [])`. The bridge matrix is always 240 entries — even when no signals exist.
- Agenda merging logic (`preserve_agenda`) is correct but complex (lines 241-256).
- `_text_tokens` regex covers Latin + Cyrillic only. CJK, Arabic, etc. excluded.
- `derived_truth_promotion_violations` counter is computed correctly. Good safety property.

**Test coverage — 3/10.** 4 unit tests covering: pairwise mesh completeness, organ coverage, no truth promotion, multi-engine agenda. Missing: signal extraction per engine_id, bridge mode classification, agenda preservation across recursive weaves, trace completeness.

**Connectivity — 6/10.** Imported by `orchestrator.py` and `test_hybrid_mesh.py`. Internal imports: `.util`, `.claims.extract_positions`.

**Top 3 weak spots:**
1. The 12-elif engine dispatch in `_signals_from_contribution`. Adding `engine_17` is a code change, not a config change.
2. Bridge matrix is O(N²) — always 240 entries even when most engines emit zero signals. Doesn't scale past 16.
3. `_text_tokens` regex is Latin+Cyrillic only. For a system named after Heidegger (German) the German umlauts work via Latin-1 supplement, but CJK inputs are silently dropped from salient-term extraction.

**Top 3 improvements:**
1. Extract engine-specific signal extraction to a registry: `SIGNAL_EXTRACTORS = {'engine_05': _extract_memory, 'engine_06': _extract_graph, ...}`. Each extractor is a small function. Adding a new engine = adding a new function + one dict entry.
2. Add `tests/test_hybrid_mesh.py` cases for: empty contributions, single-engine contribution, recursive weave with `preserve_agenda` (assert monotonic growth), CJK source text.
3. Replace `_text_tokens` with a Unicode-aware tokenizer (`regex` module, or `spacy` if available).

**Replacement alternative:** A typed message bus (**protobuf** + **NATS**/**Redis Streams**) for the signal bus; an actor framework (**Ray**, **Dapr**) for engine dispatch. The current 240-bridge matrix is a static declaration, not a runtime topology.

---

### 8. `synthesis.py` — 45 LOC

**Purpose:** `AuditableSynthesizer.synthesize(dialectical_graph, arbitration, verifier_report)` produces a synthesis dict that groups dialectical graph nodes by `operator` and splits arbitration decisions into supported vs unresolved.

**Implementation quality — 3/10.**
- The class is named `AuditableSynthesizer` but performs no synthesis. It groups nodes by `operator` (SOURCE_READING, RIVAL_FORK, HORIZON_DISCLOSURE, …) and exposes them as fields.
- `truth_effect: "NONE_BEYOND_EXISTING_ARBITRATION"` — honest, but means the function is a no-op pass-through.
- `limitations` is a hardcoded list of 3 strings.
- `synthesis_hash = canonical_hash(result)` includes the hash in the result — fragile (must exclude self when computing, which it does by computing before assignment).
- Static method — no state, no instance behavior. Could be a module-level function.

**Test coverage — 2/10.** Four test files reference it (test_constitution_property_based, test_controlled_learning_2_3, test_epistemic_core, test_synthesis_bridge) — all integration. No unit test.

**Connectivity — 5/10.** Imported by `orchestrator.py`, `test_synthesis_bridge.py`, and 2 others. Internal imports: `.util.canonical_hash`.

**Top 3 weak spots:**
1. No actual synthesis. The function is a relabeling.
2. The 11 operator names (SOURCE_READING, RIVAL_FORK, HORIZON_DISCLOSURE, SEMANTIC_COUNTERFACTUAL, GENEALOGICAL_RETURN, EVIDENCE_DISCRIMINATOR, DOUBLE_HERMENEUTIC, SUBLATION_WITH_RESIDUE, OPERATOR_MUTATION, SOURCE_RETURN, UNKNOWN) are hardcoded strings, duplicated between `dialectical_graph.py` (presumably) and here.
3. The `external_verification_status` field is a passthrough from `verifier_report.get('verification_status')` — no validation.

**Top 3 improvements:**
1. If the function is genuinely just a relabeling, rename to `synthesize_auditable_view` and document it as such. Or implement actual synthesis: combine supported claims into a coherent narrative using an LLM with explicit abstention.
2. Move operator names to an `enum` in `dialectical_graph.py` and import here.
3. Add `tests/test_synthesis.py` with cases: empty graph, all-supported, all-unresolved, mixed.

**Replacement alternative:** None directly — "nonlinear dialectical synthesis" is not a commodity problem. If LLM-assisted synthesis is acceptable, use a structured-generation library (**Outlines**, **instructor**, **guardrails-ai**) to enforce the auditable schema.

---

### 9. `adapters/base.py` — 64 LOC

**Purpose:** `EngineContribution` dataclass (12 fields) and `Adapter` abstract base class with `run` (raises NotImplementedError) and `review` (default implementation that produces a review dict from coordination state).

**Implementation quality — 5/10.**
- `EngineContribution` has 12 fields with sensible defaults — OK.
- `Adapter.run` raises `NotImplementedError` — proper abstract method.
- `Adapter.review` returns a hardcoded dict with 14 keys. No schema, no dataclass, just a dict.
- The default `review` implementation does string-based role dispatch (`role in ('CORE','CHALLENGER')` → 6 conflicts; else 3).
- `selected = conflicts[:6] if role in ('CORE','CHALLENGER') else conflicts[:3]` — magic 6 and 3.
- `state` calculation is a nested ternary: `'CHALLENGE_UNRESOLVED' if selected and role=='CHALLENGER' else ('REVIEW_CONFLICTS' if selected else ('REVIEW_HYBRID_AGENDA' if agenda else 'ACKNOWLEDGED'))` — readable but ugly.

**Test coverage — 1/10.** `test_hybrid_mesh.py` imports `EngineContribution` to build fakes. No unit test of `Adapter.review`.

**Connectivity — 7/10.** Imported by `orchestrator.py`, `hybrid_mesh.py`, `adapters/node_native.py`, `adapters/reference.py`, `adapters/registry.py`, `test_hybrid_mesh.py`. Internal imports: none (stdlib only).

**Top 3 weak spots:**
1. `Adapter.review` returns an unstructured dict. Callers must know the key names. No type safety.
2. `EngineContribution` has no validation. A status of `'WHATEVER'` is silently accepted.
3. The `state` ternary chain has 4 branches but only 3 distinct outcomes (`'CHALLENGE_UNRESOLVED'` requires `selected and role=='CHALLENGER'`; `'REVIEW_CONFLICTS'` requires `selected` and role != CHALLENGER; etc.). Easy to get wrong.

**Top 3 improvements:**
1. Convert `Adapter.review` return to a `ReviewResult` dataclass.
2. Add `engine_contribution_status` as an `Enum` (`COMPLETE`, `DEGRADED`, `FAILED`, `REFERENCE_SIMULATION_COMPLETE`, `ABSTAIN`, `UNRESOLVED`).
3. Add `tests/adapters/test_base.py` covering the 4 `state` branches.

**Replacement alternative:** **pydantic** for the dataclass with validation; **pluggy** or **stevedore** for the adapter plugin system. The current hand-rolled `Adapter` base is fine but untyped.

---

### 10. `adapters/node_native.py` — 56 LOC

**Purpose:** `NodeNativeAdapter` runs a Node.js subprocess (`bin/destruktion.mjs` or `bin/destruktion-unified.mjs`) under `run_sandboxed`, parses output JSON, and extracts claims from `records/*.json` artifacts.

**Implementation quality — 4/10.**
- `_find_root` does `for p in self.root.rglob('package.json'): if 'lineages' not in p.parts[len(self.root.parts):] or self.record['engine_id']!='engine_03': return p.parent` — confusing and probably wrong. The condition `'lineages' not in p.parts` is True for the FIRST package.json outside `lineages/`, but the `or engine_id != 'engine_03'` makes it return immediately for any non-engine_03 engine. This looks like a bug masked by the test data.
- `_claims` reads `records/*.json` and extracts `from_node`/`to_node` descriptions with hardcoded stance mapping (`'HYPOTHETICAL'/'POSSIBLE'` → PROPOSE, `'ASSERTED'/'NECESSARY'` → ASSERT).
- The single `EngineContribution(...)` constructor call on line 53 has 13 positional arguments. Easy to get the order wrong; no IDE support for which arg is which.
- `except Exception as e: return EngineContribution(... 'FAILED', ...)` — catches everything, masks bugs.
- `verify_release_file(project_root, root/'package.json')` is called on every run — O(N) scan of `SHA256SUMS.txt` per file per run.

**Test coverage — 1/10.** No direct test.

**Connectivity — 5/10.** Imported by `adapters/registry.py` and `orchestrator.py`. Internal imports: `.base`, `..security`.

**Top 3 weak spots:**
1. `_find_root` logic is wrong or at minimum unreadable. The `or` short-circuits in a way that probably doesn't match intent.
2. 13-positional-arg `EngineContribution(...)` call is fragile.
3. Broad `except Exception` masks subprocess errors, JSON parse errors, file-not-found, and permission errors as a single 'FAILED' status.

**Top 3 improvements:**
1. Use keyword arguments for the `EngineContribution(...)` call: `EngineContribution(engine_id=..., status=..., native=..., canonical=..., ...)`.
2. Decompose `_find_root` into a clear two-step: (a) find all package.json under root; (b) pick the right one based on engine_id. Add a docstring.
3. Add `tests/adapters/test_node_native.py` with a mocked subprocess.

**Replacement alternative:** **plumbum** or **sh** for cleaner subprocess wrapping; **structlog** for structured logging of subprocess failures.

---

### 11. `adapters/reference.py` — 58 LOC

**Purpose:** `ReferenceAdapter` dynamically loads `src/reference_skeleton.py` and dispatches on `engine_id` (12 elif branches) to produce reference-simulation canonical output for each of the 16 engines.

**Implementation quality — 4/10.**
- `_load(path)` does `importlib.util.spec_from_file_location` + `spec.loader.exec_module` — arbitrary code execution from a file path. Path is internal (`rglob('src/reference_skeleton.py')`), so not attacker-controlled in practice, but the pattern is dangerous.
- 12 elif branches for `eid == 'engine_05'`, `'engine_06'`, …, `'engine_16'`. Same Open/Closed violation as `hybrid_mesh._signals_from_contribution`.
- `verify_release_file(project_root, sk); verify_release_file(project_root, cfgp)` — two O(N) SHA256SUMS scans per run.
- `idx.units[str(i)] = mod.TextUnit(str(i),'input',s)` — iterates `sents[:80]`. Magic `80`.
- `salient = [w for w in sorted(freq,key=lambda x:(-freq[x],x)) if len(w)>4][:12]` — magic `4` and `12`.
- `except Exception as e: return EngineContribution(eid, 'FAILED', ...)` — masks all errors.
- The adapter is documented as `CLEAN_ROOM_CONTRACT_STUB` — honest about being a simulation.

**Test coverage — 1/10.** No direct test.

**Connectivity — 5/10.** Imported by `adapters/registry.py`, `orchestrator.py`. Internal imports: `.base`, `..security`.

**Top 3 weak spots:**
1. 12-elif engine dispatch — adding `engine_17` requires editing this file.
2. Dynamic `importlib` execution of a Python file from a path — security smell, even if not exploitable today.
3. Magic constants `80`, `4`, `12`, `6`, `5`, `8` scattered through the function.

**Top 3 improvements:**
1. Extract per-engine reference logic to a registry of small functions, like `hybrid_mesh` should do.
2. Replace `importlib.util.spec_from_file_location` with a proper module import (e.g. `from . import reference_skeleton`).
3. Move magic constants to `config/reference_architecture.json`.

**Replacement alternative:** **pluggy** for the per-engine dispatch; **hypothesis** for property-based testing of the reference contract.

---

### 12. `adapters/registry.py` — 57 LOC

**Purpose:** `AdapterRegistry.create(record, lineage_root)` dispatches on `record['execution_mode']` (`NODE_NATIVE`, `NODE_UNIFIED`, `PYTHON_REFERENCE_CONTRACT`, `LLM_MODEL`) to construct the right adapter. `disclosure(record)` returns the adapter kind/level.

**Implementation quality — 6/10.**
- Simple dict dispatch — clean.
- `LLM_MODEL` mode stores `None` for `adapter_cls` and special-cases it before `adapter_cls(record, lineage_root)` is called. The comment explains it, but the sentinel-None pattern is fragile.
- `_build_llm_config` reads 7 fields from `record` with hardcoded defaults (`'llama3.2'`, `2048`, `0.7`, `120.0`, `'OLLAMA_API_KEY'`). Could be a dataclass with `from_record` classmethod.
- `disclosure` raises `ValueError` for unknown mode — fail-closed, good.
- `silent_fallback_allowed: False` — explicit constitution compliance.

**Test coverage — 1/10.** No direct test.

**Connectivity — 6/10.** Imported by `orchestrator.py`. Internal imports: `.node_native`, `.reference`, `.base`.

**Top 3 weak spots:**
1. `LLM_MODEL: (None, "LLM_MODEL", "REAL_LLM_EXECUTOR")` — the None sentinel requires special-casing in `create()`. If someone forgets the special case, `None(record, lineage_root)` raises `TypeError: 'NoneType' object is not callable` with no helpful message.
2. `_build_llm_config` is a static method but reads from `record` (passed in). It's really a free function.
3. `LLMModelAdapter` is imported lazily inside `create()` — circular import avoidance. Works but obscures the dependency graph.

**Top 3 improvements:**
1. Replace the `None` sentinel with a callable factory: `"LLM_MODEL": (lambda r,lr: LLMModelAdapter(r, lr, AdapterRegistry._build_llm_config(r)), "LLM_MODEL", "REAL_LLM_EXECUTOR")`. Or just make `LLM_MODEL` dispatch like the others and require `record['llm_config']` to be passed in.
2. Make `_build_llm_config` a module-level function or a `@classmethod LLMModelConfig.from_record(record)`.
3. Add `tests/adapters/test_registry.py` with cases for each mode + unknown mode + LLM_MODEL with missing fields.

**Replacement alternative:** **pluggy** or **stevedore** for entry-point-based plugin discovery. The current dict dispatch is fine for 4 modes but won't scale to plugin-style extensibility.

---

### 13. `cli.py` — 325 LOC

**Purpose:** `main()` parses argparse subcommands (`run`, `route`, `replicate`, `engines`, `capabilities`, `biographies`, `topologies`, `frontier-patterns`, `parallel-benchmark`, `parallel-worlds`, `parallel-ablation`, `parallel-topologies`, `evolve`, `active-policy`, `rollback-policy`) and dispatches.

**Implementation quality — 4/10.**
- `check_development_gate` and `produce_stage_gate_summary` are well-factored (good).
- `main()` is a 70-line `if/elif a.cmd == ...` chain. Hard to test, hard to extend.
- Only `run` enforces the development gate. `route`, `replicate`, `evolve`, `rollback-policy` bypass it — inconsistent.
- `print(json.dumps(result, ensure_ascii=False, indent=2))` is repeated 12 times. Should be a `print_json(result)` helper.
- `Path(__file__).resolve().parents[1]` for `root` — fragile if the file is moved.
- `--receipt` is required for `run` but the help text doesn't say what happens if it's missing (it raises `GateCheckError`).
- `replicate` calls `replicate_run(a.run_dir, a.backend)` and wraps the result in a list before printing. Inconsistent with other commands.

**Test coverage — 1/10.** No `tests/test_cli.py`. The CLI is exercised only via subprocess in end-to-end tests (if any).

**Connectivity — 6/10.** Imported by `metaengine/__main__.py` (presumably) and external scripts. Internal imports: 9 modules.

**Top 3 weak spots:**
1. The 13-branch `if/elif a.cmd == ...` chain in `main()`. Each branch is 1-5 lines of dispatch logic.
2. Only `run` enforces the gate. `evolve`, `rollback-policy`, and `parallel-*` commands bypass it.
3. No `--version`, no `--verbose`, no `--dry-run`, no logging configuration.

**Top 3 improvements:**
1. Convert each subcommand to a function (`cmd_run(args, root)`, `cmd_route(args, root)`, …) and dispatch via a dict. Each function is independently testable.
2. Enforce the development gate for all write-commands (`run`, `evolve`, `rollback-policy`), not just `run`.
3. Add `tests/test_cli.py` with `subprocess.run([sys.executable, '-m', 'metaengine', 'route', input])` for each subcommand.

**Replacement alternative:** **Typer** (built on Click) or **Fire** — auto-generates help, type-hint-aware, much less boilerplate. The current argparse code is 325 LOC; Typer would be ~120.

---

### 14. `constitution.py` — 290 LOC

**Purpose:** Defines the constitution kernel: 12 immutable K0 invariants, K1 topics, amendment boundary. `load_constitution_kernel(root)` loads and validates. `verify_constitution_conformance(root)` cross-checks enforcement_refs and test_refs against real files.

**Implementation quality — 9/10.**
- Best-structured module in the group. Frozen dataclasses, explicit validation, hashable.
- `_REQUIRED_K0_IDS` is a frozenset of 12 — enforced at load time.
- `_load_k0` raises `ValueError('CONSTITUTION_K0_DUPLICATE_INVARIANT')`, `CONSTITUTION_K0_SET_MISMATCH` — clear error codes.
- `_ref_path` uses `candidate.relative_to(root)` to prevent path traversal — good security.
- `require_amendment_authority` raises `RuntimeError('CONSTITUTION_AMENDMENT_AUTHORITY_NOT_IMPLEMENTED')` — explicit fail-closed.
- `verify_constitution_conformance` checks that every enforcement_ref and test_ref points to a real file.
- `_load_k1` enforces `boundary.ordinary_evolution_allowed` is False and `authority_status == 'NOT_IMPLEMENTED'` — constitution is genuinely immutable.

**Test coverage — 7/10.** Four test files reference it: `test_constitution_kernel.py`, `test_constitution_property_based.py`, `test_organization_legacy.py`, `test_rlaif_trainer.py`. The first two are real unit tests.

**Connectivity — 6/10.** Imported by `orchestrator.py`, `cli.py` (via devfabric), `test_constitution_kernel.py`, `test_constitution_property_based.py`, `test_rlaif_trainer.py`. Internal imports: `.util`.

**Top 3 weak spots:**
1. The hardcoded constitution hash `'1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d'` in `orchestrator.py` should be replaced by a call to `constitution.constitution_hash(self.root)`. Right now, if the constitution file changes (it shouldn't, but if it does), the orchestrator will silently use the stale hash.
2. `_load_k0` does `set(ids) != set(_REQUIRED_K0_IDS)` — set equality, so order doesn't matter. But `_load_k1` does `len(topics) != len(set(topics))` for duplicate detection, then `tuple(sorted(topics))` for canonical ordering. Asymmetric handling.
3. `verify_constitution_conformance` is O(N×M) — for each entry, walk all enforcement_refs and test_refs and stat each file. For 12 invariants × 5 refs each = 60 stat calls. Fine for now but won't scale.

**Top 3 improvements:**
1. Add a startup assertion in `orchestrator.py` that `constitution_hash(self.root) == '1b6311bd…'` and fail loud if they diverge.
2. Cache `_ref_path` results in `verify_constitution_conformance` — many refs probably point to the same file.
3. Add a property-based test (`hypothesis`) that generates random K0 JSON and asserts `load_constitution_kernel` either succeeds or raises one of the documented error codes.

**Replacement alternative:** **pydantic** for the dataclasses with validation; this would simplify `_nonempty_text`, `_load_k0`, `_load_k1`. The current code is already good; pydantic would just make it shorter.

---

### 15. `security.py` — 164 LOC

**Purpose:** Immutable guardrails + handoff verification, secret scanning (text + bytes), untrusted-input classification, release-file integrity verification, sandboxed subprocess execution.

**Implementation quality — 7/10.**
- `IMMUTABLE_GUARDRAILS` is a tuple of 6 strings, hashed at module load. `IMMUTABLE_GUARDRAIL_HASH` is the canonical hash. Good.
- `verify_handoff` checks handoff hash, guardrail completeness, and objective presence. Fail-closed via `SecurityViolation`.
- `scan_secret_bytes` covers private keys, OpenAI-style keys, postgres URIs. Missing: AWS access keys, GCP service accounts, Azure secrets, GitHub PATs, Slack tokens.
- `redact_secrets` uses 2 regex patterns only — extremely basic. Will miss most real secrets.
- `classify_untrusted_input` has 3 marker regexes (instruction_override, credential_request, tool_escalation). Will miss most prompt-injection patterns.
- `verify_release_file` walks `SHA256SUMS.txt` linearly — O(N) per file. No caching.
- `run_sandboxed` uses `start_new_session=True` + `os.killpg(SIGKILL)` on timeout — honest comment: "This is a resource boundary, not a complete OS/network sandbox."
- `legacy_guardrail_set_status` for backwards-compat with the 2.3 release — pragmatic.

**Test coverage — 5/10.** Five test files reference it: `test_architecture_policy.py`, `test_constitution_kernel.py`, `test_constitution_property_based.py`, `test_controlled_learning_2_3.py`, `test_p1_fixes.py`. Mostly indirect.

**Connectivity — 8/10.** Imported by 11 internal modules — a true utility hub. Internal imports: `.util`.

**Top 3 weak spots:**
1. `redact_secrets` has only 2 regex patterns. Real secret scanners have dozens. Will miss AWS, GCP, Azure, GitHub, Slack, etc.
2. `classify_untrusted_input` has only 3 marker categories. Will miss encoded prompt injection (base64, unicode tricks), multilingual injection, role-play-style injection.
3. `verify_release_file` walks `SHA256SUMS.txt` linearly per file. With N files in a release, that's O(N²). Build a `{relative_path: digest}` dict once.

**Top 3 improvements:**
1. Replace `redact_secrets` + `scan_secret_bytes` with **detect-secrets** (Yelp) or **truffleHog**. They cover dozens of secret types and are battle-tested.
2. Replace `classify_untrusted_input` with **guardrails-ai** or **Lakera Guard** for prompt-injection detection. The 3-regex approach is from 2019.
3. Add `tests/test_security.py` with cases for each secret type, each marker type, each release-file edge case (missing file, tampered file, missing inventory entry).

**Replacement alternative:** **detect-secrets** (secret scanning), **guardrails-ai** or **Lakera** (prompt injection), **firejail** or **bubblewrap** (real OS sandboxing), **sigstore** (release signing). The current module is a reasonable MVP but should be replaced before production.

---

### 16. `storage.py` — 16 LOC

**Purpose:** `LocalLedger.append(run_id, kind, payload, engine_id, parent_event_ids)` writes a JSONL event to `events.jsonl`.

**Implementation quality — 5/10.**
- Tiny, focused. Single class, single method.
- JSONL append is the right format for an audit log.
- `self.seq += 1` is in-memory only — restarts lose sequence continuity. If two processes append concurrently, they'll both start at seq=0.
- No file locking — concurrent writers will corrupt the JSONL.
- No rotation, no size cap — `events.jsonl` grows unbounded.
- `canonical_hash(payload)` is computed but never verified on read — there's no read method at all.
- `now()` returns `time.time()` (float seconds since epoch) — not ISO 8601, not UTC-explicit.

**Test coverage — 0/10.** No test file references it directly. It's exercised only via the orchestrator.

**Connectivity — 3/10.** Imported only by `orchestrator.py`. Internal imports: `.util`.

**Top 3 weak spots:**
1. `self.seq` is in-memory. Restart loses sequence. Two processes → duplicate seqs.
2. No file locking. Concurrent `ledger.append` from two orchestrator runs will corrupt the JSONL.
3. No read method — no replay, no query. The ledger is write-only.

**Top 3 improvements:**
1. Replace with SQLite (the project already uses SQLite in `federation_bridge.py`). `CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, kind TEXT, payload JSON, engine_id TEXT, parent_event_ids JSON, created_at REAL)`. Concurrent-safe, queryable, no rotation needed.
2. Add `read_events_since(seq, kind_filter=None) -> Iterator[dict]` for replay.
3. Add a `rotate(max_bytes=100_000_000)` method that renames `events.jsonl` to `events.YYYYMMDD.jsonl` and starts a new file.

**Replacement alternative:** **SQLite** (already a project dependency). For distributed: **AWS QLDB** (deprecated), **DynamoDB Streams**, or **Kafka** with schema registry.

---

### 17. `util.py` — 16 LOC

**Purpose:** 6 tiny functions: `sha256_bytes`, `sha256_file`, `canonical_hash`, `new_id`, `now`, `write_json`, `load_json`.

**Implementation quality — 8/10.**
- Clean, focused, well-named.
- `canonical_hash` uses `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',',':'))` — deterministic, good for content-addressing.
- `write_json` uses `indent=2` — pretty but slow. No `compact` option.
- `load_json` will raise `FileNotFoundError` on missing file — fail-loud, good.
- `sha256_file` reads in 1MB chunks — good for large files.
- `new_id` uses `uuid.uuid4()` — random, not sortable. For audit logs, a ULID or UUIDv7 would be better (time-sortable).
- No type hints on `sha256_file(path)` — should be `sha256_file(path: str | Path) -> str`.

**Test coverage — 6/10.** Six test files reference it. Real usage, no direct unit test (`tests/test_util.py` is missing).

**Connectivity — 10/10.** Imported by 91 internal modules — the most-used module in the system. Internal imports: stdlib only.

**Top 3 weak spots:**
1. `write_json` always uses `indent=2`. For large outputs (orchestrator writes dozens of files per run), this is 2-3x slower than `indent=None`.
2. `new_id` uses `uuid4` (random). For audit logs, time-sortable IDs (ULID, UUIDv7) would help debugging.
3. No `safe_load_json(path, default=None)` — every caller must `try: ... except FileNotFoundError: ...`.

**Top 3 improvements:**
1. Add `write_json_compact(path, obj)` for large outputs.
2. Switch `new_id` to ULID (`python-ulid` package) — time-sortable, same length.
3. Add `tests/test_util.py` with cases for: `canonical_hash` determinism, `canonical_hash` of nested dicts, `write_json` then `load_json` roundtrip, `sha256_file` of empty file.

**Replacement alternative:** **orjson** for JSON serialization (5-10x faster than stdlib). **python-ulid** for sortable IDs. Otherwise, this module is fine.

---

## Cross-Cutting Patterns (Anti-Patterns Repeated Across Modules)

### A. Magic constants everywhere
- `0.65` (arbitration evidence threshold)
- `0.58, 0.36, 0.20` (routing role thresholds)
- `0.50, 0.28, 0.12, 0.10` (disagreement tension weights)
- `0.72, 0.5` (disagreement priority thresholds)
- `6, 3` (adapter review conflict limits)
- `80, 4, 12` (reference adapter magic numbers)
- `'1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d'` (orchestrator hardcoded constitution hash)

**Recommendation:** Create `config/weights.json` and load at startup. Currently, tuning requires code changes in 6+ files.

### B. Duplicated `POS` / `NEG` stance sets
Defined in `claims.py`, `disagreement.py`, `arbitration.py`. If a new stance is added, all three must be updated.

**Recommendation:** Move to `stances.py` with `POS = frozenset({...})`, `NEG = frozenset({...})`, `UNCERTAIN = frozenset({...})`. Import everywhere.

### C. Engine-ID dispatch on string equality
- `hybrid_mesh._signals_from_contribution`: 12 elif branches on `eid == 'engine_05'` … `'engine_16'`
- `adapters/reference.py`: 12 elif branches on `eid == 'engine_05'` … `'engine_16'`
- `routing._engine_score`: hardcoded `engine_01..04` set
- `hybrid_mesh.ENGINE_PRIMITIVES`: hardcoded 16-engine dict

**Recommendation:** Extract per-engine logic to a registry pattern. Each engine declares its own signal extractor / reference logic / primitive list in `config/engines/{engine_id}.json` or `engines/{engine_id}.py`.

### D. `try: ... except Exception: pass`
- 17 occurrences in `orchestrator.py`
- 1 in `adapters/node_native.py`
- 1 in `adapters/reference.py`

**Recommendation:** Replace with `except Exception as e: ledger.append(run_id, 'SUBSYSTEM_FAILED', {'name': ..., 'error': repr(e)[:200]})`. Never `pass`.

### E. No unit tests for 14 of 17 modules
Only `hybrid_mesh.py`, `constitution.py` (sort of), and `security.py` (sort of) have any direct test file. The rest are exercised only via integration tests.

**Recommendation:** Add `tests/test_{routing,fusion,claims,disagreement,arbitration,synthesis,storage,util,cli}.py` and `tests/adapters/test_{base,node_native,reference,registry}.py`. Target: 80% line coverage per module.

---

## Final Verdict

The core engine is **a research prototype that has accreted features without refactoring**. The orchestrator is the bottleneck — it's a 700-line method that swallows 17 subsystem failures silently. The fusion module doesn't fuse. The synthesis module doesn't synthesize. The adapters dispatch on string equality 24 times. The CLI is a 13-branch if/elif chain. The constitution module is the one bright spot — well-structured, well-tested, properly fail-closed.

**Top 3 actions, in priority order:**

1. **Decompose `orchestrator.run()` into 7 phase classes.** This is the single highest-leverage refactor. It unlocks unit testing, eliminates the `if 'actual_q' in dir()` idiom, and makes subsystem failures visible.

2. **Replace `fusion.py` with a real fusion algorithm** OR rename it to `inventory.py` and update all callers. The current name is a lie.

3. **Add the 11 missing `tests/test_*.py` files.** Without unit tests, every refactor is a coin flip. The constitution module proves the team can write good tests when they try; they just haven't tried for the rest.

**Average scores:**
- Implementation quality: **5.5/10**
- Test coverage: **2.4/10** ← critical gap
- Connectivity: **5.7/10**
- Overall value: **6.0/10**

The system works (259 regression tests pass), but it works *despite* the orchestrator, not *because* of it. The next slice should focus on decomposition and testing, not new features.
