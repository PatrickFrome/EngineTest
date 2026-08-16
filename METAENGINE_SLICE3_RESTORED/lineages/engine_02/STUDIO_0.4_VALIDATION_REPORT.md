# Destruktion Studio 0.4 — Validation Report

## Scope

Studio 0.4 adds `DAE-RESISTANCE-DISCOVERY-1.0` and a longitudinal resistant-source case ledger while preserving the portable baseline and all 0.3 mutation/declarative behavior.

## Verified in the build environment

- Portable required-asset fixity: **PASS 29/29**.
- Declarative gesture registry compile: **PASS**.
- Studio dependency-light regression suite: **PASS 20/20**.
- Resistance discovery unit tests: **PASS 6/6**.
- Longitudinal ledger tests: **PASS 3/3**.
- Existing mutation + declarative + comparator tests remain passing: **11/11**.
- CLI discovery fixture: **PASS** — two living analyses → one recurrent resistant-source case.
- Delta-seed firewall: **PASS** — discovered seed is `gateable=false`, `promotion_forbidden=true`, and does not receive a promotion-ready mutation decision.
- Source separation: **PASS** — different `source_id` values are never fused.
- Recurrence deduplication: **PASS** — replaying identical evidence does not increase occurrence count.
- Longitudinal upgrade: **PASS** — a second distinct discovery occurrence with new run evidence upgrades the case to `RECURRING_ACROSS_DISCOVERY_SESSIONS`.
- Session collision handling: **PASS** — two same-second same-name sessions receive distinct IDs.

## Environment limitation

`ajv@8.17.1` is not installed in the current sandbox. Therefore the original full CORE `npm test` suite and true refinery-level living A/B/C end-to-end execution are **not claimed as executed here**. `doctor` reports this explicitly. On the target machine run `SETUP.cmd` / `npm ci`, then `npm test` and the desired living cycles.

## Epistemic boundary

Resistance discovery is not source interpretation. It detects repeated structural instability at a source locator. The discovery engine cannot accept its own proposed mutation and intentionally omits the executable/source-grounded material required by the mutation gate.
