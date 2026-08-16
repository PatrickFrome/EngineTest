# Micro-local operator ecology 0.9

Outcome: **PASSES_MICRO_LOCAL_OPERATOR_ECOLOGY_REGRESSION**

Routing policy: **WINDOW_LOCAL_SELECTION_COMPOSITION_UNRESOLVED_OR_ABSTENTION_WITH_PROVENANCE_PRESERVING_BOUNDARIES**  
Promotion status: **EXPERIMENTAL_NOT_CORE**

## Windows

| Window | Profile hints | Decision | Selected/composed | Provenance | Expectation |
|---|---|---|---|---|---|
| AR_SUBSTANCE_PRIORITY | ASYMMETRIC_DEPENDENCE | SELECT_LOCAL_WINNER | SPINOZA_ASYMMETRIC_DEPENDENCE | PASS | PASS |
| AR_RELATIVES_REFERENCE | LOCAL_MODE_VARIATION | SELECT_LOCAL_WINNER | ARISTOTLE_LOCAL_MODE_VARIATION | PASS | PASS |
| AR_RECONSTRUCTION_BRIDGE | ASYMMETRIC_DEPENDENCE, LOCAL_MODE_VARIATION | LOCAL_COMPOSITION | ARISTOTLE_LOCAL_MODE_VARIATION, SPINOZA_ASYMMETRIC_DEPENDENCE | PASS | PASS |
| AR_GLOBALIZATION_CHALLENGE | — | ABSTAIN_UNRESOLVED | — | PASS | PASS |

## Boundaries

| Boundary | Transition | Status | Expectation |
|---|---|---|---|
| AR_B1_SUBSTANCE_TO_RELATIVES | AR_SUBSTANCE_PRIORITY → AR_RELATIVES_REFERENCE | PRESERVE_OPERATOR_BOUNDARY | PASS |
| AR_B2_RELATIVES_TO_RECONSTRUCTION | AR_RELATIVES_REFERENCE → AR_RECONSTRUCTION_BRIDGE | PRESERVE_OPERATOR_BOUNDARY | PASS |
| AR_B3_RECONSTRUCTION_TO_GLOBALIZATION | AR_RECONSTRUCTION_BRIDGE → AR_GLOBALIZATION_CHALLENGE | UNRESOLVED_BOUNDARY | PASS |

## Synthesis audit

- decision: **REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE**
- globally available selected operators: ARISTOTLE_LOCAL_MODE_VARIATION, SPINOZA_ASYMMETRIC_DEPENDENCE
- localization loss pairs: 4
- windows preserving local provenance: 4/4
- preregistered window expectations: 4/4
- preregistered boundary expectations: 3/3

A corpus-level composition is rejected whenever applying every globally selected operator to every micro-window would add unsupported local routing. The higher-level synthesis may summarize which operators occur, but it may not erase **where** each operator gained purchase or where the method abstained.

## Claim ceiling

INTERNAL_PREREGISTERED_MICRO_LOCAL_ROUTING_NOT_EXTERNAL_SEMANTIC_VALIDATION_OR_CORE_PROMOTION
