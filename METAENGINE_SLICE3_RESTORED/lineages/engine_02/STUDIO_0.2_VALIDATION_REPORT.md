# Destruktion Studio 0.2 — Validation Report

Date: 2026-08-11

## Scope

This report validates the new `RESISTANT-SOURCE / OPERATOR-MUTATION 1.0` layer and its integration into Studio without claiming validation that the current sandbox cannot execute.

## Passed

- `studio/studio.mjs`: Node syntax check PASS.
- `mutation/operator-mutation-engine.mjs`: Node syntax check PASS.
- `src/paths.mjs`: Node syntax check PASS.
- `src/structural-validator.mjs`: Node syntax check PASS.
- Standalone mutation regression suite: 4/4 PASS.
- Passing fixture: `mediation-compression-split.pass.json` → `ACCEPTED_CANDIDATE`.
- Gate confirms `runtime_reachability=FULL` for the conditional-family split.
- Negative test: mutation without GG1 is not promotion-ready.
- Negative test: traceability regression is not promotion-ready.
- Negative test: partially reachable GX revision remains review-only.
- Candidate promotion hash binding: PASS after canonical registry hash check.
- Process-scoped registry path override: smoke PASS.
- Portable fixity: 29/29 required assets unchanged.

## Not run in this sandbox

- Full `npm test` suite for the original DAE.
- End-to-end `living-cycle` with the promoted mutant registry.

Reason: the locked `ajv@8.17.1` dependency is not installed in this sandbox and outbound package installation is unavailable here. Studio `doctor` reports this explicitly. On the target machine, run `SETUP.cmd` / `./setup.sh`, then `npm test`, and finally a baseline/mutant pair over the same refinery and seed.

## Claim ceiling

The mutation gate establishes internal contract conformance and controlled operator variation. It does not establish philosophical superiority, empirical validity or external validation of the mutated operator.
