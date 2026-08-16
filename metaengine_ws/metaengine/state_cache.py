from __future__ import annotations
from pathlib import Path
from .util import canonical_hash,write_json,load_json
class TypedStateCache:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.hits=0; self.misses=0
    def key(self,engine_id,input_hash,pressures,topology_id,round_index,handoff=None,policy_hash=None,adapter_snapshot=None,verifier_hash=None,guardrail_hash=None):
        return canonical_hash({'engine_id':engine_id,'input_hash':input_hash,'pressures':pressures,'topology':topology_id,'round':round_index,'handoff':handoff,'policy_hash':policy_hash,'adapter_snapshot':adapter_snapshot,'verifier_hash':verifier_hash,'guardrail_hash':guardrail_hash})
    def get(self,key):
        p=self.root/f'{key}.json'
        if p.exists():
            envelope=load_json(p); payload=envelope.get('payload'); claimed=envelope.get('payload_hash')
            if payload is None or canonical_hash(payload)!=claimed:
                self.misses+=1; return None
            self.hits+=1; return payload
        self.misses+=1; return None
    def put(self,key,obj): write_json(self.root/f'{key}.json',{'cache_version':'16X-HASH_CHAINED-TYPED-CACHE-2.3','payload_hash':canonical_hash(obj),'payload':obj})
    def metrics(self): return {'hits':self.hits,'misses':self.misses,'hit_rate':round(self.hits/max(1,self.hits+self.misses),4),'policy':'HASH_BOUND_TYPED_STATE_REUSE_ONLY; NO_SEMANTIC_EQUIVALENCE_ASSUMPTION'}
