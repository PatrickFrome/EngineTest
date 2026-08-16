from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time, json, hashlib, itertools
from .orchestrator import MetaOrchestrator
from .util import canonical_hash, write_json, load_json

@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    input_path: str
    kind: str='WORLD'
    policy: dict|None=None
    parent_id: str|None=None

class ParallelExperimentalEcology:
    """Bounded outer-world concurrency with frozen biographies and post-completion comparison."""
    def __init__(self, root): self.root=Path(root)
    def _one(self, case:ExperimentCase, world_dir:Path, inner_workers:int):
        t=time.perf_counter(); out=world_dir/case.case_id
        pol={**(case.policy or {}),'freeze_biography':True,'cache_mode':'isolated'}
        try:
            state=MetaOrchestrator(self.root,persist_biographies=False).run(case.input_path,out,inner_workers,pol)
            metrics=load_json(out/'SELF_ORGANIZING_METRICS.json'); safety=load_json(out/'EPISTEMIC_SAFETY_2.1.json'); eco=load_json(out/'SELF_ORGANIZING_ECOLOGY.json'); tg=load_json(out/'TRANSFORMATION_GRAPH.json')
            return {'case_id':case.case_id,'kind':case.kind,'parent_id':case.parent_id,'status':state['status'],'elapsed_s':round(time.perf_counter()-t,4),'disabled_engines':pol.get('disabled_engines',[]),'forced_topology_id':pol.get('forced_topology_id'),'deep_executions':metrics['performance']['deep_engine_executions'],'causal_depth_diagnostic':tg['metrics']['causal_depth'],'source_reground_count_diagnostic':tg['metrics']['source_reground_count'],'hermeneutic_nonlinearity_proxy_diagnostic':metrics['hermeneutic_nonlinearity_proxy'],'epistemic_nonlinearity_proxy_diagnostic':metrics['epistemic_nonlinearity_proxy'],'depth_proxy_diagnostic':metrics['depth_proxy'],'observed_outcome':None,'promotion_eligible':False,'selected_topology':eco.get('selected_topology_id'),'stop_reason':eco.get('stop_reason'),'truth_promotion_violations':safety.get('derived_truth_promotion_violations',0),'claim_node_delta':safety.get('claim_node_delta_vs_primary',0),'native_position_delta':safety.get('native_position_delta_vs_primary',0),'run_dir':str(out)}
        except Exception as e:
            return {'case_id':case.case_id,'kind':case.kind,'parent_id':case.parent_id,'status':'FAILED','elapsed_s':round(time.perf_counter()-t,4),'error':repr(e),'run_dir':str(out)}
    def run(self,cases,out_dir,world_workers=8,inner_workers=2,batch_size=4):
        out=Path(out_dir); out.mkdir(parents=True,exist_ok=False); world_dir=out/'worlds'; world_dir.mkdir()
        batch_size=max(1,int(batch_size)); compiled={'fabric_version':'16X-PARALLEL-EXPERIMENTAL-ECOLOGY-2.3','case_count':len(cases),'world_workers':world_workers,'inner_workers':inner_workers,'worker_recycling_batch_size':batch_size,'cases':[asdict(c) for c in cases],'biography_policy':'FROZEN_READ_ONLY_UNTIL_FREEZE_BARRIER','default_cache_policy':'ISOLATED_COLD_WORLD','resource_policy':'FRESH_THREAD_POOL_PER_BATCH; BOUNDED_NESTED_CONCURRENCY','promotion_policy':'NO_PROMOTION_WITHOUT_EXTERNAL_OUTCOME'}
        compiled['compile_hash']=canonical_hash(compiled); write_json(out/'EXPERIMENT_PLAN.json',compiled)
        started=time.perf_counter(); rows=[]
        # Recycle the outer pool between bounded batches. This prevents long-lived worker
        # degradation after many nested Node/native subprocess launches while preserving
        # full isolation at the freeze-barrier level.
        for start in range(0,len(cases),batch_size):
            chunk=cases[start:start+batch_size]
            with ThreadPoolExecutor(max_workers=min(world_workers,len(chunk))) as pool:
                futs={pool.submit(self._one,c,world_dir,inner_workers):c for c in chunk}
                for fut in as_completed(futs): rows.append(fut.result())
        rows=sorted(rows,key=lambda x:x['case_id']); freeze={'barrier':'CROSS_WORLD_FREEZE_BARRIER','all_worlds_completed':len(rows)==len(cases),'completed':sum(r['status'].startswith('COMPLETE') for r in rows),'failed':sum(r['status']=='FAILED' for r in rows),'elapsed_s':round(time.perf_counter()-started,4),'no_cross_world_read_before_freeze':True}
        freeze['freeze_hash']=canonical_hash(freeze); write_json(out/'FREEZE_BARRIER.json',freeze)
        summary=self.compare(rows,freeze); write_json(out/'PARALLEL_EXPERIMENT_RESULTS.json',{'rows':rows,'summary':summary}); return {'rows':rows,'summary':summary,'freeze':freeze}
    def compare(self,rows,freeze):
        ok=[r for r in rows if r['status'].startswith('COMPLETE')]
        kinds={}
        for r in ok:kinds.setdefault(r['kind'],[]).append(r)
        def avg(key,rs): return round(sum(float(x.get(key,0)) for x in rs)/max(1,len(rs)),4)
        by_kind={k:{'n':len(v),'mean_elapsed_s':avg('elapsed_s',v),'mean_deep_executions':avg('deep_executions',v),'mean_causal_depth_diagnostic':avg('causal_depth_diagnostic',v),'mean_hermeneutic_nonlinearity_diagnostic':avg('hermeneutic_nonlinearity_proxy_diagnostic',v),'mean_epistemic_nonlinearity_diagnostic':avg('epistemic_nonlinearity_proxy_diagnostic',v),'truth_promotion_violations':sum(x.get('truth_promotion_violations',0) for x in v)} for k,v in kinds.items()}
        return {'comparison_version':'16X-CROSS-WORLD-DIFFERENTIAL-2.3','worlds_total':len(rows),'worlds_complete':len(ok),'worlds_failed':len(rows)-len(ok),'parallel_elapsed_s':freeze['elapsed_s'],'sum_individual_elapsed_s':round(sum(r.get('elapsed_s',0) for r in rows),4),'effective_parallel_speedup':round(sum(r.get('elapsed_s',0) for r in rows)/max(.001,freeze['elapsed_s']),3),'by_kind':by_kind,'external_outcome_count':sum(r.get('observed_outcome') is not None for r in ok),'promotion_eligible':False,'max_causal_depth_diagnostic':max([r.get('causal_depth_diagnostic',0) for r in ok] or [0]),'topologies_observed':sorted({r.get('selected_topology') for r in ok if r.get('selected_topology')}),'truth_promotion_violations':sum(r.get('truth_promotion_violations',0) for r in ok),'claim_ceiling':'PARALLEL_ARCHITECTURAL_DIAGNOSTICS_ONLY; USE WORLDBENCH FOR OUTCOME_GATED_PROMOTION'}

