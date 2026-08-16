from pathlib import Path
import os

from metaengine.devfabric.providers.local_tools import discover_ai_swarm_tools


def _fake_tool(bin_dir: Path, name: str, version: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\necho '{version}'\n")
    path.chmod(0o755)


def test_missing_tools_are_reported_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    states = discover_ai_swarm_tools()
    assert set(states) == {"coder", "devpod", "openhands", "agent-canvas", "ollama", "opencode"}
    assert all(not item.available for item in states.values())
    assert all(item.status == "UNAVAILABLE" for item in states.values())


def test_versions_are_captured_without_installing(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("coder", "devpod", "openhands", "agent-canvas", "ollama", "opencode"):
        _fake_tool(bin_dir, name, f"{name} 9.9.9")
    monkeypatch.setenv("PATH", str(bin_dir))

    before = sorted(p.name for p in bin_dir.iterdir())
    states = discover_ai_swarm_tools(timeout_seconds=2)
    after = sorted(p.name for p in bin_dir.iterdir())

    assert before == after
    assert all(item.available for item in states.values())
    assert all("9.9.9" in item.version for item in states.values())
    assert all(item.status == "AVAILABLE" for item in states.values())
