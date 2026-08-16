# Micro-local Ecology Downstream Integration — 0.10

## Problem

Version 0.9 could preserve several local operator regimes inside one document, but downstream analysis could still collapse them into a single corpus-level thesis. Version 0.10 adds a provenance-preserving adapter from micro-local ecology into living and expert representations.

## Command

```text
node ./bin/destruktion.mjs ecology-downstream <micro_local_ecology_result.json> --out <directory>
```

## Living representation

The adapter emits a graph containing:

- `LOCAL_INQUIRY` nodes for source-bounded windows;
- `SOURCE_BORN_OPERATOR` nodes for locally selected candidates;
- `LOCAL_RESIDUAL` nodes for unresolved or unserved remainder;
- `HERMENEUTIC_BOUNDARY` nodes for regime changes and open boundaries.

The graph preserves window identifiers, paragraph hashes and boundary provenance. It does not introduce a new philosophical verdict.

## Expert representation

Each window is adjudicated only at the routing level:

- `QUALIFIED_LOCAL_ROUTING`;
- `QUALIFIED_LOCAL_COMPOSITION`;
- `RIVALS_UNRESOLVED`;
- `INSUFFICIENT_LOCAL_ROUTING`.

When the micro-local synthesis preserves polyphony or abstains, the downstream global layer returns `POLYPHONIC_GLOBAL_ABSTENTION` and `thesis_allowed=false`.

## Claim ceiling

The downstream adapter validates preservation of local routing, residuals and boundaries. It is not external semantic validation, authorial interpretation, or evidence that any operator family is ontologically true.
