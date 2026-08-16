# Critical Analysis — Group E: Analysis Modules

**Task ID:** crit-E-analysis
**Agent:** Z.ai Code (general-purpose sub-agent)
**Scope:** 16 analysis modules in `METAENGINE_SLICE3_RESTORED/metaengine/`
**Method:** Read-only inspection — full source read of every module; existing dedicated test suites executed; import-graph mapped via `rg`.

---

## Executive Summary

| # | Module | LOC | Test LOC | Tests | Impl | Tests | Conn |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | evidence_graph.py | 269 | 138 | 12 | 7 | 7 | 3 |
| 2 | dialectical_graph.py | 156 | 0 | 0 | 5 | 0 | 4 |
| 3 | mechanism_library.py | 356 | 185 | 13 | 9 | 9 | 9 |
| 4 | cross_run_verification.py | 173 | 165 | 14 | 7 | 8 | 3 |
| 5 | architecture_sources.py | 706 | 305 | 10 | 9 | 9 | 4 |
| 6 | strict_test_factory.py | 739 | 278 | 40 | 6 | 7 | 2 |
| 7 | unified_benchmark.py | 633 | 273 | 29 | 6 | 7 | 2 |
| 8 | sealed_benchmark.py | 122 | 0 | 0 | 5 | 0 | 3 |
| 9 | worldbench.py | 394 | 0 | 0 | 7 | 0 | 2 |
| 10 | failure_taxonomy.py | 87 | 0 | 0 | 6 | 0 | 3 |
| 11 | transformation_graph.py | 62 | 0 | 0 | 4 | 0 | 3 |
| 12 | transformation_extractor.py | 78 | 0 | 0 | 6 | 0 | 4 |
| 13 | causal_attribution.py | 77 | 0 | 0 | 6 | 0 | 3 |
| 14 | nonlinearity.py | 102 | 0 | 0 | 5 | 0 | 4 |
| 15 | epistemic_gain.py | 46 | 0 | 0 | 4 | 0 | 4 |
| 16 | information_gain_selector.py | 71 | 0 | 0 | 7 | 0 | 4 |
| **Total / Avg** | **4,071** | **1,344** | **118** | **6.2** | **2.9** | **3.3** |

**Test ratio (LOC):** 1,344 / 4,071 = **0.33**
**Modules with NO dedicated test:** 10 of 16 = **62.5%**
**Existing test suites run:** 118 test functions, **all PASS** (123 dots including parametrized expansions, ~0.6 s).
**Orphan modules (zero production importers):** **0** — every module is imported by at least one production path (orchestrator.py imports 10; cli.py imports 2; api_server.py lazily imports 1; one importer each for the remaining 3).
**Brightest spot:** `mechanism_library.py` (9/9/9 — full A0–A3 state machine, evidence-gated admission, hash re-verification, lazy import to break circular dependency, 7 importers).
**Worst spot:** `transformation_graph.py` (4/0/3 — 62 LOC on 6 dense one-liner lines; duplicate state fields `_last_by_engine`/`latest_by_engine` and `_last_topology`/`last_topology` carried in parallel).

---

## Per-Module Analysis

### 1. `evidence_graph.py` — Evidence Graph Builder (Phase 3, 269 LOC)

**Purpose:** Builds a content-addressed causal evidence chain over orchestrator outputs:
`Claim ← Evidence ← Experiment ← ExecutionReceipt ← OrganizationPolicy ← Resources ← Checkpoint`. Edges: CONTRADICTS, REPLICATES, SUPERSEDES, RETRACTS, NARROWS_SCOPE, SUPPORTS, DERIVES_FROM. Adds Phase 8 accumulation primitives (`merge`/`load`/`save`).

**Implementation quality: 7/10**
- Clean frozen `@dataclass(frozen=True)` design: `EvidenceNode`, `EvidenceEdge`, `EvidenceGraph` all immutable.
- `from_dict` re-verifies `graph_hash` against recomputed hash (raises `EVIDENCE_GRAPH_HASH_MISMATCH`).
- `add_node`/`add_edge` are idempotent (returns same graph if signature already present).
- `merge` is correctly idempotent (uses `add_node`/`add_edge`).
- `build_evidence_graph_from_run` creates checkpoint + experiment + claim + verifier + (optional) oracle nodes in a single pass.
- `claim_ceiling = "EVIDENCE_GRAPH_ACCUMULATES_KNOWLEDGE_NOT_TRUTH"` + `truth_effect = "NONE"` on payload — constitution discipline excellent.

**Test coverage: 7/10 (12 tests, all pass)**
Covers: node/edge creation, empty graph, deterministic hash, idempotent add, tampered-hash rejection, build_from_run with/without oracle, claim nodes from dialectical graph. **Missing:** merge/load/save round-trip tests (Phase 8 accumulation is the main feature but is untested), `as_dict`/`from_dict` round-trip with nested nodes/edges, `EvidenceEdgeKind` enum coverage.

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. `EvidenceNode.from_dict` does NOT re-verify `content_hash` against the description — only the graph-level `graph_hash` is checked. A tampered node hash could survive if the graph_hash is also re-forged. (Low risk because graph_hash covers nodes, but asymmetric with mechanism_library which re-verifies per item.)
2. `EvidenceStatus.VERIFIED_LOCAL` is hardcoded for checkpoints and experiments in `build_evidence_graph_from_run` — even when `run_result["status"]` is `"FAILED"`.
3. `load` returns empty graph on file-not-found (correct for first-run semantics) but doesn't expose "file existed but was corrupt" — `from_dict` raises `ValueError`, which propagates as an unhandled exception to the orchestrator.
4. `EvidenceEdgeKind` has 7 values but `build_evidence_graph_from_run` only ever emits `DERIVES_FROM` and `SUPPORTS` — `CONTRADICTS`/`REPLICATES`/`SUPERSEDES`/`RETRACTS`/`NARROWS_SCOPE` are dead enums in practice.

**Recommendations:**
1. Add `test_merge_idempotent`, `test_load_save_roundtrip`, `test_load_corrupt_raises`.
2. Set checkpoint/experiment status from `run_result["status"]` (FAILED → `EvidenceStatus.CONTRADICTED`).
3. Wire `CONTRADICTS`/`SUPERSEDES` edges when a new run's evidence contradicts an existing accumulated graph node (closes the "scientific knowledge" loop the docstring claims).

---

### 2. `dialectical_graph.py` — Typed Hermeneutic Graph (156 LOC)

**Purpose:** Builds a typed dialectical graph applying 10 hermeneutic operators (SOURCE_READING, HORIZON_DISCLOSURE, RIVAL_FORK, SEMANTIC_COUNTERFACTUAL, GENEALOGICAL_RETURN, EVIDENCE_DISCRIMINATOR, DOUBLE_HERMENEUTIC, SUBLATION_WITH_RESIDUE, OPERATOR_MUTATION, SOURCE_RETURN) over a source text. R5 extends to multi-engine discourse (engine contributions + cross-engine RIVAL_FORK + EVIDENCE_DISCRIMINATOR + SUBLATION_WITH_RESIDUE).

**Implementation quality: 5/10**
- 156 LOC in essentially one massive `build()` method — no docstrings on `_sentences`/`_span`/`add` helper.
- Each operator emits hardcoded strings ("Interpretive horizon exposes modality…") with hardcoded confidence values (0.55, 0.4, 0.7, 0.6, 0.5, 0.45, 0.4) — these are not labeled as priors, no calibration mechanism.
- `truth_status` correctly set to `SOURCE_BOUNDED_READING_NOT_VERIFIED_FACT` for SOURCE_READING and `GENERATIVE_ONLY` for derived — constitution discipline excellent.
- The `add()` helper takes `**extra` and pops known keys, leaving the rest as `**extra` in the node dict — fragile (typos silently survive as extra fields).
- `_sentences` uses `re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text)` — doesn't handle abbreviations ("Dr.", "e.g.") — will fragment sentences.
- Engine-discourse block (lines 104–131) is the densest part: nested `next(n for n in nodes if …)` lookup inside a double loop is O(n²) and assumes engine_id uniqueness without checking.
- Bilingual regex (lines 65, EN+RU markers) is a thoughtful touch but is the ONLY bilingual element — other modules are EN-only, suggesting partial localization.

**Test coverage: 0/10 — NO dedicated test file** (highest-priority missing test — 2 importers including `worldbench.py`).

**Connectivity: 4/10 (2 importers: orchestrator.py, worldbench.py)**

**Weak spots:**
1. **No tests at all** despite being central to both orchestrator and worldbench — 156 LOC of complex regex/loop logic with zero coverage.
2. `_sentences` regex doesn't handle abbreviations or quotes — will produce nonsense spans on real prose.
3. Confidence values (0.55/0.4/0.7/0.6/0.5/0.45/0.4) are pure magic constants — no calibration, no schema for what "0.55 confidence" means.
4. Engine-discourse block assumes engine_id uniqueness but never asserts it.
5. `canonical_hash(node)` is called BEFORE `node["node_id"]` is set — but `node["node_id"]` is set TO `"dial-" + canonical_hash(node)[:20]`, so the hash input excludes node_id (correct). However, the `**extra` splat means ANY caller-supplied kwarg becomes part of the hash input — non-deterministic if callers vary extra fields.

