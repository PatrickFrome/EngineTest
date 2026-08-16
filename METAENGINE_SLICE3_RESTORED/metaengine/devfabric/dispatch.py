from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .models import CandidateReceipt, TaskEnvelope
from .journal import Journal
from .providers.base import ProviderAdapter
from .worktrees import WorktreeManager

_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class DispatchBatch:
    receipts: tuple[CandidateReceipt, ...]
    errors: tuple[str, ...]


def _candidate_id(provider_id: str) -> str:
    cleaned = _UNSAFE_ID.sub("-", provider_id).strip(".-")
    return (cleaned or "candidate")[:80]


class CompetitiveDispatcher:
    """Run providers concurrently in isolated Git candidate worktrees.

    Worktree creation/removal is serialized because Git mutates shared
    repository worktree metadata. Provider execution remains parallel.
    """

    def __init__(self, worktrees: WorktreeManager, *, max_parallel: int = 4, journal: Journal | None = None):
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1")
        self.worktrees = worktrees
        self.max_parallel = max_parallel
        self._git_lock = threading.Lock()
        self.journal = journal

    def _run_one(self, task: TaskEnvelope, provider: ProviderAdapter) -> CandidateReceipt:
        with self._git_lock:
            world = self.worktrees.create(task.task_id, _candidate_id(provider.descriptor.provider_id))
        try:
            return provider.execute(task, world.path)
        finally:
            with self._git_lock:
                self.worktrees.remove(world)

    def dispatch(self, task: TaskEnvelope, providers: list[ProviderAdapter] | tuple[ProviderAdapter, ...]) -> DispatchBatch:
        receipts: list[CandidateReceipt] = []
        errors: list[str] = []
        if self.journal is not None:
            self.journal.append("TASK_DISPATCHED", task.task_id, {"task_hash": task.task_hash, "providers": tuple(sorted(p.descriptor.provider_id for p in providers))})
        if not providers:
            return DispatchBatch((), ())

        workers = min(self.max_parallel, len(providers))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="metaengine-candidate") as pool:
            futures = {pool.submit(self._run_one, task, provider): provider for provider in providers}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    receipts.append(future.result())
                except Exception as exc:  # receipt is evidence; preserve provider-specific failure
                    errors.append(f"{provider.descriptor.provider_id}:{type(exc).__name__}:{exc}")

        receipts.sort(key=lambda receipt: (receipt.provider_id, receipt.candidate_hash))
        errors.sort()
        if self.journal is not None:
            for receipt in receipts:
                self.journal.append("CANDIDATE_RECEIVED", receipt.candidate_hash, receipt)
            for error in errors:
                self.journal.append("CANDIDATE_ERROR", task.task_id, {"error": error})
        return DispatchBatch(tuple(receipts), tuple(errors))
