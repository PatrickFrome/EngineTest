# Operator Mutation Gate — Split orientation-compression from adjudicative substitution

**Decision:** `ACCEPTED_CANDIDATE`  
**Promotion ready:** `true`  
**Runtime reachability:** `FULL`

## Resistant source

- Source: `FIXTURE-RESISTANT-MEDIATION-001`
- Selector: `span:120-188`
- Resistance: The same abridged dossier is harmless as orientation but distorting when it becomes the final object of adjudication.

## Incompatible unitizations

- **U-ORIENTATION:** The dossier is one reversible orientation aid pointing beyond itself.
  - Consequence: Compression is admissible when claims remain low-burden and traceback remains constitutive.
- **U-SUBSTITUTION:** The dossier is treated as the adjudicative object that replaces the heterogeneous source field.
  - Consequence: The same compression becomes a category error because losses now determine the verdict.

## Mutation

- Target: `conditional_families/F-MEDIATION-COMPRESSION`
- Kind: `SPLIT`
- Proposal: Split the family by epistemic role so the same compressed artifact can be treated differently when it orients inquiry versus when it substitutes for the source.
- Cost: More branching and a risk of overtyping epistemic roles before the use-context is known.
- Rollback: Restore F-MEDIATION-COMPRESSION from rollback_target.json and remove both split variants.

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

