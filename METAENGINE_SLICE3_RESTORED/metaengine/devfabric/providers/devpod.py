from __future__ import annotations
import hashlib, os, shlex, subprocess, time
from pathlib import Path
from typing import Mapping, Sequence
from ..models import TaskEnvelope
from ..workspaces import ExecutionResult, WorkspaceHandle, WorkspaceIsolationError
from ..worktrees import CandidateWorld

class DevPodWorkspaceBackend:
    backend_id='devpod'
    def __init__(self, *, controller_root: str|Path): self.controller_root=Path(controller_root).resolve()
    @staticmethod
    def _workspace_id(world: CandidateWorld)->str:
        raw=f"meta-{world.task_id}-{world.candidate_id}".lower()
        return ''.join(c if c.isalnum() or c=='-' else '-' for c in raw)[:63]
    def _run_cli(self,args,*,timeout=600):
        return subprocess.run(['devpod',*args],capture_output=True,text=True,timeout=timeout,check=False)
    def prepare(self,task:TaskEnvelope,source_world:CandidateWorld)->WorkspaceHandle:
        path=source_world.path.resolve()
        if path==self.controller_root: raise WorkspaceIsolationError('DevPod source must be an isolated candidate world')
        wid=self._workspace_id(source_world)
        cp=self._run_cli(['up',str(path),'--id',wid,'--ide','none'])
        if cp.returncode!=0: raise RuntimeError(f'devpod up failed: {cp.stderr.strip()}')
        return WorkspaceHandle(self.backend_id,task.task_id,source_world.candidate_id,path,False,(('workspace',wid),))
    def run(self,handle:WorkspaceHandle,argv:Sequence[str],env:Mapping[str,str]|None=None,*,timeout_seconds:float=600)->ExecutionResult:
        wid=dict(handle.metadata)['workspace']; command=shlex.join(list(argv))
        if env:
            prefix=' '.join(f"{k}={shlex.quote(str(v))}" for k,v in sorted(env.items()))
            command=f"{prefix} {command}" if prefix else command
        started=time.monotonic(); cp=self._run_cli(['ssh',wid,'--command',command],timeout=timeout_seconds); elapsed=round(time.monotonic()-started,6)
        out=cp.stdout or ''; err=cp.stderr or ''
        return ExecutionResult(cp.returncode,elapsed,out,err,hashlib.sha256(out.encode()).hexdigest(),hashlib.sha256(err.encode()).hexdigest())
    def cleanup(self,handle:WorkspaceHandle)->None:
        self._run_cli(['delete',dict(handle.metadata)['workspace']],timeout=120)
