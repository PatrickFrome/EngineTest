# Metaengine Portable Development Fabric — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended where a coding workspace supports fresh subagents) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable, zero-spend, capability-routed multi-agent development fabric that can develop Destruktion 4.0 METAENGINE 16X from an ordinary chat without making any external provider a hidden source of truth.

**Architecture:** A mandatory local control plane owns task schemas, routing policy, deterministic verification, Git isolation, local receipts, and recovery. Optional adapters add local AI and free cloud workers, while Supabase remains the sole canonical mutable authority and all provider outputs remain content-addressed proposals until deterministic gates pass.

**Tech Stack:** Python >=3.11, uv, Git/worktrees, SQLite, pytest, Hypothesis, Ruff, mypy, Semgrep CE, pip-audit, TOML/JSON schemas, Ollama, OpenCode, Antigravity CLI, Supabase, Create State, Google Drive, Linear, PostHog, Neon, Replit, Cloudflare Workers/D1/R2/Workflows/Workers AI, optional GitHub Actions.

## Global Constraints

- Source artifact SHA-256: `8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0`.
- Target release: `2.3.0-alpha.1`; do not rewrite release history during fabric construction.
- Python floor remains `>=3.11`.
- Supabase project `gzrbxoiuenkksualgpvp` remains the sole canonical mutable ledger and promotion authority.
- `zero_spend = true` is the default execution invariant; uncertain quota means route elsewhere or run locally.
- No provider may auto-upgrade a plan, enable pay-as-you-go, attach billing, or silently use paid overage.
- P3 secrets/credentials/canonical privileged material never enter prompts, portable artifacts, telemetry, or third-party task payloads.
- External AI may propose, test, criticize, and rank patches; deterministic gates plus the existing canonical promotion protocol alone can authorize canonical state change.
- Existing lineage originals remain byte-preserved; majority vote is never truth.
- Neon is sandbox-only and must never resume canonical runtime reads/writes.
- GitHub is optional; local Git is mandatory after Stage A Task 1.
- New development state is generated under `devfabric/state/` and `devfabric/artifacts/` and excluded from source commits except deterministic manifests/fixtures explicitly listed by a task.
- Every adapter must support fail-closed health/quota/privacy decisions before dispatch.
- Every child plan ends in a runnable gate; do not start a dependent stage until its prerequisite gate passes.

---

## Dependency graph

```text
Stage A: Portable local kernel  ─┬─> Stage B: Local AI swarm ───────┐
                                ├─> Stage C: Connected services ───┼─> Stage F: Development intelligence
                                ├─> Stage D: Remote edge fabric ───┘
                                └─> Stage E: GitHub/CI (only when repo access exists)
```

Stage A is mandatory. Stages B, C, D, and E may proceed independently after A if their external prerequisites exist. Stage F requires at least Stage C telemetry plus one worker stage (B or D).

## Child plans

1. `2026-08-12-stage-a-portable-local-kernel.md` — schemas, SQLite journal, capability router, worktrees, verifier, doctor/bootstrap, offline recovery/capsule.
2. `2026-08-12-stage-b-local-ai-swarm.md` — Ollama/OpenCode, local candidate workers, critic workers, outcome-aware routing without truth authority.
3. `2026-08-12-stage-c-connected-services.md` — guarded Supabase, Create State, Drive, Linear, PostHog, Neon, Replit adapters.
4. `2026-08-12-stage-d-remote-edge-fabric.md` — Cloudflare MCP gateway, D1 ephemeral state, R2 artifacts, Workflows, Workers AI, Noodle Seed alternative.
5. `2026-08-12-stage-e-github-ci-plane.md` — optional remote repository, PR projection, Actions verification, optional free review surfaces.
6. `2026-08-12-stage-f-development-intelligence.md` — provider outcome telemetry, specialization, ensemble-size recommendations, benchmark scheduling.

## Master acceptance gate

After all enabled stages:

```bash
uv sync --locked
uv run pytest -q
uv run ruff check metaengine tests
uv run mypy metaengine/devfabric
uv run semgrep --config devfabric/verification/semgrep metaengine
uv run pip-audit --locked .
uv run python -m metaengine.devfabric.cli doctor --profile offline --json
uv run python -m metaengine.devfabric.cli recover-test --control-capsule dist/METAENGINE_DEVFABRIC_CONTROL.zip --json
```

Expected:

- all tests pass;
- Ruff and mypy return exit code 0;
- project-owned Semgrep rules pass offline; pip-audit returns 0 when a current vulnerability feed is reachable, otherwise the receipt is `INCONCLUSIVE_SECURITY_FEED` and canonical release/promotion stays blocked (never suppressed);
- doctor reports `PASS` in OFFLINE mode;
- recovery test reconstructs the same source/checkpoint binding and verifies content hashes;
- no P3/secret pattern appears in capsule, receipts, or telemetry fixtures;
- no stage changes canonical champion/policy as a side effect of testing.

## Execution policy

Implement one child plan at a time. Each task gets a fresh review boundary and a commit after green tests. High-risk adapter writes remain disabled until their contract tests and dry-run gates pass. Cloud deployment, Supabase DDL, repository publication, or canonical checkpoint promotion are separate explicit mutations even if implementation code for them exists.
