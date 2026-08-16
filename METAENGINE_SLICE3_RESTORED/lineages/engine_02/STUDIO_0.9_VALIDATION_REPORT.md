# Destruktion Studio 0.9 — Validation Report

## Release gate

- Integrated automated tests: **129 / 129 PASS**.
- Frozen CORE 0.10 portable assets: **66 / 66 unchanged**.
- `portable-check`: conformant, 0 ERROR, 0 REVIEW, 0 WARNING.
- Studio doctor: CORE READY, DOCX pipeline READY, bundled offline schema validator READY.
- Frozen passage holdout audit: **PASS**.

## Holdout sample

- 9 source works.
- 27 deterministic 1,200-word excerpts.
- 81 passage×hypothesis units.
- Size gate: **READY** (minimum 80).
- DAE involved in passage selection: **false**.
- Packaged development-author overlap: **0**.
- Duplicate excerpt SHA-256: **0**.
- Filled gold in release: **0**.
- Filled external comparator outputs in release: **0**.

## New tests

Six Studio 0.9 tests cover:

1. 81-unit construction and three fixed hypotheses per excerpt;
2. frozen holdout audit and four-status DAE prediction coverage;
3. post-freeze DAE-prediction tamper detection;
4. rejection of DAE-involved passage selection;
5. rejection of packaged development-author overlap;
6. deterministic rebuild of unit IDs and DAE predictions from frozen excerpts plus real refinery observations.

## What is validated

The release validates the mechanics, fixity, blinding envelope, selection independence within the packaged project, and reproducibility of DAE predictions.

## What is not validated

The release does **not** establish:

- superior hermeneutic quality;
- agreement with domain experts;
- model-training novelty of the source texts;
- general cross-author validity;
- validity of the signal lexicons;
- correctness of open-set discovery;
- any right to promote new operators or families.

External labels and comparator outputs remain genuinely missing rather than synthetically filled.
