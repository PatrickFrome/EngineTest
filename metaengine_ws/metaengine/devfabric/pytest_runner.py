from __future__ import annotations

import os
import sys


class _ExitAfterSession:
    """Terminate the dedicated verifier runner once pytest has an exit status.

    The process exists solely to execute one deterministic pytest gate. Some host
    environments install teardown hooks that can keep Python alive after pytest
    has completed every test. Exiting at sessionfinish preserves pytest's status
    while preventing ambient teardown from holding the gate indefinitely.
    """

    def pytest_sessionfinish(self, session, exitstatus) -> None:  # pragma: no cover - process exits in integration use
        del session
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(exitstatus))


class _ExitAfterLastTest:
    """Exit after the final collected test teardown, before host session teardown."""

    def __init__(self) -> None:
        self.total = 0
        self.completed = 0
        self.failed = False

    def pytest_collectreport(self, report) -> None:
        if getattr(report, "failed", False):
            self.failed = True

    def pytest_collection_finish(self, session) -> None:
        self.total = len(session.items)

    def pytest_runtest_logreport(self, report) -> None:
        if getattr(report, "failed", False):
            self.failed = True
        if getattr(report, "when", None) != "teardown":
            return
        self.completed += 1
        if self.total and self.completed >= self.total:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1 if self.failed else 0)


def main(argv: list[str] | None = None) -> int:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    import pytest

    args = list(sys.argv[1:] if argv is None else argv)
    code = int(pytest.main(args, plugins=[_ExitAfterLastTest(), _ExitAfterSession()]))
    # Defensive fallback if a future pytest version does not call sessionfinish.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
