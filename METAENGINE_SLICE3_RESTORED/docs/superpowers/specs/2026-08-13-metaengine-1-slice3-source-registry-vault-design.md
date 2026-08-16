# METAENGINE-1 Slice 3 — Architecture Source Registry and Reference Vault

**Status:** IMPLEMENTATION-READY DERIVATIVE OF THE APPROVED METAENGINE-1 DESIGN

**Step ID:** `METAENGINE-1-SLICE-3`

**Recovery HEAD admitted for this step:** `637d0b569e38c2a965b43f7de2015ea66a788428`

**Parent design:** `docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md`

**Authority boundary:** candidate-only, patch-only, no canonical promotion, no cloud write, no credential access

## 1. Decision summary

Slice 3 will implement a deterministic, provider-neutral Architecture Source Registry and an external content-addressed Reference Vault.

The tracked repository will contain only contracts, source cards, manifests, receipts, mechanism hypotheses, and snapshot indexes. Retained foreign bytes will be stored outside Core at:

```text
reference-vault/blobs/sha256/<64-lowercase-hex>
```

The Core implementation will never fetch or execute foreign content. It will ingest only explicitly staged, regular files; verify their classification, immutable source revision, license evidence, paths, sizes, and hashes; then copy inert bytes into the vault under their SHA-256 digest.

This is deliberately a local, portable content-addressed database rather than a canonical cloud database. A remote mirror may be added later, but it must remain an untrusted availability layer whose bytes are verified locally.

## 2. Admission and evidence reviewed before code

### 2.1 Recovery and transition

- recovered candidate branch: `recovered/metaengine-1-slice2-portable`;
- recovery HEAD: `637d0b569e38c2a965b43f7de2015ea66a788428`;
- CONTROL verification: `433/433`;
- lineage verification: `9839/9839`;
- Slice 2 review receipt hash: `8e000a6bf0945f0ef4527a6e6d6eb80b1a4308190b95584a41bae63cdb2dcb17`;
- fresh transition result: `DEVELOPMENT_REVIEW_TRANSITION_ALLOWED`;
- the recovered HEAD is the authority for this candidate; dangling/lost intermediate objects are evidence only and are not treated as ancestors.

### 2.2 D6-G0 historical capsule

The newly supplied D6-G0 capsule has SHA-256:

```text
1a5aaddba68fe5dcc112066ee136846b1fd77d99b233b88ebdb4c96a37db91b7
```

Its own control verifier reports `PASS`, 385 manifest files, 9839 lineage files, no bad/missing/extra paths, and no secret hits. Eight files differ from the recovered HEAD because the recovered branch contains later D6-G1 work. Therefore the capsule is immutable historical evidence and must not overwrite the later recovered code.

## 3. Mandatory pre-code review

The review order was Constitution → Architecture Library → Policy → alternatives → evidence.

### 3.1 Constitution findings

The design preserves the relevant K0 invariants:

- `PROVENANCE_PRIMARY_EVIDENCE`: source claims point to exact public material and retained bytes;
- `MUTATION_REQUIRES_RECEIPT`: ingestion produces a deterministic receipt and snapshot hash;
- `SEPARATE_GENERATION_AND_PROMOTION`: ingestion grants no runtime, truth, or promotion authority;
- `FROZEN_EVALUATION_CONTRACT`: verification rules are versioned and hash-bound;
- `NO_EXECUTABLE_SELF_MODIFICATION`: retained code is inert reference material and is never imported or executed;
- `PRIVACY_PERMISSION_FAIL_CLOSED`: unsafe paths, special files, missing license evidence, secret-like content, and hash mismatches are rejected;
- `IMMUTABLE_HISTORY_WITH_SUPERSESSION`: new source revisions create new records; old records are not rewritten;
- `ROLLBACK_RECOVERY_REQUIRED`: tracked records are reconstructible from exact blobs and manifests.

No K0/K1 amendment is required. Source ingestion is a research evidence operation, not a constitutional or policy promotion.

### 3.2 Architecture Library findings

The approved parent design requires three source classes, A0–A3 mechanism states, and an external vault. Slice 3 is restricted to:

- `A0_OBSERVED`;
- `A1_MECHANISM_HYPOTHESIS`.

No imported artifact may become `A2_TRANSFERABLE` or `A3_ASSIMILATED` without an independent MetaEngine implementation, controlled experiment, ablation, and transfer evidence in a later step.

The storage contract borrows only stable, useful ideas from primary standards:

