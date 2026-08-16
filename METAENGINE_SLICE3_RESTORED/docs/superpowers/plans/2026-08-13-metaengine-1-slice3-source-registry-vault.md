# METAENGINE-1 Slice 3 Source Registry and Reference Vault Implementation Plan

> **Execution mode:** use `superpowers:executing-plans` inline. Multi-agent delegation is disabled for this session. Work remains inside the recovered candidate checkout and every implementation task uses RED → GREEN → REFACTOR.

**Goal:** Build a deterministic Architecture Source Registry and external content-addressed Reference Vault, materially ingest the five required permissive source packs, register restricted and closed sources with correct epistemic ceilings, and preserve all constitutional, D6-G1, CONTROL, and MCP authority boundaries.

**Architecture:** Provider-neutral Core types describe exact source facts, public claims, A0/A1 mechanism hypotheses, and content descriptors. A filesystem CAS stores inert exact bytes outside Core. A deterministic catalog builder turns locally staged official files into tracked source records, packs, receipts, and a registry snapshot. Network fetching is an operator boundary and is never part of Core or verification.

**Tech stack:** Python 3.12+ standard library, immutable dataclasses/enums, existing `metaengine.devfabric.codec`, JSON Schema 2020-12, pytest/jsonschema test extras, SHA-256, no new runtime dependency or cloud service.

## Baseline and execution environment

- Candidate branch: `recovered/metaengine-1-slice2-portable` at admitted HEAD `637d0b569e38c2a965b43f7de2015ea66a788428`.
- Environment command: `.venv/bin/python`; the environment is created with `uv run --extra test` and a task-local `UV_CACHE_DIR`/`TMPDIR`.
- The portable recovery's focused suite passes `46/46` as recorded in the handoff.
- A fresh all-tests probe reaches the suite but has 16 pre-existing failures: 15 require deliberately non-portable/generated `release-evidence` or `devfabric/CAPSULE_MANIFEST.json` assets, and one asserts the pre-D6-G1 replication fallback string. These are baseline facts, not Slice 3 regressions. Slice 3 must keep the identical baseline set while all new and focused gates pass.

## Global constraints

- Constitution → Architecture Library → Policy → alternatives review occurs before implementation and after each completed implementation task.
- No source ingestion creates truth, usefulness, runtime, promotion, active/champion, or canonical authority.
- Only `A0_OBSERVED` and `A1_MECHANISM_HYPOTHESIS` are legal in Slice 3.
- No mutable revision, missing source class, missing license classification, fake source digest, path escape, symlink, special file, hash mismatch, or secret-like content can pass.
- Foreign bytes stay under excluded `reference-vault/`; tracked Core contains metadata and receipts only.
- The 18-tool MCP surface, D6-G1 shadow adaptation, role genomes, federation protocols, current policy, and canonical readback are not modified.
- Every expected digest in a test is a hand-derived literal or an independently calculated standard-library fixture, never the production helper under test.

---

### Planning checkpoint: Commit the design and plan, then admit implementation

**Files:**
- Create: `docs/superpowers/specs/2026-08-13-metaengine-1-slice3-source-registry-vault-design.md`
- Create: `docs/superpowers/plans/2026-08-13-metaengine-1-slice3-source-registry-vault.md`
- Create after commit: `devfabric/artifacts/reviews/development/metaengine-1-slice-3-planning-review.json`

- [ ] Verify `git diff --check`, exact recovery admission evidence, all source revisions, and absence of unresolved `TODO`/`TBD` decisions.
- [ ] Commit the design and plan as `docs: specify slice 3 source registry and vault`.
- [ ] Snapshot the unchanged Constitution/Policy and the new design evidence, compare CURRENT/MINIMAL/LIBRARY/SYNTHESIS alternatives, and issue an `ACCEPT_CONTINUE` planning review bound to the planning commit.
- [ ] Verify receipt integrity and commit the review artifact. This receipt is a gate artifact, not a new implementation step.

