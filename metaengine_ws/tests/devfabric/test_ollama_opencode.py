from pathlib import Path
import json
import subprocess

import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.ollama import OllamaAdapter
from metaengine.devfabric.providers.opencode import OpenCodeAdapter, load_local_opencode_config


def _task() -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id="cp-test",
        source_tree_hash="tree",
        objective="create marker.txt containing ok",
        acceptance_tests=("marker.txt equals ok",),
        allowed_paths=("marker.txt",),
        forbidden_paths=(".git", "devfabric/state"),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.LOW,
        privacy_class=PrivacyClass.P3,
    )


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    (path / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=path, check=True)


def test_ollama_rejects_non_loopback_endpoint():
    with pytest.raises(ValueError):
        OllamaAdapter(endpoint="https://ollama.example.com/v1")


def test_ollama_is_local_unlimited_even_when_daemon_missing(monkeypatch):
    adapter = OllamaAdapter(endpoint="http://127.0.0.1:11434/v1")
    quota = adapter.quota_snapshot()
    assert quota.known is True
    assert quota.free_remaining is None
    assert quota.paid_fallback_enabled is False
    assert adapter.descriptor.billing_mode == "LOCAL_FREE"


def test_local_opencode_config_enables_only_ollama():
    root = Path(__file__).resolve().parents[2]
    config = load_local_opencode_config(root / "devfabric/opencode.local.json")
    assert config["enabled_providers"] == ["ollama"]
    assert config["provider"]["ollama"]["options"]["baseURL"] == "http://127.0.0.1:11434/v1"
    serialized = json.dumps(config).lower()
    assert "apikey" not in serialized
    assert "token" not in serialized


def test_opencode_candidate_receipt_is_bound_to_git_patch(monkeypatch, tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); _repo(repo)
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    tool = bin_dir / "opencode"
    tool.write_text("#!/bin/sh\nprintf ok > marker.txt\necho '{\"type\":\"done\"}'\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ.get('PATH','')}")

    root = Path(__file__).resolve().parents[2]
    adapter = OpenCodeAdapter(
        model="ollama/qwen3-coder",
        config_path=root / "devfabric/opencode.local.json",
        timeout_seconds=5,
    )
    receipt = adapter.execute(_task(), repo)

    assert receipt.provider_id == "opencode-ollama-local"
    assert receipt.changed_paths == ("marker.txt",)
    assert receipt.patch_hash != ""
    assert dict(receipt.metadata)["exit_code"] == "0"
    assert (repo / "marker.txt").read_text() == "ok"