- OCI descriptor fields (`mediaType`, digest, and size) for independently verifiable blobs: <https://github.com/opencontainers/image-spec/blob/main/descriptor.md>;
- SPDX license expressions for machine-readable license identity: <https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/>;
- an in-toto-shaped subject/predicate receipt envelope for later attestability: <https://github.com/in-toto/attestation/blob/main/spec/README.md>;
- immutable revision and provenance expectations from SLSA source requirements: <https://slsa.dev/spec/v1.2/source-requirements>.

Slice 3 does not claim OCI, in-toto, or SLSA conformance. It uses a minimal compatible vocabulary and avoids false assurance levels.

### 3.3 Policy findings

The implementation must not:

- change the active/champion policy;
- mutate D6-G1 shadow adaptation state or federation finalization;
- widen the 18-tool MCP surface or any provider allowlist;
- add a runtime dependency on foreign repositories;
- write a canonical cloud registry;
- access secrets or canonical credentials;
- treat ranking, popularity, model performance, or publisher claims as scientific truth.

The existing Git history plus tracked content-addressed metadata is the candidate development ledger for this step. A cloud database would violate the current no-canonical-authority boundary and is not needed for reproducibility.

## 4. Alternatives considered

| Alternative | Strength | Failure mode | Decision |
|---|---|---|---|
| Vendor repositories or use Git submodules | Familiar browsing and complete trees | Mutable upstream expectations, large history, license/runtime leakage into Core, weak offline pack identity | Reject |
| Put source rows/blobs in Supabase or another cloud DB | Central queries and collaboration | Introduces canonical availability/authority, credentials, egress, and non-portable recovery | Reject for Slice 3 |
| Tracked metadata + external local CAS | Immutable byte identity, offline verification, small Core, no provider lock-in | Needs explicit mirroring and garbage-collection policy later | Select |

The selected alternative is the smallest design that makes an ingested source independently verifiable while preserving the project's portability and authority boundaries.

## 5. Domain contract

### 5.1 Source classes

```text
PERMISSIVE_CODE
RESTRICTED_REFERENCE
CLOSED_BEHAVIORAL_ONLY
```

Classification is mandatory and fail-closed.

`PERMISSIVE_CODE` requires an exact immutable revision, an SPDX expression accepted by the Slice 3 policy, retained license bytes, and at least one retained source/document blob. Allowed use is limited to analysis, reference, and clean-room reimplementation. It does not create a runtime dependency.

`RESTRICTED_REFERENCE` permits public license/model-card/reference material to be retained in the external vault when allowed, but forbids copying it into Core or using it as a runtime dependency. Custom licenses use a `LicenseRef-*` identifier and an explicit use ceiling.

`CLOSED_BEHAVIORAL_ONLY` contains only official public documentation locators and public behavioral/capability claims. It must not state hidden implementation details as facts. Retained internal code/weights are forbidden.

### 5.2 Ingestion states

```text
REGISTERED_ONLY
INGESTED
BLOCKED
SUPERSEDED
```

`source_sha256` and blob descriptors are required for `INGESTED`. They remain `null` for `REGISTERED_ONLY`; the implementation must never manufacture a digest of locator metadata and call it a source digest.

`BLOCKED` requires a stable reason code. A blocked or registered-only entry cannot satisfy a permissive first-wave ingestion gate.

### 5.3 Blob descriptor

Each retained file is represented by:

```text
media_type
digest_algorithm = "sha256"
digest
size
relative_path
git_blob_id (optional evidence, never substituted for SHA-256)
```

The digest is the SHA-256 of exact retained bytes. `relative_path` is descriptive provenance; the storage key is always the digest.

### 5.4 Source record

The source record contains the approved parent fields plus explicit epistemic and ingestion state:

```text
registry_schema_version
source_id
publisher
system_name
version
source_class
ingestion_status
official_source_locator
exact_commit_or_release
retrieved_at
source_sha256
source_sha256_scope
license_name
license_expression
license_sha256
license_evidence_locator
allowed_use
forbidden_use
epistemic_ceiling
architecture_claims
retained_reference_paths
blob_descriptors
mechanism_candidates
blockers
record_sha256
```

`architecture_claims` must distinguish `SOURCE_FACT`, `PUBLISHER_CLAIM`, and `METAENGINE_HYPOTHESIS`. Closed-system claims may be only public `PUBLISHER_CLAIM` or explicitly labeled hypotheses.

### 5.5 Pack and registry roots

Canonical JSON is UTF-8 encoded with sorted keys, compact separators, no NaN/Infinity, and a terminating newline only at the file layer.

The source pack root is:

```text
sha256(canonical_json(pack_without_pack_root_sha256))
```

Blob descriptors are sorted by `(relative_path, digest)` before hashing.

The registry snapshot root is:

```text
sha256(canonical_json(sorted(source_id, record_sha256, pack_root_sha256)))
```

