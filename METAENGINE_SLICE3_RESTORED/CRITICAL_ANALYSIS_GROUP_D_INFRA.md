# Critical Analysis — Group D: Infrastructure (12 modules)

**Task ID:** crit-D-infra
**Agent:** general-purpose (sub-agent)
**Scope:** 12 infrastructure modules bridging orchestrator output to long-horizon learning, federation, provenance, REST API, and small leaf modules (oracles, telemetry, biographies, predictive model, meta-learning, calibration).
**Method:** Read every source file in full (Read tool, no truncation). Ran the 7 existing dedicated test suites (114 passed, 1 skipped in 48.7s). Mapped inbound/outbound imports via Grep for all 12 modules. Counted anti-patterns (bare `except Exception`, hardcoded anchors, magic constants). Read orchestrator.py wiring sites (lines 31–35, 101, 301–304, 410, 436, 452–462, 489–501, 675).

---

## Executive Summary Table

| # | Module | Impl LOC | Test LOC | Tests (#) | Impl | Tests | Connectivity | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `api_server.py` | 674 | 245 | 24 | 7 | 7 | 4 | REST API + rate limit + auth; not wired to orchestrator (control plane only) |
| 2 | `cross_run_accumulator.py` | 369 | 357 | 30 | 6 | 8 | 5 | 7 silent `except Exception: pass` (data loss) |
| 3 | `external_validator.py` | 553 | 301 | 28 | 7 | 7 | 4 | LLM-as-judge; brittle regex JSON parser |
| 4 | `federation_bridge.py` | 312 | 212 | 6 | 6 | 5 | 5 | Hardcoded `cp001` (4×) + canonical policy hash (1×) |
| 5 | `adaptation_bridge.py` | 159 | 149 | 7 | 7 | 7 | 4 | Clean adapter; double-invokes D6-G1 guard |
| 6 | `signed_provenance.py` | 272 | 181 | 11 | **9** | 8 | 5 | **Bright spot**: Ed25519, self-ref-safe hashing |
| 7 | `local_outcome_oracle.py` | 124 | **0** | 0 | 6 | 1 | 2 | **NO TEST FILE**; 50% threshold is magic |
| 8 | `telemetry.py` | 70 | **0** | 0* | 8 | 4 | 3 | Tested incidentally in test_controlled_learning_2_3.py (1 test) |
| 9 | `biographies.py` | 91 | **0** | 0* | 5 | 4 | **10** | **Most-connected module (14 importers); dense one-liners; smoke-tested only** |
| 10 | `predictive_model.py` | 177 | 106 | 9 | 7 | 6 | 5 | Mean-based baseline predictor; clean but minimal |
| 11 | `meta_learning.py` | 116 | **0** | 0* | 6 | 1 | 3 | Only `MetaLearner is not None` smoke check |
| 12 | `uncertainty_calibration.py` | 61 | **0** | 0 | 7 | 1 | 3 | Clean ECE-style bucketed calibration; untested |
| **Total / Avg** | | **3,008** | **1,551** | **115** | **6.75** | **4.92** | **4.42** | 7 dedicated test suites, 5 modules with NO dedicated test file |

\* = incidental coverage in another test file (not a dedicated `test_<mod>.py`)

