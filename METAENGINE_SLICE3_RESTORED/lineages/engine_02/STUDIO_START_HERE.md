# Destruktion Studio 0.6 — Open-Set Engine Integration

Studio 0.6 is the external development/reflexive layer around the **frozen Destruktion Automation Engine 0.10.0-alpha.1**.

## Architecture

- **Frozen 0.10 baseline:** 66 cryptographically bound portable assets; declarative GX1–GX7 runtime; source resistance; open-set discovery; `ADD_OPERATOR`; cross-corpus regression; local competition; open-set micro-local routing; bundled offline AJV-compatible validator.
- **Studio layer:** immutable runs, mutation gating, longitudinal resistant-source discovery, historical 0.9 control, A/B/C comparison, development snapshots, and semantic-review debt for open-set births.
- **Preserved 0.9 compatibility audit:** localization-loss micro-local regression remains available separately because it tests a stronger question than the 0.10 router: whether corpus-wide synthesis erases where an operator actually had local warrant.

The frozen 0.10 assets are never silently rewritten by Studio.

## First commands

```bash
node studio/studio.mjs doctor
node studio/studio.mjs card
node studio/studio.mjs
```

`doctor` should report the 66 frozen assets as valid. `node_modules/ajv` is optional because the engine includes `vendor/ajv-compat/2020.mjs`.

## Living analysis and controlled comparison

```bash
node studio/studio.mjs run:living <refinery-dir> --seed controlled
node studio/studio.mjs run:living-declarative <refinery-dir> --seed controlled
node studio/studio.mjs run:living-mutant-declarative <refinery-dir> --registry <candidate.json> --seed controlled
node studio/studio.mjs compare:living <refinery-dir> --registry <candidate.json> --seed controlled
```

`compare:living` now means:

1. historical 0.9 registry control;
2. frozen 0.10 open-set baseline;
3. accepted 0.10 mutant candidate.

Structural difference is measured; it is not automatically interpreted as philosophical improvement.

## Open-set operator birth

0.10 adds:

`REGISTRY_BLIND_SPOT → UNKNOWN_OPERATOR_FAMILY → ADD_OPERATOR → candidate registry`

The family is source-signature based and reversible. It is **not** a discovered ontology.

Mutation workflow:

```bash
node studio/studio.mjs delta:gate <operator_delta.json>
node studio/studio.mjs delta:promote <accepted-gate-dir>
```

For an `ADD_OPERATOR` birth Studio writes an `open_set_semantic_review` debt into `ACTIVATION.json`. Experimental execution is allowed, but CORE/universalization claims remain blocked in principle until predicate/polarity, attribution, modality, argumentative role, paraphrase/translation and decoy controls are supplied.

## Two different micro-local modes

### 0.10 open-set routing

```bash
node studio/studio.mjs ecology:open-set <hypothesis_bank.json> --out <dir>
```

Local outcomes:

- `KNOWN_PROFILE_LOCAL`
- `OPEN_SET_LOCAL_CANDIDATE`
- `KEEP_KNOWN_AND_OPEN_SET_RIVALS`
- `ABSTAIN_LOCAL`

### Preserved 0.9 localization-loss regression

```bash
node studio/studio.mjs ecology:regression <micro_local_operator_ecology_manifest.json> --out <dir>
```

This audit can return:

`REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE`

when a global synthesis would apply locally unsupported operators.

## Resistant-source discovery

```bash
node studio/studio.mjs discover:resistance <living-analysis-or-directory>...
node studio/studio.mjs discover:history
```

Studio discovery remains non-promoting. Its automatically generated delta seeds are intentionally non-gateable until source inspection supplies a real discriminator and executable before/after test.

## Regression and competition

```bash
node studio/studio.mjs regress:operator <manifest.json> --out <dir>
node studio/studio.mjs compete:operators <manifest.json> --out <dir>
```

Retirement, quarantine, unresolved rivalry and abstention are first-class outcomes.

## Development discipline

```bash
node studio/studio.mjs snapshot before-change
# change
node studio/studio.mjs snapshot after-change
npm test
node studio/studio.mjs doctor
```

Read `ENGINE_INTEGRATION_REPORT_0.6.md` and `STUDIO_0.6_VALIDATION_REPORT.md` for the merge rationale and validation evidence.


## 0.7 — Independent-family ecology

Run the supplied controlled oracle:

```text
node studio/studio.mjs ecology:independent experiments/independent-family-ecology-0.10/micro_local_ecology_manifest.json --out ./workspace/independent-ecology
node studio/studio.mjs ecology:downstream ./workspace/independent-ecology/micro_local_ecology_result.json --out ./workspace/independent-downstream
```

Probe a new DOCX without granting the proposed family promotion rights:

```text
node studio/studio.mjs family:probe ./source.docx --out ./workspace/family-probe
```

The important distinction is: open-set operator novelty, interrogative-family novelty, and localization-loss are three separate tests. Do not collapse them into one score.