**Recommendations:**
1. Write `tests/test_dialectical_graph.py` — at minimum: build with empty source, build with all 10 operators active, build with engine_contributions, verify `truth_effect=NONE` on every node, verify graph_hash determinism, verify `policy.validate()` is called.
2. Replace `_sentences` with `nltk` or `spacy` sentence tokenizer, OR document the limitation explicitly in the docstring.
3. Replace magic confidence constants with a `ConfidencePrior` enum/dataclass.
4. Hoist `**extra` to explicit named fields — silent extra-kwargs is a typo bug class.

---

### 3. `mechanism_library.py` — Mechanism Library A0–A3 (Slice 4, 356 LOC)

**Purpose:** Full A0→A1→A2→A3 mechanism state machine with **evidence-gated admission**: A0/A1 require no receipt (hypothesis stage); A2/A3 require an `AssimilationReceipt` in `promotion_authority`. Only A3 may influence organization generation; `assert_no_a3_influence()` enforces the SEPARATE_GENERATION_AND_PROMOTION invariant in Slice 3.

**Implementation quality: 9/10 — model module**
- Frozen dataclass with 16 fields, all validated in `create()` and re-validated in `validate()`.
- A2/A3 admission gated by `promotion_authority is None` check (raises `A2_REQUIRES_GATE_RECEIPT` / `A3_REQUIRES_GATE_RECEIPT`).
- `_receipt_hashes` validates all `experiment_receipts`/`ablation_receipts`/`transfer_receipts` are 64-char hex — fails fast on receipt forgery.
- `from_dict` calls `_deserialize_promotion_authority` which **lazily imports** `AssimilationReceipt` to avoid circular import — and the lazy import re-verifies the receipt hash.
- `MechanismLibrary.create` deduplicates by `mechanism_id` (raises `MECHANISM_ID_DUPLICATE`).
- `from_dict` re-verifies `library_hash` against recomputed hash (raises `LIBRARY_HASH_MISMATCH`).
- `verify()` independently re-hashes every candidate and the library — useful for tamper detection.
- `load` returns empty library on file-not-found (first-run semantics); `save` uses `write_json` (canonical).
- `add_candidate` is idempotent on `mechanism_id`.

**Test coverage: 9/10 (13 tests, all pass)**
Covers: enum has 4 states, Slice 3 admits A0/A1 only, Slice 4 rejects A2/A3 without gate receipt, create+hash roundtrip, tampered-hash rejection, origin_source_ids required, receipt_hashes must be hex, library order-independence, duplicate rejection, library from_dict roundtrip, `assert_no_a3_influence` in Slice 3, version constant. **Missing:** `add_candidate` idempotency test, `load`/`save` round-trip test, `verify()` returns False on tampered library.

**Connectivity: 9/10 (7 importers — strongest hub in Group E):** orchestrator, cross_model_transfer_tester, assimilation, trace_extractor, policy_generator, selfplay_trainer, assimilation_loop.

**Weak spots:**
1. `validate()` is called twice on every `create()` (once at end of `create`, once via `payload()` callers? No — `payload()` also calls `validate()`). Triple validation on serialization.
2. `promotion_authority: Any` type annotation (with comment "lazy-typed to avoid circular import") — loses type safety. Could use `TYPE_CHECKING` block for proper typing without runtime cost.
3. `assert_no_a3_influence` raises `MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN_IN_SLICE3` — the error code mentions "SLICE3" but the module is Slice 4. Stale error message.
4. `MechanismCandidate.from_dict` deserializes `promotion_authority` via `_deserialize_promotion_authority` — but if the receipt hash is tampered, `AssimilationReceipt.from_dict` raises and the caller gets an opaque `ValueError` rather than `MECHANISM_AUTHORITY_TAMPERED` code.

**Recommendations:**
1. Add `test_add_candidate_idempotent`, `test_load_save_roundtrip`, `test_verify_detects_tamper`.
2. Use `TYPE_CHECKING` block: `if TYPE_CHECKING: from .assimilation import AssimilationReceipt` for proper type hints.
3. Rename `MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN_IN_SLICE3` → `MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN` (Slice-agnostic).
4. Wrap `_deserialize_promotion_authority` failures in a `MechanismAuthorityError(code="MECHANISM_AUTHORITY_TAMPERED")`.

---

### 4. `cross_run_verification.py` — Ed25519 Cross-Run Verification (Phase 12, 173 LOC)

**Purpose:** Verifies Ed25519 signatures on persisted artifacts when loading them on subsequent runs. Closes the feedback loop: signed_receipt (run N) → verification (run N+1). If a signature is invalid (tampered), the orchestrator refuses to load.

**Implementation quality: 7/10**
- `VerificationResult` is a frozen dataclass with `verified`/`reason`/`payload_hash` — clean public contract.
- `verify_signed_artifact` correctly handles: file-not-found (FILE_NOT_FOUND), corrupt JSON (LOAD_FAILED), missing signature fields (NO_SIGNATURE — first run), public-key mismatch (PUBLIC_KEY_MISMATCH), signature verification (SIGNATURE_VALID / SIGNATURE_INVALID).
- Uses `cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey` directly — minimal dependency surface.
- `verify_accumulated_state` walks a hardcoded list of 4 artifacts (`storage/evidence_graph.json`, `storage/mechanism_library.json`, `storage/predictive_model.json`, `SIGNED_RUN_RECEIPT.json`).
- **BUG (line 98):** duplicate import `from .signed_provenance import SigningKeyPair` inside the function body — the same name was already imported at module top (line 18). Dead code.
- **`except Exception` 3× (lines 114, 121, 155):** all silent — `SIGNATURE_INVALID` and `VERIFICATION_ERROR` swallow the underlying exception object only into the reason string, losing stack trace. `verify_accumulated_state`'s `except Exception: return {}` (line 155) silently returns empty dict if the key file is corrupt — caller cannot distinguish "no key configured" from "key file corrupt".

**Test coverage: 8/10 (14 tests across 2 classes, all pass)**
Covers: signed artifact verification, public key mismatch, no-signature case, file-not-found, valid signature, invalid signature, accumulated state verification. **Missing:** corrupt public key file (`verify_accumulated_state` returns `{}` silently), `payload_hash_field` parameter variation, concurrent verification.

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. **Duplicate import (line 98):** `from .signed_provenance import SigningKeyPair` — dead code (already imported at module top).
2. **3 silent `except Exception`:** line 114 (signature verification), line 121 (overall try), line 155 (key file load). All swallow the exception.
3. **Hardcoded artifact list (lines 162–167):** 4 paths hardcoded. If a new signed artifact is added, this list must be manually updated.
4. **`verify_accumulated_state` returns empty dict on any error:** caller cannot distinguish "no public key configured" (expected first run) from "public key file is corrupt" (security incident).
5. **No `verify_accumulated_state` test for the "no key" path** — likely untested branch.

**Recommendations:**
1. Remove duplicate import (line 98).
2. Replace silent `except Exception` with explicit `except (ValueError, TypeError) as exc:` for signature verification; log the full traceback at WARNING level.
3. Replace hardcoded artifact list with a glob pattern (`storage/*.json` + `SIGNED_RUN_RECEIPT.json`) or a registry.
4. Have `verify_accumulated_state` return a sentinel `{"_error": "..."}` instead of `{}` on key-file corruption.
5. Add `test_verify_accumulated_state_corrupt_key_file`.

---

### 5. `architecture_sources.py` — Source Registry (Slice 3, 706 LOC)

**Purpose:** Content-addressed registry for foreign architecture sources. Three source classes (PERMISSIVE_CODE / RESTRICTED_REFERENCE / CLOSED_BEHAVIORAL_ONLY), four ingestion statuses (REGISTERED_ONLY / INGESTED / BLOCKED / SUPERSEDED), architecture claims with three kinds (SOURCE_FACT / PUBLISHER_CLAIM / METAENGINE_HYPOTHESIS), mechanism candidates capped at A0/A1 (epistemic ceiling). Enforces license approval (MIT, Apache-2.0), blob path safety (no absolute paths, no `..`), and pack-root hash re-verification.