This root identifies the registry state without making any one filesystem, Git host, or cloud service authoritative.

## 6. Component boundaries

### 6.1 Core domain module

`metaengine/architecture_sources.py` will define immutable source classes, records, claims, mechanism candidates, canonical serialization, validation, and deterministic hashes. It will perform no network or subprocess calls.

### 6.2 Vault module

`metaengine/reference_vault.py` will:

- validate staged paths and regular-file status;
- enforce configured file-count and byte budgets;
- scan retained bytes for configured secret-like patterns;
- calculate SHA-256 and size;
- store blobs atomically at the content address;
- verify an existing pack without trusting filenames;
- emit deterministic pack and verification receipts.

It will not import, compile, execute, or inspect model weights.

### 6.3 Fetch boundary

Network retrieval is outside Core and outside the deterministic verifier. Official files are staged by a separate operator/tool boundary. The ingestion command receives only local paths plus expected provenance.

This separation makes tests deterministic and prevents a repository URL from becoming an implicit runtime dependency.

### 6.4 Tracked layout

```text
schemas/architecture_source_record.schema.json
schemas/reference_vault_pack.schema.json
research/architecture_library/registry.json
research/architecture_library/catalog/first_wave.json
research/architecture_library/sources/<source_id>.json
research/architecture_library/packs/<source_id>.json
research/architecture_library/receipts/<source_id>.json
research/architecture_library/mechanisms/<mechanism_id>.json
```

### 6.5 External layout

```text
reference-vault/
  blobs/sha256/<digest>
  staging/                 # optional, excluded and disposable
```

`reference-vault/` is ignored by Git and excluded from CONTROL capsules. A capsule may contain only tracked manifests and receipts, never retained foreign bytes.

For an `INGESTED` record, `source_sha256` equals the deterministic source-pack root and `source_sha256_scope` is `RETAINED_SOURCE_PACK`. Individual exact-byte identities remain in the blob descriptors.

## 7. Ingestion flow

```text
official immutable revision
  → explicitly staged regular files
  → path / size / secret / license / class validation
  → exact-byte SHA-256 descriptors
  → atomic CAS write
  → deterministic source pack
  → source record and registry snapshot
  → independent vault verification receipt
```

Failure at any validation step leaves no passing record. Pre-existing CAS blobs are safe to reuse only after their size and SHA-256 are reverified.

## 8. Stable failure codes

The first contract reserves these deterministic codes:

- `SOURCE_CLASS_REQUIRED`;
- `INGESTION_STATUS_INVALID`;
- `UNPINNED_SOURCE_REVISION`;
- `LICENSE_CLASSIFICATION_REQUIRED`;
- `LICENSE_EVIDENCE_REQUIRED`;
- `PERMISSIVE_PACK_EMPTY`;
- `CLOSED_SOURCE_BYTES_FORBIDDEN`;
- `MECHANISM_CEILING_EXCEEDED`;
- `PATH_NOT_RELATIVE`;
- `PATH_ESCAPE`;
- `NON_REGULAR_FILE`;
- `FILE_COUNT_LIMIT_EXCEEDED`;
- `BYTE_LIMIT_EXCEEDED`;
- `SECRET_LIKE_CONTENT`;
- `HASH_MISMATCH`;
- `VAULT_BLOB_MISSING`;
- `REGISTRY_SNAPSHOT_MISMATCH`.

Validation collects deterministic findings where safe, but no error may be downgraded by an AI judgment.

## 9. First source wave

### 9.1 Permissive code/reference packs — actual ingestion required

| Source ID | Exact official revision | License | Retained scope | Initial mechanism ceiling |
|---|---|---|---|---|
| `deepseek-v3.2-exp-87e509a` | `deepseek-ai/DeepSeek-V3.2-Exp@87e509a2e5a100d221c97df52c6e8be7835f0057` | MIT | license, README, selected official inference/model code | A1 |
| `qwen3.6-0886e34` | `QwenLM/Qwen3.6@0886e34d2d6947e631b8338088a1293862243300` | Apache-2.0 | license and official architecture documentation; no model implementation is claimed | A1 |
| `kimi-linear-8c1d85e` | `MoonshotAI/Kimi-Linear@8c1d85eb6b5f8fcefb15758691b0ce50b0827ce3` | MIT | license and README; the large report is an explicit deferred blob if not retained | A1 |
| `mistral-inference-9eaeb91` | `mistralai/mistral-inference@9eaeb91c17450e09021b6065a1d5cc69876507c8` | Apache-2.0 | license, README, selected transformer/MoE reference code; archived status recorded | A1 |
| `glm-4.5-170f20b` | `zai-org/GLM-4.5@170f20b2c10659008fdbc909d478bc2a75bc3627` | MIT | license and README; external framework code is not misattributed to this repo | A1 |