def write_variants(source_path,out_dir,count=24):
    src=Path(source_path); text=src.read_text(errors='ignore'); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    transforms=[
      ('identity',lambda s:s),('paraphrase_frame',lambda s:'Reformulated problem-space:\n'+s),('negation_probe',lambda s:s+'\nCounterfactual: the central attribution is explicitly negated.'),('quotation_probe',lambda s:'"'+s.replace('"','')+'"\nThe quotation is mentioned rather than endorsed.'),('rival_reading',lambda s:s+'\nRival reading: preserve an incompatible interpretation without resolving it.'),('source_order',lambda s:'\n'.join(reversed(s.splitlines()))),('scope_probe',lambda s:s+'\nQuestion whether modality changes the scope of the central claim.'),('memory_probe',lambda s:s+'\nCompare this reading with its historical transformation and rejected predecessors.'),('graph_probe',lambda s:s+'\nRepresent dependencies as a graph and identify a relation whose removal changes the result.'),('evidence_probe',lambda s:s+'\nDemand a discriminating piece of evidence for the strongest rival branches.'),('operator_probe',lambda s:s+'\nAssume the current analytic operator may itself be inadequate.'),('perspective_probe',lambda s:s+'\nGenerate an independent perspective that shares no conclusion with the first reading.'),
    ]
    paths=[]
    for i in range(count):
        name,fn=transforms[i%len(transforms)]; cycle=i//len(transforms); body=fn(text)+f'\nExperimental variant cycle: {cycle}. Surface token: V{i:03d}.'
        p=out/f'variant_{i:03d}_{name}.md'; p.write_text(body); paths.append(p)
    return paths

def single_ablation_cases(source_path):
    base=[ExperimentCase('ablate_none',str(source_path),'ABLATION_SINGLE',{'skip_reviews':True,'max_rounds':2,'max_deep_engines':5})]
    return base+[ExperimentCase(f'ablate_{i:02d}',str(source_path),'ABLATION_SINGLE',{'disabled_engines':[f'engine_{i:02d}'],'skip_reviews':True,'max_rounds':2,'max_deep_engines':5}) for i in range(1,17)]

def pair_ablation_cases(source_path,limit=None):
    pairs=list(itertools.combinations([f'engine_{i:02d}' for i in range(1,17)],2)); pairs=pairs[:limit] if limit else pairs
    return [ExperimentCase(f'pair_{a[-2:]}_{b[-2:]}',str(source_path),'ABLATION_PAIR',{'disabled_engines':[a,b],'skip_reviews':True,'max_rounds':2,'max_deep_engines':4}) for a,b in pairs]

def topology_cases(source_path,repeats=4):
    ids=['HERMENEUTIC_SPIRAL','EVIDENCE_FIRST','GRAPH_FIRST','ADVERSARIAL_FORK','MEMORY_GENEALOGY','WORKFLOW_SWARM']
    return [ExperimentCase(f'topo_{tid.lower()}_{r:02d}',str(source_path),'TOPOLOGY_WORLD',{'forced_topology_id':tid,'skip_reviews':True,'max_rounds':2,'max_deep_engines':5}) for tid in ids for r in range(repeats)]
