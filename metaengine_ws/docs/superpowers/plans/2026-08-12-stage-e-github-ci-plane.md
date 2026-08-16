# Stage E — Optional GitHub / CI Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional GitHub remote, PR projection, and reproducible CI verification without making GitHub necessary for local development or recovery.

**Architecture:** Local Git remains mandatory source history. GitHub mirrors branches/PRs and runs deterministic gates; CI receipts are evidence inputs, not canonical promotion commands.

**Tech Stack:** GitHub connector/gh, GitHub Actions, uv, Python verification stack, optional review plugins only when free/privacy-compatible.

## Global Constraints

- Do not execute remote mutations until a repository is visible and authorized.
- Never make private source public merely to obtain a free reviewer.
- Actions gets no Supabase service-role/canonical promotion secret.
- CI failure blocks promotion; CI success alone never promotes.

---

### Task 1: Add repository readiness gate

**Files:** `metaengine/devfabric/providers/github.py`, `tests/devfabric/test_github_readiness.py`.

- [ ] Test zero repositories => `UNAVAILABLE_NO_REPOSITORY` and no repository auto-creation.
- [ ] Implement readiness/remote identity capture.
- [ ] Run tests; commit `feat: gate optional GitHub integration`.

### Task 2: Add deterministic CI workflows

**Files:** `.github/workflows/verify.yml`, `.github/workflows/capsule.yml`, YAML policy tests.

- [ ] Test least privilege (`contents: read`) and absence of canonical credentials.
- [ ] Implement Python 3.11+ matrix with `uv sync --locked`, pytest, Ruff, mypy, Semgrep, pip-audit, capsule verify.
- [ ] Validate workflow syntax; commit `ci: add deterministic verification workflows`.

### Task 3: Add PR projection/receipt ingestion

**Files:** `metaengine/devfabric/github_projection.py`, tests.

- [ ] Test PR metadata cannot alter Candidate/Verification hashes.
- [ ] Implement push/PR mapping behind explicit write intent.
- [ ] Run tests; commit `feat: project candidates into GitHub pull requests`.

### Task 4: Gate optional free review surfaces

**Files:** `devfabric/profiles/github-review.toml`, tests.

- [ ] Encode prerequisites: repository visibility/privacy, free quota, no paid fallback.
- [ ] CodeRabbit/Sonar/Copilot stay disabled when prerequisites fail.
- [ ] Run tests; commit `chore: gate optional GitHub reviewers`.

### Task 5: Stage E gate

- [ ] If no repository exists, generate `stage-e-gate.json` with `SKIPPED_NO_REPOSITORY`.
- [ ] If authorized repository exists, push only after local gates, run CI, ingest receipts, verify hashes.
- [ ] Commit gate receipt locally.
