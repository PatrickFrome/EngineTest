# Operator Mutation Gate — Split residual probe into exclusion and cost probes

**Decision:** `ACCEPTED_CANDIDATE`  
**Promotion ready:** `true`  
**Runtime reachability:** `FULL`

## Resistant source

- Source: `DECLARATIVE-GESTURE-FIXTURE`
- Selector: `span:gx1-resistant-001`
- Resistance: The same successful concept can hide either an excluded phenomenon or the cost of its own explanatory compression; one residual node collapses these unitizations.

## Incompatible unitizations

- **U-EXCLUSION:** Read the remainder as a phenomenon excluded by the successful frame.
  - Consequence: Probe what cannot become visible inside the concept.
- **U-COST:** Read the remainder as a cost produced by the successful frame itself.
  - Consequence: Probe the distinction compressed by the concept even when nothing is simply outside it.

## Mutation

- Target: `generative_gestures/GX1`
- Kind: `SPLIT`
- Proposal: Split GX1 into two executable declarative gestures so resistant material can distinguish exclusion from compression-cost without adding runtime code.
- Cost: The gesture ecology gains another branch and therefore another source of traversal pressure.
- Rollback: Restore GX1 from rollback_target.json and discard the candidate registry.

## Machine gates

- ✓ structurally_and_semantically_valid
- ✓ resistant_source_bound_to_same_fixture
- ✓ incompatible_unitizations_present
- ✓ new_distinction_present
- ✓ source_traceability_non_degrading
- ✓ negative_tests_pass
- ✓ runtime_reachability_full
- ✓ mutation_effect_observed

## Built-in negative tests

- ✓ candidate differs from baseline
- ✓ operator ids unique after mutation
- ✓ protocol refs preserved or suspension explicit
- ✓ same source fixture enforced

## Issues

- None.

## Interpretation

The delta changes an executable operator under a same-source before/after fixture, adds GG1, preserves traceability and passes negative gates.

> An accepted candidate is not silently installed into the baseline registry. Promotion is a separate explicit action, and rollback remains possible from the stored before-target.

