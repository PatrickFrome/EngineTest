# Stage A — Portable Local Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended where supported) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a fully usable OFFLINE development control plane with immutable task/receipt contracts, local journal/outbox, capability routing, isolated Git candidate worlds, deterministic verification, bootstrap/doctor, and a self-verifying CONTROL capsule.

**Architecture:** New fabric code lives under `metaengine/devfabric/` and does not alter the existing reasoning-engine adapter registry. Configuration and generated state live under top-level `devfabric/`; the new CLI is additive and existing `destruktion-meta16` behavior remains unchanged.

**Tech Stack:** Python >=3.11, uv, dataclasses/enums, sqlite3, subprocess/Git worktrees, pytest, Hypothesis, Ruff, mypy, Semgrep CE, pip-audit, TOML, SHA-256.

## Global Constraints

- Source artifact SHA-256: `8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0`.
- Supabase remains canonical; Stage A performs no canonical cloud writes.
- `zero_spend = true`; Stage A has no paid dependency.
- No secrets are stored in repository, journal fixtures, or capsule.
- Do not modify lineage bytes or existing `SHA256SUMS.txt`/legacy root integrity metadata in place.
- Existing CLI command behavior remains backwards compatible.

---

### Task 1: Establish source binding and local Git baseline

**Files:**
- Create: `devfabric/source_binding.json`
- Create: `.gitignore` if absent, otherwise modify it
- Test: `tests/test_devfabric_git_baseline.py`

**Interfaces:**
- Consumes: uploaded archive SHA-256 from the approved design.
- Produces: Git `HEAD` baseline and `devfabric/source_binding.json` with keys `artifact_sha256`, `release_version`, `binding_version`.

- [ ] **Step 1: Write the failing baseline test**

```python
from pathlib import Path
import json, subprocess

ROOT = Path(__file__).resolve().parents[1]

def test_source_binding_matches_git_baseline():
    binding = json.loads((ROOT / "devfabric/source_binding.json").read_text())
    assert binding["artifact_sha256"] == "8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0"
    assert binding["release_version"] == "2.3.0-alpha.1"
    assert subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() == "true"
```

- [ ] **Step 2: Run the test and verify it fails before Git/source binding exists**

Run: `python -m pytest tests/test_devfabric_git_baseline.py -v`
Expected: FAIL because `devfabric/source_binding.json` and/or Git metadata are absent.

- [ ] **Step 3: Create deterministic source binding and initialize Git**

Create `devfabric/source_binding.json`:

```json
{
  "binding_version": "METAENGINE-DEVFABRIC-SOURCE-BINDING-1",
  "artifact_sha256": "8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0",
  "release_version": "2.3.0-alpha.1",
  "canonical_checkpoint_policy": "APPEND_ONLY_PROPOSAL_NO_AUTOPROMOTION"
}
```

Append to `.gitignore`:

```gitignore
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
__pycache__/
devfabric/state/*
!devfabric/state/.gitkeep
devfabric/artifacts/candidates/*
devfabric/artifacts/reports/runtime/*
dist/
.env
.env.*
!.env.example
```

Initialize and baseline:

```bash
git init
git add .
git -c user.name="Metaengine Bootstrap" -c user.email="metaengine-bootstrap@local.invalid" commit -m "chore: bind portable source baseline"
```

- [ ] **Step 4: Run the baseline test**

