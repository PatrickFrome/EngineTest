# GX1 declarative split — executable example

This fixture demonstrates a `generative_gestures` mutation with `FULL` runtime reachability under the declarative runtime.

`GX1` is split into two independently executable gestures:

- `GX1A-EXCLUSION` — preserves the exclusion/deconflation pressure;
- `GX1B-SUCCESS-COST` — makes the cost of a successful reconstruction independently activatable.

No gesture-specific JavaScript branch is added. Both variants are validated and emitted by the generic declarative gesture interpreter.

Re-run the gate:

```bash
node studio/studio.mjs delta:gate ./examples/operator-mutation/gx1-declarative-split/operator_delta.json --out ./examples/operator-mutation/gx1-declarative-split/gate-output-rerun
```

The included gate output is evidence of contract execution, not philosophical validation.
