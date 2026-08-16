from __future__ import annotations
from pathlib import Path
import hashlib, json, time, uuid

def sha256_bytes(data: bytes)->str: return hashlib.sha256(data).hexdigest()
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def canonical_hash(obj)->str:
    return sha256_bytes(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def new_id(prefix:str)->str: return f"{prefix}-{uuid.uuid4()}"
def now()->float: return time.time()
def write_json(path,obj): Path(path).parent.mkdir(parents=True,exist_ok=True); Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2))
def load_json(path): return json.loads(Path(path).read_text())
