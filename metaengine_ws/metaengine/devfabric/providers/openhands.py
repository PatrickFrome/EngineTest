from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from ..models import CandidateReceipt, TaskEnvelope
from .base import ProviderDescriptor, HealthSnapshot, QuotaSnapshot
from .common import receipt_from_git, task_prompt


class OpenHandsAdapter:
    def __init__(
        self,
        *,
        model: str = "ollama/qwen3-coder",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 900.0,
    ):
        if not (base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost") or base_url.startswith("http://[::1]")):
            raise ValueError("OpenHands local profile requires loopback Ollama")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.descriptor = ProviderDescriptor(
            "openhands-ollama-local",
            ("CODE_GENERATOR", "CODE_REVIEWER"),
            False,
            "LOCAL_FREE",
            effectiveness=0.55,
            independence_group="openhands",
        )

    def health_check(self) -> HealthSnapshot:
        return HealthSnapshot(shutil.which("openhands") is not None, detail="openhands-headless-cli")

    def quota_snapshot(self) -> QuotaSnapshot:
        return QuotaSnapshot(True, None, False, "self-hosted local model")

    def execute(self, task: TaskEnvelope, workdir: Path) -> CandidateReceipt:
        env = os.environ.copy()
        env.update(
            {
                "OPENHANDS_SUPPRESS_BANNER": "1",
                "LLM_MODEL": self.model,
                "LLM_BASE_URL": self.base_url,
                # OpenHands/LiteLLM requires a non-empty value for some local providers.
                # This sentinel is not a credential and never leaves the local process.
                "LLM_API_KEY": "ollama-local",
            }
        )
        argv = [
            "openhands",
            "--headless",
            "--json",
            "--override-with-envs",
            "--exit-without-confirmation",
            "-t",
            task_prompt(task),
        ]
        try:
            cp = subprocess.run(
                argv,
                cwd=workdir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
                "model": self.model,
                "mode": "headless-json",
            },
        )

    def cancel(self, task_id: str) -> bool:
        return False
