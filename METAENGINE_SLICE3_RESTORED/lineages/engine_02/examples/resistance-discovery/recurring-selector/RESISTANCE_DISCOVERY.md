# Resistant-Source Discovery Report

- Contract: `DAE-RESISTANCE-DISCOVERY-1.0`
- Analyses: **2**
- Selectors observed: **1**
- Resistant cases: **1**
- Same source across inputs: **true**

> This engine detects recurrent structural resistance, not the meaning of the source. A discovery case cannot promote itself and is not an operator-delta acceptance decision.

## RSC-DISCOVERY-FIXTURE-2B610842AA

- Source: `DISCOVERY-FIXTURE`
- Selector: `span:same-001`
- Runs: **2**
- Seeds: `seed-a`, `seed-b`
- Runtimes: `DAE-LIVING-DECLARATIVE-1.0`
- Distinct structural unitizations: **2**
- Resistance runs: **2**
- Residual runs: **1**
- Revision-pressure runs: **1**
- Cross-runtime only: **false**
- Target hypothesis: `generative_gestures/GX1` (COMMON_PRESSURE_GENERATOR_ACROSS_UNITIZATIONS)

### Rival unitizations

- **U-DISC-1** — Structural routing 1: roles [REVISION_TRIGGER, SELF_CRITIQUE], pressure generators [GX1, GX6], families [F-UNDERDETERMINATION].
  - consequence: This routing produces residual/revision pressure through [GX1, GX6] with residual kinds [R3-G, R3-R]; it must not be collapsed with a rival routing before source review.
  - runs: `DISC-R2`
- **U-DISC-2** — Structural routing 2: roles [DECONFLATION, OPEN_RESIDUAL], pressure generators [GX1], families [F-UNDERDETERMINATION].
  - consequence: This routing produces residual/revision pressure through [GX1] with residual kinds [R3-R]; it must not be collapsed with a rival routing before source review.
  - runs: `DISC-R1`

### Review gate before any mutation

1. Inspect the actual source span at the selector; generated propositions are not source semantics.
2. State the lost distinction in source-grounded language rather than structural role names.
3. Provide a discriminator that can decide between the rival unitizations on the same material.
4. Author executable mutation changes/variants and run the existing operator-delta gate.
5. Run same-material before/after and negative tests; discovery cannot mark its own proposal promotion-ready.

## Epistemic discipline

1. Recurrence is evidence that the current analytical routing deserves review; it is not evidence that the source itself contains the inferred distinction.
2. Rival structural signatures are candidate unitizations, not automatically valid interpretations.
3. The generated `operator_delta_seed` is deliberately non-gateable and has `promotion_forbidden=true`.
4. Only the existing mutation gate may produce an `ACCEPTED_CANDIDATE`, and only after source-grounded before/after and negative tests.

Claim ceiling: `STRUCTURAL_RESISTANCE_HYPOTHESIS_NOT_SOURCE_SEMANTICS_OPERATOR_VALIDITY_OR_PHILOSOPHICAL_TRUTH`

