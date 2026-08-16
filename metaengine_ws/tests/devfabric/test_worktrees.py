from pathlib import Path

import pytest

from metaengine.devfabric.worktrees import WorktreeBaseMismatch, WorktreeManager

ROOT = Path(__file__).resolve().parents[2]


def test_candidate_world_is_isolated_and_patch_is_hashable():
    mgr = WorktreeManager(ROOT)
    world = mgr.create("task-1", "cand-1")
    try:
        (world.path / "candidate_only.txt").write_text("isolated\n")
        assert not (ROOT / "candidate_only.txt").exists()
        patch = mgr.collect_patch(world)
        assert "candidate_only.txt" in patch.changed_paths
        assert len(patch.patch_hash) == 64
        assert b"candidate_only.txt" in patch.patch_bytes
    finally:
        mgr.remove(world)


def test_base_mismatch_and_unsafe_ids_are_rejected():
    mgr = WorktreeManager(ROOT)
    with pytest.raises(ValueError):
        mgr.create("../task", "cand")
    world = mgr.create("task-2", "cand-2")
    try:
        with pytest.raises(WorktreeBaseMismatch):
            mgr.verify_base(world, "0" * 40)
    finally:
        mgr.remove(world)