**Implementation quality: 9/10 — model module**
- Exhaustive input validation via `_text`/`_source_id`/`_sha256`/`_optional_sha256`/`_enum_value`/`_texts`/`_relative_path`/`_retrieved_at` helpers — all raise `ArchitectureSourceValidationError(code, detail)`.
- `_HEX_40_OR_64` regex permits both SHA-1 (40) and SHA-256 (64) git blob IDs — forward-compatible.
- `_relative_path` rejects absolute paths, `..`, empty parts, and `.` — full traversal-safety.
- `SourceRecord.create` enforces 7 cross-field invariants: CLOSED_BEHAVIORAL_ONLY cannot have descriptors/paths/digests; REGISTERED_ONLY cannot have digest/scope; BLOCKED requires blockers; INGESTED requires descriptors + digest + scope + path-match + pack-hash-match; PERMISSIVE_CODE requires permissive license + license digest in descriptor set; CLOSED cannot have SOURCE_FACT claims; mechanism status cannot exceed epistemic_ceiling.
- `SourcePack.create` recomputes `pack_root_sha256` from the canonical payload; `from_dict` rejects hash mismatch.
- `SourceRegistry.create` cross-checks records ↔ packs (VAULT_BLOB_MISSING, HASH_MISMATCH, NON_INGESTED_SOURCE_PACK_FORBIDDEN).
- `from_dict` re-verifies `registry_snapshot_sha256` — tamper-evident.
- Uses `devfabric.codec.canonical_digest` (separate from `util.canonical_hash`) — odd inconsistency but both are deterministic.

**Test coverage: 9/10 (10 tests, all pass)**
Covers: pack digest + descriptor order independence, record normalization + round-trip, tamper detection, permissive fail-closed on missing classification/evidence (parametrized), registered-only cannot claim digest, closed-behavioral cannot retain bytes, Slice-3 rejects A2/A3, blob path escape rejection (parametrized), registry snapshot order independence + ingested-pack requirement, pack hash changes on descriptor digest change. **Missing:** `SourceRegistry.from_dict` tamper test, `ArchitectureClaim.from_dict` round-trip, `MechanismCandidate.create` invalid-status rejection.

**Connectivity: 4/10 (1 importer: `reference_vault.py` — but foundational to Slice 3)**

**Weak spots:**
1. `_enum_value` has `raise AssertionError("unreachable") from exc` after `_fail(code, str(value))` — `_fail` always raises, so the `raise AssertionError` is dead code (defensive but unreachable).
2. `ArchitectureClaim.from_dict` and `MechanismCandidate.from_dict` both call `cls.create(**dict(value))` — if the input dict has extra keys, they become unexpected kwargs and raise `TypeError` (not `ArchitectureSourceValidationError`). Inconsistent with the rest of the module's error discipline.
3. `SourceRecord._payload` is a `@staticmethod` taking `**fields` and indexing by key — fragile (no type checking, KeyError on missing key). The `payload()` method does `fields = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "record_sha256"}` then `self._payload(**fields)` — works but is awkward.
4. `PERMISSIVE_LICENSE_EXPRESSIONS = frozenset({"MIT", "Apache-2.0"})` — hardcoded; no SPDX registry lookup. Adding a new permissive license requires code change.
5. `BlobDescriptor.create` checks `isinstance(size, bool)` to reject `True/False` as int — good defensive coding, but `size: int` annotation doesn't catch this at type-check time.

**Recommendations:**
1. Add `test_registry_from_dict_tamper`, `test_claim_from_dict_extra_keys_rejected`, `test_mechanism_invalid_status_rejected`.
2. Wrap `cls.create(**dict(value))` calls in a `_filter_known_fields` helper that rejects unknown keys with `ArchitectureSourceValidationError("UNKNOWN_FIELD", key)`.
3. Move `PERMISSIVE_LICENSE_EXPRESSIONS` to a config file or a SPDX allowlist module.
4. Remove the dead `raise AssertionError("unreachable")` lines (3 occurrences in `_enum_value`, `_retrieved_at`).

---

### 6. `strict_test_factory.py` — Strict Test Factory (Phase 55, 739 LOC)

**Purpose:** Generates and runs 25 test cases across 8 categories (CONSTITUTION_COMPLIANCE × 8, RLAIF_REWARD_QUALITY × 3, TRACE_EXTRACTION_QUALITY × 3, FAITHFULNESS_ACCURACY × 2, TRANSFER_VALIDITY × 2, RED_TEAM_DETECTION × 3, SYNTHESIS_VALIDATION × 2, ACCUMULATION_IDEMPOTENCY × 2). `ExternalValidator` uses LLM bridge as independent judge. Test results are observational (`truth_effect=NONE`).

**Implementation quality: 6/10**
- Well-structured test case catalog with `TestCase`/`TestResult`/`TestSuiteResult` dataclasses.
- `result_hash` and `suite_hash` are canonical hashes of the payload (excluding timing) — deterministic.
- `truth_effect=NONE` and `claim_ceiling="TEST_RESULT_IS_OBSERVATIONAL_NOT_TRUTH"` on every payload — constitution discipline excellent.
- **CRITICAL BUG:** 5 classes are prefixed `Test*` (`TestStatus`, `TestSeverity`, `TestCategory`, `TestResult`, `TestSuiteResult`) — pytest tries to collect them as test classes and emits `PytestCollectionWarning` for each (5 warnings visible in test run). The classes are uninstantiable as test classes (have `__init__`), so pytest skips them, but the warnings are noise and the naming convention is misleading.
- **SKIP-as-PASS bug:** 8 of the 25 test cases return `True` (PASS) when the data file is absent — `_test_no_truth_promotion` (line 442), `_test_preserve_abstention` (460), `_test_immutable_history` (520), `_test_rlaif_range` (531), `_test_rlaif_differentiated` (540), `_test_rlaif_source` (553), `_test_traces_non_empty` (561), `_test_faithfulness_range` (581), `_test_hallucination_non_negative` (590), `_test_transfer_rate_range` (600). This conflates SKIP with PASS — inflates the pass rate silently. The `TestSuiteResult.skipped` counter is always 0.
- **Hash mutation hack (line 701):** `result = TestResult(**{**result.__dict__, "result_hash": h})` — reconstructs the frozen dataclass via `__dict__` splat to set `result_hash`. Works but is fragile (breaks if `__slots__` is added). Should use `dataclasses.replace(result, result_hash=h)`.
- **`_test_no_code_modification` (line 473):** checks `now - mtime < 60` — any file touched in the last 60 seconds (e.g., by a developer editing code) will cause this test to FAIL, even if no run-time modification occurred. False-positive prone.
- **`_test_synthesis_valid_operators` (line 634):** calls `bridge._validate_mechanisms(["INVALID", "SOURCE_READING"])` — accesses a private method (`_validate_mechanators`) — couples the test to the internal API.

**Test coverage: 7/10 (40 tests across 7 classes, all pass)**
Covers: enum values, payload shapes, factory initialization, 8-category presence, constitution tests, RLAIF tests, redteam tests, callable test_fn, severity presence, run_all return, results count, pass_rate range, determinism, constitution tests, truth_effect=NONE, severity counting, 16 individual test functions, summary fields, summary categories, evaluative tests, no code modification by factory, no auto-promotion by factory. **Missing:** `_test_no_code_modification` false-positive test, skip-as-pass behavior assertion (the bug above is untested).

**Connectivity: 2/10 (1 lazy importer: `unified_benchmark.py:593` inside `all_modules_working` try/except — existence check only, not a real call)**

**Weak spots:**
1. **pytest collection warnings** — 5 `Test*` classes trigger warnings on every test run.
2. **SKIP-as-PASS bug** — 8 test cases silently return PASS when data files are absent; `skipped` counter is always 0.
3. **Hash mutation hack** — `TestResult(**{**result.__dict__, "result_hash": h})` instead of `dataclasses.replace`.
4. **False-positive file-mtime check** — `_test_no_code_modification` will fail if any developer edits the source within 60 s of the test run.
5. **Private method access** — `_test_synthesis_valid_operators` calls `bridge._validate_mechanisms` (private).
6. **Hardcoded storage paths** — 8 hardcoded paths like `storage/phase32_real_llm_run/engines/engine_16/CONTRIBUTION.json`.

**Recommendations:**
1. **Rename** `TestStatus`→`StrictTestStatus`, `TestSeverity`→`StrictTestSeverity`, `TestCategory`→`StrictTestCategory`, `TestResult`→`StrictTestResult`, `TestSuiteResult`→`StrictTestSuiteResult`. Eliminates 5 pytest warnings. ~30 min.
2. **Replace `return True  # SKIP`** with `return None` and treat `None` as SKIP in `run_all_tests` (increment `skipped` counter, set status=`TestStatus.SKIP`). Closes the pass-rate inflation bug. ~1 hour.
3. Replace `TestResult(**{**result.__dict__, "result_hash": h})` with `dataclasses.replace(result, result_hash=h)`.
4. Replace `now - mtime < 60` with a content-hash comparison (compute SHA-256 of the source file at start and end of run; FAIL if changed).
5. Extract hardcoded storage paths to a `StorageLayout` config class.

---

### 7. `unified_benchmark.py` — Unified Benchmark Suite (Phase 57–63, 633 LOC)

