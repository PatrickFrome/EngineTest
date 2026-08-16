from __future__ import annotations
import json, os, shutil, subprocess, time
from pathlib import Path
from ..models import CandidateReceipt, TaskEnvelope
from .base import ProviderDescriptor, HealthSnapshot, QuotaSnapshot
from .common import task_prompt, receipt_from_git

def load_local_opencode_config(path: str|Path)->dict: return json.loads(Path(path).read_text())

class OpenCodeAdapter:
    def __init__(self, *, model="ollama/qwen3-coder", config_path: str|Path, timeout_seconds: float=600):
        self.model=model; self.config_path=Path(config_path); self.timeout_seconds=timeout_seconds
        self.descriptor=ProviderDescriptor("opencode-ollama-local",("CODE_GENERATOR","CODE_REVIEWER"),False,"LOCAL_FREE",effectiveness=0.5,independence_group="opencode")
    def health_check(self)->HealthSnapshot: return HealthSnapshot(shutil.which("opencode") is not None, detail="opencode-cli")
    def quota_snapshot(self)->QuotaSnapshot: return QuotaSnapshot(True,None,False,"local Ollama")
    def execute(self, task: TaskEnvelope, workdir: Path)->CandidateReceipt:
        config=load_local_opencode_config(self.config_path)
        env=os.environ.copy(); env.update({"OPENCODE_CONFIG_CONTENT":json.dumps(config,separators=(",",":")),"OPENCODE_DISABLE_AUTOUPDATE":"true","OPENCODE_AUTO_SHARE":"false"})
        argv=["opencode","run","--auto","--format","json","--model",self.model,task_prompt(task)]
        try:
            cp=subprocess.run(argv,cwd=workdir,env=env,capture_output=True,text=True,timeout=self.timeout_seconds,check=False)
            code=cp.returncode; out=cp.stdout or ""; err=cp.stderr or ""
        except subprocess.TimeoutExpired as e:
            code=124; out=e.stdout or ""; err=e.stderr or ""
            if isinstance(out,bytes): out=out.decode(errors="replace")
            if isinstance(err,bytes): err=err.decode(errors="replace")
        return receipt_from_git(task=task,provider_id=self.descriptor.provider_id,workdir=Path(workdir),metadata={"exit_code":str(code),"stdout_sha256":__import__('hashlib').sha256(out.encode()).hexdigest(),"stderr_sha256":__import__('hashlib').sha256(err.encode()).hexdigest(),"model":self.model})
    def cancel(self,task_id:str)->bool: return False
