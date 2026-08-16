from pathlib import Path
import os

from metaengine.devfabric.models import PrivacyClass,RiskClass,TaskEnvelope
from metaengine.devfabric.providers.devpod import DevPodWorkspaceBackend
from metaengine.devfabric.worktrees import CandidateWorld


def task(): return TaskEnvelope.create(source_checkpoint_id='cp',source_tree_hash='t',objective='x',acceptance_tests=('x',),allowed_paths=('x',),forbidden_paths=('.git',),capabilities_required=('CODE_GENERATOR',),risk_class=RiskClass.LOW,privacy_class=PrivacyClass.P2)

def test_devpod_backend_uses_local_path_and_deterministic_workspace(monkeypatch,tmp_path):
    controller=tmp_path/'controller'; worldp=tmp_path/'world'; controller.mkdir(); worldp.mkdir()
    log=tmp_path/'log'; bind=tmp_path/'bin'; bind.mkdir(); exe=bind/'devpod'
    exe.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit 0\n"); exe.chmod(0o755)
    monkeypatch.setenv('PATH',f"{bind}:{os.environ.get('PATH','')}")
    backend=DevPodWorkspaceBackend(controller_root=controller)
    handle=backend.prepare(task(),CandidateWorld(task_id='task-abc',candidate_id='cand-01',path=worldp,base_commit='x'))
    assert handle.backend_id=='devpod'
    backend.run(handle,['python','-V'])
    backend.cleanup(handle)
    lines=log.read_text().splitlines()
    assert lines[0].startswith(f"up {worldp.resolve()} --id meta-task-abc-cand-01 --ide none")
    assert lines[1]=="ssh meta-task-abc-cand-01 --command python -V"
    assert lines[2]=="delete meta-task-abc-cand-01"
