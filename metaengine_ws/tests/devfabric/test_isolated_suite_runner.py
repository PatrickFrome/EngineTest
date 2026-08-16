from pathlib import Path

from metaengine.devfabric.isolated_suite_runner import discover_pytest_groups


ROOT = Path(__file__).resolve().parents[2]


def test_discover_pytest_groups_covers_devfabric_exactly_once() -> None:
    groups = discover_pytest_groups(ROOT / "tests" / "devfabric")
    flattened = [path.name for group in groups for path in group]
    expected = sorted(path.name for path in (ROOT / "tests" / "devfabric").glob("test_*.py"))
    assert sorted(flattened) == expected
    assert len(flattened) == len(set(flattened))


def test_sensitive_verifier_worktree_modules_are_isolated_from_bulk_group() -> None:
    groups = discover_pytest_groups(ROOT / "tests" / "devfabric")
    assert len(groups) == 2
    sensitive = {path.name for path in groups[0]}
    assert sensitive == {
        "test_swarm.py",
        "test_verifier.py",
        "test_workspace_backends.py",
        "test_worktrees.py",
    }
    assert not sensitive.intersection(path.name for path in groups[1])