All five records must reach `INGESTED` and pass independent blob verification before Slice 3 can pass. A README-only or documentation-only pack is valid when that is the exact official repository scope, but the record must not claim retained model implementation code.

### 9.2 Restricted reference records

| Source ID | Exact official revision | Classification | Ceiling |
|---|---|---|---|
| `kimi-k3-3cb39df` | `MoonshotAI/Kimi-K3@3cb39dfd32e51c3328e2e4b4af21341247d06c43` | `RESTRICTED_REFERENCE`, `LicenseRef-Kimi-K3-2026` | A1 |
| `llama4-0e0b8c5` | `meta-llama/llama-models@0e0b8c519242d5833d8c11bffc1232b77ad7f301`, `models/llama4` | `RESTRICTED_REFERENCE`, Llama 4 Community License | A1 |

These records may retain license and model-card bytes in the external vault, but they cannot satisfy permissive-code gates and cannot create a Core/runtime dependency.

### 9.3 Closed behavioral records

| Source ID | Official public locator | Classification | Ceiling |
|---|---|---|---|
| `openai-gpt-5.6-public` | <https://developers.openai.com/api/docs/models/gpt-5.6-sol> | `CLOSED_BEHAVIORAL_ONLY` | A1 |
| `anthropic-claude-public` | <https://www.anthropic.com/constitution> | `CLOSED_BEHAVIORAL_ONLY` | A1 |
| `google-gemini-deep-think-public` | <https://deepmind.google/models/gemini/deep-think/> | `CLOSED_BEHAVIORAL_ONLY` | A1 |

These entries register only public behavior, product documentation, or published governance/training descriptions. They make no hidden-architecture claim, have no retained internal source digest, and cannot be promoted beyond A1 in Slice 3.

## 10. Mechanism candidates

The first records may name hypotheses such as sparse evidence attention, hybrid compressed-state/full-attention organization, sparse conditional routing, residual organization paths, parallel hypothesis generation and critique, or constitution-derived testing.

Every candidate must include:

- the exact originating source record;
- the public fact boundary;
- a provider-neutral semantic definition;
- a falsifiable effect hypothesis;
- an explicit A0/A1 status;
- a statement that ingestion is not evidence of usefulness or assimilation.

Brand names and publisher performance claims are not mechanism definitions.

## 11. Test strategy

Implementation proceeds RED → GREEN → REFACTOR.

Required deterministic tests include:

1. canonical records and registry snapshots are order-independent and stable;
2. missing classification, immutable revision, or license evidence fails closed;
3. permissive packs cannot pass empty;
4. closed records cannot retain source-code blobs;
5. A0/A1 candidates cannot be represented as A2/A3;
6. absolute paths, traversal, symlinks, and special files are rejected;
7. size/count limits and secret-like content fail closed;
8. CAS write and duplicate reuse verify exact size and SHA-256;
9. altered/missing blob verification fails;
10. all five permissive source packs are materially present and independently verified;
11. restricted/closed entries preserve their epistemic ceilings;
12. `reference-vault/` never enters Git or the CONTROL capsule;
13. existing constitution, organization-policy, D6 federation, shadow-adaptation, and 18-tool MCP-surface tests remain green.

## 12. Completion and review boundary

Slice 3 is complete only when:

- contracts, schemas, and stable failure codes exist;
- the five permissive source packs are actually ingested into the external vault;
- all pack blobs and roots reverify independently;
- restricted and closed sources are separately registered with correct ceilings;
- tracked metadata reconstructs and verifies the registry snapshot;
- D6-G1 and CONTROL exclusions remain unchanged in authority and behavior;
- deterministic tests and a full regression suite pass;
- a post-step Development Evolution Review receipt binds the completed commit, evidence, Constitution snapshot, Architecture Library snapshot, and Policy snapshot before Slice 4 begins.

## 13. Qualitative-next-level assessment after this design step

The highest-value decision is the separation of **availability** from **authority**: GitHub, a future object-store mirror, or a local cache may provide bytes, but only exact digest verification plus the tracked record establishes identity. This turns architecture research from mutable browsing notes into reproducible evidence.

The next qualitative jump after Slice 3 is not a larger source catalog. It is a two-part evidence loop:

1. signed/attested source-pack provenance with independently mirrored CAS availability; and
2. provider-neutral mechanism tournaments that test causal deltas through ablation and transfer.

Only the second part can move a mechanism from A1 to A2/A3. Therefore Slice 4 should prioritize one small, falsifiable mechanism experiment over broad additional ingestion.