---

### Task 1: Source domain contract and JSON schemas

**Files:**
- Create: `metaengine/architecture_sources.py`
- Create: `schemas/architecture_source_record.schema.json`
- Create: `schemas/reference_vault_pack.schema.json`
- Create: `tests/test_architecture_sources.py`
- Modify: `tests/test_schemas.py`

**Interfaces:**
- `SourceClass`, `IngestionStatus`, `ClaimKind`, `MechanismStatus`.
- `ArchitectureClaim.create(...)`, `MechanismCandidate.create(...)`.
- `BlobDescriptor.create(...)`, `SourcePack.create(...)`, `SourceRecord.create(...)`.
- `SourceRegistry.create(records, packs)` and round-trip `as_dict()` / `from_dict()`.
- `ArchitectureSourceValidationError.code` supplies stable failure codes.

- [ ] **Write RED canonicalization tests.** Reordering unordered claims, uses, descriptors, mechanisms, or registry rows must retain the same literal record/pack/snapshot digest. Mutating a byte digest, relative path, or immutable revision must change it.
- [ ] **Write RED fail-closed tests.** Cover missing classification/revision/license, empty permissive packs, `REGISTERED_ONLY` with a fake `source_sha256`, `CLOSED_BEHAVIORAL_ONLY` with source-code blobs, and A2/A3 status attempts.
- [ ] **Write RED schema tests.** Hand-authored valid and invalid fixtures must be accepted/rejected by jsonschema.
- [ ] **Run RED:**

```bash
TMPDIR="$TASK_TMP" .venv/bin/python -m pytest tests/test_architecture_sources.py tests/test_schemas.py::test_architecture_source_schemas_enforce_contract -q
```

Expected: import failure for `metaengine.architecture_sources`.

- [ ] **Implement minimal immutable types.** Use canonical primitive payloads and exact SHA-256 validation. Exclude each object's own digest from its digest payload. Sort only semantically unordered fields.
- [ ] **Implement schemas.** Require all parent-design fields plus explicit ingestion status, epistemic ceiling, claim kind, digest scope, blockers, and self-hash.
- [ ] **Run GREEN and mutation check:** remove one validation branch locally in reasoning; identify the named test that would fail for each realistic mutation.
- [ ] **Run focused regressions:**

```bash
TMPDIR="$TASK_TMP" .venv/bin/python -m pytest tests/test_architecture_sources.py tests/test_schemas.py tests/test_constitution_kernel.py tests/test_organization_policy.py -q
.venv/bin/python -m compileall -q metaengine
```

- [ ] **Commit:** `feat: add deterministic architecture source contracts`.
- [ ] **Post-task review:** Constitution, library standards, policy, four alternatives, evidence. Issue and verify a task review receipt before Task 2.

---

### Task 2: Secure external content-addressed Reference Vault

**Files:**
- Create: `metaengine/reference_vault.py`
- Create: `tests/test_reference_vault.py`
- Modify: `.gitignore`
- Modify: `metaengine/devfabric/capsule.py`
- Modify: `tests/devfabric/test_capsule.py`

**Interfaces:**
- `VaultLimits(max_files, max_total_bytes, max_file_bytes)`.
- `StagedSourceFile(path, relative_path, media_type, git_blob_id=None)`.
- `ReferenceVault(root).ingest(source_id, exact_revision, files, limits)` → `SourcePack`.
- `ReferenceVault.verify(pack)` → deterministic `VaultVerificationReceipt`.
- `ReferenceVault.blob_path(digest)` resolves only `blobs/sha256/<digest>`.

