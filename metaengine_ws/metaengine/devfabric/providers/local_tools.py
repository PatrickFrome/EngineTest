from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolState:
    name: str
    available: bool
    status: str
    path: str | None = None
    version: str = ""
    detail: str = ""


_VERSION_ARGS: dict[str, tuple[str, ...]] = {
    "coder": ("version",),
    "devpod": ("version",),
    "openhands": ("--version",),
    "agent-canvas": ("--version",),
    "ollama": ("--version",),
    "opencode": ("--version",),
}


def _capture_version(path: str, args: tuple[str, ...], timeout_seconds: float) -> tuple[str, str]:
    try:
        cp = subprocess.run(
            [path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", str(exc)
    text = (cp.stdout or cp.stderr).strip().splitlines()
    version = text[0][:240] if text else f"exit={cp.returncode}"
    detail = "" if cp.returncode == 0 else f"version_exit={cp.returncode}"
    return version, detail


def discover_ai_swarm_tools(*, timeout_seconds: float = 3.0) -> dict[str, ToolState]:
    result: dict[str, ToolState] = {}
    for name, version_args in _VERSION_ARGS.items():
        path = shutil.which(name)
        if path is None:
            result[name] = ToolState(name=name, available=False, status="UNAVAILABLE")
            continue
        version, detail = _capture_version(path, version_args, timeout_seconds)
        result[name] = ToolState(
            name=name,
            available=True,
            status="AVAILABLE",
            path=str(Path(path)),
            version=version,
            detail=detail,
        )
    return result
