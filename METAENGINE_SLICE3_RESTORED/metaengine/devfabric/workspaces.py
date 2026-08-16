from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .models import TaskEnvelope
from .worktrees import CandidateWorld


class WorkspaceIsolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceHandle:
    backend_id: str
    task_id: str
    candidate_id: str
    path: Path
    external: bool = False
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    wall_seconds: float
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str


class WorkspaceBackend(Protocol):
    backend_id: str

    def prepare(self, task: TaskEnvelope, source_world: CandidateWorld) -> WorkspaceHandle: ...
    def run(
        self,
        handle: WorkspaceHandle,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        timeout_seconds: float = 600.0,
    ) -> ExecutionResult: ...
    def cleanup(self, handle: WorkspaceHandle) -> None: ...


class LocalWorkspaceBackend:
    backend_id = "local"

    def __init__(self, *, controller_root: str | Path):
        self.controller_root = Path(controller_root).resolve()

    def prepare(self, task: TaskEnvelope, source_world: CandidateWorld) -> WorkspaceHandle:
        world_path = source_world.path.resolve()
        if world_path == self.controller_root:
            raise WorkspaceIsolationError("candidate world must not be the controlling checkout")
        if not world_path.exists() or not world_path.is_dir():
            raise WorkspaceIsolationError(f"candidate world does not exist: {world_path}")
        return WorkspaceHandle(
            backend_id=self.backend_id,
            task_id=task.task_id,
            candidate_id=source_world.candidate_id,
            path=world_path,
            external=False,
        )

    def run(
        self,
        handle: WorkspaceHandle,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        timeout_seconds: float = 600.0,
    ) -> ExecutionResult:
        if handle.path.resolve() == self.controller_root:
            raise WorkspaceIsolationError("refusing to execute in controlling checkout")
        child_env = os.environ.copy()
        if env:
            child_env.update({str(k): str(v) for k, v in env.items()})
        started = time.monotonic()
        try:
            cp = subprocess.run(
                list(argv),
                cwd=handle.path,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code = int(cp.returncode)
            stdout = cp.stdout or ""
            stderr = cp.stderr or ""
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            stderr = f"{stderr}\nTIMEOUT".strip()
        elapsed = round(time.monotonic() - started, 6)
        return ExecutionResult(
            exit_code=exit_code,
            wall_seconds=elapsed,
            stdout=stdout,
            stderr=stderr,
            stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest(),
        )

    def cleanup(self, handle: WorkspaceHandle) -> None:
        return None