- [ ] **Write RED exact-byte tests.** Ingest two real temporary files, assert hand-calculated SHA-256/size, CAS paths, deterministic pack root, and idempotent duplicate ingestion.
- [ ] **Write RED corruption tests.** Alter and remove stored blobs; verification must return named `HASH_MISMATCH`/`VAULT_BLOB_MISSING` findings and never PASS.
- [ ] **Write RED boundary tests.** Absolute/traversal paths, symlinks, FIFOs/special files, count/byte limits, and representative private-key/API-key/credential-URI patterns must fail without a passing pack.
- [ ] **Write RED capsule behavior test.** Build a small project fixture containing `reference-vault/blobs/...`; the blob must not enter `_payload_paths` or a capsule. This tests behavior rather than grepping configuration.
- [ ] **Run RED.** Expected: missing vault module and failed capsule exclusion behavior.
- [ ] **Implement streaming SHA-256, safe path validation, bounded scanning, and atomic same-directory writes.** Source code is retained as inert bytes; it is never imported, compiled, or executed.
- [ ] **Add `/reference-vault/` to Git ignore and `reference-vault` to capsule top-level exclusions.**
- [ ] **Run GREEN and regressions:**

```bash
TMPDIR="$TASK_TMP" .venv/bin/python -m pytest tests/test_reference_vault.py tests/devfabric/test_capsule.py tests/test_architecture_sources.py -q
```

- [ ] **Commit:** `feat: add fail-closed content-addressed reference vault`.
- [ ] **Post-task review:** compare plain-directory, Git-LFS/submodule, cloud-DB, and selected CAS designs; issue and verify a task receipt before Task 3.

---

### Task 3: Deterministic catalog builder and offline verifier

**Files:**
- Create: `scripts/architecture_source_registry.py`
- Create: `tests/test_architecture_source_registry_cli.py`
- Create: `research/architecture_library/README.md`
- Create: `research/architecture_library/catalog/first_wave.json`

**Interfaces:**

```text
python scripts/architecture_source_registry.py ingest \
  --catalog research/architecture_library/catalog/first_wave.json \
  --staging-root reference-vault/staging \
  --vault-root reference-vault \
  --output-root research/architecture_library

python scripts/architecture_source_registry.py verify \
  --registry research/architecture_library/registry.json \
  --vault-root reference-vault
```

- [ ] **Write RED end-to-end CLI test with real local files.** A two-source catalog (one permissive ingested, one closed registered-only) must produce source cards, pack, receipt, registry, stable exit JSON, and a re-verifiable snapshot.
- [ ] **Write RED failure tests.** Missing stage file, mismatch between catalog and exact revision, closed staged bytes, and incomplete permissive pack must exit non-zero and must not emit a PASS registry.
- [ ] **Run RED.** Expected: script not found.
- [ ] **Implement the CLI as a thin adapter.** Parsing and filesystem output live here; validation/hashing remain in Core modules. Output JSON is canonical/stable and all paths stored in receipts are project-relative, never absolute runtime paths.
- [ ] **Create the first-wave catalog.** It pins the ten exact source records, expected staged paths, SPDX/custom license classification, allowed/forbidden use, public claim boundaries, blockers, and A0/A1 mechanism candidates.
- [ ] **Run GREEN twice from two different temporary roots.** Registry snapshot hashes and tracked output bytes must match.
- [ ] **Commit:** `feat: add offline architecture source catalog builder`.
- [ ] **Post-task review:** confirm the CLI is an operator adapter, not network/runtime authority; issue and verify a task receipt before Task 4.

---

### Task 4: Materialize and verify the first source wave

**Files:**
- External, excluded: `reference-vault/staging/<source_id>/...`
- External, excluded: `reference-vault/blobs/sha256/<digest>`
- Generate tracked: `research/architecture_library/registry.json`
- Generate tracked: `research/architecture_library/sources/*.json`
- Generate tracked: `research/architecture_library/packs/*.json`
- Generate tracked: `research/architecture_library/receipts/*.json`
- Generate tracked: `research/architecture_library/mechanisms/*.json`
- Create: `tests/test_architecture_source_registry_artifacts.py`