**Purpose:** 7 benchmarks inspired by GSM8K (math), TruthfulQA (truthfulness), MMLU (knowledge), HellaSwag (commonsense), BBH (reasoning), BBQ (safety), and a meta-benchmark for architecture self-development. Each benchmark uses an external LLM validator (independent judge). Constitution compliance verified across all benchmarks.

**Implementation quality: 6/10**
- Clean dataclass hierarchy: `BenchmarkTask` → `BenchmarkResult` → `BenchmarkCategoryResult` → `UnifiedReport`.
- `PASS_THRESHOLDS` dict per category (MATHEMATICS=0.70, TRUTHFULNESS=0.80, etc.) — magic constants but at least centralized.
- `truth_effect=NONE` and `claim_ceiling="BENCHMARK_REPORT_IS_EVALUATIVE_NOT_TRUTH"` on every payload.
- `_validate_exact_match` extracts the LAST number from the answer for math tasks — fragile (e.g., "The answer is 391, as shown in step 4" extracts "4").
- `constitution_score = 0.9` default in `_validate_exact_match` — bumps to 0.3 only if `"definitely true"` or `"absolutely certain"` substring matches. Substring match is naive ("indefinitely true" would trigger).
- `_call_llm` and `health_check` are **duplicated for the 4th time** across the codebase (also in `rlaif_trainer.py`, `redteam_adversary.py`, `llm_judge.py` per Group B findings).
- `_parse_judge_response` uses `re.search(r'\{[^}]*\}', response, re.DOTALL)` — won't match nested JSON. Returns `{"score": 0.5, "constitution": 0.5, "analysis": "PARSE_FAILED"}` on failure — silent fallback to 0.5 (neutral) rather than failing the benchmark.
- `run_all` imports 19 modules inside a try/except to set `all_modules_working` — if ANY module is missing, the flag is False, but the benchmark still runs and reports results. The flag is not surfaced as a hard failure.
- Task banks are hardcoded (`get_mathematics_tasks` returns 7 tasks, `get_truthfulness_tasks` returns 5, etc.) — no external dataset loading.

**Test coverage: 7/10 (29 tests across 7 classes, all pass)**
Covers: task bank non-empty, all categories present, math has 7 tasks, self-dev has 4 tasks, ground_truth/verification_type presence, BenchmarkResult payload, UnifiedReport payload, runner init, health_check returns bool, summary, solve_task returns string, exact match math correct/wrong, exact match knowledge correct, LLM judge returns result, parse judge response valid/malformed, run_all returns report, run_all with mock, identifies strengths, constitution compliant, all modules working, self-dev tasks exist/cover architecture, self-dev score in report, all results evaluative, no code modification, no auto-promotion. **Missing:** `_validate_exact_match` numeric extraction edge cases (e.g., "answer is 391, as shown in step 4"), `_call_llm` retry/timeout, `run_all` with `max_tasks_per_category=0`.

**Connectivity: 2/10 (1 lazy importer: `api_server.py:387` inside an HTTP handler)**

**Weak spots:**
1. **4th copy of `_call_llm` + `health_check`** — same bridge protocol triplicated per Group B findings, now quadruplicated.
2. **Naive substring matching for constitution_score** — `"definitely true" in answer_clean` matches "indefinitely true", "definitely untrue", etc.
3. **Silent fallback to 0.5** in `_parse_judge_response` — masks validator failures.
4. **Hardcoded task banks** — no external dataset loading; 7+5+5+4+4+3+4 = 32 tasks total, will be memorized quickly.
5. **`max_tasks_per_category=3` default** in `run_all` — only 21 tasks run by default, but `get_all_tasks()` returns 32. The default truncates silently.
6. **`PASS_THRESHOLDS` magic constants** — no documentation for why MATHEMATICS=0.70 vs TRUTHFULNESS=0.80.

**Recommendations:**
1. Extract `_call_llm`/`health_check` to `metaengine/llm_bridge_client.py` (closes 4-way duplication).
2. Replace substring matching with regex word-boundary match (`re.search(r'\bdefinitely true\b', answer_clean, re.I)`).
3. Raise on `_parse_judge_response` failure or log a WARNING and exclude the task from scoring.
4. Document `PASS_THRESHOLDS` rationale or move to a config file.
5. Add `test_validate_exact_match_extracts_last_number` (positive) and `test_validate_exact_match_rejects_step_number` (negative).

---

### 8. `sealed_benchmark.py` — Sealed Benchmark Suite (Phase 18, 122 LOC)

**Purpose:** Generates benchmark tasks UNKNOWN to the engine's candidate generator, policy evolution, and development workers — ensures capability gains are real, not benchmark overfitting. 8 sealed dimensions (REASONING_DEPTH, LONG_HORIZON_COHERENCE, PLANNING, ERROR_RECOVERY, UNCERTAINTY_CALIBRATION, NOVEL_PROBLEM_SOLVING, ROBUSTNESS_TO_MISLEADING_CONTEXT, CONTEXT_COMPRESSION).

**Implementation quality: 5/10**
- Clean `SealedDimension` enum + `SealedTask` frozen dataclass.
- `truth_effect="NONE"` and `claim_ceiling="SEALED_TASK_IS_EVALUATIVE_NOT_TRUTH"` on every payload.
- 8 task templates × 6 contexts = 48 unique combinations (but `generate_sealed_tasks(count=5)` only samples 5, with seed=42 for determinism).
- **Awkward hash-setting pattern (lines 98–113):** `SealedTask` is created with `task_hash=""`, then `canonical_hash(task.payload())` is computed, then a SECOND `SealedTask` is constructed with the hash. This breaks immutability ergonomics — should use a `@classmethod create` that computes the hash internally (pattern used everywhere else in the codebase).
- `suite_hash` calls `self.generate_sealed_tasks()` (default count=5) — side effect: computing the suite hash generates 5 tasks. Wasteful and surprising.
- `expected_outcome` is `{"must_identify": source_text[:50], "quality_threshold": 0.7, "dimension_scores": {d.value: 0.5 for d in dims}}` — `0.7` and `0.5` are magic constants.
- Only 6 contexts total — small sealed set; will repeat after 6 draws (with replacement, but the rng.choice can repeat).

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. **No tests.**
2. Awkward double-construction hash pattern (lines 98–113) — should be a `@classmethod create`.
3. `suite_hash` has a side effect (generates 5 tasks).
4. Only 6 contexts — small sealed set.
5. Magic constants `0.7` (quality_threshold) and `0.5` (dimension_scores default).

**Recommendations:**
1. Write `tests/test_sealed_benchmark.py` — generate 5 tasks, verify determinism (same seed → same tasks), verify `truth_effect=NONE`, verify `task_hash` is set, verify all dimensions covered, verify `suite_hash` doesn't mutate state.
2. Refactor to `SealedTask.create(...)` classmethod that computes `task_hash` internally.
3. Make `suite_hash` accept a `task_count` parameter or cache the generated tasks.

---

### 9. `worldbench.py` — World Benchmark + Evolution Campaign (394 LOC)

**Purpose:** Runs generation-frozen policies against content-addressed local outcome oracles. 6 suite blueprints (PARALLEL, SEQUENTIAL, ADVERSARIAL, TOOL_LIKE, HERMENEUTIC, EVIDENCE). `EvolutionCampaign` performs declarative policy evolution with paired outcomes, multiplicity-corrected lower-confidence-bound promotion gate, and rollback preservation.

