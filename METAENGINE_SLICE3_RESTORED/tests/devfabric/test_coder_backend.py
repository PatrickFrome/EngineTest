from pathlib import Path
import os

from metaengine.devfabric.models import PrivacyClass,RiskClass,TaskEnvelope
from metaengine.devfabric.providers.coder import CoderWorkspaceBackend, coder_endpoint_external
from metaengine.devfabric.worktrees import CandidateWorld


def task(): return TaskEnvelope.create(source_checkpoint_id='cp',source_tree_hash='t',objective='x',acceptance_tests=('x',),allowed_paths=('x',),forbidden_paths=('.git',),capabilities_required=('CODE_GENERATOR',),risk_class=RiskClass.LOW,privacy_class=PrivacyClass.P1)

def test_coder_endpoint_classification():
    assert coder_endpoint_external('http://127.0.0.1:3000') is False
    assert coder_endpoint_external('http://localhost:3000') is False
    assert coder_endpoint_external('https://coder.example.com') is True

def test_coder_backend_executes_in_preprovisioned_workspace_without_delete(monkeypatch,tmp_path):
    controller=tmp_path/'controller'; worldp=tmp_path/'world'; controller.mkdir(); worldp.mkdir()
    log=tmp_path/'log'; bind=tmp_path/'bin'; bind.mkdir(); exe=bind/'coder'
    exe.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit 0\n"); exe.chmod(0o755)
    monkeypatch.setenv('PATH',f"{bind}:{os.environ.get('PATH','')}")
    backend=CoderWorkspaceBackend(controller_root=controller,workspace='metaengine-stage-b',access_url='http://127.0.0.1:3000')
    handle=backend.prepare(task(),CandidateWorld(task_id='task-a',candidate_id='cand-a',path=worldp,base_commit='x'))
    backend.run(handle,['python','-V']); backend.cleanup(handle)
    assert log.read_text().splitlines()==['ssh metaengine-stage-b -- python -V']
    assert dict(handle.metadata)['workspace']=='metaengine-stage-b'