- [ ] **Fetch only official files at the pinned revisions through the external retrieval boundary.** Retain LICENSE/README for every permissive pack; add selected official model/reference code for DeepSeek and Mistral. Retain no weights, caches, mutable checkout, or unregistered transitive repository.
- [ ] **Calculate expected local SHA-256 independently and reconcile with any Git blob ID.** Never confuse Git SHA-1 object IDs with source SHA-256.
- [ ] **Run the ingest command.** All five permissive targets must be `INGESTED`; restricted Kimi K3/Llama 4 records remain reference-only; GPT-5.6/Claude/Gemini remain registered-only behavioral evidence.
- [ ] **Write RED artifact gate before accepting generated output.** It must name the five required source IDs, prove every descriptor has a matching vault blob, assert license hashes, enforce class-specific allowed/forbidden use, preserve A0/A1 ceilings, and reject a mutated copy.
- [ ] **Run independent verification:**

```bash
.venv/bin/python scripts/architecture_source_registry.py verify \
  --registry research/architecture_library/registry.json \
  --vault-root reference-vault
TMPDIR="$TASK_TMP" .venv/bin/python -m pytest tests/test_architecture_source_registry_artifacts.py -q
```

- [ ] **Commit tracked metadata only:** `data: register and verify first architecture source wave`.
- [ ] **Post-task review:** explicitly state that ingestion is not usefulness/assimilation evidence; issue and verify a task receipt before Task 5.

---

### Task 5: Bind the registry into development review and close Slice 3

**Files:**
- Modify: `config/development_review_bootstrap_v1.json`
- Modify: `tests/devfabric/test_development_review_artifact.py` or create `tests/devfabric/test_architecture_source_review_artifact.py`
- Create: `devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-*.json`
- Create after final implementation commit: `devfabric/artifacts/reviews/development/metaengine-1-slice-3-review.json`
- Create: `08_HANDOFF/NEXT_ACTION.json` equivalent inside the portable handoff bundle, not as canonical project policy.

- [ ] **Write RED review-context test.** Architecture Library snapshot must bind the Slice 3 design, registry, schemas, mechanism cards, and tracked verification receipts. Any source-card change must alter the snapshot.
- [ ] **Update review bootstrap paths and run GREEN.** Constitution and Policy path sets remain unchanged.
- [ ] **Run focused gates:** source contracts/vault/artifacts, schemas, Constitution, OrganizationPolicy, development gate, D6 federation/adaptation, capsule, security, and MCP/tool-surface assertions.
- [ ] **Run all tests and compare against baseline.** New tests must pass; no new failure may appear beyond the 16 documented portable-baseline failures. Run compileall, `git diff --check`, ignored-vault proof, secret scan, and Git integrity.
- [ ] **Commit final implementation binding:** `chore: bind source registry to development review`.
- [ ] **Perform final Constitution → Architecture Library → Policy → alternatives → evidence review.** Generate evidence files with command, exit status, environment fingerprint, observed counts/hashes, and SHA-256.
- [ ] **Issue `METAENGINE-1-SLICE-3` review receipt** bound to the final implementation commit and current snapshot hashes. `next_step_allowed` may be true only if every deterministic acceptance gate passes.
- [ ] **Verify the receipt and commit it:** `docs: certify metaengine 1 slice 3`.
- [ ] **Build and independently verify a portable handoff** containing Git continuity, tracked CONTROL metadata, the external Reference Vault pack, evidence, exact NEXT_ACTION, and no credentials. Do not claim the new handoff as canonical or push it.

## Qualitative-next-level decision after execution

Do not expand the registry merely to increase source count. Review Slice 3 evidence and choose one provider-neutral A1 mechanism with:

- a small independent implementation;
- a frozen baseline and evaluator;
- a causal ablation;
- at least two task/resource regimes;
- explicit complexity/cost accounting.

That experiment is the shortest path from a reproducible architecture library to a learning architecture system. Signed provenance and a mirrored CAS improve supply-chain resilience, but only causal transfer evidence can justify A2/A3 assimilation.
