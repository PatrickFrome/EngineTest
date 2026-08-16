from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from .providers.local_tools import discover_ai_swarm_tools as discover_local_tools


@dataclass(frozen=True)
class DoctorCheck:
    code: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class DoctorReport:
    profile: str
    status: str
    requires_cloud_credentials: bool
    checks: tuple[DoctorCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "status": self.status,
            "requires_cloud_credentials": self.requires_cloud_credentials,
            "checks": [asdict(c) for c in self.checks],
        }


class Doctor:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _profile(self, name: str) -> dict[str, object]:
        path = self.root / "devfabric" / "profiles" / f"{name}.toml"
        data = tomllib.loads(path.read_text())
        return data

    @staticmethod
    def _version_ok() -> bool:
        return sys.version_info >= (3, 11)

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=False
        )


    def inspect_ai_swarm(self) -> DoctorReport:
        tools = discover_local_tools()
        checks = tuple(
            DoctorCheck(
                code=f"AI_TOOL_{name.upper().replace('-', '_')}",
                ok=state.available,
                detail=(f"{state.path or ''} {state.version or ''}".strip() if state.available else state.status),
                required=False,
            )
            for name, state in sorted(tools.items())
        )
        available = {name for name, state in tools.items() if state.available}
        local_agent_ready = "ollama" in available and bool({"opencode", "openhands"} & available)
        if local_agent_ready:
            status = "READY"
        elif available:
            status = "PARTIAL"
        else:
            status = "OPTIONAL_PROVIDER_UNAVAILABLE"
        return DoctorReport(
            profile="ai-swarm",
            status=status,
            requires_cloud_credentials=False,
            checks=checks,
        )

    def inspect(self, profile: str = "offline") -> DoctorReport:
        pdata = self._profile(profile)
        requires_cloud = bool(pdata.get("require_cloud_credentials", False))
        checks: list[DoctorCheck] = []

        checks.append(
            DoctorCheck(
                "PYTHON_FLOOR",
                self._version_ok(),
                f"runtime={sys.version.split()[0]} required=>=3.11",
            )
        )
        uv = shutil.which("uv")
        checks.append(DoctorCheck("UV_AVAILABLE", uv is not None, uv or "uv not found"))
        git = shutil.which("git")
        checks.append(DoctorCheck("GIT_AVAILABLE", git is not None, git or "git not found"))

        binding_path = self.root / "devfabric" / "source_binding.json"
        try:
            binding = json.loads(binding_path.read_text())
            binding_ok = (
                binding.get("artifact_sha256")
                == "8e7a9f483192180b5f870e5301253cfe2266f5392754cbc680854b505f8a54b0"
                and binding.get("release_version") == "2.3.0-alpha.1"
            )
            detail = f"artifact_sha256={binding.get('artifact_sha256', '')}"
        except Exception as exc:
            binding_ok = False
            detail = f"invalid source binding: {exc}"
        checks.append(DoctorCheck("SOURCE_BINDING", binding_ok, detail))

        git_probe = self._git("rev-parse", "--is-inside-work-tree")
        checks.append(
            DoctorCheck(
                "GIT_BASELINE",
                git_probe.returncode == 0 and git_probe.stdout.strip() == "true",
                git_probe.stdout.strip() or git_probe.stderr.strip() or "not a git worktree",
            )
        )

        lock = self.root / "uv.lock"
        checks.append(
            DoctorCheck(
                "UV_LOCK",
                lock.is_file(),
                "uv.lock present" if lock.is_file() else "uv.lock missing (dependency resolution incomplete)",
            )
        )

        audit_lock = self.root / "pylock.toml"
        checks.append(
            DoctorCheck(
                "PYLOCK_AUDIT_EXPORT",
                audit_lock.is_file(),
                "pylock.toml present" if audit_lock.is_file() else "pylock.toml missing (export from uv.lock required for locked audit)",
            )
        )

        toolchain_path = self.root / "devfabric" / "TOOLCHAIN.lock"
        unresolved: list[str] = []
        try:
            toolchain = json.loads(toolchain_path.read_text())
            for name, value in toolchain.get("required_tools", {}).items():
                if isinstance(value, dict) and value.get("status") == "UNRESOLVED_OFFLINE":
                    unresolved.append(name)
            tool_ok = toolchain.get("resolution_status") != "UNRESOLVED_OFFLINE" and not unresolved
            tool_detail = "resolved" if tool_ok else "unresolved=" + ",".join(sorted(unresolved))
        except Exception as exc:
            tool_ok = False
            tool_detail = f"invalid TOOLCHAIN.lock: {exc}"
        checks.append(DoctorCheck("TOOLCHAIN_RESOLVED", tool_ok, tool_detail))

        state_dir = self.root / "devfabric" / "state"
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            fd, probe_path = tempfile.mkstemp(prefix="doctor-", dir=state_dir)
            os.close(fd)
            Path(probe_path).unlink()
            writable = True
            writable_detail = str(state_dir)
        except OSError as exc:
            writable = False
            writable_detail = str(exc)
        checks.append(DoctorCheck("LOCAL_STATE_WRITABLE", writable, writable_detail))

        unstaged = self._git("diff-files", "--quiet", "--", "lineages")
        staged = self._git("diff-index", "--quiet", "HEAD", "--cached", "--", "lineages")
        lock_path = self.root / "devfabric" / "LINEAGE_LOCK_SHA256.txt"
        expected_count = sum(1 for line in lock_path.read_text().splitlines() if line.strip()) if lock_path.is_file() else -1
        actual_count = sum(1 for path in (self.root / "lineages").rglob("*") if path.is_file())
        lineage_ok = unstaged.returncode == 0 and staged.returncode == 0 and actual_count == expected_count
        lineage_detail = (
            f"tracked_clean={unstaged.returncode == 0 and staged.returncode == 0}; "
            f"files={actual_count}; lock_entries={expected_count}"
        )
        checks.append(DoctorCheck("LINEAGE_UNMODIFIED", lineage_ok, lineage_detail))

        # OFFLINE deliberately performs zero cloud credential probes.
        if requires_cloud:
            checks.append(
                DoctorCheck(
                    "CLOUD_CREDENTIAL_POLICY",
                    False,
                    "cloud credential checks belong to Stage C adapters, not Stage A doctor",
                    required=False,
                )
            )

        blocked = any(c.required and not c.ok for c in checks)
        return DoctorReport(
            profile=profile,
            status="BLOCKED" if blocked else "PASS",
            requires_cloud_credentials=requires_cloud,
            checks=tuple(checks),
        )
