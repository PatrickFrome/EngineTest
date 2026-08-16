# Destruktion Studio 0.4

`studio.mjs` is the dependency-light orchestration layer around the frozen portable baseline, declarative living runtime, mutation gate and resistant-source discovery engine.

Design rules:

1. Preserve the 29 frozen portable assets as the control surface.
2. Never overwrite a prior run; session IDs are collision-safe.
3. Mutant registry injection is process-scoped and reversible.
4. Structural change is not philosophical superiority.
5. Discovery groups only exact `source_id + selector` evidence.
6. Discovery never claims source semantics.
7. Discovery delta seeds are non-gateable and `promotion_forbidden=true`.
8. Repeated identical evidence is deduplicated in the discovery ledger.
9. Only the mutation gate can produce `ACCEPTED_CANDIDATE`.
10. The engine's epistemic claim ceiling remains explicit.

Core Studio commands:

```bash
node studio/studio.mjs doctor
node studio/studio.mjs discover:resistance <living_analysis.json|dir>...
node studio/studio.mjs discover:history
node studio/studio.mjs delta:gate path/to/operator_delta.json
node studio/studio.mjs compare:living <refinery> --registry <accepted-candidate> --seed <seed>
```

See `docs/RESISTANT_SOURCE_DISCOVERY.md`, `docs/OPERATOR_MUTATION.md` and `docs/DECLARATIVE_GESTURE_RUNTIME.md`.


# Studio 0.7 — Independent-Family Ecology Integration

New commands:

```text
ecology:independent   # source-birth-checked local competition across interrogative families
ecology:downstream    # preserve local residuals/boundaries into living + expert representations
family:probe          # detect processual-family pressure without promotion rights
```

(The CLI spellings are `ecology:independent` and `ecology:downstream`; the split above is only descriptive text.)

The supplied 0.10 regression archive is treated as a behavioral oracle because no source runtime for the new family was supplied. The reconstruction must reproduce 6/6 local routing expectations, five boundary transitions, one downstream residual and global `POLYPHONIC_GLOBAL_ABSTENTION` while the frozen 0.10 baseline remains byte-identical.

## Studio 0.8 — External validation

The 0.8 layer adds a non-promoting external validation envelope. See `EXTERNAL_VALIDATION_START_HERE.md`.

```bash
node studio/studio.mjs validation:init <benchmark-dir> --out <campaign-dir>
node studio/studio.mjs validation:freeze <campaign-dir> --system <predictions.json> --challenge <challenge.json>
node studio/studio.mjs validation:evaluate <campaign-dir> --gold <gold.json> --core-result <BENCHMARK_RESULT.json> --adversarial <results.json> --out <dir>
node studio/studio.mjs validation:status <campaign-dir>
```

The layer forbids scalar global-winner scoring and uses a Pareto comparison across empirical performance, safety, calibration, coverage and semantic adversarial robustness. It does not fabricate human labels or external model outputs.
