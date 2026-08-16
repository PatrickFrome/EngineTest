from __future__ import annotations
from .util import canonical_hash


def evaluate_polycentric_extension(polycentric,effects,mesh,claim_graph,baseline_1_3):
    pm=(polycentric or {}).get('metrics',{}); gm=(polycentric or {}).get('graph',{})
    rounds=(polycentric or {}).get('rounds',[])
    active=set(); all_types=set(); peer_pairs=set()
    for rr in rounds:
        for r in rr.get('results',[]):
            active.add(r.get('engine_id'))
            all_types.update(r.get('claim_types',[]))
            for src in r.get('peer_sources',[]):peer_pairs.add((src,r.get('engine_id')))
    # Structural extension metrics are directly interpretable fractions rather than truth/quality scores.
    herm={
      'all_engine_recursive_span':round(len(active)/16,4),
      'peer_return_pair_coverage':round(len(peer_pairs)/(16*15),4),
      'interpretive_type_diversity':round(min(1.0,len(all_types)/48),4),
      'recursive_novelty':round(pm.get('mean_round_novelty',0),4),
      'source_reground_density':round(min(1.0,gm.get('reground_required_edges',0)/max(1,pm.get('total_generative_positions',1))),4),
    }
    epi={
      'useful_effect_activation':(effects or {}).get('metrics',{}).get('effect_activation_rate',0),
      'peer_causal_coverage':round(len(peer_pairs)/(16*15),4),
      'adaptive_stopping_present':1.0 if pm.get('adaptive_stop_used') else 0.5,
      'architecture_claim_type_span':round(min(1.0,len(all_types)/32),4),
      'truth_promotion_safety':1.0 if (effects or {}).get('metrics',{}).get('derived_truth_promotion_violations',0)==0 else 0.0,
    }
    depth={
      'recursive_round_fraction':round(min(1.0,pm.get('round_count',0)/3),4),
      'all16_round_fraction':round(min(1.0,pm.get('all16_rounds',0)/2),4),
      'peer_return_density':round(min(1.0,gm.get('peer_return_edges',0)/(16*15)),4),
      'reground_cycle_density':round(min(1.0,gm.get('reground_required_edges',0)/96),4),
      'generative_transform_yield':round(min(1.0,pm.get('total_generative_positions',0)/128),4),
    }
    ext={'hermeneutic_extension':round(sum(herm.values())/len(herm),4),'epistemic_extension':round(sum(epi.values())/len(epi),4),'depth_extension':round(sum(depth.values())/len(depth),4)}
    out={'metric_version':'16X-POLYCENTRIC-EXTENSION-1.4','baseline_1_3_proxies':{'hermeneutic_nonlinearity_proxy':baseline_1_3.get('hermeneutic_nonlinearity_proxy'),'epistemic_nonlinearity_proxy':baseline_1_3.get('epistemic_nonlinearity_proxy'),'depth_proxy':baseline_1_3.get('depth_proxy')},'extension_components':{'hermeneutic':herm,'epistemic':epi,'depth':depth},'extension_scores':ext,'raw':{'active_recursive_engines':sorted(active),'unique_claim_types':sorted(all_types),'peer_causal_pairs':len(peer_pairs),'round_count':pm.get('round_count',0),'stop_reason':(polycentric or {}).get('stop_reason'),'total_generative_positions':pm.get('total_generative_positions',0),'useful_effects_present':(effects or {}).get('metrics',{}).get('present_or_strong_effects',0)},'epistemic_safety':{'native_claim_nodes_unchanged_required':True,'derived_truth_promotion_violations':(effects or {}).get('metrics',{}).get('derived_truth_promotion_violations',0),'majority_vote_forbidden':True},'claim_ceiling':'POLYCENTRIC_EXTENSION_METRICS_MEASURE_ARCHITECTURAL_BEHAVIOR_NOT_EXTERNAL_PHILOSOPHICAL_QUALITY'}
    out['evaluation_hash']=canonical_hash({k:v for k,v in out.items() if k!='evaluation_hash'})
    return out
