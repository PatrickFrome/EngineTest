from pathlib import Path
import json
from .util import canonical_hash, new_id, now

class LocalLedger:
    def __init__(self,root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.events=self.root/'events.jsonl'; self.seq=0
    def append(self,run_id,kind,payload,engine_id=None,parent_event_ids=None):
        self.seq+=1
        ev={
          'event_id':new_id('evt'),'meta_run_id':run_id,'engine_id':engine_id,'seq':self.seq,
          'event_type':kind,'payload':payload,'payload_hash':canonical_hash(payload),
          'parent_event_ids':list(parent_event_ids or []),'created_at':now()
        }
        with self.events.open('a',encoding='utf8') as f: f.write(json.dumps(ev,ensure_ascii=False)+'\n')
        return ev
