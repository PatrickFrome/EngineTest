# Operator Competition / Composition — 0.8

The 0.8 competition layer prevents a successful experimental operator from becoming a new default ontology.

## Contract

A candidate must be **source-born**: its origin hypothesis bank must contain the required profile hints and its living run must contain the corresponding method mutation. Manifest declaration alone is insufficient.

On a target corpus, the layer computes source-bounded distinction gain, distortion loss and a small complexity cost. It may return one of four local routing decisions:

- `SELECT_LOCAL_WINNER`
- `LOCAL_COMPOSITION`
- `KEEP_RIVALS_UNRESOLVED`
- `ABSTAIN_UNRESOLVED`

No decision changes frozen CORE.

## Philosophical firewall

`local routing success ≠ philosophical truth ≠ universal operator superiority`.

Composition means only that two or more profiles contribute non-redundant local distinctions. It does not create a higher synthetic ontology by default.

## CLI

`destruktion operator-competition <manifest.json> --out <new-directory>`

The run emits `operator_competition_result.json` and `OPERATOR_COMPETITION_REPORT.md`.
