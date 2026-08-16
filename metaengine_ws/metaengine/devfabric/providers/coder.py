from __future__ import annotations
import hashlib, shlex, subprocess, time
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlparse
from ..models import TaskEnvelope
from ..workspaces import ExecutionResult, WorkspaceHandle, WorkspaceIsolationError
from ..worktrees import CandidateWorld

def coder_endpoint_external(url:str)->bool:
    host=urlparse(url).hostname
    return host not in {'127.0.0.1','localhost','::1'}

class CoderWorkspaceBackend:
    backend_id='coder'
    def __init__(self,*,controller_root:str|Path,workspace:str,access_url:str):
        if not workspace: raise ValueError('Coder workspace must be pre-provisioned')
        self.controller_root=Path(controller_root).resolve(); self.workspace=workspace; self.access_url=access_url
    def prepare(self,task:TaskEnvelope,source_world:CandidateWorld)->WorkspaceHandle:
        if source_world.path.resolve()==self.controller_root: raise WorkspaceIsolationError('Coder source must be an isolated candidate world')
        return WorkspaceHandle(self.backend_id,task.task_id,source_world.candidate_id,source_world.path.resolve(),coder_endpoint_external(self.access_url),(('workspace',self.workspace),('access_url',self.access_url),('mcp_http_path','/api/experimental/mcp/http')))
    def run(self,handle:WorkspaceHandle,argv:Sequence[str],env:Mapping[str,str]|None=None,*,timeout_seconds:float=600)->ExecutionResult:
        cmd=list(argv)
        if env:
            cmd=['env',*[f'{k}={v}' for k,v in sorted(env.items())],*cmd]
        started=time.monotonic()
        cp=subprocess.run(['coder','ssh',dict(handle.metadata)['workspace'],'--',*cmd],capture_output=True,text=True,timeout=timeout_seconds,check=False)
        elapsed=round(time.monotonic()-started,6); out=cp.stdout or ''; err=cp.stderr or ''
        return ExecutionResult(cp.returncode,elapsed,out,err,hashlib.sha256(out.encode()).hexdigest(),hashlib.sha256(err.encode()).hexdigest())
    def cleanup(self,handle:WorkspaceHandle)->None:
        # Coder workspaces are persistent control-plane resources; never delete implicitly.
        return None