**Test ratio:** 1,551 test LOC / 3,008 impl LOC = 0.52 (Group D is below the Group B ratio of 0.79 and Group A's effective-ratio-after-zeros).

---

## Per-Module Analysis

### 1. `api_server.py` — 674 LOC, 245 test LOC (24 tests)

**Purpose:** REST API server (stdlib `http.server` only). 12 endpoints exposing project summary, constitution, modules, accumulation, benchmark, strict tests, fitness, recursive, events. POST `/api/benchmark/run` and `/api/recursive/run` spawn background threads. Token-bucket per-endpoint rate limiting (default 1 call / 60s, burst 1). Optional Bearer-token auth on POST endpoints (C4). CORS `*` enabled.

**Implementation quality: 7/10** — clean stdlib-only design; rate-limiter is a real token bucket; auth path is conditional (`api_token is not None`). The factory pattern (`type("BoundHandler", ...)` at line 620) is reasonable for stdlib `BaseHTTPRequestHandler` which doesn't accept `__init__` args. But: (a) `do_GET` is a 36-branch elif chain on URL path (Open/Closed violation; adding an endpoint requires editing the dispatcher); (b) `_send_json` always sets `Access-Control-Allow-Origin: *` — even for POST endpoints requiring auth — making CORS effectively permissive; (c) the rate-limit state is mutated from multiple threads without a lock (line 125: `history.append(now); self._rate_limit_state[endpoint] = history`) — race condition under concurrent POSTs; (d) `_handle_orchestrator_run` does NOT actually run the orchestrator — it returns a string telling the user to use the CLI. So `POST /api/run` is misleadingly named.

**Test coverage: 7/10** — 24 tests (TestServerStarts, TestGetEndpoints, TestRateLimiting, TestAuth, TestBenchmarkRun). Uses `urllib.request.urlopen` against a live server on port 8081 — true integration test. Covers happy paths + rate-limit 429 + auth 401. Gaps: no test for CORS preflight (`do_OPTIONS`), no test for `_check_bridge` failure, no test for concurrent rate-limit races, no test for the 36-branch dispatcher's 404 path.

**Connectivity: 4/10** — Only 2 importers (`tests/test_p1_fixes.py`, `tests/test_api_server.py`). **NOT imported by orchestrator, cli, or any production module.** The api_server imports `metaengine.unified_benchmark`, `metaengine.real_recursive`, `metaengine.tiered_fitness`, `metaengine.event_publisher` lazily inside handlers — so it's a control plane on top of MetaEngine, not part of the orchestrator's hot path. This is acceptable but means a bug in api_server cannot affect orchestration correctness.

**Weak spots:**
1. Rate-limit state mutation is not thread-safe (`ThreadingHTTPServer` spawns one thread per request; concurrent POSTs to the same endpoint can both pass the `len(history) < burst` check before either appends).
2. CORS `*` on POST endpoints that require auth is a foot-gun: if a browser extension can read the response, an attacker page can submit authenticated POSTs (CSRF). The `Access-Control-Allow-Headers: Content-Type` does not help; this should require `Authorization` echoed in `Access-Control-Allow-Headers` AND an Origin allowlist.
3. `_handle_orchestrator_run` (line 436) returns 202 "accepted" but does nothing — the user gets a 202 with instructions to use the CLI instead. This is a documented dead endpoint.
4. Hardcoded `localhost:3031` (line 575) — bridge health check fails silently if bridge is on a different port.

**Recommendations:**
1. Add a `threading.Lock` around `_rate_limit_state` mutations (or move to `collections.deque` + atomic `len()`).
2. Replace the 36-branch elif dispatcher with a dict mapping `(method, path)` → handler callable.
3. Make CORS Origin-configurable; default to same-origin only.
4. Either implement `/api/run` (call `Orchestrator.run()` in a background thread, write receipt to `storage/runs/<id>/`) or remove the endpoint from the docs.

**Replacement alternative:** `fastapi.FastAPI` would handle routing, OpenAPI docs, dependency injection, and CORS in 1/3 the LOC. But that adds a dependency; stdlib-only is a defensible choice given the constitution's "no external dependencies required" comment.

---

### 2. `cross_run_accumulator.py` — 369 LOC, 357 test LOC (30 tests)

**Purpose:** Persist learning artifacts (mechanism IDs, RLAIF rewards, faithfulness scores, transferable IDs, biography observations, evidence graph stats, synthesized policy hashes, run history) across multiple orchestrator runs. Idempotent accumulation: re-accumulating the same run produces no new entries.

**Implementation quality: 6/10** — clean dataclass structure (`AccumulatedState` with 12 fields, `payload()` + `compute_hash()` follow the receipt pattern). Constitution compliance fields (truth_effect=NONE, claim_ceiling, idempotent flag) are correct. **But: 7 silent `except Exception: pass` blocks (lines 160, 215, 231, 253, 265, 306, 337).** Each one masks persistent state corruption: if a JSON parse fails on a run dir artifact (e.g. `REASONING_TRACE_EXTRACTION.json` is truncated), the accumulator silently reports `new_mechanisms: 0` and moves on. Idempotent accumulation becomes a data-losing black hole. Also: (a) `accumulate_run` synthesizes fake mechanism IDs `f"trace.{run_id[:12]}.{i:02d}"` from a count (line 211) instead of reading actual mechanism IDs from the trace — so two runs with the same `run_id[:12]` prefix will be treated as the same mechanisms (false idempotency); (b) `evidence_graph_nodes = max(...)` (line 263) is not accumulation — it's "remember the largest seen graph", which loses smaller graphs; (c) the `set` type for `mechanism_ids` is JSON-serialized as a `list` in `payload()` (line 83) but `load()` reads `set(data.get(...))` (line 147) — fine, but the on-disk format is implicit.

**Test coverage: 8/10** — 30 tests across 4 test classes (TestAccumulatedState, TestCrossRunAccumulator, TestLoadSave, TestAccumulateRun). Fixture `mock_run_dir` is well-built with realistic JSON. Covers happy path, idempotency, load-or-empty, save, summary. **Gaps:** no test for malformed JSON (which would hit the `except Exception: pass` and silently lose data — this is exactly the bug we'd want a test for); no test for the `mechanism_id` synthesis collision; no test for `evidence_graph_nodes` max-vs-sum behavior.

**Connectivity: 5/10** — 3 importers: `metaengine/strict_test_factory.py`, `metaengine/unified_benchmark.py`, `tests/test_cross_run_accumulator.py`. So the accumulator is wired into the benchmark/strict-test pipeline but **NOT into the orchestrator** (orchestrator does not call `CrossRunAccumulator`). This is suspicious: the module's stated purpose is "accumulate across orchestrator runs", but the orchestrator doesn't invoke it. Either orchestrator should call `accumulator.accumulate_run(out, run_id=run_id)` after `run()`, or this module is effectively dead code in production.

**Weak spots:**
1. **7 silent `except Exception: pass`** — each one is a potential data-loss site. Idempotent accumulation should be idempotent AND lossless.
2. `accumulate_run` synthesizes mechanism IDs from a count (`f"trace.{run_id[:12]}.{i:02d}"`) instead of reading real IDs — false idempotency if run IDs collide in the first 12 chars.
3. `evidence_graph_nodes = max(...)` is not accumulation — it's tracking the largest graph. A smaller subsequent graph leaves the value unchanged, hiding that runs are shrinking.
4. **Orchestrator does not call this module** — the cross-run loop is not closed.

**Recommendations:**
1. Replace 7 silent `except Exception: pass` with `errors: list[str]` in the return dict; surface parse failures to the caller.
2. Read actual mechanism IDs from `REASONING_TRACE_EXTRACTION.json` (it has a `traces` field); don't synthesize.
3. Change `evidence_graph_nodes` to a cumulative count or running average; document the choice.
4. Wire `CrossRunAccumulator.accumulate_run()` into `Orchestrator.run()` after the run completes (estimated 5 LOC change in orchestrator + 1 test).

**Replacement alternative:** None — the module is the right shape, just needs the silent-catch fixes and orchestrator wiring.

---

### 3. `external_validator.py` — 553 LOC, 301 test LOC (28 tests)

**Purpose:** External LLM-as-judge validator. 12 default tasks across 5 categories (ARITHMETIC, LOGIC, REASONING, ANALYSIS, SAFETY). For each task: (1) call LLM bridge to solve (engine_16 persona, temp=0.4), (2) call LLM bridge as independent judge with ground truth (temp=0.1), (3) parse JSON scores (correctness/completeness/constitution/quality), (4) compute weighted overall (0.40+0.20+0.25+0.15), (5) pass if overall ≥ 0.6. Returns content-addressed `ValidationSuite` with per-category breakdown.

**Implementation quality: 7/10** — clean separation: `ValidationTask`/`ValidationResult`/`ValidationSuite` frozen dataclasses, all with `payload()` + `as_dict()` + content-addressed hash. Default task bank is well-curated (the SAFETY tasks test K0 abstention directly). **But:** (a) `_parse_validator_response` uses `re.search(r'\{[^}]*\}', response, re.DOTALL)` (line 444) — this matches the FIRST `{...}` block and cannot handle nested JSON. The validator prompt asks for `{"correctness": ..., "analysis": "brief critical analysis"}` — if the analysis contains a `}`, the regex stops early; (b) `_call_llm` uses `urllib.request.urlopen` directly (no retry, no backoff beyond `rate_limit_delay`); (c) `validate_answer` has `except Exception: scores = {"correctness": 0.0, ..., "constitution": 0.5, "analysis": "VALIDATOR_ERROR"}` (line 409) — this silently turns network errors into 0.5 constitution scores, masking validator failures; (d) weights (0.40/0.20/0.25/0.15) and threshold (0.6) are class constants — reasonable but not configurable per-task; (e) `solve_task` is the SAME LLM bridge as `validate_answer` — the "external" judge is the same model as the solver, which defeats the independence claim (the docstring says "independent LLM call" but it's the same bridge endpoint).

**Test coverage: 7/10** — 28 tests across 4 classes (TestValidationResult, TestValidationTask, TestExternalValidatorFactory, TestValidationSuite). Uses `unittest.mock.patch` to mock `_call_llm`. Covers happy path, parse failure fallback, rate-limit timing, weight computation, content-addressed hash. **Gaps:** no test for nested-JSON-in-analysis (the regex bug); no test for the "external judge is same LLM as solver" independence claim; no test for what happens when bridge returns empty string.

**Connectivity: 4/10** — 2 importers: `metaengine/unified_benchmark.py` (which runs validation as part of the benchmark), `tests/test_external_validator.py`. NOT imported by orchestrator. So external validation runs only when the benchmark is invoked manually — not part of every orchestrator run.

**Weak spots:**
1. `_parse_validator_response` regex `r'\{[^}]*\}'` cannot parse JSON with nested braces (analysis field with `}` breaks it).
2. The "independent judge" uses the same `_call_llm` (same bridge, same model, same endpoint) as `solve_task` — independence is only conceptual (different temperature, different prompt), not architectural.
3. `validate_answer`'s `except Exception:` swallows validator errors as 0.5 fallback scores — a validator outage silently degrades to mediocrity.
4. `_rate_limit` is a simple `time.sleep(self.rate_limit_delay - elapsed)` — single-threaded, not a token bucket. Concurrent `validate_all` calls would each sleep, not share the bucket.

**Recommendations:**
1. Replace the regex JSON parser with a real JSON parser: try `json.loads(response)` first, fall back to extracting the largest balanced-brace substring.
2. Allow `validate_answer` to take a separate `validator_bridge_endpoint` (default same as solver), so users can configure a different judge model.
3. Replace the swallowed exception with `status="VALIDATOR_ERROR"` in the result; let callers decide whether to count it as pass/fail.
4. Document explicitly: "Independence is conceptual (different prompt + temperature), not architectural (same bridge). For true independence, configure `validator_bridge_endpoint` to a different model."

**Replacement alternative:** None — the design is sound; the fixes are surgical.

---

### 4. `federation_bridge.py` — 312 LOC, 212 test LOC (6 tests)

**Purpose:** Wires orchestrator engine execution through the FederationStore (C0-C7 slots, epoch, candidates, finalization). Provides `run_federated()` which creates an epoch, dispatches a task to slot C0, collects engine contributions as candidates (round-robin across C1-C5, C7), and finalizes the epoch (builds recovery cut, computes terminal snapshot hash, inserts session+snapshot FK rows).

**Implementation quality: 6/10** — the API surface is clean (4 methods: `create_epoch`, `dispatch_task`, `collect_candidates`, `finalize_epoch`, plus the orchestration `run_federated`). The federation types are properly imported. **But:** (a) **Hardcoded canonical anchors 4×**: `"metaengine-chat-2.3.0-alpha.1-cp001"` at lines 107, 126, 174, 206, and `"1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"` at line 207. This duplicates the orchestrator.py anti-pattern flagged in Group A — the canonical checkpoint ID should be read from `canonical_connector` or passed as a parameter, not baked into the bridge. If the canonical checkpoint ever advances (Slice-3 → Slice-4 → …), this bridge silently produces receipts against a stale checkpoint; (b) `collect_candidates` uses `hashlib.sha256(str(canonical_payload).encode("utf-8")).hexdigest()` (line 161) instead of `canonical_hash(canonical_payload)` — `str(dict)` is non-deterministic across Python versions for some key types (though CPython 3.7+ guarantees insertion order, this is still a different hash function from the rest of the codebase); (c) `collect_candidates` assigns slots in round-robin order (`candidate_slots[i % len(candidate_slots)]`) — this ignores actual engine-role fit. engine_16 (the LLM bridge) might end up in C1 in one run and C7 in another, breaking any downstream role-based analysis; (d) `finalize_epoch` does `INSERT OR IGNORE INTO session(...)` and `INSERT OR IGNORE INTO snapshot(...)` directly on `self.store.connection` (lines 241, 247) — bypassing the store's API. This is a leaky abstraction; the store should expose a `put_session()` / `put_snapshot()` method.

**Test coverage: 5/10** — only 6 tests. Covers: bridge creates epoch, dispatches task, collects candidates, finalizes epoch, full round-trip. **Gaps:** no test that the hardcoded checkpoint ID is current (drift detection); no test for slot assignment determinism (same contributions → same slot assignment?); no test for the `str(dict)` hash vs `canonical_hash` divergence; no test for the `INSERT OR IGNORE` behavior when session already exists.

**Connectivity: 5/10** — 2 importers: `metaengine/orchestrator.py` (line 31, line 410: `fed_bridge = FederationBridge(store_path=out/'federation_store.db')`), `tests/test_federation_bridge.py`. So this IS wired into the orchestrator's main run path.

**Weak spots:**
1. Hardcoded `"metaengine-chat-2.3.0-alpha.1-cp001"` (4×) and canonical policy hash `"1868b3c7..."` (1×) — drift hazard if canonical checkpoint advances.
2. `hashlib.sha256(str(canonical_payload).encode())` diverges from the codebase's `canonical_hash()` standard.
3. Round-robin slot assignment ignores engine-role fit.
4. Direct `INSERT OR IGNORE` on `store.connection` bypasses the store API (leaky abstraction).
5. `_ORCHESTRATOR_ROLE_PROFILE_HASH = "0" * 64` (line 37) — a placeholder that should come from the role genome store.

**Recommendations:**
1. Accept `base_checkpoint_id` and `policy_hash` as parameters to `finalize_epoch` (already accepted by `create_epoch` and `dispatch_task` — just not by `finalize_epoch`).
2. Replace `hashlib.sha256(str(...))` with `canonical_hash(canonical_payload)`.
3. Add a `slot_assignment_strategy` parameter (default `round_robin`, future: `role_fitted`).
4. Add `store.put_session()` / `store.put_snapshot()` methods and call them instead of raw SQL.
5. Add a test that asserts `finalize_epoch` fails (or warns) if the checkpoint ID has drifted from `canonical_connector.verify_against_expected()`.

**Replacement alternative:** None — the bridge is the right shape; the fixes are surgical.

---

### 5. `adaptation_bridge.py` — 159 LOC, 149 test LOC (7 tests)

**Purpose:** Bridges orchestrator run output to the federation adaptation receipt builder. Converts `run_result["fusion"]["epistemic_coordination"]` into `FinalizedEpochMetrics`, calls `build_adaptation_receipt()` with D6-G1 guard, returns `AdaptationBridgeResult` (status, d6_g1_guard_passed, truth_effect=NONE, assimilation_effect=NONE).

**Implementation quality: 7/10** — clean and minimal. `build_metrics_from_run` (lines 63–105) is a clear mapping function. `AdaptationBridge.build_adaptation_from_run` is 25 lines. **But:** (a) the D6-G1 guard is asserted TWICE — once inside `build_adaptation_receipt` (per the comment "instrumented in Step 4 / Task 31") and once explicitly at line 150 (`assert_d6_g1_shadow_only(receipt)`). The comment calls this "defense in depth" but it's actually redundant work that doubles the failure surface; (b) `build_metrics_from_run` uses `coord.get("deep_engine_executions", 0)` for BOTH `producer_concurrency` AND `candidate_count` (lines 86, 88) — the same value semantically mapped to two structurally-different metrics. If a run has 12 deep_engine_executions but only 8 candidates (because 4 engines failed), the receipt will overstate candidate_count; (c) `current_producer_concurrency=max(2, min(6, coord.get("deep_engine_executions", 4)))` (line 143) — magic 2/4/6 bounds with no comment. Why 2 minimum? Why 6 maximum? (d) `task_count=1` hardcoded (line 87) — every orchestrator run is treated as 1 task from the adaptation perspective. If a run dispatches multiple tasks (which `federation_bridge` allows), this is wrong.

**Test coverage: 7/10** — 7 tests covering build_metrics_from_run happy path, AdaptationBridge.build_adaptation_from_run, D6-G1 guard pass, status field. Uses a realistic `run_result` fixture. **Gaps:** no test for the double-guard invocation; no test for the `producer_concurrency == candidate_count` conflation; no test for `task_count=1` when the run actually dispatched multiple tasks; no test for the magic 2/4/6 bounds.

**Connectivity: 4/10** — 2 importers: `metaengine/orchestrator.py` (line 32, line 436: `adapt_bridge = AdaptationBridge()`), `tests/test_adaptation_bridge.py`. Wired into orchestrator's main run path.

**Weak spots:**
1. Double D6-G1 guard invocation (redundant, doubles failure surface).
2. `producer_concurrency == candidate_count == deep_engine_executions` — semantic conflation.
3. `task_count=1` hardcoded — breaks if orchestrator dispatches multiple tasks per run.
4. Magic `max(2, min(6, ...))` bounds on producer_concurrency with no rationale comment.

**Recommendations:**
1. Drop the explicit `assert_d6_g1_shadow_only(receipt)` at line 150 (or move it to a single assertion site in `build_adaptation_receipt`).
2. Distinguish `producer_concurrency` (orchestrator-level: how many engines ran in parallel) from `candidate_count` (federation-level: how many contributions were collected). Map them to different fields in `coord`.
3. Make `task_count` come from `len(run_result.get("tasks", [run_result]))` or pass it explicitly.
4. Add a comment explaining the 2/4/6 bounds OR replace with constants `MIN_PRODUCER_CONCURRENCY = 2`, `MAX_PRODUCER_CONCURRENCY = 6`, `DEFAULT_PRODUCER_CONCURRENCY = 4`.

**Replacement alternative:** None — the bridge is appropriately minimal.

---

### 6. `signed_provenance.py` — 272 LOC, 181 test LOC (11 tests) — **BRIGHT SPOT**

**Purpose:** Adds Ed25519 cryptographic signatures to content-addressed receipts. Closes the gap where content-addressing alone can be defeated by replacing both the data AND the claimed hash. `SigningKeyPair` (private signs, public verifies; private never serialized). `SignedReceipt` (signature is over the canonical hash of the payload *without* the hash field — avoiding self-reference). `sign_manifest` for batch provenance over a list of receipt hashes.

**Implementation quality: 9/10** — this is the best-structured module in Group D. (a) The self-reference problem is handled correctly: `SignedReceipt.sign` strips the `payload_hash_field` before computing `signed_hash`, then re-inserts it (lines 162–167). `verify` re-strips and re-hashes (lines 195–196). `from_dict` re-verifies on load (lines 230–241); (b) `_is_hex(value, 128)` validates the signature format before the cryptography library is invoked (line 208) — fast-fail; (c) `to_public_record()` returns ONLY the public key (line 89), with the private key explicitly never serialized — Boundary 6 compliant; (d) `cryptography` package is a hard dependency with a clear error message; (e) `sign_manifest` uses `sorted(receipt_hashes)` (line 269) — manifest is order-independent, so re-signing the same set of receipts produces the same signature. **Minor weak spots:** (1) `from_dict` doesn't re-verify the signature itself (only the payload hash) — a tampered signature would be caught only on a later `verify()` call. This is defensible (load ≠ verify) but worth documenting; (2) `generate_signing_keypair()` is called inside `orchestrator.py` line 452 **PER RUN** — meaning every run generates a new keypair and writes a new `SIGNED_RUN_RECEIPT.json` with a new `public_key_hex`. This breaks cross-run verification: a receipt from run N cannot be verified against a keypair from run N+1. The orchestrator should load a project-level keypair from a secret store (Boundary 6: "generated once per project and stored as a secret"), not generate one per run.

**Test coverage: 8/10** — 11 tests covering keypair generation, sign/verify round-trip, payload_hash_field self-reference handling, tamper detection (signature, payload, public key), manifest signing, from_dict re-verification. **Gaps:** no test for the per-run keypair regeneration anti-pattern in orchestrator.py (that's an orchestrator bug, not a signed_provenance bug); no test for cross-receipt verification (verify a receipt signed by keypair A against keypair B — should fail with PUBLIC_KEY_MISMATCH, which is in the code but not tested).

**Connectivity: 5/10** — 4 importers: `metaengine/orchestrator.py`, `metaengine/cross_run_verification.py`, `tests/test_signed_provenance.py`, `tests/test_cross_run_verification.py`. So this is wired into both the orchestrator's run path and the cross-run verification subsystem.

**Weak spots:**
1. `from_dict` does not re-verify the Ed25519 signature (only the payload hash) — defensible but undocumented.
2. No `verify_manifest` helper — `sign_manifest` exists but verification requires manual `SignedReceipt.verify()` on the manifest + separate verification of each receipt.
3. The orchestrator's per-run `generate_signing_keypair()` call (orchestrator.py:452) defeats cross-run verification — the project-level keypair should be loaded from a secret, not regenerated.

**Recommendations:**
1. Add `SignedReceipt.verify_manifest(manifest_receipt, expected_keypair, receipt_hashes)` that verifies the manifest signature AND checks `set(manifest.payload["receipt_hashes"]) == set(receipt_hashes)`.
2. Add a test `test_cross_keypair_verification_fails` to lock in the PUBLIC_KEY_MISMATCH path.
3. Refactor orchestrator.py:452 to `keypair = load_project_signing_keypair()` (read from a secret path); fall back to `generate_signing_keypair()` only if no keypair exists, then persist it once.
4. Document in `from_dict` docstring: "Does NOT re-verify the signature. Call `verify(expected_keypair)` after `from_dict` for full verification."

**Replacement alternative:** None — Ed25519 is the right choice, the implementation is correct, and `cryptography` is the standard library.

---

### 7. `local_outcome_oracle.py` — 124 LOC, NO TEST FILE

**Purpose:** Deterministic local oracle to close the self-learning loop. When the external verifier returns `INSUFFICIENT_EXTERNAL_EVIDENCE`, this oracle validates that dialectical graph nodes have source-grounded spans (start/end/text_hash) pointing to real source text. Returns `VERIFIED_LOCAL` (not `VERIFIED` — explicitly labeled `LOCAL_DETERMINISTIC_OUTCOME_NOT_FRONTIER_MODEL_EQUIVALENCE`). Allows `biographies.update()` to accept the outcome and update scheduler priors.

**Implementation quality: 6/10** — minimal and honest. The `ORACLE_AUTHORITY` constant is excellent boundary discipline. The `evaluate()` method (lines 66–124) iterates nodes, validates each span's `(start, end)` is within `len(source_text)` and that `sha256(source_text[start:end]) == span["text_hash"]`. **But:** (a) the 50% threshold (`valid_spans / total_spans >= 0.5`, line 96) is magic — no comment explaining why 50% is the right cutoff; (b) `quality_proxy = round(valid_spans / max(1, total_spans), 4)` (line 99) is a thin proxy for quality — a graph where all spans point to the same 1-character substring would score 100%; (c) `span_coverage = nodes_with_spans / max(1, len(nodes))` (line 100) — a graph with 1 node and 1 valid span scores 1.0, even if it's missing 99% of the source; (d) `promotion_eligible = False` always (line 123) — correct, but it's a constant, not a derived value; (e) the oracle is instantiated PER RUN inside orchestrator.py:303 (`LocalOutcomeOracle.create(source_text)`) — no persistence across runs. The oracle's "commitment" is content-addressed but never stored or compared across runs, so there's no way to detect that the same source text produced different oracle outputs in two runs.

**Test coverage: 1/10** — **NO dedicated test file.** The module is exercised only via orchestrator integration (orchestrator.py:303–305 writes `LOCAL_OUTCOME_ORACLE.json`). No unit test for: span validation logic, 50% threshold, NO_SOURCE_SPANS path, INSUFFICIENT_LOCAL_EVIDENCE path, `commitment()` determinism.

**Connectivity: 2/10** — 1 importer: `metaengine/orchestrator.py`. Used exactly once (line 303).

**Weak spots:**
1. **No tests** — the oracle's correctness (span validation, threshold logic) is unverified.
2. 50% threshold is magic.
3. `quality_proxy` based only on span validity, not span content quality — easy to game.
4. No cross-run persistence of oracle commitments.

**Recommendations:**
1. Write `tests/test_local_outcome_oracle.py` (~15 tests): VERIFIED_LOCAL happy path, INSUFFICIENT_LOCAL_EVIDENCE (<50% valid), NO_SOURCE_SPANS (empty), out-of-range spans (start > end), hash mismatch detection, `commitment()` determinism, `promotion_eligible` always False.
2. Make the threshold a class constant `VERIFICATION_THRESHOLD = 0.5` with a docstring explaining the choice.
3. Add a `span_content_hash` check: store `sha256(span_text_normalized)` to detect "all spans point to the same trivial substring".
4. Add `LocalOutcomeOracle.load(path)` / `.save(path)` for cross-run persistence and commitment comparison.

**Replacement alternative:** None — the design is correct for its stated boundary (LOCAL_DETERMINISTIC, not frontier).

---

### 8. `telemetry.py` — 70 LOC, NO dedicated test file (1 incidental test)

**Purpose:** Thread-safe run telemetry ledger. `record(kind, **fields)` appends a content-addressed event with ordinal, monotonic_seconds, previous_event_hash (hash-chained). `span(kind)` context manager emits START/COMPLETE (or FAILED on exception). `artifact()` returns the full ledger with `telemetry_hash`. `write(path)` persists to JSON. Unknown token/USD data remains missing (never zero-filled) — Boundary-compliant.

**Implementation quality: 8/10** — excellent for 70 LOC. (a) Hash-chained events (`previous_event_hash`) make tampering detectable; (b) `redact_secrets(value)` is called on every string field (line 25) — secret non-disclosure by default; (c) `token_coverage` and `usd_coverage` are explicitly `MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER` (lines 59–60) — no fake numbers; (d) `claim_ceiling = "TELEMETRY_MEASURES_EXECUTION_NOT_EPISTEMIC_QUALITY"` (line 61) — correct boundary; (e) the `span()` context manager correctly emits FAILED on exception with `wall_seconds` and `error=repr(exc)` (line 47). **Minor weak spots:** (1) `event_hash` is computed BEFORE the event is appended (line 36) — fine, but the `previous_event_hash` is read inside the lock, so the chain is consistent; (2) no max-events limit — a long-running process could grow `self.events` indefinitely; (3) `monotonic_seconds` is `time.perf_counter() - self.started` — wall-clock-ish, not CPU time. For a self-improving system, CPU/wall distinction matters.

**Test coverage: 4/10** — **No dedicated test file.** One incidental test in `tests/test_controlled_learning_2_3.py::test_telemetry_is_hash_chained_and_redacts_secrets` (verified via Grep). That test covers hash-chaining and redaction. **Gaps:** no test for `span()` context manager FAILED path; no test for `write(path)` round-trip; no test for thread-safety under concurrent `record()` calls; no test for the `MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER` claim.

**Connectivity: 3/10** — 3 importers: `metaengine/telemetry.py` (self), `metaengine/orchestrator.py` (line 103: `telemetry=TelemetryLedger(run_id)`), `tests/test_controlled_learning_2_3.py`. Wired into orchestrator's run path; the ledger is passed to subsequent phases but not persisted at the module level.

**Weak spots:**
1. No max-events limit — unbounded memory growth on long runs.
2. `monotonic_seconds` is wall-clock-derived; no CPU-time tracking.
3. Only 1 incidental test — coverage is minimal.
4. No `read(path)` companion to `write(path)` — once written, the ledger is one-shot.

**Recommendations:**
1. Write `tests/test_telemetry.py` (~10 tests): record hash-chaining, span COMPLETE/FAILED, redaction of common secret patterns, write+read round-trip, concurrent record thread-safety, MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER invariants.
2. Add `max_events` parameter (default 10000) with circular truncation.
3. Add a `cpu_seconds` field via `time.process_time()` alongside `monotonic_seconds`.
4. Add `TelemetryLedger.read(path)` for post-mortem analysis.

**Replacement alternative:** None — `TelemetryLedger` is appropriately minimal.

---

### 9. `biographies.py` — 91 LOC, NO dedicated test file — **HIGHEST CONNECTIVITY**

**Purpose:** Persistent empirical engine biographies. Per-engine records of context-specific marginal usefulness (per-domain `mean_gain`, `pair_synergy`, `effects`, `failure_modes`, `last_runs`). `contextual_prior(engine_id, fingerprint)` blends learned gains with a 0.5 prior by confidence `min(1.0, obs/24)`. `update()` accepts ONLY externally-verified outcomes (`verification_status == 'EXTERNALLY_VERIFIED'`); all others are ignored and counted as `unverified_observations_ignored`.

**Implementation quality: 5/10** — the *logic* is correct (only-external-evidence gate is the right constitution-discipline), but the *form* is the worst in Group D. The entire module is 91 lines of dense one-liners: `b['mean_realized_gain']=round((b.get('mean_realized_gain',0.5)*n+g)/(n+1),4)` (line 63), `pr=b.setdefault('pair_synergy',{}).setdefault(peer,{'n':0,'mean_gain':0.5}); pn=pr['n']; pr['n']=pn+1; pr['mean_gain']=round((pr['mean_gain']*pn+gain)/(pn+1),4)` (line 80). The `update()` method (lines 52–88) is a 37-line for-loop with nested `setdefault` chains, no docstrings on any method, no type annotations, no helper extraction. **Specific bugs/anti-patterns:** (a) `confidence=min(1.0,obs/24)` (line 38) — magic 24, no comment; (b) the pair-synergy loop (lines 76–80) is O(n²) in `verified_rows` — fine for small n but undocumented; (c) `b['last_runs']=b['last_runs'][-20:]` (line 73) — truncates to last 20 silently; (d) `biography_hash` is computed TWICE — once in `update()` (line 86) and once in `snapshot()` (line 91) — but `snapshot()` overrides the value just computed in `update()`. Not a bug (the hashes are equal) but wasteful and confusing; (e) `DOMAINS` is a module-level tuple (line 6) but never used inside the module — engines' domains come from `meta_engine.json` config, not this constant; (f) `pair_prior` returns 0.5 if no pair synergy exists (line 46) — symmetric: `pair_prior(A, [B]) == pair_prior(B, [A])`? No — `pair_prior(A, [B])` reads A's record for peer B, `pair_prior(B, [A])` reads B's record for peer A. These are NOT necessarily equal (A may have observed B more times than B observed A), but the function name suggests symmetry. This is a real correctness issue for any coalition-formation code that relies on pair-prior symmetry.

**Test coverage: 4/10** — **No dedicated test file.** One smoke test in `tests/test_epistemic_core.py` (verified via Grep: `EngineBiographyStore(root, persist=False)` is called, but only to verify it constructs). **Gaps:** no test for the update gate (unverified outcomes ignored), no test for the contextual_prior confidence formula, no test for the pair_prior asymmetry, no test for the last_runs truncation, no test for the `biography_hash` determinism.

**Connectivity: 10/10** — **14 importers** (highest in Group D): `metaengine/architecture_search.py`, `metaengine/orchestrator.py`, `metaengine/biographies.py` (self), `metaengine/stress_matrices.py`, `metaengine/rlaif_trainer.py`, `metaengine/cli.py`, `tests/test_epistemic_core.py`, `tests/test_parallel_ecology_2_1.py`, `tests/test_controlled_learning_2_3.py`, `tests/test_self_organizing_2_0.py`, `tests/test_rlaif_trainer.py`, `tests/test_cross_run_accumulator.py`, `INTEGRATION_REPORT.md`, `CRITICAL_ANALYSIS_GROUP_B_TRAINING.md`. This is a true hub module — used by scheduler, topology library, evolution engine, RLAIF trainer, CLI, and 6 test files. A bug here propagates everywhere.

**Weak spots:**
1. **Asymmetric `pair_prior(A, [B])` vs `pair_prior(B, [A])`** — a correctness bug for any coalition code assuming symmetry.
2. `confidence=min(1.0,obs/24)` — magic 24.
3. `DOMAINS` tuple (line 6) is dead code.
4. `biography_hash` computed twice (update + snapshot).
5. Dense one-liner formatting, no docstrings, no type hints — hard to maintain despite 14 importers.

**Recommendations:**
1. Write `tests/test_biographies.py` (~20 tests): update gate (unverified ignored), contextual_prior confidence formula (obs=0 → 0.5, obs=24 → 1.0, obs=48 → 1.0), pair_prior symmetry (assert `pair_prior(A, [B]) == pair_prior(B, [A])` after symmetric updates), last_runs truncation, biography_hash determinism.
2. Refactor: extract `_update_engine_bio(eid, gain, cost, active_domains)` and `_update_pair_synergy(a, b, gain)` helpers; add docstrings + type hints.
3. Delete the dead `DOMAINS` constant or wire it to validate `active_domains` in `contextual_prior`.
4. Compute `biography_hash` once in `update()` and have `snapshot()` return the cached value.
5. **Fix the pair_prior asymmetry**: either (a) document that pair_prior is intentionally asymmetric (one engine's observation of a peer), or (b) make it symmetric by averaging `(A→B, B→A)`.

**Replacement alternative:** None — the data model is correct; the fixes are formatting + tests + symmetry.

---

### 10. `predictive_model.py` — 177 LOC, 106 test LOC (9 tests)

**Purpose:** Builds a world model of the design space: (Task × Resources × Organization) → predicted Outcomes (quality, cost, latency, confidence). `OrganizationModel.predict(task_id, policy_id)` uses mean of past observations for the same policy (or all if none). `verify_prediction(prediction, actual_*)` compares predicted vs actual within `tolerance=0.15`. `prediction_accuracy(receipts)` returns fraction CORRECT.

**Implementation quality: 7/10** — clean frozen-dataclass design, `from_dict`/`payload`/`receipt_hash` pattern is correct. `OrganizationModel.create()` sorts observations deterministically (line 101) — content-addressing works. **But:** (a) `predict()` is a pure mean — no regression, no features, no task-conditioning. The model is essentially "average of past outcomes for this policy". For a "predictive organization model", this is a baseline only; (b) `confidence = min(1.0, len(policy_obs) / 10.0)` (line 119) — magic 10, full confidence at 10+ observations; (c) the default prior `q, c, l = 0.5, 1.0, 0.5` (line 126) with `conf = 0.0` — reasonable, but the magic numbers are uncommented; (d) `verify_prediction` uses `tolerance=0.15` for ALL three dimensions (quality, cost, latency) — but these have different scales (quality is 0..1, cost is USD, latency is seconds). A 0.15 tolerance on cost (USD) is much stricter than 0.15 on quality; (e) `PredictionStatus` is binary CORRECT/INCORRECT/UNVERIFIED — no PARTIAL or NEAR_MISS.

**Test coverage: 6/10** — 9 tests across 3 classes (TestOrganizationPrediction, TestPredictionReceipt, TestOrganizationModel). Covers prediction with data, prediction without data, verify_prediction CORRECT/INCORRECT, prediction_accuracy. **Gaps:** no test for the confidence formula at the 10-observation boundary; no test for the default prior when observations is empty; no test for `tolerance` scale mismatch (cost vs quality).

**Connectivity: 5/10** — 5 importers: `scripts/run_phase34_finalize.py`, `scripts/run_phase34_recursive.py`, `metaengine/orchestrator.py` (line 35, used as `pred_model = OrganizationModel.create()` at orchestrator line ~?), `metaengine/predictive_model.py` (self), `tests/test_predictive_model.py`. Wired into orchestrator and two scripts.

**Weak spots:**
1. Pure-mean prediction — no regression, no features, no task-conditioning.
2. `tolerance=0.15` applied uniformly to quality (0..1), cost (USD), latency (seconds) — scale mismatch.
3. Magic 10 for confidence saturation; magic 0.5/1.0/0.5 default prior.
4. Binary CORRECT/INCORRECT — no PARTIAL.

**Recommendations:**
1. Add per-dimension tolerance: `quality_tol=0.15, cost_tol=0.50, latency_tol=0.50` (or relative tolerance `0.15 * max(1.0, actual)`).
2. Replace pure-mean with at least a per-policy linear regression on (task_features → outcome).
3. Add `PredictionStatus.PARTIAL` for "1 of 3 dimensions correct".
4. Make `CONFIDENCE_SATURATION = 10` a class constant with docstring.

**Replacement alternative:** `sklearn.linear_model.LinearRegression` or `xgboost` for production; the current mean-baseline is fine for early Slice development.

---

### 11. `meta_learning.py` — 116 LOC, NO dedicated test file

**Purpose:** "Learning to learn" — compares experiment selection strategies to determine which is most efficient. `MetaLearner.record_strategy(strategy_id, experiments_run, correct_predictions, compute_cost)`, `compare_strategies()` ranks by `efficiency = accuracy / cost`, returns `MetaLearningResult` with `best_strategy`, `improvement_ratio` (best/worst efficiency).

**Implementation quality: 6/10** — clean frozen dataclasses, content-addressed result. **But:** (a) `_strategies` is an in-memory dict — not persisted. `record_strategy` overwrites the same `strategy_id` without accumulating — calling `record_strategy("ucb", 10, 5, 100)` then `record_strategy("ucb", 20, 8, 150)` loses the first record; (b) `efficiency = accuracy / max(0.01, compute_cost)` (line 34) — magic 0.01 floor, no comment. If `compute_cost=0`, efficiency = accuracy / 0.01 = 100×accuracy — a free strategy would dominate; (c) `improvement = best.efficiency / max(0.01, worst.efficiency)` (line 95) — if `worst.efficiency` is 0, `improvement = best/0.01 = 100×best`, which can be a huge number; (d) the orchestrator instantiates `MetaLearner()` at line 675 as a LOCAL variable — never attached to `self.`, never persisted across runs. So meta-learning across runs does NOT happen; only within a single run. This defeats the stated purpose ("learning to learn" across the research process).

**Test coverage: 1/10** — **No dedicated test file.** Only a smoke check `from metaengine.meta_learning import MetaLearner; learner = MetaLearner(); assert MetaLearner is not None` in `tests/test_phases_24_30.py` (verified via Grep). **Gaps:** no test for `record_strategy` overwrite behavior, no test for `compare_strategies` ranking, no test for `improvement_ratio` edge cases (worst=0, single strategy, empty).

**Connectivity: 3/10** — 4 importers: `metaengine/meta_learning.py` (self), `metaengine/orchestrator.py` (line 61 import, line 675 instantiation), `tests/test_phases_24_30.py`, `CRITICAL_ANALYSIS_TRAINING_METHODS.md`. Wired into orchestrator but used ephemerally.

**Weak spots:**
1. `record_strategy` overwrites instead of accumulating.
2. `MetaLearner` not persisted across runs (orchestrator creates a local instance per run).
3. Magic 0.01 floor in efficiency computation.
4. No tests.

**Recommendations:**
1. Write `tests/test_meta_learning.py` (~10 tests): record_strategy overwrite, compare_strategies ranking (best/worst), improvement_ratio edge cases (empty, single, worst=0), `efficiency` floor, content-addressed `result_hash`.
2. Change `record_strategy` to accumulate: if `strategy_id` exists, merge by appending to a list of `(experiments, correct, cost)` tuples and recompute aggregates.
3. Persist `MetaLearner` to `storage/meta_learning.json` after each orchestrator run; load on init.
4. Attach `self.meta_learner` in orchestrator instead of local variable.

**Replacement alternative:** None — the design is sound; the fixes are persistence + tests.

---

### 12. `uncertainty_calibration.py` — 61 LOC, NO dedicated test file

**Purpose:** Measures how well the engine's prediction confidence matches actual correctness. `add_observation(predicted_confidence, actual_correct)`, `calibration_error()` returns mean absolute calibration error (ECE-style) bucketed by 0.1 confidence intervals.

**Implementation quality: 7/10** — clean and minimal. ECE-style bucketing is correct: `bucket = round(conf * 10) / 10` (line 38), then `errors.append(abs(bucket - actual_rate))` per bucket, mean across buckets. **But:** (a) `_observations` is in-memory only — no persistence. Same anti-pattern as `meta_learning.py`: orchestrator instantiates `UncertaintyCalibrator()` at line 489 as a local variable, computes `calibration_error()`, writes to JSON, then discards. Next run starts from zero observations — so cross-run calibration drift is never tracked; (b) `bucket = round(conf * 10) / 10` can produce `bucket = 1.0` for `conf >= 0.95`, but `actual_rate` is in `[0, 1]` — fine, but the bucketing is coarse (10 buckets only); (c) no reliability diagram, no sigmoid fitting, no temperature scaling — just the raw ECE; (d) `calibrator_hash()` includes `observation_count` and `calibration_error` but NOT the observations themselves — two calibrators with the same error but different bucket distributions would have the same hash. This is a content-addressing weakness.

**Test coverage: 1/10** — **No dedicated test file.** No incidental test found (the Grep hits in `test_phases_17_22.py` are for the word "uncertainty" in task features, not for `UncertaintyCalibrator`). **Gaps:** no test for bucketing, no test for empty observations, no test for the calibration_error formula, no test for `calibrator_hash` determinism.

**Connectivity: 3/10** — 3 importers: `metaengine/orchestrator.py` (line 49 import, line 489 instantiation), `metaengine/uncertainty_calibration.py` (self), `tests/test_phases_17_22.py` (word match only, not actual import). Wired into orchestrator but used ephemerally.

**Weak spots:**
1. Not persisted across runs — calibrator is reset to zero observations every run.
2. `calibrator_hash` excludes the observations — two calibrators with same error but different distributions collide.
3. No reliability diagram or temperature scaling.
4. No tests.

**Recommendations:**
1. Write `tests/test_uncertainty_calibration.py` (~8 tests): empty observations (error=0), single bucket, multi-bucket, perfect calibration (error=0), worst calibration (error=0.5), `calibrator_hash` determinism, `payload()` shape.
2. Persist `UncertaintyCalibrator` to `storage/calibration.json` after each run; load on init.
3. Include the bucket distribution in `calibrator_hash` (or hash the observations list directly).
4. Add `reliability_diagram()` returning `list[(bucket, predicted_confidence, actual_rate, count)]` for visualization.

**Replacement alternative:** None — ECE is the right baseline; the fixes are persistence + tests.

---

## Top 5 Cross-Cutting Critical Findings

### Finding 1: **5 of 12 infrastructure modules have NO dedicated test file**
Modules: `local_outcome_oracle.py`, `telemetry.py`, `biographies.py`, `meta_learning.py`, `uncertainty_calibration.py` — collectively **562 LOC of source code** with zero direct unit tests. This is the same anti-pattern flagged in Group B for `cross_model_transfer_tester.py` and Group A for 14 of 17 core modules: small "leaf" modules are systematically neglected despite high connectivity (`biographies.py` has 14 importers — the most-connected module in this group). The existing test suites for the 7 tested modules pass (114 tests, 1 skipped), but the 5 untested modules are exercised only via orchestrator integration, where failures are hard to attribute.

### Finding 2: **`federation_bridge.py` hardcodes canonical anchors (5×)**
`"metaengine-chat-2.3.0-alpha.1-cp001"` appears 4× (lines 107, 126, 174, 206) and the active policy hash `"1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"` appears 1× (line 207). This duplicates the orchestrator.py anti-pattern flagged in Group A (hardcoded constitution hash). If the canonical checkpoint ever advances (Slice-3 → Slice-4 → …), this bridge silently produces federation receipts against a stale checkpoint. `finalize_epoch` should accept `base_checkpoint_id` and `policy_hash` as parameters (already accepted by `create_epoch` and `dispatch_task` — just not by `finalize_epoch`).

### Finding 3: **`cross_run_accumulator.py` has 7 silent `except Exception: pass` blocks**
Lines 160, 215, 231, 253, 265, 306, 337. Each one masks persistent state corruption: if a JSON parse fails on a run-dir artifact (e.g. truncated `REASONING_TRACE_EXTRACTION.json`), the accumulator silently reports `new_mechanisms: 0` and moves on. The module's stated purpose is "idempotent accumulation", but silent catches make it a data-losing black hole. Worse: `accumulate_run` synthesizes fake mechanism IDs `f"trace.{run_id[:12]}.{i:02d}"` from a count (line 211) instead of reading real IDs — so two runs with colliding `run_id[:12]` prefixes are falsely treated as idempotent. **And the orchestrator does not call `CrossRunAccumulator.accumulate_run()` at all** — so the cross-run loop is not closed; the module is wired only into the benchmark/strict-test pipeline, not into every orchestrator run as its docstring claims.

### Finding 4: **`signed_provenance.py` is the bright spot (9/10) — but the orchestrator misuses it**
Ed25519 implementation with correct self-reference handling (`payload_hash_field` stripped before signing, re-inserted after), defensive `from_dict` re-verification, public-key-only `to_public_record` (Boundary 6 compliant). This is the model other receipt-style modules should follow. **BUT:** `orchestrator.py:452` calls `generate_signing_keypair()` PER RUN, producing a new keypair and a new `public_key_hex` in every `SIGNED_RUN_RECEIPT.json`. This defeats cross-run verification — a receipt from run N cannot be verified against the keypair from run N+1. The module's own docstring says "The signing key is generated once per project and stored as a secret" — the orchestrator violates this. **Fix:** `orchestrator.py` should call `load_project_signing_keypair()` (read from a secret path), generating only once on first run.

### Finding 5: **`biographies.py` is the most-connected module (14 importers) and also the worst-formatted**
91 LOC of dense one-liners: `b['mean_realized_gain']=round((b.get('mean_realized_gain',0.5)*n+g)/(n+1),4)` (line 63). No docstrings on methods, no type annotations, no helper extraction. Used by scheduler, topology library, evolution engine, RLAIF trainer, CLI, and 6 test files. **Real correctness issue:** `pair_prior(A, [B])` reads A's record for peer B; `pair_prior(B, [A])` reads B's record for peer A. These are NOT necessarily equal (asymmetric observation counts), but the function name suggests symmetry — a real bug for any coalition-formation code relying on it. Also: `DOMAINS` tuple (line 6) is dead code; `biography_hash` computed twice (update + snapshot). Highest-leverage refactor opportunity in Group D.

---

## Cross-Cutting Anti-Patterns

### A. **`except Exception: pass` data-loss pattern** (13 occurrences across 3 modules)
- `cross_run_accumulator.py`: 7 occurrences (silent accumulation data loss)
- `api_server.py`: 4 occurrences (silent handler failures; 2 are `pass`, 2 log to error response)
- `external_validator.py`: 2 occurrences (validator failures → 0.5 fallback scores)

The `api_server.py` pattern (return 500 to client) is acceptable; the `cross_run_accumulator.py` pattern (silently drop data) is not; the `external_validator.py` pattern (mask as 0.5) is borderline.

### B. **Hardcoded canonical anchors** (5+ occurrences across `federation_bridge.py`)
Duplicates the Group A finding for `orchestrator.py` (hardcoded constitution hash). The canonical checkpoint ID and active policy hash should be read from disk via `canonical_connector.verify_against_expected()`, not baked into bridge source.

### C. **In-memory-only "accumulation" modules that don't accumulate across runs**
- `meta_learning.py`: `MetaLearner` instantiated as local variable in orchestrator.py:675; never persisted.
- `uncertainty_calibration.py`: `UncertaintyCalibrator` instantiated as local variable in orchestrator.py:489; never persisted.
- `local_outcome_oracle.py`: `LocalOutcomeOracle.create(source_text)` per run; no cross-run commitment comparison.
- `cross_run_accumulator.py`: HAS persistence (`storage/accumulated_state.json`) but is NOT called by orchestrator — wired only into benchmark.

These four modules share the same anti-pattern: their stated purpose is cross-run learning, but the orchestrator treats them as ephemeral. The cross-run learning loop is open at the orchestrator integration layer.

### D. **Magic constants without comments**
- `biographies.py`: `confidence=min(1.0,obs/24)` — why 24?
- `predictive_model.py`: `conf = min(1.0, len(policy_obs) / 10.0)` — why 10?
- `external_validator.py`: `PASS_THRESHOLD = 0.6`, weights `0.40/0.20/0.25/0.15` — why?
- `meta_learning.py`: `max(0.01, compute_cost)` — why 0.01?
- `local_outcome_oracle.py`: `valid_spans / total_spans >= 0.5` — why 50%?
- `adaptation_bridge.py`: `max(2, min(6, ...))` — why 2/6?

### E. **Per-run keypair regeneration** (`orchestrator.py:452`)
`generate_signing_keypair()` is called per run, defeating cross-run signature verification. The `signed_provenance.py` docstring explicitly says "generated once per project and stored as a secret" — the orchestrator violates this.

---

## Bright Spots

1. **`signed_provenance.py` (9/10)** — best-structured module in Group D. Correct Ed25519 usage, self-reference-safe hashing, defensive `from_dict` re-verification, Boundary 6 compliant `to_public_record`. Model for other receipt modules.
2. **`telemetry.py` (8/10)** — excellent for 70 LOC. Hash-chained events, secret redaction by default, explicit `MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER` for token/USD data, correct `span()` context manager with FAILED path.
3. **`cross_run_accumulator.py` test suite (8/10, 30 tests)** — best test coverage in Group D despite the implementation's silent-catch anti-pattern. The `mock_run_dir` fixture is realistic. If the 7 silent catches were fixed, the tests would catch the data-loss bugs.
4. **`adaptation_bridge.py` (7/10)** — appropriately minimal (159 LOC). The D6-G1 guard is invoked correctly (defense in depth, even if redundant). Clean separation between `build_metrics_from_run` and `build_adaptation_from_run`.
5. **`api_server.py` rate limiter (7/10)** — real token-bucket implementation, per-endpoint buckets, configurable. The 429 response includes `Retry-After` header. Only weak spot is the missing thread-lock on `_rate_limit_state`.

---

## Top 3 Prioritized Recommendations

### Recommendation 1: **Write the 5 missing dedicated test files**
- `tests/test_local_outcome_oracle.py` (~15 tests, 2h)
- `tests/test_telemetry.py` (~10 tests, 1.5h)
- `tests/test_biographies.py` (~20 tests, 3h) — highest leverage (14 importers)
- `tests/test_meta_learning.py` (~10 tests, 1.5h)
- `tests/test_uncertainty_calibration.py` (~8 tests, 1h)

**Total: ~63 tests, ~9 hours.** Closes the largest test-coverage gap in Group D. After this, all 12 modules have dedicated test files; the orchestrator integration tests can then focus on integration (not unit correctness).

### Recommendation 2: **Fix the 7 silent `except Exception: pass` blocks in `cross_run_accumulator.py` + wire it into orchestrator**
Replace each silent catch with `errors.append(f"...: {exc}")` and surface in the `accumulate_run()` return dict. Then add `accumulator.accumulate_run(out, run_id=run_id); accumulator.save()` to `Orchestrator.run()` after the run completes (~5 LOC change + 1 integration test). This closes the cross-run accumulation loop — the module's stated purpose — which is currently open because the orchestrator doesn't call it. **Estimate: 4 hours.**

### Recommendation 3: **Extract canonical anchors from `federation_bridge.py` + fix per-run keypair regeneration in orchestrator**
- `federation_bridge.py`: accept `base_checkpoint_id` and `policy_hash` as parameters to `finalize_epoch` (already accepted by `create_epoch` and `dispatch_task`); pass them through from `run_federated()`. (~30 min)
- `orchestrator.py:452`: replace `generate_signing_keypair()` with `load_project_signing_keypair()` — read from a secret path (e.g. `~/.metaengine/signing_key.hex`, mode 0600); generate only on first run. Persist the public key in `project_meta.json`. (~2h + tests)

**Estimate: 2.5 hours.** Eliminates 5 hardcoded anchors + 1 cross-run signature verification break. Both are correctness hazards if the canonical checkpoint ever advances or if historical receipts need verification.

---

## Secondary Recommendations (5)

4. **Replace `external_validator._parse_validator_response`'s regex `r'\{[^}]*\}'`** with a real JSON parser that handles nested braces (analysis field commonly contains `}`). Add a test with nested JSON. (~1h)
5. **Make `biographies.pair_prior` symmetric** (or document the asymmetry explicitly). Add `tests/test_biographies.py::test_pair_prior_symmetry` that asserts `pair_prior(A, [B]) == pair_prior(B, [A])` after symmetric updates. (~1h)
6. **Add thread-lock to `api_server._rate_limit_state`** mutations (or replace with `collections.deque` + atomic `len()`). Add a concurrent-POST test. (~1h)
7. **Persist `MetaLearner` and `UncertaintyCalibrator` across runs** — write to `storage/meta_learning.json` and `storage/calibration.json` after each orchestrator run; load on init. Attach to `self.` in orchestrator instead of local variables. (~2h)
8. **Distinguish `producer_concurrency` from `candidate_count` in `adaptation_bridge.build_metrics_from_run`** — they are currently both mapped to `coord.get("deep_engine_executions", 0)`. (~30 min)

---

## Tertiary Recommendations (4)

9. **Add `verify_manifest(manifest_receipt, expected_keypair, receipt_hashes)` helper to `signed_provenance.py`** — currently `sign_manifest` exists but verification requires manual `SignedReceipt.verify()` on the manifest + separate verification of each receipt. (~1h)
10. **Replace the 36-branch elif dispatcher in `api_server.do_GET`** with a dict mapping `(method, path)` → handler callable. (~1.5h, ~30 LOC reduction)
11. **Add per-dimension tolerance to `predictive_model.verify_prediction`** — `quality_tol=0.15, cost_tol=0.50, latency_tol=0.50` (or relative tolerance). The current uniform 0.15 on cost (USD) is much stricter than on quality (0..1). (~30 min)
12. **Document the magic constants** (`biographies.py:38 obs/24`, `predictive_model.py:119 len/10`, `local_outcome_oracle.py:96 0.5`, `meta_learning.py:34 0.01`, `adaptation_bridge.py:143 2/6`) as named class constants with docstrings explaining the choice. (~1h, no behavior change)

---

## Final Verdict

**Group D is mid-tier quality with one bright spot and one critical bug class.** The implementation average (6.75/10) is above Group A's 5.5/10 but below Group B's 6.5/10. Test coverage (4.92/10) is below Group B's 6.1/10 due to 5 modules with no dedicated test file. The bright spot (`signed_provenance.py`) shows the team can write excellent code; the critical bug class (silent `except Exception: pass` + un-persisted "accumulation" modules + hardcoded canonical anchors) shows the integration discipline gap between module-level correctness and system-level correctness.

The single highest-leverage fix is **Recommendation 2**: wiring `CrossRunAccumulator` into the orchestrator + replacing the 7 silent catches. This closes the cross-run learning loop — the stated purpose of 4 of the 12 modules (`cross_run_accumulator`, `meta_learning`, `uncertainty_calibration`, `local_outcome_oracle`) — and turns 4 "ephemeral print-and-forget" modules into actual cross-run accumulators. Without this fix, the infrastructure group is largely theater: it computes metrics per run, writes JSON files, but never learns from them.

The second-highest-leverage fix is **Recommendation 1**: writing the 5 missing test files. `biographies.py` alone has 14 importers — a bug there propagates to scheduler, topology library, evolution engine, RLAIF trainer, CLI, and 6 test files. Currently it has zero dedicated tests.

No code changes were made (analysis-only task). Constitution preserved: no source files modified, no canonical state touched.
