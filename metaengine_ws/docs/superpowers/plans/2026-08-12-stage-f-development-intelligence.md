# Stage F — Metaengine Development Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learn which worker ensembles are effective for which development task classes while preserving deterministic verification and canonical promotion rules.

**Architecture:** Development outcomes are observational routing evidence. A local model computes task-class priors and ensemble recommendations; PostHog/remote telemetry may enrich metrics, but no learned score becomes truth weight or bypasses gates.

**Tech Stack:** Python statistics, local SQLite, Stage C PostHog adapter, existing Metaengine benchmark/evolution machinery where suitable.

## Global Constraints

- Stage C telemetry plus at least one worker stage must exist.
- Routing effectiveness is advisory only.
- Structural novelty and AI agreement are not promotion objectives.
- Quality claims require external/holdout outcome gates consistent with Metaengine 2.3.

---

### Task 1: Define development outcome schema

**Files:** `metaengine/devfabric/outcomes.py`, `tests/devfabric/test_outcomes.py`.

- [ ] Test fields: task class, provider/ensemble, deterministic verdict, repair count, latency, patch size, benchmark delta, promotion outcome; source text/secrets absent.
- [ ] Implement frozen `DevelopmentOutcome` with canonical digest.
- [ ] Run tests; commit `feat: define development outcome evidence`.

### Task 2: Build task-class specialization model

**Files:** `metaengine/devfabric/specialization.py`, tests.

- [ ] Test score changes router order but cannot alter verifier verdict.
- [ ] Implement minimum-observation threshold plus uncertainty interval; sparse data => `NO_SPECIALIZATION_PRIOR`.
- [ ] Run tests; commit `feat: learn task-class worker specialization`.

### Task 3: Add ensemble-size recommender

**Files:** `metaengine/devfabric/ensemble.py`, tests.

- [ ] Test trivial=1, normal default=2, high-risk <=4 only when free quota/local capacity permits.
- [ ] Implement risk + observed marginal improvement + quota + independence scoring; never reduce deterministic gate profile.
- [ ] Run tests; commit `feat: recommend bounded candidate ensembles`.

### Task 4: Add differential development benchmark scheduler

**Files:** `metaengine/devfabric/devbench.py`, `benchmarks/devfabric/`, tests.

- [ ] Test frozen holdout IDs and equal-budget comparators.
- [ ] Implement comparisons: single worker, best-of-N, simple orchestrator, fabric router; record independent verifier outcomes.
- [ ] Run synthetic tests; commit `feat: benchmark development orchestration policies`.

### Task 5: Add analytics readback without authority

**Files:** `metaengine/devfabric/analytics.py`, tests.

- [ ] Test remote metric discrepancy yields reconciliation finding and never overwrites local receipt hash.
- [ ] Implement aggregate import/readback only.
- [ ] Run tests; commit `feat: reconcile development analytics`.

### Task 6: Stage F evidence gate

- [ ] Run full deterministic suite.
- [ ] Require at least 48 paired holdout observations per critical task class before specialization claims; otherwise `INSUFFICIENT_EVIDENCE`.
- [ ] Require positive lower confidence bound and no safety/cost regression before enabling a routing prior by default.
- [ ] Generate measured `stage-f-gate.json` and commit.
