from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from ..models import CandidateReceipt, PrivacyClass, TaskEnvelope
from ..policy import zero_spend_allowed
from .base import HealthSnapshot, ProviderDescriptor, QuotaSnapshot
from .common import receipt_from_git, task_prompt
from .external import ConnectorPolicyError


Runner = Callable[..., Any]
QuotaReader = Callable[[], Mapping[str, Any]]


class AntigravityAdapter:
    def __init__(
        self,
        *,
        settings_path: str | Path,
        effective_settings_path: str | Path | None = None,
        binary: str = "agy",
        quota_reader: QuotaReader | None = None,
        runner: Runner = subprocess.run,
        timeout_seconds: float = 900.0,
    ):
        self.settings_path = Path(settings_path)
        self.effective_settings_path = Path(effective_settings_path) if effective_settings_path else Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
        self.binary = str(binary)
        self.quota_reader = quota_reader
        self.runner = runner
        self.timeout_seconds = float(timeout_seconds)
        self.descriptor = ProviderDescriptor(
            provider_id="antigravity-zero-spend",
            capabilities=("CODE_GENERATOR", "CODE_REVIEWER"),
            external=True,
            billing_mode="PAID_CAPABLE",
            effectiveness=0.6,
            independence_group="antigravity",
        )

    @staticmethod
    def _load_settings(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConnectorPolicyError("ANTIGRAVITY_SETTINGS_UNVERIFIED") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ConnectorPolicyError("ANTIGRAVITY_SETTINGS_INVALID") from exc
        if not isinstance(data, dict):
            raise ConnectorPolicyError("ANTIGRAVITY_SETTINGS_INVALID")
        return data

    def _validate_effective_settings(self) -> dict[str, Any]:
        data = self._load_settings(self.effective_settings_path)
        if data.get("useG1Credits") is not False:
            raise ConnectorPolicyError("PAID_FALLBACK_NOT_DISABLED")
        if data.get("allowNonWorkspaceAccess") is not False:
            raise ConnectorPolicyError("NON_WORKSPACE_ACCESS_ENABLED")
        if data.get("enableTerminalSandbox") is not True:
            raise ConnectorPolicyError("SANDBOX_REQUIRED")
        if data.get("toolPermission") != "proceed-in-sandbox":
            raise ConnectorPolicyError("SAFE_TOOL_PERMISSION_REQUIRED")
        return data

    def health_check(self) -> HealthSnapshot:
        binary_path = shutil.which(self.binary) if not Path(self.binary).is_absolute() else self.binary
        if not binary_path or not Path(binary_path).exists():
            return HealthSnapshot(False, detail="agy-cli-unavailable")
        try:
            self._validate_effective_settings()
        except ConnectorPolicyError as exc:
            return HealthSnapshot(False, detail=exc.reason_code)
        try:
            cp = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return HealthSnapshot(False, detail=type(exc).__name__)
        detail = (cp.stdout or cp.stderr or "agy").strip().splitlines()[0][:160]
        return HealthSnapshot(cp.returncode == 0, detail=detail)

    def quota_snapshot(self) -> QuotaSnapshot:
        try:
            settings = self._validate_effective_settings()
        except ConnectorPolicyError as exc:
            return QuotaSnapshot(False, None, True, exc.reason_code)
        paid_fallback = bool(settings.get("useG1Credits"))
        if self.quota_reader is None:
            return QuotaSnapshot(False, None, paid_fallback, "machine-readable quota unavailable")
        try:
            result = dict(self.quota_reader())
        except Exception as exc:
            return QuotaSnapshot(False, None, paid_fallback, f"quota-read-{type(exc).__name__}")
        return QuotaSnapshot(
            known=bool(result.get("known")),
            free_remaining=int(result["free_remaining"]) if result.get("free_remaining") is not None else None,
            paid_fallback_enabled=paid_fallback or bool(result.get("paid_fallback_enabled")),
            detail=str(result.get("detail") or ""),
        )

    def build_argv(self, task: TaskEnvelope, workdir: str | Path) -> list[str]:
        prompt = task_prompt(task)
        return [
            self.binary,
            "-p",
            prompt,
            "--cwd",
            str(Path(workdir)),
            "--output-format",
            "json",
            "--mode=accept-edits",
            "--sandbox",
        ]

    def execute(self, task: TaskEnvelope, workdir: Path) -> CandidateReceipt:
        if task.privacy_class not in (PrivacyClass.P0, PrivacyClass.P1):
            raise ConnectorPolicyError("PRIVACY_CLASS_BLOCKED")
        self._validate_effective_settings()
        quota = self.quota_snapshot()
        allowed, reason = zero_spend_allowed(task, self.descriptor, quota)
        if not allowed:
            raise ConnectorPolicyError(reason or "ZERO_SPEND_BLOCKED")
        argv = self.build_argv(task, workdir)
        if any(flag in argv for flag in ("--dangerously-skip-permissions", "--yolo")):
            raise ConnectorPolicyError("DANGEROUS_PERMISSION_FLAG_FORBIDDEN")
        try:
            cp = self.runner(
                argv,
                cwd=Path(workdir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            code = int(cp.returncode)
            stdout = cp.stdout or ""
            stderr = cp.stderr or ""
        except subprocess.TimeoutExpired as exc:
            code = 124
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return receipt_from_git(
            task=task,
            provider_id=self.descriptor.provider_id,
            workdir=Path(workdir),
            metadata={
                "exit_code": str(code),
                "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
                "mode": "print-json-sandbox",
            },
        )

    def cancel(self, task_id: str) -> bool:
        del task_id
        return False
