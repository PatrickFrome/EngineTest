from __future__ import annotations
from .util import canonical_hash

def evaluate_ecology_effects(ecology,transform,scheduler_rounds,biographies,mesh):
    tm=transform.get('metrics',{}); rounds=len(scheduler_rounds); selected=[e for r in scheduler_rounds for e in r.get('scheduler',{}).get('selected',[])]
    compiled=sum(1 for r in scheduler_rounds for x in r.get('engine_results',[]) if x.get('compiled_mode'))
    specialized=sum(1 for r in scheduler_rounds for x in r.get('engine_results',[]) if x.get('specialized_native_executed'))
    specialized_passed=sum(1 for r in scheduler_rounds for x in r.get('engine_results',[]) if x.get('specialized_native_success'))
    effects=[
      ('SPARSE_DEEP_EXECUTION', rounds>0 and len(selected)<16*max(1,rounds), min(1,1-len(selected)/(16*max(1,rounds)))),
      ('NATIVE_REENTRY_COMPILATION', compiled>0, min(1,compiled/8)),
      ('SPECIALIZED_NATIVE_SUBCOMMANDS', specialized>0, min(1,specialized/4)),
      ('SPECIALIZED_NATIVE_SUBCOMMAND_PASSES', specialized_passed>0, min(1,specialized_passed/4)),
      ('EMPIRICAL_ENGINE_BIOGRAPHIES', bool(biographies.get('engines')), min(1,sum(b.get('observations',0) for b in biographies.get('engines',{}).values())/16)),
      ('TEMPORARY_COALITION_FORMATION', bool(ecology.get('coalitions')), min(1,len(ecology.get('coalitions',[]))/4)),
      ('DYNAMIC_TOPOLOGY_SELECTION', bool(ecology.get('architecture_history')), min(1,len(ecology.get('architecture_history',[]))/2)),
      ('DISAGREEMENT_DRIVEN_REORGANIZATION', ecology.get('disagreement_reorganizations',0)>0, min(1,ecology.get('disagreement_reorganizations',0)/2)),
      ('TRANSFORMATION_GRAPH_DEPTH', tm.get('causal_depth',0)>=3, min(1,tm.get('causal_depth',0)/10)),
      ('SOURCE_REGROUNDING_LOOPS', tm.get('source_reground_count',0)>0, min(1,tm.get('source_reground_count',0)/12)),
      ('MARGINAL_GAIN_STOPPING', ecology.get('stop_reason') in {'STOP_RECURSIVE_ECHO','STOP_MARGINAL_GAIN','STOP_PROLIFERATION','STOP_BUDGET_EXHAUSTED','STOP_MAX_DEPTH_SAFETY'}, 1.0 if ecology.get('stop_reason','').startswith('STOP_') else .4),
      ('ARCHITECTURE_MUTATION', ecology.get('architecture_mutations',0)>0, min(1,ecology.get('architecture_mutations',0)/2)),
      ('TRUTH_PROMOTION_FIREWALL', mesh.get('metrics',{}).get('derived_truth_promotion_violations',0)==0, 1.0 if mesh.get('metrics',{}).get('derived_truth_promotion_violations',0)==0 else 0.0),
    ]
    rows=[{'effect_id':k,'present':p,'strength_score':round(s,4),'epistemic_status':'ARCHITECTURAL_EFFECT_NOT_TRUTH'} for k,p,s in effects]
    out={'effects_version':'16X-SELF-ORGANIZING-USEFUL-EFFECTS-2.0','effects':rows,'metrics':{'effect_count':len(rows),'present_or_strong_effects':sum(1 for x in rows if x['present']),'mean_strength':round(sum(x['strength_score'] for x in rows)/len(rows),4),'derived_truth_promotion_violations':mesh.get('metrics',{}).get('derived_truth_promotion_violations',0)},'claim_ceiling':'USEFUL_ARCHITECTURAL_EFFECTS_DO_NOT_ESTABLISH_EXTERNAL_PHILOSOPHICAL_CORRECTNESS'}
    out['effects_hash']=canonical_hash({k:v for k,v in out.items() if k!='effects_hash'}); return out
