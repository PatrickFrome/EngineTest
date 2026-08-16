from __future__ import annotations
import json, urllib.request
from pathlib import Path
from urllib.parse import urlparse
from ..models import CandidateReceipt, TaskEnvelope
from .base import ProviderDescriptor, HealthSnapshot, QuotaSnapshot

class OllamaAdapter:
    def __init__(self, *, endpoint: str="http://127.0.0.1:11434/v1", health_endpoint: str="http://127.0.0.1:11434/api/tags"):
        host=urlparse(endpoint).hostname
        if host not in {"127.0.0.1","localhost","::1"}: raise ValueError("Ollama endpoint must be loopback in zero-spend local profile")
        self.endpoint=endpoint; self.health_endpoint=health_endpoint
        self.descriptor=ProviderDescriptor("ollama-local",("MODEL_RUNTIME",),False,"LOCAL_FREE",independence_group="local-ollama")
    def health_check(self)->HealthSnapshot:
        try:
            with urllib.request.urlopen(self.health_endpoint, timeout=1.5) as r:
                ok=200 <= r.status < 300
                return HealthSnapshot(ok, detail="ollama-api" if ok else f"http={r.status}")
        except Exception as e: return HealthSnapshot(False, detail=type(e).__name__)
    def quota_snapshot(self)->QuotaSnapshot: return QuotaSnapshot(True,None,False,"local compute")
    def execute(self, task: TaskEnvelope, workdir: Path)->CandidateReceipt: raise NotImplementedError("Ollama is a model runtime; compose it with an agent")
    def cancel(self, task_id:str)->bool: return False
