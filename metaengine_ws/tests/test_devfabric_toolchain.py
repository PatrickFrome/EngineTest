from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_toolchain_lock_declares_required_commands():
    lock = json.loads((ROOT / "devfabric/TOOLCHAIN.lock").read_text())
    for name in ("pytest", "hypothesis", "ruff", "mypy", "pip-audit", "semgrep"):
        assert name in lock["required_tools"]
    assert lock["python_floor"] == "3.11"
