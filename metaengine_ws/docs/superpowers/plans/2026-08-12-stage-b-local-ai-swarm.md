# Stage B — Multi-Agent Development Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a zero-spend, portable multi-agent development layer combining Coder OSS, DevPod, OpenHands OSS, Ollama, and OpenCode without giving any worker canonical authority.

**Architecture:** Stage B separates workspace backends from AI agents. Coder and DevPod provide replaceable workspace execution planes; OpenHands and OpenCode provide agent execution; Ollama provides the default local model runtime. A composition registry exposes concrete swarm nodes while Stage A worktrees, receipts, router privacy gates, journal, and deterministic verifier remain authoritative.

**Tech Stack:** Python 3.11+, Git worktrees, Coder CLI/MCP, DevPod CLI/devcontainers, OpenHands headless/Agent Server, Ollama OpenAI-compatible local API, OpenCode CLI, TOML/JSON configuration, subprocess and HTTP health checks.

## Global Constraints

- Stage B branches from Stage A commit `c5a22e5a208a2a5673a7579b78560d92f3d7b170`.
- Supabase remains the sole canonical mutable authority; Stage B performs zero canonical cloud writes.
- Missing optional binaries yield `UNAVAILABLE`; they never make OFFLINE development fail.
- P3 tasks remain local-only. Remote Coder endpoints are external unless explicitly loopback/private-local classified.
- `zero_spend=true` denies any paid-capable/unknown-quota remote provider.
- OpenCode defaults to Ollama at `http://127.0.0.1:11434/v1`; no API credentials are stored in project files.
- OpenHands defaults to local Ollama and headless execution; worker self-reported success never overrides deterministic verification.
- Coder and DevPod are workspace/control-plane backends, not canonical stores.
- No provider may apply a patch to the controlling checkout; all candidates originate from isolated Stage A worktrees.

---

### Task 1: Provider discovery and immutable Stage B profile

**Files:** `metaengine/devfabric/providers/local_tools.py`, `devfabric/profiles/ai-swarm.toml`, `tests/devfabric/test_local_tools.py`.

- [x] Write tests for discovery/version capture of `coder`, `devpod`, `openhands`, `agent-canvas`, `ollama`, and `opencode`, including missing-tool `UNAVAILABLE` state.
- [x] Run tests and verify RED.
- [x] Implement bounded discovery only; discovery must never install or authenticate tools.
- [x] Run tests and verify GREEN.
- [x] Commit `feat: discover multi-agent development toolchain`.

### Task 2: Workspace backend contract and local backend

**Files:** `metaengine/devfabric/workspaces.py`, `tests/devfabric/test_workspace_backends.py`.

**Interfaces:** `WorkspaceBackend.prepare(task, source_world) -> WorkspaceHandle`, `run(handle, argv, env) -> ExecutionResult`, `cleanup(handle)`.

- [x] Write tests proving a local backend executes only inside the supplied candidate world and cannot target the controlling checkout.
- [x] Run RED.
- [x] Implement immutable handles/results and `LocalWorkspaceBackend`.
- [x] Run GREEN.
- [x] Commit `feat: add composable workspace backend contract`.

### Task 3: Ollama runtime and OpenCode agent

**Files:** `metaengine/devfabric/providers/ollama.py`, `metaengine/devfabric/providers/opencode.py`, `devfabric/opencode.local.json`, `tests/devfabric/test_ollama_opencode.py`.

- [x] Write tests for loopback-only Ollama endpoint, local-unlimited quota, credential-free OpenCode config, bounded execution, and CandidateReceipt hashing.
- [x] Run RED.
- [x] Implement Ollama health/model discovery and OpenCode headless command construction using local Ollama.
- [x] Run GREEN.
- [x] Commit `feat: add Ollama OpenCode candidate worker`.

### Task 4: OpenHands local-agent adapter

**Files:** `metaengine/devfabric/providers/openhands.py`, `tests/devfabric/test_openhands_adapter.py`.

- [x] Write tests proving headless JSON execution, local Ollama environment, banner suppression, timeout, no embedded credentials, and CandidateReceipt creation.
- [x] Run RED.
- [x] Implement OpenHands command adapter; support local headless CLI first and Agent Server endpoint as a health/readiness surface.
- [x] Run GREEN.
- [x] Commit `feat: add OpenHands local agent worker`.

### Task 5: DevPod workspace backend

**Files:** `metaengine/devfabric/providers/devpod.py`, `.devcontainer/devcontainer.json`, `tests/devfabric/test_devpod_backend.py`.

