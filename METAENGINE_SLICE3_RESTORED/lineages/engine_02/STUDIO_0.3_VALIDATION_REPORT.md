# Destruktion Studio 0.3 — Validation Report

Generated: 2026-08-11T16:21:50Z

## Release scope

Studio 0.3 adds an executable declarative generative-gesture runtime, fully reachable generative-gesture mutation, and controlled A/B/C comparison while preserving the original portable control point.

## Passed checks

- **Portable fixity:** 29/29 required assets match their recorded size and SHA-256.
- **Studio syntax:** `studio/studio.mjs` and `studio/living-comparator.mjs` pass Node syntax checks.
- **Declarative registry:** baseline GX registry compiles under the generic activation/emission interpreter.
- **Studio regression suite:** **11/11 PASS** via `node --test tests/studio/*.test.mjs`.
- **GX mutation gate:** `GX1 → GX1A-EXCLUSION + GX1B-SUCCESS-COST` returns `ACCEPTED_CANDIDATE`, `promotion_ready=true`, `runtime_reachability=FULL`.
- **Comparator controls:** same-seed validation and mutation-structure detection are covered by dependency-light tests.
- **Baseline rewrite:** false; frozen registry and required portable assets are not overwritten.

## Studio test coverage

The 11 passing tests cover declarative registry compilation, generic loop emission, FULL gesture split reachability, invalid-program rejection, structural summaries, A/B/C mutation detection, same-seed controls, resistant-source family split acceptance, GG1 enforcement, traceability regression blocking and review-only handling of partial reachability.

## Dependency-limited checks

The current sandbox does **not** contain the package-lock dependency `ajv@8.17.1`. Therefore the full original `npm test`, engine-level `portable-check`, and true end-to-end A/B/C living execution cannot be honestly marked as passed here. The observed failure occurs at module resolution:

```text
ERR_MODULE_NOT_FOUND: Cannot find package 'ajv' imported from src/structural-validator.mjs
```

On the target machine run:

```bash
npm ci
npm test
node studio/studio.mjs compare:living <refinery-dir> --registry <accepted-declarative-registry> --seed controlled-a
```

## Architectural result

A resistant source can now split or revise a **generative gesture grammar** and the new variants are executed by the same generic interpreter. No gesture-specific JavaScript branch is required. Controlled comparison makes the behavioral delta auditable without treating extra complexity as a philosophical success criterion.