Run: `python -m pytest tests/test_devfabric_git_baseline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit any test adjustment only if it was not included in baseline**

```bash
git add tests/test_devfabric_git_baseline.py devfabric/source_binding.json .gitignore
git commit -m "test: verify source-bound git baseline"
```

---

### Task 2: Add locked Python development toolchain

**Files:**
- Modify: `pyproject.toml`
- Create: `uv.lock`
- Create: `devfabric/TOOLCHAIN.lock`
- Test: `tests/test_devfabric_toolchain.py`

**Interfaces:**
- Consumes: Python project metadata.
- Produces: project-pinned dev commands available via `uv run`; machine-readable toolchain receipt.

- [ ] **Step 1: Write the failing toolchain test**

```python
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def test_toolchain_lock_declares_required_commands():
    lock = json.loads((ROOT / "devfabric/TOOLCHAIN.lock").read_text())
    for name in ("pytest", "hypothesis", "ruff", "mypy", "pip-audit", "semgrep"):
        assert name in lock["required_tools"]
    assert lock["python_floor"] == "3.11"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_devfabric_toolchain.py -v`
Expected: FAIL because lock does not exist.

- [ ] **Step 3: Add project development dependencies and lock them**

Run:

```bash
uv add --dev pytest jsonschema hypothesis ruff mypy pip-audit semgrep
uv lock
uv sync --locked
```

Create `devfabric/TOOLCHAIN.lock` from actual installed versions using a one-shot command:

```bash
uv run python - <<'PY'
import importlib.metadata as m, json, platform
names = {"pytest":"pytest", "hypothesis":"hypothesis", "ruff":"ruff", "mypy":"mypy", "pip-audit":"pip-audit", "semgrep":"semgrep"}
versions = {logical: m.version(dist) for logical, dist in names.items()}
print(json.dumps({"lock_version":"METAENGINE-DEVFABRIC-TOOLCHAIN-1","python_floor":"3.11","python_runtime":platform.python_version(),"required_tools":versions}, indent=2, sort_keys=True))
PY
```

Redirect the JSON output to `devfabric/TOOLCHAIN.lock`.

- [ ] **Step 4: Run lock/tool tests**

Run:

```bash
uv run pytest tests/test_devfabric_toolchain.py -v
uv run ruff --version
uv run mypy --version
uv run pip-audit --version
uv run semgrep --version
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock devfabric/TOOLCHAIN.lock tests/test_devfabric_toolchain.py
git commit -m "build: lock portable development toolchain"
```

---

### Task 3: Implement immutable development exchange objects

**Files:**
- Create: `metaengine/devfabric/__init__.py`
- Create: `metaengine/devfabric/models.py`
- Create: `metaengine/devfabric/codec.py`
- Test: `tests/devfabric/test_models.py`

**Interfaces:**
- Produces: `TaskEnvelope`, `CandidateReceipt`, `VerificationReceipt`, `PromotionProposal`, `PrivacyClass`, `RiskClass`, `Verdict`, `canonical_digest(value)`.
- Consumed by: every later fabric task and adapter.

- [ ] **Step 1: Write failing model/hash tests**

```python
import pytest
from dataclasses import FrozenInstanceError
from metaengine.devfabric.models import TaskEnvelope, PrivacyClass, RiskClass


