from __future__ import annotations
import hashlib, subprocess
from pathlib import Path
from typing import Mapping
from ..models import CandidateReceipt, TaskEnvelope


def task_prompt(task: TaskEnvelope) -> str:
    return "\n".join([
        "METAENGINE CANDIDATE TASK — NO_CANONICAL_AUTHORITY",
        f"Task: {task.task_id}", f"Objective: {task.objective}",
        "Acceptance tests:", *[f"- {x}" for x in task.acceptance_tests],
        "Allowed paths:", *[f"- {x}" for x in task.allowed_paths],
        "Forbidden paths:", *[f"- {x}" for x in task.forbidden_paths],
        "Work only in this isolated candidate checkout. Do not publish, promote, push, or access canonical credentials.",
    ])


def receipt_from_git(*, task: TaskEnvelope, provider_id: str, workdir: Path, metadata: Mapping[str,str] | None=None) -> CandidateReceipt:
    head = subprocess.run(["git","rev-parse","HEAD"], cwd=workdir, capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git","add","-N","--","."], cwd=workdir, capture_output=True, check=True)
    status = subprocess.run(["git","status","--porcelain=v1","-z"], cwd=workdir, capture_output=True, check=True).stdout
    changed=[]
    for rec in status.split(b"\0"):
        if not rec: continue
        p=rec.decode("utf-8",errors="surrogateescape")[3:]
        if " -> " in p: p=p.split(" -> ",1)[1]
        changed.append(p)
    patch=subprocess.run(["git","diff","--binary","--no-ext-diff","HEAD","--","."],cwd=workdir,capture_output=True,check=True).stdout
    return CandidateReceipt.create(task_id=task.task_id,provider_id=provider_id,base_tree_hash=head,patch_hash=hashlib.sha256(patch).hexdigest(),changed_paths=changed,metadata=metadata)
