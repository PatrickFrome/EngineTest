# External Facts Errata and Runtime-Discovery Notes — 2026-08-12

This file records vendor facts discovered while converting the approved architecture into implementation plans. It does not change architectural authority or the approved zero-spend design.

## Neon free-plan quota correction

The approved design text included a planning-time hint that Neon Free currently allowed 10 projects. The current official Neon pricing page observed during implementation planning reports **100 projects**, **100 CU-hours monthly per project**, **0.5 GB storage per project**, and access to branching on Free.

Implementation consequence: no fixed project-count value is treated as truth. `NeonAdapter.quota_snapshot()` must query/inspect live account capability where available or mark the quota unknown. This is already consistent with the approved design rule that vendor quotas are runtime-discovered configuration hints.

## Antigravity zero-spend guard

Current Antigravity documentation exposes model quota usage through `/usage`/`/quota`. Its settings include `useG1Credits`; when set to `false`, the CLI does not consume personal AI credits after baseline quota is exhausted. The Individual tier is currently listed at $0/month with basic weekly rate limits.

Implementation consequence: the portable project config requires `useG1Credits=false`, and the adapter fails closed if free baseline quota cannot be established. Authentication and personal global settings remain outside the portable capsule.

## Offline security verification

Semgrep Community Edition can run against local rules without login, so Stage A vendors a minimal project-owned rule pack for offline SAST. `pip-audit` checks known dependency vulnerabilities and may require a current advisory feed. If that feed is unavailable, the OFFLINE development gate may remain usable with `INCONCLUSIVE_SECURITY_FEED`, but canonical release/promotion is blocked until a fresh dependency audit succeeds.

## uv lock / PEP 751 audit interchange correction

Current uv documentation states that ordinary project commands may automatically update lock state unless `--locked` or `--frozen` is used. It also supports `uv export --format pylock.toml` for PEP 751 interchange. Current pip-audit documentation states that `--locked` project auditing searches supported project/lock formats including `pylock.*.toml`; uv.lock is not treated as the audit interchange file.

Implementation consequence: deterministic verifier commands use `uv run --locked`; bootstrap exports `pylock.toml` from an already resolved `uv.lock`; Doctor requires both artifacts before release/promotion certification. The execution container used for Stage A has no PyPI DNS access and no adequate uv package cache, so neither lock is fabricated: certification remains `BLOCKED_EXTERNAL_TOOLCHAIN` until resolution can run on a network-enabled machine.
