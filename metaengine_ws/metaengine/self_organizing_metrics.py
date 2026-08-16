from __future__ import annotations
from .util import canonical_hash

def evaluate_self_organization(transformation_graph,scheduler_rounds,architecture_history,mesh,claim_graph,baseline=None):
    tm=transformation_graph.get('metrics',{})
    rounds=len(scheduler_rounds); selected=sum(len(r.get('scheduler',{}).get('selected',[])) for r in scheduler_rounds)
    all16_equiv=max(1,16*max(1,rounds)); sparse_ratio=1-selected/all16_equiv
    topo_mut=sum(1 for a in architecture_history if str(a.get('mutation','')).startswith('MUTATE'))
    causal=min(1.0,tm.get('causal_depth',0)/10)
    diversity=min(1.0,tm.get('type_diversity',0))
    cycles=min(1.0,tm.get('cycle_pressure',0)/24)
    reground=min(1.0,tm.get('source_reground_count',0)/16)
    herm=round(min(1.0,.30*causal+.25*diversity+.20*cycles+.25*reground),4)
    epistemic=round(min(1.0,.28*diversity+.24*reground+.18*min(1,topo_mut/2)+.18*min(1,mesh.get('metrics',{}).get('multi_engine_agenda_items',0)/12)+.12*min(1,tm.get('unresolved_tensions',0)/3)),4)
    depth=round(min(1.0,.42*causal+.22*reground+.20*min(1,rounds/3)+.16*diversity),4)
    performance={'sparse_deep_execution_ratio':round(max(0,sparse_ratio),4),'deep_engine_executions':selected,'full16_recursive_equivalent':all16_equiv,'architecture_mutations':topo_mut}
    safety={'native_claim_nodes':claim_graph.get('node_count',0),'native_claim_positions':claim_graph.get('position_count',0),'derived_truth_promotion_violations':mesh.get('metrics',{}).get('derived_truth_promotion_violations',0),'majority_vote_used':False}
    result={'evaluation_version':'16X-DIAGNOSTIC-SELF-ORGANIZING-METRICS-2.3','hermeneutic_nonlinearity_proxy':herm,'epistemic_nonlinearity_proxy':epistemic,'depth_proxy':depth,'performance':performance,'safety':safety,'eligible_for_policy_promotion':False,'eligible_for_truth_promotion':False,'metric_role':'DIAGNOSTIC_COVARIATES_ONLY','claim_ceiling':'ARCHITECTURAL_PROXIES_AND_SCHEDULER_EFFICIENCY_NOT_EXTERNAL_PHILOSOPHICAL_SUPERIORITY'}
    if baseline:
        result['delta_vs_baseline']={k:round(result[k]-float(baseline.get(k,0)),4) for k in ('hermeneutic_nonlinearity_proxy','epistemic_nonlinearity_proxy','depth_proxy')}
    result['evaluation_hash']=canonical_hash({k:v for k,v in result.items() if k!='evaluation_hash'}); return result
