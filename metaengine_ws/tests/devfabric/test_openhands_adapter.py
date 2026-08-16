from pathlib import Path
import os, subprocess

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.openhands import OpenHandsAdapter


def _repo(path: Path) -> None:
    subprocess.run(["git","init","-q"],cwd=path,check=True)
    subprocess.run(["git","config","user.name","Test"],cwd=path,check=True)
    subprocess.run(["git","config","user.email","test@example.invalid"],cwd=path,check=True)
    (path/"base.txt").write_text("base\n")
    subprocess.run(["git","add","."],cwd=path,check=True)
    subprocess.run(["git","commit","-qm","base"],cwd=path,check=True)


def _task():
    return TaskEnvelope.create(source_checkpoint_id="cp",source_tree_hash="t",objective="write marker",acceptance_tests=("marker",),allowed_paths=("marker.txt",),forbidden_paths=(".git",),capabilities_required=("CODE_GENERATOR",),risk_class=RiskClass.LOW,privacy_class=PrivacyClass.P3)


def test_openhands_headless_uses_local_ollama_and_returns_receipt(monkeypatch,tmp_path):
    repo=tmp_path/"repo"; repo.mkdir(); _repo(repo)
    bin_dir=tmp_path/"bin"; bin_dir.mkdir()
    tool=bin_dir/"openhands"
    tool.write_text("#!/bin/sh\nprintf ok > marker.txt\nprintf '%s\\n' \"$OPENHANDS_SUPPRESS_BANNER|$LLM_MODEL|$LLM_BASE_URL|$LLM_API_KEY\" > env.txt\necho '{\"event\":\"FinishAction\"}'\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH",f"{bin_dir}:{os.environ.get('PATH','')}")
    adapter=OpenHandsAdapter(model="ollama/qwen3-coder",base_url="http://127.0.0.1:11434",timeout_seconds=5)
    receipt=adapter.execute(_task(),repo)
    assert receipt.provider_id=="openhands-ollama-local"
    assert "marker.txt" in receipt.changed_paths
    env=(repo/"env.txt").read_text().strip().split("|")
    assert env[0]=="1"
    assert env[1]=="ollama/qwen3-coder"
    assert env[2]=="http://127.0.0.1:11434"
    assert env[3]=="ollama-local"
    assert dict(receipt.metadata)["exit_code"]=="0"


def test_openhands_descriptor_is_local_free():
    adapter=OpenHandsAdapter()
    assert adapter.descriptor.external is False
    assert adapter.quota_snapshot().paid_fallback_enabled is False
