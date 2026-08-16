"""ray_backend.py — Optional Ray-based distributed compute backend for
MetaEngine benchmark runner.

When Ray is installed and a cluster is available, the benchmark runner can
distribute tasks across multiple workers (potentially on different machines).

Usage:
  # Local Ray cluster (single machine, multiple processes)
  ray start --head --num-cpus=4

  # Then run benchmark with --backend ray
  python3 scripts/run_massive_benchmark.py --backend ray --ray-address auto

  # Or connect to an existing cluster (e.g. on another machine)
  ray start --address='<head-node-ip>:6379' --num-cpus=4
  python3 scripts/run_massive_benchmark.py --backend ray --ray-address '<head>:6379'

This module is imported lazily — only when --backend ray is used. If Ray is
not installed, we fall back to the default ThreadPoolExecutor backend.

Free Ray cluster options:
  - Anyscale Community Cloud: 30 free CPU-hours/month, no credit card
    https://console.anyscale.com/
  - Local Ray cluster: just `ray start --head` on this machine
  - Ray on Kubernetes: scale to N pods
  - Ray on spot instances: ~$0.05/hour per worker

Free GPU via Ray + Colab:
  1. Run `ray start --head` on this machine
  2. Open Colab notebook, install ray, connect to our head node via ngrok
  3. Now Colab's T4 GPU is a Ray worker — GP fitting runs there
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Auto-discover ROOT
ROOT = Path(os.environ.get("ME_BENCHMARK_ROOT") or Path(__file__).resolve().parent.parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False


def is_available() -> bool:
    """Check if Ray is installed and importable."""
    return RAY_AVAILABLE


def init_cluster(address: str = "auto", num_cpus: int | None = None) -> bool:
    """Initialize Ray cluster connection. Returns True if connected."""
    if not RAY_AVAILABLE:
        return False
    try:
        if not ray.is_initialized():
            ray.init(
                address=address,
                num_cpus=num_cpus,
                ignore_reinit_error=True,
                include_dashboard=False,
                log_to_driver=False,
            )
        # Log cluster resources
        resources = ray.cluster_resources()
        print(f"[ray] Connected. Cluster resources: {resources}")
        return True
    except Exception as exc:
        print(f"[ray] init failed: {exc}")
        return False


# Decorate the remote task function
if RAY_AVAILABLE:
    @ray.remote
    def _remote_evaluate_task(task_dict: dict, run_dir_str: str,
                              use_zai: bool, max_workers: int) -> dict:
        """Ray remote function — runs on a Ray worker.

        Reconstructs the task + run_dir, calls the local evaluate_task,
        returns the result dict. Each worker uses 1 CPU by default
        (override with @ray.remote(num_cpus=2) for more).
        """
        # These imports happen on the worker, not the driver
        from scripts.run_massive_benchmark import (
            BenchTask,
            evaluate_task,
        )
        # Reconstruct the BenchTask from dict
        task = BenchTask(
            task_id=task_dict["task_id"],
            category=task_dict["category"],
            difficulty=task_dict["difficulty"],
            prompt=task_dict["prompt"],
            must_contain=tuple(task_dict.get("must_contain", ())),
            must_not_contain=tuple(task_dict.get("must_not_contain", ())),
            ground_truth=task_dict.get("ground_truth", ""),
            numeric_answer=task_dict.get("numeric_answer"),
        )
        run_dir = Path(run_dir_str)
        run_dir.mkdir(parents=True, exist_ok=True)
        # Each Ray worker has its own cached orchestrator (no sharing across workers)
        result, _ = evaluate_task(task, run_dir, use_zai=use_zai,
                                  max_workers=max_workers, _cached_orch=None)
        return result


def run_round_distributed(tasks: list, round_dir: Path, use_zai: bool,
                           max_workers: int) -> tuple[dict, list[dict]]:
    """Run a benchmark round distributed across Ray workers.

    Returns (summary_dict, per_task_results).
    """
    if not RAY_AVAILABLE:
        raise RuntimeError("Ray is not installed — cannot use distributed backend")

    round_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    n = len(tasks)

    print(f"[ray] submitting {n} tasks to Ray cluster")

    # Submit all tasks as Ray futures
    futures = []
    for task in tasks:
        task_dict = {
            "task_id": task.task_id,
            "category": task.category,
            "difficulty": task.difficulty,
            "prompt": task.prompt,
            "must_contain": task.must_contain,
            "must_not_contain": task.must_not_contain,
            "ground_truth": task.ground_truth,
            "numeric_answer": task.numeric_answer,
        }
        task_dir = round_dir / task.task_id
        fut = _remote_evaluate_task.remote(task_dict, str(task_dir), use_zai, max_workers)
        futures.append((task, fut))

    # Wait for all to complete, reporting progress
    per_task: list[dict] = []
    completed = 0
    for task, fut in futures:
        try:
            result = ray.get(fut, timeout=600)
            per_task.append(result)
        except Exception as exc:
            print(f"[ray] task {task.task_id} failed: {exc}")
            per_task.append({
                "task_id": task.task_id,
                "category": task.category,
                "difficulty": task.difficulty,
                "prompt": task.prompt,
                "ground_truth": task.ground_truth,
                "engine_answer": "",
                "engine_status": "RAY_ERROR",
                "runtime_sec": 0.0,
                "deterministic_score": {"scorer": "ray_error", "passed": False, "score": 0.0},
                "zai_judge": None,
                "dialectical_counts": {"total": 0},
                "dialectical_depth": 0.0,
                "constitution": {},
                "constitution_score": 0.0,
                "combined_score": 0.0,
                "fitness": 0.0,
                "error": str(exc)[:500],
            })
        completed += 1
        if completed % 5 == 0 or completed == n:
            elapsed = time.perf_counter() - t0
            rate = completed / elapsed if elapsed > 0 else 0
            print(f"[ray] {completed}/{n} done ({rate:.2f} tasks/sec, "
                  f"eta={(n-completed)/rate:.0f}s)" if rate > 0 else f"[ray] {completed}/{n} done")

    elapsed = time.perf_counter() - t0

    # Aggregate summary (same as local run_round)
    n = len(per_task)
    avg_fitness = sum(r["fitness"] for r in per_task) / n if n else 0.0
    avg_depth = sum(r["dialectical_depth"] for r in per_task) / n if n else 0.0
    avg_const = sum(r["constitution_score"] for r in per_task) / n if n else 0.0
    pass_rate = sum(1 for r in per_task if r["deterministic_score"]["passed"]) / n if n else 0.0
    total_rivals = sum(r["dialectical_counts"].get("RIVAL_FORK", 0) for r in per_task)
    total_sublations = sum(r["dialectical_counts"].get("SUBLATION_WITH_RESIDUE", 0) for r in per_task)

    summary = {
        "round_id": int(time.time()),
        "started_at": "2026-01-01T00:00:00Z",  # placeholder
        "tasks_total": n,
        "elapsed_sec": round(elapsed, 3),
        "avg_fitness": round(avg_fitness, 6),
        "avg_dialectical_depth": round(avg_depth, 6),
        "avg_constitution_score": round(avg_const, 6),
        "total_rival_forks": total_rivals,
        "total_sublations": total_sublations,
        "pass_rate": round(pass_rate, 4),
        "backend": "ray",
        "cluster_resources": dict(ray.cluster_resources()) if RAY_AVAILABLE else {},
    }
    return summary, per_task


def shutdown() -> None:
    """Shut down the Ray cluster if we started it."""
    if RAY_AVAILABLE and ray.is_initialized():
        try:
            ray.shutdown()
            print("[ray] cluster shut down")
        except Exception:
            pass
