from __future__ import annotations
from collections import Counter, defaultdict
import math
from .util import canonical_hash


def _norm_entropy(counts):
    vals=[v for v in counts if v>0]; n=sum(vals)
    if n<=0 or len(vals)<=1:return 0.0
    h=-sum((v/n)*math.log(v/n,2) for v in vals)
    return h/math.log(len(vals),2)


def evaluate_nonlinearity(mesh, claim_graph, disagreements, arbitration, reentry=None):
    """Architectural proxy metrics. They do NOT assert philosophical correctness.

    Three dimensions are deliberately separated:
    - hermeneutic_nonlinearity: multiplicity/return/rival-reading structure;
    - epistemic_nonlinearity: plurality and reversibility of epistemic procedures;
    - depth: recursive transformational depth.
    Epistemic safety is reported separately and does not inflate nonlinearity scores.
    """
    metrics=(mesh or {}).get('metrics',{})
    agenda=(mesh or {}).get('research_agenda',[])
    traces=(mesh or {}).get('cross_architecture_traces',[])
    core4_rounds=(reentry or {}).get('rounds',[])
    return_edges=(reentry or {}).get('return_edges',[])
    source_counts=[len(a.get('source_engines',[])) for a in agenda]
    agenda_source_entropy=_norm_entropy(Counter(source_counts).values())
    branch_factor=(sum(source_counts)/max(1,len(source_counts))) if source_counts else 0.0
    conflict_count=(disagreements or {}).get('conflict_count',0)
    decision_states=Counter(d.get('state') for d in (arbitration or {}).get('decisions',[]))
    unresolved=decision_states.get('UNRESOLVED_RESEARCH_PRIORITY',0)+decision_states.get('QUALIFIED_UNRESOLVED',0)
    generative=decision_states.get('GENERATIVE_ONLY',0)
    decisions=sum(decision_states.values())
    reentry_positions=sum(r.get('metrics',{}).get('generative_positions',0) for r in core4_rounds)
    core4_div=sum(r.get('metrics',{}).get('pairwise_mean_divergence',0) for r in core4_rounds)/max(1,len(core4_rounds)) if core4_rounds else 0.0
    reentry_types=[]
    for r in core4_rounds:
        for res in r.get('results',[]):
            reentry_types.extend([p.get('claim_type') for p in res.get('generative_positions',[]) if p.get('claim_type')])
    type_set=set(reentry_types)
    core4_engines={res.get('engine_id') for r in core4_rounds for res in r.get('results',[]) if res.get('generative_position_count',0)>0}
    cycle_count=(reentry or {}).get('metrics',{}).get('hermeneutic_cycle_count',0)
    round1=core4_rounds[0].get('metrics',{}) if core4_rounds else {}
    round2=core4_rounds[1].get('metrics',{}) if len(core4_rounds)>1 else {}
    peer_second_order={'SECOND_ORDER_DESTRUCTION','OPERATOR_ECOLOGY_PROBE','CROSS_LINEAGE_DIFFERENTIAL','COUNTERFACTUAL_GATE'}
    peer_uptake=len(peer_second_order & type_set)/len(peer_second_order)

    herm_components={
        'multi_path_branching':min(1.0,branch_factor/10.0),
        'recursive_return':min(1.0,len(return_edges)/12.0),
        'source_reground_cycles':min(1.0,cycle_count/32.0),
        'core4_rival_divergence':min(1.0,core4_div),
        'cross_architecture_trace_depth':min(1.0,(sum(t.get('cross_family_depth',0) for t in traces)/max(1,len(traces)))/7.0) if traces else 0.0,
        'agenda_source_distribution':agenda_source_entropy,
    }
    epistemic_components={
        'methodological_plurality':min(1.0,len(type_set)/14.0),
        'core4_independent_pressure':min(1.0,len(core4_engines)/4.0),
        'reversible_operator_pressure':1.0 if 'OPERATOR_MUTATION_CANDIDATE' in type_set else 0.0,
        'counterfactual_pressure':1.0 if 'COUNTERFACTUAL_GATE' in type_set else 0.0,
        'semantic_boundary_pressure':1.0 if {'SEMANTIC_DIFFERENTIAL','CROSS_LINEAGE_DIFFERENTIAL','CANONICALIZATION_RESIDUE'} & type_set else 0.0,
        'interrogative_destabilization':1.0 if {'INTERROGATIVE_FRAME_ATOM','SECOND_ORDER_DESTRUCTION'} & type_set else 0.0,
        'peer_method_uptake':peer_uptake,
        'state_multiplicity':min(1.0,len(decision_states)/4.0) if decisions else 0.0,
        'dissent_preservation_when_present':(min(1.0,unresolved/max(1,conflict_count)) if conflict_count else 0.5),
    }
    depth_components={
        'recursive_round_depth':min(1.0,(reentry or {}).get('metrics',{}).get('recursive_rounds',0)/3.0),
        'reground_cycle_depth':min(1.0,cycle_count/32.0),
        'core4_transformational_yield':min(1.0,reentry_positions/64.0),
        'core4_architecture_coverage':min(1.0,len(core4_engines)/4.0),
        'five_layer_trace_completeness':min(1.0,metrics.get('full_five_layer_trace_count',0)/max(1,metrics.get('cross_architecture_traces',1))),
        'peer_second_order_uptake':peer_uptake,
        'round2_transform_growth':min(1.0,(round2.get('generative_positions',0)/max(1,round1.get('generative_positions',1)))/2.0) if round2 else 0.0,
    }
    safety={
        'provenance_complete':bool(claim_graph.get('provenance_complete')),
        'majority_vote_unused':not any(d.get('majority_vote_used') for d in (arbitration or {}).get('decisions',[])),
        'derived_truth_promotion_violations':metrics.get('derived_truth_promotion_violations',0)+(reentry or {}).get('metrics',{}).get('truth_promotion_violations',0),
        'reentry_claim_ceiling_present':bool((reentry or {}).get('claim_ceiling')) if reentry else True,
    }
    H=round(sum(herm_components.values())/len(herm_components),4)
    E=round(sum(epistemic_components.values())/len(epistemic_components),4)
    D=round(sum(depth_components.values())/len(depth_components),4)
    out={
        'metric_version':'16X-NONLINEARITY-PROXY-1.3.1',
        'hermeneutic_nonlinearity_proxy':H,'epistemic_nonlinearity_proxy':E,'depth_proxy':D,
        'components':{'hermeneutic':herm_components,'epistemic':epistemic_components,'depth':depth_components},
        'epistemic_safety':safety,
        'raw':{
            'agenda_items':len(agenda),'avg_source_engines_per_agenda_item':metrics.get('avg_source_engines_per_agenda_item',0),
            'return_edges':len(return_edges),'reentry_generative_positions':reentry_positions,'core4_mean_divergence':round(core4_div,4),'reentry_claim_types':sorted(type_set),'core4_active_engines':sorted(core4_engines),'hermeneutic_cycle_count':cycle_count,
            'round1_positions':round1.get('generative_positions',0),'round2_positions':round2.get('generative_positions',0),'peer_second_order_type_coverage':peer_uptake,
            'claim_nodes':claim_graph.get('node_count',0),'claim_edges':claim_graph.get('edge_count',0),'conflicts':conflict_count,
            'arbitration_states':dict(decision_states),
        },
        'claim_ceiling':'ARCHITECTURAL_PROXY_FOR_NONLINEARITY_AND_DEPTH; NOT_EXTERNAL_PHILOSOPHICAL_QUALITY_VALIDATION',
    }
    out['evaluation_hash']=canonical_hash({k:v for k,v in out.items() if k!='evaluation_hash'})
    return out