def test_task_envelope_is_immutable_and_hash_stable():
    task = TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 64,
        objective="Add a deterministic feature",
        acceptance_tests=("pytest -q",),
        allowed_paths=("metaengine/", "tests/"),
        forbidden_paths=("lineages/",),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.NORMAL,
        privacy_class=PrivacyClass.P1,
    )
    assert task.zero_spend is True
    assert len(task.task_hash) == 64
    with pytest.raises(FrozenInstanceError):
        task.objective = "mutated"
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/devfabric/test_models.py -v`
Expected: import failure.

- [ ] **Step 3: Implement canonical codec and frozen models**

`metaengine/devfabric/codec.py`:

```python
from __future__ import annotations
import hashlib, json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_primitive(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): to_primitive(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [to_primitive(v) for v in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
```

Implement enums and frozen dataclasses in `models.py`; `TaskEnvelope.create()` derives `task_id = "task-" + digest[:20]` and `task_hash` from all non-derived fields. `CandidateReceipt` binds `task_id`, `provider_id`, `base_tree_hash`, `patch_hash`, `changed_paths`; `VerificationReceipt` binds verifier/version/commands/exit statuses/verdict; `PromotionProposal` references hashes only and never performs writes.

- [ ] **Step 4: Run model tests plus property test for key-order stability**

Add:

```python
from hypothesis import given, strategies as st
from metaengine.devfabric.codec import canonical_digest

@given(st.dictionaries(st.text(min_size=1, max_size=8), st.integers(), max_size=8))
def test_canonical_digest_ignores_mapping_insertion_order(value):
    assert canonical_digest(value) == canonical_digest(dict(reversed(list(value.items()))))
```

Run: `uv run pytest tests/devfabric/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add metaengine/devfabric tests/devfabric/test_models.py
git commit -m "feat: add immutable development exchange contracts"
```

---

### Task 4: Implement SQLite journal and append-only local outbox

**Files:** `metaengine/devfabric/journal.py`, `devfabric/state/.gitkeep`, `tests/devfabric/test_journal.py`.

**Interfaces:** `Journal.append(kind, object_id, payload) -> JournalReceipt`, `Journal.pending_outbox()`, `Journal.mark_replayed(event_id, remote_receipt_hash)`.

- [ ] **Step 1: Write failing append/tamper tests**

```python
from metaengine.devfabric.journal import Journal


def test_journal_is_hash_chained(tmp_path):
    j = Journal(tmp_path / "session.sqlite")
    first = j.append("TASK_CREATED", "task-1", {"x": 1})
    second = j.append("CANDIDATE_RECEIVED", "cand-1", {"y": 2})
    assert second.parent_hash == first.event_hash
    assert j.verify_chain() == []
```

- [ ] **Step 2: Verify failure** — run `uv run pytest tests/devfabric/test_journal.py -v`; expect import failure.
- [ ] **Step 3: Implement transactional schema** — tables `events` and `outbox`; use `BEGIN IMMEDIATE`; hash payload and previous event hash; reject conflicting replay hashes.
- [ ] **Step 4: Add direct-corruption and replay-idempotency tests** — tampering must be detected; same replay receipt is idempotent, different receipt raises `JournalConflict`.
- [ ] **Step 5: Run tests and commit** — `git commit -m "feat: add hash-chained local development journal"`.

---

### Task 5: Implement capability registry, privacy gate, and zero-spend router

**Files:** `metaengine/devfabric/providers/base.py`, `metaengine/devfabric/capabilities.py`, `metaengine/devfabric/policy.py`, `metaengine/devfabric/router.py`, `devfabric/metaenv.toml`, `devfabric/profiles/{offline,free-cloud,max-swarm}.toml`, `tests/devfabric/test_router.py`.

**Interfaces:** `ProviderDescriptor`, `QuotaSnapshot`, `ProviderAdapter`, `DispatchDecision`, `DevFabricRouter.route(task, providers)`.

- [ ] **Step 1: Write failing P3 and unknown-paid-quota tests**

```python

def test_p3_never_routes_external(task_factory, fake_external_provider):
    decision = DevFabricRouter().route(task_factory(privacy_class=PrivacyClass.P3), [fake_external_provider])
    assert decision.selected == ()
    assert "PRIVACY_CLASS_BLOCKED" in decision.reasons


def test_unknown_paid_quota_fails_closed(task_factory, fake_paid_provider_unknown_quota):
    decision = DevFabricRouter().route(task_factory(), [fake_paid_provider_unknown_quota])
    assert decision.selected == ()
    assert "ZERO_SPEND_QUOTA_UNKNOWN" in decision.reasons
```

- [ ] **Step 2: Verify failure** — `uv run pytest tests/devfabric/test_router.py -v`.
- [ ] **Step 3: Implement exact provider protocol**

```python
class ProviderAdapter(Protocol):
    descriptor: ProviderDescriptor
    def health_check(self) -> HealthSnapshot: ...
    def quota_snapshot(self) -> QuotaSnapshot: ...
    def execute(self, task: TaskEnvelope, workdir: Path) -> CandidateReceipt: ...
    def cancel(self, task_id: str) -> bool: ...
```

Ranking is deterministic: privacy eligibility, health, free-quota certainty, task-class effectiveness, independence, latency hint, provider_id lexical tie-break. Routing history never changes truth verdicts.

- [ ] **Step 4: Run deterministic-order tests** — expected PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: add fail-closed capability router"`.

---

### Task 6: Implement isolated Git candidate worlds

**Files:** `metaengine/devfabric/worktrees.py`, `tests/devfabric/test_worktrees.py`.

**Interfaces:** `WorktreeManager.create(task_id, candidate_id)`, `verify_base`, `collect_patch`, `remove`.

- [ ] Write failing isolation test proving a candidate file never appears in main checkout.
- [ ] Run test; expect import failure.
- [ ] Implement `git worktree add --detach`, safe IDs `[A-Za-z0-9_.-]`, worktree root under `devfabric/state/worktrees/`, binary diff SHA and changed-path capture.
- [ ] Test cleanup/base mismatch; expect PASS.
- [ ] Commit `feat: isolate candidate patches with git worktrees`.

---

### Task 7: Implement deterministic verifier profiles

**Files:** `metaengine/devfabric/verifier.py`, `devfabric/verification/profiles.toml`, `devfabric/verification/semgrep/python-security.yml`, `tests/devfabric/test_verifier.py`.

**Interfaces:** `Verifier.run(profile_name, candidate_dir) -> VerificationReceipt`; profiles `fast`, `normal`, `high-risk`, `release`.

- [ ] Write failing test: exit code 7 yields `FAIL` regardless of positive AI review.
- [ ] Run test; expect import failure.
- [ ] Implement `normal` commands:

```text
uv run pytest -q
uv run ruff check metaengine tests
uv run mypy metaengine/devfabric
uv run semgrep --config devfabric/verification/semgrep metaengine
uv run pip-audit --locked .
```

Vendor a minimal project-owned Semgrep rule pack under `devfabric/verification/semgrep/` so SAST works with no network. Every command stores tool version, cwd, exit code, wall time, stdout/stderr digest. `pip-audit` is the only Stage A gate that may need a current vulnerability feed: feed/network unavailability becomes `INCONCLUSIVE_SECURITY_FEED` and blocks canonical promotion, but it does not prevent OFFLINE editing, testing, packaging, or checkpoint proposal. Deterministic test/static/Semgrep failures are always `FAIL`.
- [ ] Run PASS/FAIL/INCONCLUSIVE tests.
- [ ] Commit `feat: add deterministic development verifier`.

---

### Task 8: Implement doctor and cross-platform bootstrap

**Files:** `metaengine/devfabric/doctor.py`, `devfabric/bootstrap/{linux,macos,windows-wsl}.sh`, `tests/devfabric/test_doctor.py`.

**Interfaces:** `Doctor.inspect(profile) -> DoctorReport`.

- [ ] Write failing test asserting OFFLINE doctor requires no cloud credential checks.
- [ ] Run test; expect import failure.
- [ ] Implement checks: Python >=3.11, uv, Git, writable local state, source binding, Git baseline, lock consistency, required tools, no protected lineage modifications. Bootstrap may install uv then `uv sync --locked`; it does not authenticate or install cloud agents.
- [ ] Run unit tests and real OFFLINE doctor.
- [ ] Commit `feat: add portable offline doctor and bootstrap`.

---

### Task 9: Add additive development CLI

**Files:** `metaengine/devfabric/cli.py`, `pyproject.toml`, `tests/devfabric/test_cli.py`.

**Interfaces:** `metaengine-dev doctor`, `task-create`, `journal-verify`, `verify`, `capsule-build`, `recover-test`, `gate-verify`.

- [ ] Write failing test that both `metaengine-dev --help` and existing `destruktion-meta16 --help` succeed after implementation.
- [ ] Run test; expect new command missing.
- [ ] Add `metaengine-dev = "metaengine.devfabric.cli:main"`; canonical write commands do not exist in Stage A.
- [ ] Run CLI tests.
- [ ] Commit `feat: expose portable development CLI`.

---

### Task 10: Build and verify portable CONTROL capsule

**Files:** `metaengine/devfabric/capsule.py`, `devfabric/CAPSULE_POLICY.md`, `scripts/build_devfabric_capsule.py`, `tests/devfabric/test_capsule.py`.

**Interfaces:** `build_control_capsule(root, out)`, `verify_control_capsule(path)`; deterministic ZIP and manifest root.

- [ ] Write failing test asserting no bad/missing/extra files and zero secret hits after extraction.
- [ ] Run test; expect import failure.
- [ ] Implement sorted relative POSIX paths, normalized ZIP timestamp `1980-01-01T00:00:00`, SHA rows, payload root; exclude `.git`, `.venv`, caches, local journals, worktrees, credentials, generated candidates.
- [ ] Run `metaengine-dev capsule-build` and `recover-test`; expect identical payload root after extraction.
- [ ] Commit `feat: build self-verifying development control capsule`.

---

### Task 11: Stage A integrated OFFLINE gate

**Files:** generated `devfabric/artifacts/manifests/stage-a-gate.json`, modify `README.md`.

- [ ] Run:

```bash
uv sync --locked
uv run pytest -q
uv run ruff check metaengine tests
uv run mypy metaengine/devfabric
uv run semgrep --config devfabric/verification/semgrep metaengine
uv run pip-audit --locked .
uv run metaengine-dev doctor --profile offline --json
uv run metaengine-dev capsule-build --out dist/METAENGINE_DEVFABRIC_CONTROL.zip --json
uv run metaengine-dev recover-test --control-capsule dist/METAENGINE_DEVFABRIC_CONTROL.zip --json
```

- [ ] If local Semgrep or deterministic security checks fail, STOP. If only the online vulnerability feed is unreachable, record `INCONCLUSIVE_SECURITY_FEED`; the OFFLINE gate may still certify development/recovery capability, but promotion/release remains blocked until a fresh `pip-audit --locked .` succeeds.
- [ ] Generate the gate receipt only from measured outputs: source SHA, Git HEAD, uv.lock hash, test counts, verifier receipt hash, capsule SHA/payload root.
- [ ] Verify `uv run metaengine-dev gate-verify devfabric/artifacts/manifests/stage-a-gate.json --json` returns PASS.
- [ ] Commit `docs: certify portable offline development kernel`.
