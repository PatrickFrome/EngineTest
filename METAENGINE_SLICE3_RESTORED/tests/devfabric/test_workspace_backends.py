from pathlib import Path

import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.workspaces import LocalWorkspaceBackend, WorkspaceIsolationError
from metaengine.devfabric.worktrees import CandidateWorld


def _task() -> TaskEnvelope:
    return TaskEnvelope.create(
        source_checkpoint_id="cp-test",
        source_tree_hash="abc",
        objective="write marker",
        acceptance_tests=("marker exists",),
        allowed_paths=("marker.txt",),
        forbidden_paths=(".git",),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.LOW,
        privacy_class=PrivacyClass.P3,
    )


def test_local_backend_runs_only_inside_candidate_world(tmp_path):
    controller = tmp_path / "controller"
    world_path = tmp_path / "candidate"
    controller.mkdir(); world_path.mkdir()
    world = CandidateWorld(task_id="task-a", candidate_id="cand-a", path=world_path, base_commit="abc")
    backend = LocalWorkspaceBackend(controller_root=controller)

    handle = backend.prepare(_task(), world)
    result = backend.run(handle, ["python", "-c", "from pathlib import Path; Path('marker.txt').write_text('ok')"])

    assert result.exit_code == 0
    assert (world_path / "marker.txt").read_text() == "ok"
    assert not (controller / "marker.txt").exists()
    assert result.stdout_sha256
    assert result.stderr_sha256


def test_local_backend_rejects_controlling_checkout(tmp_path):
    controller = tmp_path / "controller"
    controller.mkdir()
    world = CandidateWorld(task_id="task-a", candidate_id="cand-a", path=controller, base_commit="abc")
    backend = LocalWorkspaceBackend(controller_root=controller)

    with pytest.raises(WorkspaceIsolationError):
        backend.prepare(_task(), world)
