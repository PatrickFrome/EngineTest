from pathlib import Path

from metaengine.devfabric.doctor import Doctor
from metaengine.devfabric.providers.local_tools import ToolState


def missing_inventory():
    names=('coder','devpod','openhands','agent-canvas','ollama','opencode')
    return {name:ToolState(name,False,'UNAVAILABLE',path=None,version=None) for name in names}


def test_offline_doctor_does_not_require_optional_ai_tools(monkeypatch):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setattr('metaengine.devfabric.doctor.discover_local_tools',lambda: missing_inventory())
    report=Doctor(root).inspect('offline')
    assert all(not check.code.startswith('AI_TOOL_') for check in report.checks)


def test_stage_b_doctor_reports_each_missing_tool_without_failing_offline(monkeypatch):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setattr('metaengine.devfabric.doctor.discover_local_tools',lambda: missing_inventory())
    report=Doctor(root).inspect_ai_swarm()
    assert report.status=='OPTIONAL_PROVIDER_UNAVAILABLE'
    codes={check.code for check in report.checks}
    assert {f'AI_TOOL_{name.upper().replace("-","_")}' for name in missing_inventory()} <= codes
    assert all(check.required is False for check in report.checks)


def test_ai_swarm_manifest_is_zero_spend_and_opt_in():
    import json
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'devfabric/toolchain/AI_SWARM_MANIFEST.json').read_text())
    assert manifest['zero_spend'] is True
    assert manifest['auto_install'] is False
    assert {'coder','devpod','openhands','ollama','opencode'} <= set(manifest['tools'])
    text=(root/'devfabric/bootstrap/install-ai-swarm.sh').read_text()
    assert '--install' in text and 'MODE=print' in text
