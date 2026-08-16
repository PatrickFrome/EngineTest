# Passing mutation example — mediation/compression split

Source contract: `fixtures/mutation/mediation-compression-split.pass.json`.

The example demonstrates a real accepted candidate without installing it into the baseline registry. Inspect:

- `gate-output/MUTATION_REPORT.md` — human-readable gate;
- `gate-output/mutation_receipt.json` — machine decision and hashes;
- `gate-output/candidate_living_operator_registry.json` — candidate registry;
- `gate-output/rollback_target.json` — exact target required for rollback.

Expected decision: `ACCEPTED_CANDIDATE` with `runtime_reachability=FULL`.
