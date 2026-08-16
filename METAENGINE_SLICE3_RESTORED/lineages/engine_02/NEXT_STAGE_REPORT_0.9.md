# Operator Evolution 0.9 — Genetic–Ecological Integration

## Result
A source-bound declarative mutation was gated without modifying the baseline registry, emitted a reversible candidate registry, and that candidate registry was executed by the ordinary living-cycle runtime.

## Mutation gate
- Delta: `DELTA-GX1-RESIDUAL-SPLIT-001`
- Decision: `ACCEPTED_CANDIDATE`
- Runtime reachability: `FULL`
- Baseline registry silently modified: **no**
- Candidate: `GX1 → GX1A-EXCLUSION + GX1B-SUCCESS-COST`
- Rollback target: emitted

## Mutant execution
Corpus: controlled Geviert refinery from cross-corpus regression 0.7.

- constellations: **12**
- nodes: **391**
- edges: **612**
- active moves: **121**
- all active moves add a traceable generative gain: **true**
- sufficient openness: **true**

This demonstrates an executable path from operator mutation to a real living run. It does **not** establish philosophical superiority of the mutant. Regression and competition remain downstream requirements.

## Conformance
- full tests: **77/77 passed**
- portable manifest: **50 required assets**
- portable errors: **0**