- [x] Write fake-CLI tests for Docker/SSH provider readiness, `devpod up ... --ide none`, command execution through `devpod ssh --command`, and cleanup.
- [x] Run RED.
- [x] Implement DevPod backend with deterministic workspace names and no cloud provider by default.
- [x] Run GREEN.
- [x] Commit `feat: add portable DevPod workspace backend`.

### Task 6: Coder workspace/control-plane backend

**Files:** `metaengine/devfabric/providers/coder.py`, `devfabric/coder/README.md`, `tests/devfabric/test_coder_backend.py`.

- [x] Write fake-CLI tests for `coder list --output json`, loopback/remote classification, `coder ssh <workspace> -- <command>`, and no automatic workspace deletion.
- [x] Run RED.
- [x] Implement Coder backend for pre-provisioned workspaces and expose MCP readiness metadata without relying on beta MCP for deterministic execution.
- [x] Run GREEN.
- [x] Commit `feat: add Coder workspace control plane`.

### Task 7: Composition registry and competitive swarm dispatcher

**Files:** `metaengine/devfabric/swarm.py`, `metaengine/devfabric/dispatch.py`, `tests/devfabric/test_swarm.py`, `tests/devfabric/test_dispatch.py`.

- [x] Write tests composing `local+opencode+ollama`, `local+openhands+ollama`, `devpod+opencode+ollama`, and `coder+openhands+ollama`; unavailable components must prune only their nodes.
- [x] Write tests proving competing candidates start from one base commit and never modify the controlling checkout.
- [x] Run RED.
- [x] Implement capability composition, bounded parallel dispatch, independence groups, and journal receipts.
- [x] Run GREEN.
- [x] Commit `feat: compose competitive multi-agent swarm`.

### Task 8: Non-authoritative critics and outcome-aware routing

**Files:** `metaengine/devfabric/review.py`, `metaengine/devfabric/performance.py`, `tests/devfabric/test_review.py`, `tests/devfabric/test_performance_routing.py`.

- [x] Test positive AI review cannot override deterministic FAIL; negative critic may block proposal.
- [x] Test EWMA history changes worker ordering but never verifier verdicts or privacy policy.
- [x] Run RED.
- [x] Implement hash-bound AIReviewReceipt and local routing priors.
- [x] Run GREEN.
- [x] Commit `feat: add swarm critic and measured routing priors`.

### Task 9: Stage B doctor/bootstrap and zero-spend install manifests

**Files:** `metaengine/devfabric/doctor.py`, `devfabric/bootstrap/install-ai-swarm.sh`, `devfabric/bootstrap/install-ai-swarm-wsl.sh`, `devfabric/toolchain/AI_SWARM_MANIFEST.json`, `tests/devfabric/test_stage_b_doctor.py`.

- [x] Write tests proving OFFLINE doctor remains usable with every optional tool missing, while local-ai readiness reports each tool separately.
- [x] Run RED.
- [x] Implement installer scripts that print/execute official installation paths only on explicit invocation and never configure paid providers.
- [x] Run GREEN.
- [x] Commit `feat: bootstrap optional multi-agent swarm`.

### Task 10: Stage B integration gate

**Files:** `devfabric/artifacts/manifests/stage-b-gate.json`.

- [x] Run all Stage A and Stage B tests, compileall, fast verifier, doctor, and lineage invariant.
- [x] If real providers are absent, run deterministic fake-provider composition smoke and record `OPTIONAL_PROVIDER_UNAVAILABLE` per missing binary rather than failing Stage B.
- [x] Verify zero canonical cloud writes and no project secrets.
- [x] Generate content-addressed Stage B gate receipt with tool availability and tested compositions.
- [x] Commit `docs: attest multi-agent development fabric`.


## Execution Record — 2026-08-12

- Implementation branch: `stage-b-multi-agent-fabric`.
- Real optional binaries on the current executor: Coder, DevPod, OpenHands, Agent Canvas, Ollama, OpenCode = `UNAVAILABLE`.
- Their CLI/workspace/agent contracts are exercised through deterministic fake-CLI/provider tests; missing optional binaries do not weaken OFFLINE correctness.
- Deterministic verification remains authoritative; AI reviews and performance priors are non-authoritative.
- Stage A release/security certification blockers remain inherited until `uv.lock`, PEP 751 `pylock.toml`, and the pinned external toolchain are resolved on a network-enabled executor.
