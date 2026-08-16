from pathlib import Path
from collections import Counter
import importlib.util, re, json, time
from .base import Adapter, EngineContribution
from ..security import verify_release_file

def _load(path):
    spec=importlib.util.spec_from_file_location('ref_'+path.parent.parent.name.replace('-','_'),path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def _tokens(text): return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё][\wÀ-ÖØ-öø-ÿА-Яа-яЁё-]{2,}",text,flags=re.UNICODE)
def _sentences(text): return [x.strip() for x in re.split(r'(?<=[.!?])\s+',text) if x.strip()]

class ReferenceAdapter(Adapter):
    def _paths(self):
        sk=next(self.root.rglob('src/reference_skeleton.py')); cfg=next(self.root.rglob('config/reference_architecture.json')); return sk,cfg
    def run(self,input_path,out_dir,context):
        started=time.perf_counter(); eid=self.record['engine_id']; native={}; canon={'kind':'reference_architecture_execution','claims':[]}
        try:
            text=Path(input_path).read_text(errors='ignore'); sk,cfgp=self._paths()
            project_root=self.root.parents[1]; verify_release_file(project_root,sk); verify_release_file(project_root,cfgp)
            cfg=json.loads(cfgp.read_text()); mod=_load(sk); words=_tokens(text); sents=_sentences(text)
            canon.update({'architecture_id':cfg.get('architecture_id'),'focus':cfg.get('focus'),'stages':cfg.get('stages',[]),'input_words':len(words),'input_sentences':len(sents)})
            if eid=='engine_05':
                mm=mod.MemoryManager(str(Path(out_dir)/'memory')); st=mm.load('meta-agent'); mm.edit_block(st,'active_input_hash',context['input_hash']); mm.archive(st,text[:2000],tags=('meta-run',)); mm.save(st); native={'blocks':list(st.blocks),'archival_count':len(st.archival)}; canon['memory_updates']=native
            elif eid=='engine_06':
                idx=mod.GraphIndex();
                for i,s in enumerate(sents[:80]): idx.units[str(i)]=mod.TextUnit(str(i),'input',s)
                # deterministic co-occurrence graph from repeated salient terms
                freq=Counter(w.lower() for w in words); salient=[w for w in sorted(freq,key=lambda x:(-freq[x],x)) if len(w)>4][:12]
                for i in range(len(salient)-1): idx.edges.append(mod.Edge(salient[i],'co_occurs',salient[i+1],str(i%max(1,len(idx.units)))))
                q=mod.QueryEngine(idx); loc=q.local(salient[0]) if salient else {}; loc={'entity':loc.get('entity'),'links':loc.get('links',[]),'text_units':[u.__dict__ if hasattr(u,'__dict__') else u for u in loc.get('text_units',[])]}; native={'entities':salient,'edges':[e.__dict__ for e in idx.edges],'local':loc}; canon['graph']=native
            elif eid=='engine_07':
                evid=[mod.Evidence('input',s,0.0,0.0) for s in sents[:24]]; st=mod.ResearchState('analyze input',evidence=evid); native={'evidence_count':len(evid),'hypothesis_slots':max(1,min(8,len(evid)//3))}; canon['evidence']=native
            elif eid=='engine_08':
                native={'manager_plan':[{'objective':'preserve native lineages','capability':'governance','critical':False},{'objective':'fuse without erasure','capability':'synthesis','critical':False}]}; canon['plan']=native
            elif eid=='engine_09':
                unique=sorted(set(w.lower() for w in words if len(w)>7))[:20]; native={'research_gaps':[f'verify:{w}' for w in unique[:8]],'citation_policy':'source_refs_required'}; canon['research']=native
            elif eid=='engine_10':
                tasks=[mod.Task(str(i),r,r) for i,r in enumerate(self.record['roles'][:4])]; native={'workforce_tasks':[t.__dict__ for t in tasks],'parallelizable':True}; canon['workforce']=native
            elif eid=='engine_11':
                ctx=mod.RunContext(); ctx.emit('meta.adapter.start',engine=eid); ctx.emit('workflow.checkpoint'); native={'events':ctx.events}; canon['workflow']=native
            elif eid=='engine_12':
                cp=mod.JsonCheckpointer(str(Path(out_dir)/'checkpoints')); st=mod.State(context['meta_run_id'],data={'input_hash':context['input_hash']},next_node='END'); cp.save(st); native={'checkpoint':str((Path(out_dir)/'checkpoints'/f"{st.thread_id}.json").name)}; canon['durable_state']=native
            elif eid=='engine_13':
                qs=[f'Investigate semantic cluster: {w}' for w in sorted(set(w.lower() for w in words if len(w)>6))[:6]]; native={'planned_questions':qs,'parallel_executor_width':min(8,max(1,len(qs)))}; canon['research_pipeline']=native
            elif eid=='engine_14':
                clusters=sorted(set(w.lower() for w in words if len(w)>7))[:5]; native={'perspectives':[{'name':w,'rationale':'source-derived lexical perspective'} for w in clusters],'outline_slots':len(clusters)}; canon['perspectives']=native
            elif eid=='engine_15':
                roots=[s[:160] for s in sents[:4]] or ['UNRESOLVED']; native={'branch_seeds':roots,'max_branches':cfg.get('budgets',{}).get('max_branches',16),'preserve_failed_branches':True}; canon['research_tree']=native
            elif eid=='engine_16':
                sig=mod.Signature(inputs=('source','context'),outputs=('candidate','trace')); native={'signature':{'inputs':sig.inputs,'outputs':sig.outputs},'optimization_target':['evidence_fidelity','abstention_calibration','rival_preservation']}; canon['program_optimization']=native
            else: native={}
            usage={'wall_seconds':round(time.perf_counter()-started,6),'input_tokens':None,'output_tokens':None,'cost_usd':None,'tool_calls':0}
            canon['adapter_disclosure']={'adapter_kind':'REFERENCE_SIMULATION','implementation_level':'CLEAN_ROOM_CONTRACT_STUB','eligible_for_frontier_comparison':False}
            return EngineContribution(eid,'REFERENCE_SIMULATION_COMPLETE',native,canon,None,'REFERENCE_SIMULATION','CLEAN_ROOM_CONTRACT_STUB',[],[],[{'event':'REFERENCE_CONTRACT_EXECUTED'}],usage,{'lineage_integrity_verified':True})
        except Exception as e:
            return EngineContribution(eid,'FAILED',native,canon,repr(e),'REFERENCE_SIMULATION','CLEAN_ROOM_CONTRACT_STUB',usage={'wall_seconds':round(time.perf_counter()-started,6)})
