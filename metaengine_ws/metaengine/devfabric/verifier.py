from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .codec import canonical_digest
from .models import Verdict, VerificationReceipt


@dataclass(frozen=True)
class CommandEvidence:
    command: str
    cwd: str
    exit_code: int
    wall_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    tool_version: str

    @property
    def evidence_hash(self) -> str:
        return canonical_digest(self)


class Verifier:
    def __init__(self, profiles_path: str | Path):
        self.profiles_path = Path(profiles_path)
        self.last_evidence: tuple[CommandEvidence, ...] = ()

    def _load_commands(self, profile_name: str) -> tuple[str, ...]:
        data = tomllib.loads(self.profiles_path.read_text())
        profiles = data.get("profiles", {})
        if profile_name not in profiles:
            raise KeyError(f"unknown verifier profile: {profile_name}")
        return tuple(str(x) for x in profiles[profile_name].get("commands", ()))

    @staticmethod
    def _tool_version(argv: list[str], cwd: Path) -> str:
        if not argv:
            return "unknown"
        executable = argv[0]
        try:
            cp = subprocess.run(
                [executable, "--version"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return "unavailable"
        text = (cp.stdout or cp.stderr).strip().splitlines()
        return text[0][:200] if text else f"exit={cp.returncode}"

    @staticmethod
    def _candidate_hash(candidate_dir: Path) -> str:
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=candidate_dir,
                capture_output=True,
                check=True,
            ).stdout.strip()
            diff = subprocess.run(
                ["git", "diff", "--binary", "HEAD", "--", "."],
                cwd=candidate_dir,
                capture_output=True,
                check=True,
            ).stdout
            return hashlib.sha256(head + b"\0" + diff).hexdigest()
        except subprocess.SubprocessError:
            return canonical_digest({"directory_name": candidate_dir.name})

    @staticmethod
    def _is_security_feed_failure(command: str, stderr: str, stdout: str) -> bool:
        text = f"{command}\n{stdout}\n{stderr}".lower()
        if "pip-audit" not in text:
            return False
        network_markers = (
            "temporary failure in name resolution",
            "name or service not known",
            "connection error",
            "connection refused",
            "network is unreachable",
            "failed to establish a new connection",
            "dns",
        )
        return any(marker in text for marker in network_markers)

    def run(self, profile_name: str, candidate_dir: str | Path) -> VerificationReceipt:
        cwd = Path(candidate_dir).resolve()
        commands = self._load_commands(profile_name)
        evidence: list[CommandEvidence] = []
        statuses: list[int] = []
        verdict = Verdict.PASS

        for command in commands:
            argv = shlex.split(command)
            started = time.monotonic()
            try:
                # File-backed capture avoids a pipe-lifetime deadlock when a
                # verified command spawns descendants that inherit stdout/stderr.
                # We only wait for the direct command; descendants cannot keep a
                # TemporaryFile at EOF-open the way they can keep a PIPE open.
                with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
                    env = dict(os.environ)
                    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
                    cp = subprocess.run(
                        argv,
                        cwd=cwd,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        env=env,
                        check=False,
                    )
                    exit_code = int(cp.returncode)
                    stdout_file.seek(0)
                    stderr_file.seek(0)
                    stdout = stdout_file.read().decode("utf-8", errors="replace")
                    stderr = stderr_file.read().decode("utf-8", errors="replace")
            except OSError as exc:
                exit_code = 127
                stdout = ""
                stderr = str(exc)
            elapsed = time.monotonic() - started
            statuses.append(exit_code)
            item = CommandEvidence(
                command=command,
                cwd=".",
                exit_code=exit_code,
                wall_seconds=round(elapsed, 6),
                stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
                stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest(),
                tool_version=self._tool_version(argv, cwd),
            )
            evidence.append(item)
            if exit_code != 0:
                if self._is_security_feed_failure(command, stderr, stdout):
                    if verdict is Verdict.PASS:
                        verdict = Verdict.INCONCLUSIVE_SECURITY_FEED
                else:
                    verdict = Verdict.FAIL

        self.last_evidence = tuple(evidence)
        return VerificationReceipt.create(
            candidate_hash=self._candidate_hash(cwd),
            verifier_id="metaengine-devfabric-verifier",
            verifier_version="1",
            commands=commands,
            exit_statuses=statuses,
            verdict=verdict,
            evidence_hashes=(item.evidence_hash for item in evidence),
        )
