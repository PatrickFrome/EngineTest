from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class WorktreeBaseMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateWorld:
    task_id: str
    candidate_id: str
    path: Path
    base_commit: str


@dataclass(frozen=True)
class PatchBundle:
    patch_hash: str
    patch_bytes: bytes
    changed_paths: tuple[str, ...]


class WorktreeManager:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self.worktree_root = self.repo_root / "devfabric" / "state" / "worktrees"
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_id(value: str) -> str:
        if not _SAFE_ID.fullmatch(value):
            raise ValueError(f"unsafe worktree id: {value!r}")
        return value

    def _run(self, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def create(self, task_id: str, candidate_id: str) -> CandidateWorld:
        task_id = self._validate_id(task_id)
        candidate_id = self._validate_id(candidate_id)
        path = self.worktree_root / f"{task_id}--{candidate_id}"
        if path.exists():
            raise FileExistsError(path)
        base_commit = self._run("rev-parse", "HEAD").stdout.decode().strip()
        self._run("worktree", "add", "--detach", str(path), base_commit)
        return CandidateWorld(task_id=task_id, candidate_id=candidate_id, path=path, base_commit=base_commit)

    def verify_base(self, world: CandidateWorld, expected_commit: str) -> None:
        actual = self._run("rev-parse", "HEAD", cwd=world.path).stdout.decode().strip()
        if actual != expected_commit:
            raise WorktreeBaseMismatch(f"expected {expected_commit}, got {actual}")

    def collect_patch(self, world: CandidateWorld) -> PatchBundle:
        self.verify_base(world, world.base_commit)
        # Intent-to-add makes untracked files visible to git diff without committing them.
        self._run("add", "-N", "--", ".", cwd=world.path)
        status = self._run("status", "--porcelain=v1", "-z", cwd=world.path).stdout
        changed: list[str] = []
        for record in status.split(b"\0"):
            if not record:
                continue
            text = record.decode("utf-8", errors="surrogateescape")
            path = text[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            changed.append(path)
        patch = self._run("diff", "--binary", "--no-ext-diff", "HEAD", "--", ".", cwd=world.path).stdout
        return PatchBundle(
            patch_hash=hashlib.sha256(patch).hexdigest(),
            patch_bytes=patch,
            changed_paths=tuple(sorted(set(changed))),
        )

    def remove(self, world: CandidateWorld) -> None:
        self._run("worktree", "remove", "--force", str(world.path), check=False)
        self._run("worktree", "prune", check=False)
