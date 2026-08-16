from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


_SENSITIVE_MODULES = frozenset(
    {
        "test_swarm.py",
        "test_verifier.py",
        "test_workspace_backends.py",
        "test_worktrees.py",
    }
)


def discover_pytest_groups(test_dir: str | Path) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Return deterministic pytest groups that cover test_*.py exactly once.

    The verifier/worktree-heavy modules are deliberately isolated from the bulk
    DevFabric suite.  Those modules are individually correct, but running them
    in the same long-lived pytest process as the rest of DevFabric has exposed
    host-specific teardown interactions.  Keeping exactly two child pytest
    processes preserves full coverage while keeping the parent verifier stable.
    """

    root = Path(test_dir).resolve()
    discovered = tuple(sorted(root.glob("test_*.py"), key=lambda path: path.name))
    if not discovered:
        raise ValueError(f"no test_*.py modules found in {root}")

    sensitive = tuple(path for path in discovered if path.name in _SENSITIVE_MODULES)
    bulk = tuple(path for path in discovered if path.name not in _SENSITIVE_MODULES)

    missing_sensitive = sorted(_SENSITIVE_MODULES.difference(path.name for path in sensitive))
    if missing_sensitive:
        raise ValueError(f"missing sensitive DevFabric tests: {missing_sensitive}")
    if not bulk:
        raise ValueError("bulk DevFabric pytest group is empty")
    return sensitive, bulk


def run_isolated_suite(test_dir: str | Path, *, timeout_seconds: float = 180.0) -> int:
    groups = discover_pytest_groups(test_dir)
    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    for index, group in enumerate(groups, start=1):
        print(f"DEVFABRIC_GROUP_{index}_START files={len(group)}", flush=True)
        argv = [
            sys.executable,
            "-m",
            "metaengine.devfabric.pytest_runner",
            "-q",
            *(str(path) for path in group),
        ]
        try:
            completed = subprocess.run(
                argv,
                env=env,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            print(f"DEVFABRIC_GROUP_{index}_TIMEOUT", file=sys.stderr, flush=True)
            return 124
        exit_code = int(completed.returncode)
        print(f"DEVFABRIC_GROUP_{index}_END exit={exit_code}", flush=True)
        if exit_code != 0:
            return exit_code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metaengine-devfabric-isolated-suite")
    parser.add_argument("test_dir")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_isolated_suite(args.test_dir, timeout_seconds=args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
