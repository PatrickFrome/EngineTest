from pathlib import Path
import json

from metaengine.devfabric.models import Verdict
from metaengine.devfabric.verifier import Verifier


def _profile(tmp_path: Path, name: str, command: str) -> Path:
    p = tmp_path / "profiles.toml"
    p.write_text(f'[profiles.{name}]\ncommands = [{json.dumps(command)}]\n')
    return p


def test_nonzero_exit_is_fail_regardless_of_external_opinion(tmp_path):
    profile = _profile(tmp_path, "fail", "python -c 'import sys; sys.exit(7)'")
    receipt = Verifier(profile).run("fail", tmp_path)
    assert receipt.verdict is Verdict.FAIL
    assert receipt.exit_statuses == (7,)


def test_successful_commands_pass(tmp_path):
    profile = _profile(tmp_path, "ok", "python -c 'print(42)'")
    receipt = Verifier(profile).run("ok", tmp_path)
    assert receipt.verdict is Verdict.PASS


def test_pip_audit_network_failure_is_inconclusive_security_feed(tmp_path):
    cmd = "python -c 'import sys; print(\"pip-audit Temporary failure in name resolution\", file=sys.stderr); sys.exit(1)'"
    profile = _profile(tmp_path, "feed", cmd)
    receipt = Verifier(profile).run("feed", tmp_path)
    assert receipt.verdict is Verdict.INCONCLUSIVE_SECURITY_FEED


def test_normal_profile_uses_locked_uv_execution_and_locked_audit():
    root = Path(__file__).resolve().parents[2]
    commands = Verifier(root / "devfabric/verification/profiles.toml")._load_commands("normal")
    assert all(not cmd.startswith("uv run ") or cmd.startswith("uv run --locked ") for cmd in commands)
    assert any("pip-audit --locked ." in cmd for cmd in commands)

def test_fast_profile_splits_devfabric_and_engine_suites():
    root = Path(__file__).resolve().parents[2]
    commands = Verifier(root / 'devfabric/verification/profiles.toml')._load_commands('fast')
    assert commands == (
        'python -m metaengine.devfabric.pytest_runner -q tests/devfabric',
        'python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric',
    )


def test_verifier_capture_is_not_held_open_by_descendant_process(tmp_path):
    import time

    command = (
        "python -c 'import subprocess,sys; "
        "subprocess.Popen([sys.executable,\"-c\",\"import time; time.sleep(2)\"]); "
        "print(\"parent-done\")'"
    )
    baseline = _profile(tmp_path, "baseline", "python -c 'print(\"parent-done\")'")
    started = time.monotonic()
    assert Verifier(baseline).run("baseline", tmp_path).verdict is Verdict.PASS
    baseline_elapsed = time.monotonic() - started

    profile = _profile(tmp_path, "descendant", command)
    started = time.monotonic()
    receipt = Verifier(profile).run("descendant", tmp_path)
    descendant_elapsed = time.monotonic() - started
    assert receipt.verdict is Verdict.PASS
    assert descendant_elapsed - baseline_elapsed < 1.0


def test_verifier_disables_ambient_pytest_plugin_autoload(tmp_path):
    command = (
        "python -c 'import os,sys; "
        "sys.exit(0 if os.environ.get(\"PYTEST_DISABLE_PLUGIN_AUTOLOAD\") == \"1\" else 9)'"
    )
    profile = _profile(tmp_path, "isolated_pytest_env", command)
    receipt = Verifier(profile).run("isolated_pytest_env", tmp_path)
    assert receipt.verdict is Verdict.PASS
    assert receipt.exit_statuses == (0,)


def test_pytest_runner_force_exit_hook_uses_session_exit_status(monkeypatch):
    from metaengine.devfabric import pytest_runner

    seen = []

    def fake_exit(code):
        seen.append(code)
        raise RuntimeError("exit intercepted")

    monkeypatch.setattr(pytest_runner.os, "_exit", fake_exit)
    hook = pytest_runner._ExitAfterSession()
    import pytest

    with pytest.raises(RuntimeError, match="exit intercepted"):
        hook.pytest_sessionfinish(None, 7)
    assert seen == [7]


def test_pytest_runner_exits_after_last_test_teardown(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from metaengine.devfabric import pytest_runner

    seen = []

    def fake_exit(code):
        seen.append(code)
        raise RuntimeError("exit intercepted")

    monkeypatch.setattr(pytest_runner.os, "_exit", fake_exit)
    hook = pytest_runner._ExitAfterLastTest()
    hook.pytest_collection_finish(SimpleNamespace(items=[object(), object()]))
    hook.pytest_runtest_logreport(SimpleNamespace(when="call", failed=False))
    hook.pytest_runtest_logreport(SimpleNamespace(when="teardown", failed=False))
    assert seen == []
    hook.pytest_runtest_logreport(SimpleNamespace(when="call", failed=False))
    with pytest.raises(RuntimeError, match="exit intercepted"):
        hook.pytest_runtest_logreport(SimpleNamespace(when="teardown", failed=False))
    assert seen == [0]


def test_pytest_runner_last_test_exit_preserves_failure(monkeypatch):
    from types import SimpleNamespace
    from metaengine.devfabric import pytest_runner

    seen = []
    monkeypatch.setattr(pytest_runner.os, "_exit", lambda code: seen.append(code))
    hook = pytest_runner._ExitAfterLastTest()
    hook.pytest_collection_finish(SimpleNamespace(items=[object()]))
    hook.pytest_runtest_logreport(SimpleNamespace(when="call", failed=True))
    hook.pytest_runtest_logreport(SimpleNamespace(when="teardown", failed=False))
    assert seen == [1]
