from pathlib import Path
import json,time
from .base import Adapter, EngineContribution
from ..security import redact_secrets,run_sandboxed,verify_release_file

class NodeNativeAdapter(Adapter):
    def _find_root(self):
        for p in self.root.rglob('package.json'):
            if 'lineages' not in p.parts[len(self.root.parts):] or self.record['engine_id']!='engine_03':
                return p.parent
        raise FileNotFoundError('package.json')

    def _claims(self,out):
        claims=[]
        for p in sorted(out.rglob('records/*.json')):
            try:d=json.loads(p.read_text())
            except Exception:continue
            for name in ('from_node','to_node'):
                n=d.get(name) or {}; text=n.get('description')
                if not text: continue
                facets=n.get('claim_facets') or {}; force=facets.get('force','UNRESOLVED')
                stance='PROPOSE' if force in ('HYPOTHETICAL','POSSIBLE') else ('ASSERT' if force in ('ASSERTED','NECESSARY') else 'UNRESOLVED')
                claims.append({
                    'proposition':text,'proposition_key':None,'stance':stance,'claim_type':'SOURCE_BOUNDED_CLAIM','force':force,
                    'source_refs':n.get('support_refs') or [],'evidence_kind':'NATIVE_SOURCE_RECORD',
                    'evidence_strength':0.7 if n.get('support_refs') else 0.25,
                    'claim_ceiling':'NATIVE_CLAIM_CEILING_PRESERVED','metadata':{'record_id':d.get('record_id'),'node_id':n.get('node_id'),'outcome':d.get('outcome')}
                })
        return claims

    def run(self,input_path,out_dir,context):
        started=time.perf_counter(); root=self._find_root(); input_path=Path(input_path).resolve(); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
        try:
            if self.record['engine_id']=='engine_03':
                cmd=['node','bin/destruktion-unified.mjs','delegate','portable','analyze',str(input_path),'--out',str(out/'native'),'--json']
            else:
                cmd=['node','bin/destruktion.mjs','analyze',str(input_path),'--out',str(out/'native'),'--json']
            project_root=self.root.parents[1]; verify_release_file(project_root,root/'package.json'); verify_release_file(project_root,root/cmd[1])
            cp=run_sandboxed(cmd,cwd=root,timeout=context.get('engine_timeout',600))
            files=[str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()]
            parsed=None; s=cp.stdout.strip()
            if s:
                try: parsed=json.loads(s)
                except Exception: parsed=None
            canonical={'kind':'destruktion_native_analysis','exit_code':cp.returncode,'artifact_count':len(files),'artifacts':files[:200],
                       'claim_ceiling':'CANDIDATE_GENERATION_OR_NATIVE_CEILING','stdout_digest':s[-4000:],'claims':self._claims(out)}
            if parsed and isinstance(parsed,dict):
                canonical['native_json_keys']=sorted(parsed.keys())
                v=parsed.get('validation',{}).get('counts',{}) if isinstance(parsed.get('validation'),dict) else {}
                canonical['validation_counts']=v
            status='COMPLETE' if cp.returncode==0 else 'DEGRADED'
            usage={'wall_seconds':round(time.perf_counter()-started,6),'input_tokens':None,'output_tokens':None,'cost_usd':None,'tool_calls':0}
            return EngineContribution(self.record['engine_id'],status,{'stdout':redact_secrets(s),'stderr':redact_secrets(cp.stderr[-8000:]),'command':cmd},canonical,None if cp.returncode==0 else f'exit={cp.returncode}','NATIVE_LOCAL','REAL_EXECUTOR',canonical.get('claims',[]),[],[{'event':'NODE_NATIVE_EXECUTED','exit_code':cp.returncode}],usage,{'lineage_integrity_verified':True})
        except Exception as e:
            return EngineContribution(self.record['engine_id'],'FAILED',{}, {'kind':'destruktion_native_analysis','claims':[]},repr(e),'NATIVE_LOCAL','REAL_EXECUTOR',usage={'wall_seconds':round(time.perf_counter()-started,6)})
