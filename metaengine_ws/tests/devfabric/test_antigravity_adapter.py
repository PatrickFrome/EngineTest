import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.antigravity import AntigravityAdapter
from metaengine.devfabric.providers.external import ConnectorPolicyError
from metaengine.devfabric.router import DevFabricRouter


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "devfabric" / "antigravity" / "settings.json"
RULE = ROOT / ".agents" / "rules" / "metaengine-devfabric.md"
AGENTS = ROOT / "AGENTS.md"


def task(privacy=PrivacyClass.P1):
    return TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 40,
        objective="Improve connector layer",
        acceptance_tests=("tests pass",),
        allowed_paths=("metaengine/devfabric/",),
        forbidden_paths=(".env", "chat_env/"),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.NORMAL,
        privacy_class=privacy,
    )


def test_project_settings_disable_credits_and_non_workspace_access():
    data = json.loads(SETTINGS.read_text())
    assert data["useG1Credits"] is False
    assert data["allowNonWorkspaceAccess"] is False
    assert data["enableTerminalSandbox"] is True
    assert data["enableTelemetry"] is False
    assert data["toolPermission"] == "proceed-in-sandbox"


def test_workspace_rule_is_always_referenced_and_declares_no_authority():
    rule = RULE.read_text()
    agents = AGENTS.read_text()
    assert "@.agents/rules/metaengine-devfabric.md" in agents
    for phrase in (
        "NO_CANONICAL_AUTHORITY",
        "PATCH_ONLY_OUTPUT",
        "DETERMINISTIC_GATES_REQUIRED",
        "DO_NOT_ACCESS_CANONICAL_CREDENTIALS",
    ):
        assert phrase in rule


def test_build_argv_uses_headless_json_sandbox_without_dangerous_skip_flags(tmp_path: Path):
    adapter = AntigravityAdapter(
        settings_path=SETTINGS,
        effective_settings_path=SETTINGS,
        binary="agy",
    )
    argv = adapter.build_argv(task(), tmp_path)
    joined = " ".join(argv)
    assert argv[0] == "agy"
    assert "-p" in argv
    assert "--cwd" in argv
    assert "--output-format" in argv and "json" in argv
    assert "--mode=accept-edits" in argv
    assert "--sandbox" in argv
    assert "--dangerously-skip-permissions" not in joined
    assert "--yolo" not in joined


def test_unknown_quota_is_rejected_by_zero_spend_router(monkeypatch):
    adapter = AntigravityAdapter(
        settings_path=SETTINGS,
        effective_settings_path=SETTINGS,
        binary="agy",
        quota_reader=None,
    )
    monkeypatch.setattr(adapter, "health_check", lambda: __import__(
        "metaengine.devfabric.providers.base", fromlist=["HealthSnapshot"]
    ).HealthSnapshot(True, 1, "test"))
    decision = DevFabricRouter().route(task(), [adapter])
    assert decision.selected == ()
    assert "ZERO_SPEND_QUOTA_UNKNOWN" in decision.reasons


def test_p2_p3_execution_is_blocked(tmp_path: Path):
    adapter = AntigravityAdapter(
        settings_path=SETTINGS,
        effective_settings_path=SETTINGS,
        binary="agy",
    )
    for privacy in (PrivacyClass.P2, PrivacyClass.P3):
        with pytest.raises(ConnectorPolicyError) as exc:
            adapter.execute(task(privacy), tmp_path)
        assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"


def test_execute_returns_patch_receipt_with_fake_headless_runner(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)

    def runner(argv, **kwargs):
        assert kwargs["cwd"] == tmp_path
        (tmp_path / "candidate.txt").write_text("candidate\n")
        return SimpleNamespace(returncode=0, stdout='{"result":"ok"}', stderr="")

    adapter = AntigravityAdapter(
        settings_path=SETTINGS,
        effective_settings_path=SETTINGS,
        binary="agy",
        quota_reader=lambda: {"known": True, "free_remaining": 3},
        runner=runner,
    )
    receipt = adapter.execute(task(), tmp_path)
    assert receipt.provider_id == "antigravity-zero-spend"
    assert "candidate.txt" in receipt.changed_paths
    assert dict(receipt.metadata)["exit_code"] == "0"


def test_effective_settings_must_be_verified_before_execution(tmp_path: Path):
    unsafe = tmp_path / "settings.json"
    unsafe.write_text(json.dumps({
        "useG1Credits": True,
        "allowNonWorkspaceAccess": False,
        "enableTerminalSandbox": True,
        "enableTelemetry": False,
        "toolPermission": "proceed-in-sandbox",
    }))
    adapter = AntigravityAdapter(
        settings_path=SETTINGS,
        effective_settings_path=unsafe,
        binary="agy",
    )
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.execute(task(), tmp_path)
    assert exc.value.reason_code == "PAID_FALLBACK_NOT_DISABLED"