**Implementation quality: 7/10 — strongest analytical engine in Group E**
- `_bootstrap_lcb` implements bootstrap lower-confidence-bound (1200 draws, alpha-quantile) — statistically sound.
- `_evaluate` performs successive halving: stage_one (8 candidates, 2 case-ordinals), stage_two (3 finalists, 2 case-ordinals), final (4 case-ordinals). Bonferroni correction `0.05 / len(finalists)`.
- Promotion gate requires: `lcb > 0.005` AND `failures == 0` AND `noninferior` (all suite mean deltas ≥ -0.02) AND `cost_ratio ≤ 1.60` — multi-criteria, conservative.
- `GENERATION_CROSS_WORLD_FREEZE` barrier: `learning_updates_before_barrier: 0`, `completion_order_excluded_from_decision: True` — proper learning-freeze discipline.
- `oracle_authority: "LOCAL_DETERMINISTIC_OUTCOME_NOT_FRONTIER_MODEL_EQUIVALENCE"` — explicit claim ceiling.
- `invariants` block lists 7 invariants (updates_only_after_generation_freeze, no self-mod code, no verifier mutation, no guardrail mutation, oracle invisible to candidate, rollback preserved, no structural proxies for promotion) — self-documenting.
- **`ThreadPoolExecutor.submit` doesn't handle exceptions** (line 180) — if `self._world` raises, `future.result()` will raise on iteration, aborting the entire run. No try/except around `future.result()`.
- **`_bootstrap_lcb` resampling bug (line 117):** `for _ in values` uses `len(values)` as the sample size (correct bootstrap), but `rnd.randrange(len(values))` is called `len(values)` times — fine. However, `index = max(0, min(len(means) - 1, int(alpha * len(means))))` — for `alpha=0.05` and `draws=1200`, `index = 60`, which is the 5th percentile. Correct.
- **`_candidates` (line 207):** generates `operator_sets` from missing operators, then itertools.combinations of 2 and 3. If `count > len(operator_sets)`, falls back to topology-only mutations (`HERMENEUTIC_SPIRAL`, `EVIDENCE_FIRST`, `ADVERSARIAL_FORK`, `GRAPH_RETURN`). The `while len(candidates) < count` loop will infinite-loop if `mutate_policy` produces duplicate hashes (line 223 dedupes, but the while doesn't check). Edge case.
- **Hardcoded `seeds: tuple[int, ...] = (17, 43)`** in `run()` — only 2 seeds by default, statistical power is low.

**Test coverage: 0/10 — NO dedicated test file.** (394 LOC of complex statistics + threading + promotion logic with zero coverage — highest-leverage missing test in Group E.)

**Connectivity: 2/10 (1 importer: `cli.py` only — control plane)**

**Weak spots:**
1. **No tests** — 394 LOC of LCB/bootstrap/successive-halving/promotion-gate logic with zero coverage. Highest-risk untested module in Group E.
2. `ThreadPoolExecutor.submit` doesn't handle exceptions — one bad world aborts the run.
3. `_candidates` while-loop can infinite-loop on hash collisions.
4. Hardcoded `seeds=(17, 43)` — only 2 seeds, low statistical power.
5. `_bootstrap_lcb` uses `draws=1200` — fixed, not configurable.
6. `case_ordinal` parses `key[0].rsplit("-", 1)[1]` — fragile if case_id format changes.

**Recommendations:**
1. Write `tests/test_worldbench.py` — at minimum: `built_in_cases` returns 6×8=48 cases, `BenchmarkCase.public_manifest` includes source_hash + oracle_commitment, `_bootstrap_lcb` returns -1 on empty, `_mean` handles empty list, `_evaluate` returns `RETAIN_CHAMPION` when no candidate crosses LCB gate, `run` with `generations=1` and mock policies produces a campaign artifact.
2. Wrap `future.result()` in try/except, collect failures into a `failed_worlds` list.
3. Add a max-iterations guard to the `_candidates` while-loop.
4. Make `seeds` and `draws` configurable via `EvolutionCampaign.run(seeds=(...), draws=...)`.

---

### 10. `failure_taxonomy.py` — Failure Taxonomy (Phase 22b, 87 LOC)

**Purpose:** Classifies engine failures into 6 classes (RESOURCE, REASONING, ARCHITECTURE, EVIDENCE, SAFETY, UNKNOWN) via a 14-entry `_FAILURE_MAP`. Enables pattern recognition and targeted improvement.

**Implementation quality: 6/10**
- Simple, correct, frozen dataclass.
- `truth_effect=NONE` and `claim_ceiling="FAILURE_FINDING_IS_DIAGNOSTIC_NOT_TRUTH"` on payload.
- `finding_id = f"failure.{failure_type}.{canonical_hash(ctx)[:8]}"` — **8-char hash truncation** → collision risk after ~65,536 findings (birthday paradox at 8 hex chars = 32 bits). Acceptable for a single project but not for federation.
- 14 hardcoded failure-type strings — no schema/registry.
- `_FAILURE_MAP.get(failure_type, FailureClass.UNKNOWN)` — silent UNKNOWN classification for unrecognized types (could be a configuration error).
- No `from_dict` / `as_dict` round-trip — `FailureFinding` has `payload()` but no `as_dict()` that includes `finding_hash`. Inconsistent with other receipt-style modules.
- No accumulation primitive (`load`/`save`/`merge`).

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. **No tests.**
2. 8-char hash truncation → collision risk at scale.
3. Silent UNKNOWN classification for unrecognized failure types.
4. No `as_dict()` / `from_dict` round-trip — inconsistent with rest of codebase.
5. No accumulation primitive — failures cannot be persisted across runs.
6. 14 hardcoded failure-type strings — no schema.

**Recommendations:**
1. Write `tests/test_failure_taxonomy.py` — classify each of the 14 known types, verify UNKNOWN for unrecognized, verify `finding_hash` matches `canonical_hash(payload())`, verify `truth_effect=NONE`.
2. Truncate hash to 16 chars (64 bits) — collision risk drops to ~1 in 10^9.
3. Add `FailureFinding.as_dict()` and `from_dict()` for round-trip persistence.
4. Emit a WARNING when classifying as UNKNOWN (don't silently swallow).

---

### 11. `transformation_graph.py` — Transformation Graph (62 LOC)

**Purpose:** Builds a transformation graph: SOURCE → DIAGNOSTIC / CONTRADICTION / QUESTION → ARCHITECTURE_TOPOLOGY → NATIVE_REENTRY → transformations. Tracks `latest_by_engine` and `_last_topology` for causal chaining. Metrics include `causal_depth` (longest acyclic-by-round chain), `cycle_pressure`, `topology_mutation_edges`.

**Implementation quality: 4/10 — worst-formatted module in Group E**
- 62 LOC on **6 dense one-liner lines** (e.g., line 7 is the entire `__init__`; line 60 is the entire `metrics` return).
- **Duplicate state fields:** `self._last_by_engine = {}` AND `self.latest_by_engine = {}` (line 7) — both maintained in parallel but only `_last_by_engine` is used in `add_deep_result`; `latest_by_engine` is set but never read. Same for `self._last_topology` and `self.last_topology` — `_last_topology` is used, `last_topology` is set but never read.
- `edge()` uses `if all(canonical_hash(x)!=sig for x in self.edges)` — O(n) per edge insertion, O(n²) total. Should use a set of sigs.
- `add_node` computes `nid = 'tr-' + canonical_hash(base)[:18]` — 18-char truncation (72 bits) — collision risk after ~10^9 nodes.
- `seed_primary` accesses `c.engine_id` (line 17, attribute access) but `c.get('representative', ...)` (line 19, dict access) — inconsistent: contribs are objects, disagreements are dicts. No type hints.
- `metrics` is a single 60-character-spaced line — unreadable. The `dist = {'SOURCE': 0}; ordered = sorted(...)` block computes longest path in a DAG, but the `if base < 0: continue` (line 58) silently drops unreachable nodes — could mask graph-disconnect bugs.
- `cycle_pressure = sum(1 for e in self.edges if e['kind'] in {'CHANGES_SPACE_OF','SELF_REVISION','MUTATES_TOPOLOGY'})` — but `SELF_REVISION` is never emitted by any `edge()` call in this module. Dead set member.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. **No tests.**
2. Worst formatting in Group E — 6 dense one-liners, no docstrings, no type hints.
3. Duplicate state fields (`_last_by_engine`/`latest_by_engine`, `_last_topology`/`last_topology`) — second copy is dead.
4. O(n²) edge deduplication.
5. 18-char hash truncation — collision risk at scale.
6. `SELF_REVISION` in `cycle_pressure` set is never emitted.
7. `metrics` returns a dict with 10 keys but no schema documentation.

**Recommendations:**
1. **Reformat** — break the 6 one-liners into readable multi-line functions. Add docstrings and type hints.
2. Remove dead duplicate fields (`latest_by_engine`, `last_topology`).
3. Replace O(n²) edge dedup with a `set` of sigs.
4. Write `tests/test_transformation_graph.py` — `seed_primary` with empty contribs, `add_topology` chain, `add_deep_result` with transformations, `metrics` returns expected keys, `artifact` round-trip with hash re-verification.

---

### 12. `transformation_extractor.py` — Transformation Extractor (78 LOC)

**Purpose:** Extracts `TypedTransformation` records from actual adapter output (canonical + native dicts). 10 operator patterns (SOURCE_READING, HORIZON_DISCLOSURE, RIVAL_FORK, SEMANTIC_COUNTERFACTUAL, GENEALOGICAL_RETURN, EVIDENCE_DISCRIMINATOR, DOUBLE_HERMENEUTIC, SUBLATION_WITH_RESIDUE, OPERATOR_MUTATION, SOURCE_RETURN) with bilingual EN+RU regex. `peer_sources` field is hardcoded to empty list (never populated).

**Implementation quality: 6/10**
- Clean `_candidate_strings` recursive walker — yields (path, text) for any string ≥12 chars in a nested dict/list structure.
- `_source_span` returns `EvidenceRef` tuple with start/end/sha256 — proper source-bound provenance.
- `extract_transformations` deduplicates by `(transformation_type, text[:240])` — sensible.
- `assumptions=() if spans else ("DERIVED_OUTPUT_REQUIRES_SOURCE_RETURN",)` — correctly flags ungrounded transformations.
- `provenance="ACTUAL_EXECUTOR_OUTPUT"` — explicit provenance tag.
- **`peer_sources = []` hardcoded (line 73)** — the field exists in `TypedTransformation` but is never populated. Dead field.
- `limit=24` default — magic constant.
- Bilingual regex is thoughtful but inconsistent with the rest of the codebase (most modules are EN-only).
- `_candidate_strings` doesn't handle sets or frozensets — will raise `TypeError` on `isinstance(value, (list, tuple))` check passing but iteration failing on a set. (Unlikely but possible.)
- No `as_dict` / `from_dict` on the extractor itself — but `TypedTransformation` (from `contracts.py`) handles that.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 4/10 (1 importer: `native_reentry_compiler.py`)**

**Weak spots:**
1. **No tests.**
2. `peer_sources = []` hardcoded — dead field.
3. Magic `limit=24` and `len(cleaned) >= 12` constants.
4. `_candidate_strings` doesn't handle sets/frozensets.
5. No type hints on `extract_transformations` return (returns `list[dict[str, Any]]` but the dicts are `TypedTransformation.as_dict()` outputs — should be typed).

**Recommendations:**
1. Write `tests/test_transformation_extractor.py` — extract from empty canonical, extract from canonical with SOURCE_READING keyword, verify `source_spans` populated when text matches source_text, verify `assumptions` includes `DERIVED_OUTPUT_REQUIRES_SOURCE_RETURN` when no span, verify deduplication, verify limit enforcement.
2. Either populate `peer_sources` from a peer-engines parameter or remove the field.
3. Add `isinstance(value, (set, frozenset))` branch to `_candidate_strings`.

---

### 13. `causal_attribution.py` — Causal Attribution Engine (Phase 15, 77 LOC)

**Purpose:** Determines WHY an architecture won (not just THAT it won). Uses ablation results: `effect_size = quality_with - quality_without`, `confidence = min(1.0, |effect_size| / max(0.01, quality_with))`.

**Implementation quality: 6/10**
- Simple, correct, frozen dataclass.
- `truth_effect=NONE` and `claim_ceiling="CAUSAL_FINDING_IS_LOCAL_NOT_UNIVERSAL"` — excellent claim ceiling.
- **`confidence` formula is questionable:** `min(1.0, abs(effect) / max(0.01, quality_with))` — this is a normalized effect size (Cohen's d-like), NOT a statistical confidence. No sample size, no variance, no p-value. Misleading name.
- `effect_size = round(effect, 6)` — rounds before hashing, deterministic.
- `finding_id = f"causal.{ablated_component}.{winner_policy[:8]}"` — 8-char policy hash truncation → collision risk.
- No `from_dict` / `as_dict` round-trip — inconsistent.
- No accumulation primitive.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 3/10 (1 importer: orchestrator.py)**

**Weak spots:**
1. **No tests.**
2. `confidence` is a normalized effect size, not a statistical confidence — misleading name.
3. 8-char policy hash truncation in `finding_id`.
4. No `as_dict()` / `from_dict` round-trip.
5. No accumulation primitive.
6. `max(0.01, quality_with)` — magic floor.

**Recommendations:**
1. Write `tests/test_causal_attribution.py` — positive effect (winner > loser), negative effect (loser > winner, ablation helps), zero effect, `quality_with=0` edge case, `finding_hash` determinism.
2. Rename `confidence` → `normalized_effect_size` OR add a real statistical confidence (requires sample size + variance inputs).
3. Add `as_dict()` / `from_dict` round-trip.
4. Truncate `winner_policy` to 16 chars in `finding_id`.

---

### 14. `nonlinearity.py` — Nonlinearity Proxy Metrics (102 LOC)

**Purpose:** Architectural proxy metrics for hermeneutic/epistemic/depth nonlinearity. Three component groups (hermeneutic × 6 sub-metrics, epistemic × 9, depth × 7) averaged into H/E/D scores. Explicitly does NOT assert philosophical correctness.

**Implementation quality: 5/10**
- 102 LOC on ~10 effective lines — dense one-liners.
- `claim_ceiling='ARCHITECTURAL_PROXY_FOR_NONLINEARITY_AND_DEPTH; NOT_EXTERNAL_PHILOSOPHICAL_QUALITY_VALIDATION'` — excellent claim ceiling.
- **21+ magic thresholds:** `min(1.0, branch_factor/10.0)`, `min(1.0, len(return_edges)/12.0)`, `min(1.0, cycle_count/32.0)`, `min(1.0, len(type_set)/14.0)`, `min(1.0, len(core4_engines)/4.0)`, `min(1.0, reentry_positions/64.0)`, `min(1.0, .../max(1, ...))`, etc. No documentation for why 10, 12, 32, 14, 4, 64 are the normalization constants.
- `peer_second_order = {'SECOND_ORDER_DESTRUCTION','OPERATOR_ECOLOGY_PROBE','CROSS_LINEAGE_DIFFERENTIAL','COUNTERFACTUAL_GATE'}` — hardcoded set of 4 strings.
- `peer_uptake = len(peer_second_order & type_set) / len(peer_second_order)` — always divides by 4 (constant).
- `dissent_preservation_when_present = (min(1.0, unresolved/max(1,conflict_count)) if conflict_count else 0.5)` — 0.5 default is a magic neutral prior.
- `safety` block has 4 boolean checks — no scoring, just booleans.
- `(reentry or {}).get('metrics', {})` repeated 6× — should be hoisted to a local variable.
- `round2 = core4_rounds[1].get('metrics', {}) if len(core4_rounds) > 1 else {}` — `round1`/`round2` hardcoded; no `round3+`.
- No `as_dict` / `from_dict` — `evaluate_nonlinearity` returns a plain dict.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 4/10 (2 importers: orchestrator.py, stress_matrices.py)**

**Weak spots:**
1. **No tests.**
2. 21+ magic thresholds with no documentation.
3. Dense one-liner formatting.
4. `peer_uptake` always divides by 4 (constant) — should be `len(peer_second_order & type_set) / 4` explicitly, or use a variable.
5. `round1`/`round2` hardcoded — no `round3+` support.
6. `(reentry or {}).get('metrics', {})` repeated 6×.

**Recommendations:**
1. Write `tests/test_nonlinearity.py` — empty inputs return 0.0, single-round input doesn't crash, H/E/D scores in [0, 1], `evaluation_hash` determinism, `claim_ceiling` present.
2. Extract magic thresholds to a `NonlinearityConfig` dataclass at module top.
3. Hoist `(reentry or {}).get('metrics', {})` to a local `reentry_metrics` variable.
4. Replace `round1`/`round2` with a loop over `core4_rounds`.

---

### 15. `epistemic_gain.py` — Expected Epistemic Gain Scheduler (46 LOC)

**Purpose:** Scores engine assignments by expected epistemic gain and allocates engines within a budget. Formula combines relevance, biography prior, independence (neutral 0.5 prior), tension, pressure, pair synergy, novelty. `allocate` performs greedy selection with required-engine and min-engine constraints.

**Implementation quality: 4/10 — worst magic-constant density in Group E**
- 46 LOC on ~5 effective lines — extremely dense.
- `PREDICTED_COST_UNITS` dict with 16 hardcoded engine costs (engine_01: 1.8, engine_02: 1.9, …, engine_16: 0.7) — no calibration mechanism, no source for these numbers.
- 6 hardcoded domain→engine-set mappings (SEMANTIC_SCOPE → engines with SEMANTIC/SCOPE/PARSE capabilities, PHILOSOPHICAL_HERMENEUTICS → engine_01-04, EVIDENCE_RESEARCH → engine_06/07/09/13/14, MEMORY_LONGITUDINAL → engine_05/06/12, HYPOTHESIS_EXPERIMENT → engine_07/15/16/04).
- 7 magic weight coefficients: `.28*rel + .18*prior + .15*independence + .14*tension + .12*pair_synergy + .13*min(1.0, pressure+novelty)` — no documentation for why these weights.
- `independence = .5` — neutral prior is good (avoids rewarding self-declared independence), but hardcoded.
- `utility = expected / (.55 + cost*.45)` — magic coefficients .55 and .45.
- `min_engines = 4 if round_index == 1 else (3 if round_index == 2 else 2)` — hardcoded round-index → min-engine mapping.
- `budget_units * 1.25` for required engines, `budget_units * 1.10` for min-engine fill — magic budget-buffer coefficients.
- `plan['plan_hash']` is computed and set — good content-addressing.
- `claim_ceiling` is excellent: `'FULL_16_DIAGNOSTIC_PARTICIPATION_PLUS_SPARSE_DEEP_EXECUTION; PREDICTED_GAIN_AND_COST_ARE_PREEXECUTION_HEURISTICS_NOT_OBSERVED_OUTCOMES'`.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 4/10 (2 importers: orchestrator.py, autonomous_loop.py)**

**Weak spots:**
1. **No tests.**
2. 16 hardcoded engine costs + 6 domain→engine-set mappings + 7 magic weight coefficients — no central config, no calibration.
3. Dense one-liner formatting.
4. `allocate` mutates `required` (line 31): `required = [e for e in dict.fromkeys(required or []) if …]` — reassigns the parameter, which is fine but confusing.
5. `if spent + x['cost_units'] <= budget_units * 1.25` — silently exceeds budget by 25% for required engines; could surprise callers.

**Recommendations:**
1. Write `tests/test_epistemic_gain.py` — score returns expected_gain in [0, 1], `allocate` respects budget (with 25% buffer for required), `allocate` fills min_engines, `plan_hash` determinism, `claim_ceiling` present, `independence=0.5` neutral prior.
2. Extract `PREDICTED_COST_UNITS`, domain→engine-set mappings, and weight coefficients to a `SchedulerConfig` dataclass.
3. Document the budget-buffer semantics (1.25× for required, 1.10× for min-fill).

---

### 16. `information_gain_selector.py` — Information-Gain Experiment Selection (Phase 21, 71 LOC)

**Purpose:** Selects experiments by maximizing information gain per unit cost. Formula: `information_gain = expected_gain × uncertainty × novelty / cost`. Greedy knapsack within budget.

**Implementation quality: 7/10 — cleanest small module in Group E**
- Simple `InformationGainSelector` class with `select()` and `_compute_info_gain()`.
- Greedy knapsack is correct: sort by gain descending, add if cost ≤ remaining_budget.
- `_compute_info_gain` handles `cost <= 0` (returns 0.0) — defensive.
- `SELECTOR_VERSION = "METAENGINE-INFORMATION-GAIN-SELECTOR-1"` — versioned, but **never emitted** in any output (no `as_dict`/`payload`).
- **No `canonical_hash` on result** — inconsistent with the rest of the codebase (every other module content-addresses its outputs).
- No `truth_effect`/`claim_ceiling` on the result — inconsistent.
- No `as_dict` / `from_dict` round-trip.
- No accumulation primitive.

**Test coverage: 0/10 — NO dedicated test file.**

**Connectivity: 4/10 (2 importers: orchestrator.py, autonomous_loop.py)**

**Weak spots:**
1. **No tests.**
2. No `canonical_hash` / `as_dict` / `from_dict` — inconsistent with codebase conventions.
3. No `truth_effect`/`claim_ceiling` on result.
4. `SELECTOR_VERSION` defined but never emitted.
5. Greedy knapsack is suboptimal for large budgets (no DP) — acceptable for small candidate sets but undocumented.

**Recommendations:**
1. Write `tests/test_information_gain_selector.py` — empty candidates, single best, budget exhausted exactly, cost=0 candidate handled, deterministic order on ties.
2. Add `as_dict()` with `canonical_hash` and `truth_effect=NONE` + `claim_ceiling="INFORMATION_GAIN_SELECTION_IS_HEURISTIC_NOT_OBSERVED_OUTCOME"`.
3. Emit `SELECTOR_VERSION` in the output.

---

## Cross-Cutting Critical Findings (Top 5)

### Finding 1: 10 of 16 modules have NO dedicated test file (62.5% zero-test rate)
**Modules:** dialectical_graph (156 LOC), sealed_benchmark (122), worldbench (394), failure_taxonomy (87), transformation_graph (62), transformation_extractor (78), causal_attribution (77), nonlinearity (102), epistemic_gain (46), information_gain_selector (71). **Total: 1,295 LOC of source with zero direct tests.** Test ratio drops from 0.33 (already low) to 0.00 for these modules. The 6 tested modules average 7.83/10 test coverage; the 10 untested average 0. **This is the single highest-leverage gap in Group E.** Priority: worldbench (394 LOC, complex LCB/bootstrap/promotion logic), dialectical_graph (156 LOC, central to orchestrator + worldbench), nonlinearity (102 LOC, 21+ magic thresholds).

### Finding 2: `strict_test_factory.py` SKIP-as-PASS bug + pytest collection warnings
8 of 25 test cases return `True` (PASS) when data files are absent, conflating SKIP with PASS and inflating the pass rate silently. `TestSuiteResult.skipped` counter is always 0. Separately, 5 classes prefixed `Test*` (`TestStatus`, `TestSeverity`, `TestCategory`, `TestResult`, `TestSuiteResult`) trigger pytest collection warnings on every test run. The factory that is supposed to *enforce* strict external validation has a self-inflating pass rate — ironic and concerning. **Highest-priority fix in Group E** because it undermines the credibility of the entire strict-test subsystem.

### Finding 3: `mechanism_library.py` is the model module (9/9/9) — pattern not replicated elsewhere
`mechanism_library.py` demonstrates the correct pattern: frozen dataclass, evidence-gated admission (A2/A3 require `AssimilationReceipt`), hash re-verification on `from_dict`, lazy import to break circular dependency, `validate()` called in `create()` AND `payload()`, `assert_no_a3_influence` constitutional guard, full accumulation primitive (`load`/`save`/`add_candidate`), 13 tests covering all admission paths. **None of the other 15 modules replicate this full pattern.** `evidence_graph.py` comes closest (7/7/3) but skips per-node hash re-verification and lacks merge/load/save tests. `architecture_sources.py` (9/9/4) replicates the validation discipline but is foundational (1 importer). The pattern should be templated and applied to `failure_taxonomy`, `causal_attribution`, `transformation_graph`, `nonlinearity`, `epistemic_gain`, `information_gain_selector` — all of which lack `as_dict`/`from_dict`/hash re-verification.

### Finding 4: Dense one-liner formatting in 3 modules (transformation_graph, nonlinearity, epistemic_gain)
`transformation_graph.py` (62 LOC on 6 lines), `nonlinearity.py` (102 LOC on ~10 effective lines), `epistemic_gain.py` (46 LOC on ~5 lines) — unreadable, unmaintainable, untestable. `transformation_graph` has duplicate state fields (`_last_by_engine`/`latest_by_engine`, `_last_topology`/`last_topology`) where the second copy is set but never read. `epistemic_gain` has 16 hardcoded engine cost constants + 6 domain→engine-set mappings + 7 magic weight coefficients with no central config. `nonlinearity` has 21+ magic thresholds. **Reformatting + config extraction would make these modules testable.**

### Finding 5: `_call_llm` + `health_check` quadruplicated; magic constants pervasive across 12+ modules
`_call_llm` and `health_check` are duplicated for the 4th time in `unified_benchmark.py` (also in `rlaif_trainer.py`, `redteam_adversary.py`, `llm_judge.py` per Group B findings — ~200 LOC duplication total). Beyond that, magic constants pervade: `unified_benchmark.PASS_THRESHOLDS` (7 thresholds), `epistemic_gain.PREDICTED_COST_UNITS` (16 costs) + 7 weight coefficients, `nonlinearity` (21+ thresholds), `strict_test_factory` (8 hardcoded storage paths), `worldbench._bootstrap_lcb` (draws=1200, alpha-quantile), `failure_taxonomy` (14 hardcoded failure-type strings). **No central config module exists.** A `metaengine/scheduler_config.py` or `metaengine/thresholds.py` would consolidate ~80 magic constants into one audited location.

---

## Cross-Cutting Anti-Patterns

### Anti-Pattern A: SKIP-as-PASS / silent neutral fallback
- `strict_test_factory._test_no_truth_promotion` (and 7 others) return `True` when data files are absent.
- `unified_benchmark._parse_judge_response` returns `{"score": 0.5, "constitution": 0.5}` on parse failure.
- `cross_run_verification.verify_accumulated_state` returns `{}` on key-file corruption.
- `causal_attribution.confidence = min(1.0, ...)` clamps to 1.0 silently.

### Anti-Pattern B: Missing `as_dict` / `from_dict` round-trip
- `failure_taxonomy.FailureFinding` has `payload()` but no `as_dict()` (no `finding_hash` in payload output).
- `causal_attribution.CausalFinding` has `as_dict()` but no `from_dict()`.
- `nonlinearity.evaluate_nonlinearity` returns a plain dict with `evaluation_hash` but no `from_dict`.
- `epistemic_gain.allocate` returns a plan dict with `plan_hash` but no `from_dict`.
- `information_gain_selector.select` returns `list[dict]` with no hash at all.
- `transformation_graph.artifact` returns a dict with `graph_hash` but no `from_dict`.

### Anti-Pattern C: Hash truncation to 8 chars (32-bit collision domain)
- `failure_taxonomy.finding_id`: `canonical_hash(ctx)[:8]` — collision after ~65K findings.
- `causal_attribution.finding_id`: `winner_policy[:8]` — collision after ~65K policies.
- `transformation_graph.add_node`: `canonical_hash(base)[:18]` — better (72 bits) but still truncated.

### Anti-Pattern D: Duplicate `_call_llm` / `health_check` (4-way duplication)
- `unified_benchmark.py` lines 312–356 (45 LOC).
- Also in `rlaif_trainer.py`, `redteam_adversary.py`, `llm_judge.py` (per Group B).
- Same bridge protocol, same rate-limit pattern, same error handling — 4 places to patch for any bridge change.

### Anti-Pattern E: Hardcoded storage paths
- `strict_test_factory` has 8 hardcoded paths like `storage/phase32_real_llm_run/engines/engine_16/CONTRIBUTION.json`.
- `cross_run_verification.verify_accumulated_state` has 4 hardcoded paths.
- `unified_benchmark` has 1 path `storage/phase57_63_unified_benchmark`.
- No `StorageLayout` config class.

---

## Bright Spots

1. **`mechanism_library.py` (9/9/9)** — model module. Full A0–A3 state machine, evidence-gated admission, hash re-verification, lazy import for circular-dependency avoidance, 7 importers, 13 tests covering all admission paths. Should be the template for all receipt-style modules.
2. **`architecture_sources.py` (9/9/4)** — exhaustive validation, 7 cross-field invariants, license-class enforcement, blob path-traversal safety, hash re-verification. 706 LOC of well-structured defensive code. Foundational to Slice 3.
3. **`cross_run_verification.py` (7/8/3)** — Ed25519 verification, clean `VerificationResult` contract, 14 tests. Marred only by 3 silent `except Exception` and a duplicate import.
4. **`worldbench.py` (7/0/2)** — strongest analytical engine in Group E. Bootstrap LCB, Bonferroni correction, successive halving, multi-criteria promotion gate, freeze barrier, 7 invariants self-documented. Marred only by zero tests and `ThreadPoolExecutor` exception handling.
5. **Constitution discipline uniformly excellent** — every payload in every module carries `truth_effect=NONE` and a `claim_ceiling` string. No module promotes derived content to truth. This is the strongest cross-cutting property of Group E.

---

## Final Verdict

Group E is **implementation-strong but test-weak**. The 6 tested modules average 7.83/10 test coverage and pass 118/118 tests; the 10 untested modules average 0/10. The implementation quality average (6.2/10) is dragged down by 3 dense one-liner modules (transformation_graph 4, epistemic_gain 4, nonlinearity 5) and 2 naive modules (dialectical_graph 5, sealed_benchmark 5). The connectivity average (3.3/10) is low because most modules have only 1 importer (orchestrator.py imports 10 of 16); `mechanism_library` (7 importers) is the exception.

The single highest-leverage intervention is **writing the 10 missing test files** — ~120 tests, ~15 hours, would lift the test-coverage average from 2.9 to ~6.5 and expose the dense-one-liner bugs that are currently invisible.

---

## Top 3 Prioritized Recommendations

### Recommendation 1: Write 10 missing dedicated test files (highest leverage)
**Priority order (LOC × complexity × importer count):**
1. `tests/test_worldbench.py` (~20 tests, 3 hours) — 394 LOC of LCB/bootstrap/successive-halving/promotion-gate logic, zero coverage, highest-risk untested module.
2. `tests/test_dialectical_graph.py` (~15 tests, 2 hours) — 156 LOC, 2 importers (orchestrator + worldbench), central to hermeneutic analysis.
3. `tests/test_nonlinearity.py` (~12 tests, 2 hours) — 102 LOC, 21+ magic thresholds, 2 importers.
4. `tests/test_transformation_graph.py` (~10 tests, 1.5 hours) — 62 LOC, dense one-liners, expose duplicate-state-field bugs.
5. `tests/test_transformation_extractor.py` (~8 tests, 1 hour) — 78 LOC, 1 importer.
6. `tests/test_epistemic_gain.py` (~10 tests, 1.5 hours) — 46 LOC, 16 hardcoded costs, 2 importers.
7. `tests/test_causal_attribution.py` (~6 tests, 1 hour) — 77 LOC, 1 importer.
8. `tests/test_failure_taxonomy.py` (~6 tests, 1 hour) — 87 LOC, 1 importer.
9. `tests/test_sealed_benchmark.py` (~8 tests, 1 hour) — 122 LOC, 1 importer.
10. `tests/test_information_gain_selector.py` (~6 tests, 1 hour) — 71 LOC, 2 importers, simplest module.

**Total: ~101 tests, ~15 hours.** Lifts test-coverage average from 2.9/10 to ~6.5/10. Closes the largest test-coverage gap in Group E.

### Recommendation 2: Fix `strict_test_factory.py` SKIP-as-PASS + pytest warnings (highest credibility risk)
1. **Rename 5 `Test*` classes** to `StrictTest*` (TestStatus→StrictTestStatus, etc.) — eliminates 5 pytest collection warnings. ~30 min.
2. **Replace `return True  # SKIP`** with `return None` in the 8 affected test functions; in `run_all_tests`, treat `None` as `TestStatus.SKIP` (increment `skipped` counter, set status=`TestStatus.SKIP`, don't count as PASS or FAIL). ~1 hour.
3. **Replace `TestResult(**{**result.__dict__, "result_hash": h})`** with `dataclasses.replace(result, result_hash=h)` — 2 occurrences (line 701 for result, line 720 for suite). ~15 min.
4. **Replace `now - mtime < 60`** in `_test_no_code_modification` with a content-hash comparison (SHA-256 of source file at start and end of run; FAIL if changed). ~1 hour.

**Total: ~3 hours.** Restores credibility of the strict-test subsystem — currently its pass rate is silently inflated.

### Recommendation 3: Extract magic constants to a central config + reformat dense one-liners
1. **Create `metaengine/scheduler_config.py`** with: `PREDICTED_COST_UNITS` (16 engine costs), `DOMAIN_ENGINE_SETS` (6 domain→engine-set mappings), `WEIGHT_COEFFICIENTS` (7 weights), `BUDGET_BUFFERS` (1.25×, 1.10×), `MIN_ENGINES_PER_ROUND` (4/3/2). Import in `epistemic_gain.py`. ~2 hours.
2. **Create `metaengine/nonlinearity_config.py`** with the 21+ thresholds (`BRANCH_FACTOR_MAX=10`, `RETURN_EDGES_MAX=12`, `CYCLE_COUNT_MAX=32`, etc.). Import in `nonlinearity.py`. ~1.5 hours.
3. **Create `metaengine/llm_bridge_client.py`** with `call_llm` + `health_check` + `rate_limit`. Import in `unified_benchmark.py`, `rlaif_trainer.py`, `redteam_adversary.py`, `llm_judge.py`. ~2 hours (closes 4-way duplication).
4. **Create `metaengine/storage_layout.py`** with all hardcoded storage paths. Import in `strict_test_factory.py`, `cross_run_verification.py`, `unified_benchmark.py`. ~1 hour.
5. **Reformat `transformation_graph.py`** — break 6 one-liners into readable multi-line functions, remove duplicate state fields. ~1 hour.

**Total: ~7.5 hours.** Consolidates ~80 magic constants into 4 audited config modules and makes 3 dense modules readable.

---

## Secondary Recommendations (5)

4. **Add `as_dict` / `from_dict` round-trip** to `failure_taxonomy.FailureFinding`, `causal_attribution.CausalFinding`, `nonlinearity.evaluate_nonlinearity` output, `epistemic_gain.allocate` output, `information_gain_selector.select` output. ~3 hours.
5. **Truncate hash IDs to 16 chars (64 bits)** instead of 8 chars (32 bits) in `failure_taxonomy.finding_id`, `causal_attribution.finding_id`, `transformation_graph.add_node`. ~30 min.
6. **Replace silent `except Exception`** (3 in `cross_run_verification.py`, 1 in `unified_benchmark._parse_judge_response`, 1 in `unified_benchmark._validate_llm_judge`) with explicit exception types or WARNING logs. ~2 hours.
7. **Wire `CONTRADICTS` / `SUPERSEDES` edges** in `evidence_graph.build_evidence_graph_from_run` when a new run's evidence contradicts an existing accumulated graph node — closes the "scientific knowledge" loop the docstring claims. ~3 hours.
8. **Make `worldbench` `seeds` and `draws` configurable**, add try/except around `future.result()`, add max-iterations guard to `_candidates` while-loop. ~2 hours.

## Tertiary Recommendations (4)

9. Replace `_sentences` regex in `dialectical_graph.py` with a proper sentence tokenizer or document the abbreviation limitation.
10. Rename `MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN_IN_SLICE3` → `MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN` (Slice-agnostic).
11. Use `TYPE_CHECKING` block in `mechanism_library.py` for proper `AssimilationReceipt` type hints without runtime cost.
12. Move `PERMISSIVE_LICENSE_EXPRESSIONS` in `architecture_sources.py` to a config file or SPDX allowlist module.

---

## Files Touched

- **CREATED:** `/home/z/my-project/METAENGINE_SLICE3_RESTORED/CRITICAL_ANALYSIS_GROUP_E_ANALYSIS.md` (this document, ~24 KB)
- **No code changes** (analysis-only task).

## Constitution Preserved

- No source files modified.
- No tests run for mutation.
- No canonical state touched.
- No truth effects produced.
- Pure read-only critical analysis.

---

**End of Group E Analysis.**
