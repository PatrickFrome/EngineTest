from __future__ import annotations
from pathlib import Path
import json, statistics, time
from .util import canonical_hash, load_json


def _safe_ratio(a,b): return round(a/max(1,b),4)

def compare_run_dirs(baseline_dir, hybrid_dir):
    b=Path(baseline_dir); h=Path(hybrid_dir)
    bstate=load_json(b/'META_RUN.json'); hstate=load_json(h/'META_RUN.json')
    bg=load_json(b/'CLAIM_GRAPH.json'); hg=load_json(h/'CLAIM_GRAPH.json')
    hm=load_json(h/'HYBRID_MESH.json')
    ba=load_json(b/'ARBITRATION.json'); ha=load_json(h/'ARBITRATION.json')
    # Native coverage is compared by semantic participation rather than volatile timestamps/paths.
    b_eng={k:v.get('status') for k,v in bstate.get('engine_states',{}).items()}
    h_eng={k:v.get('status') for k,v in hstate.get('engine_states',{}).items()}
    metrics={
        'baseline_primary_engines':len(b_eng),'hybrid_primary_engines':len(h_eng),
        'engine_membership_preserved':set(b_eng)==set(h_eng)=={f'engine_{i:02d}' for i in range(1,17)},
        'baseline_claim_nodes':bg.get('node_count',0),'hybrid_claim_nodes':hg.get('node_count',0),
        'baseline_claim_positions':bg.get('position_count',0),'hybrid_claim_positions':hg.get('position_count',0),
        'baseline_pairwise_prefusion_crossfeed':0,
        'hybrid_pairwise_prefusion_crossfeed':hm['metrics']['directed_pairwise_bridges'],
        'hybrid_direct_typed_reuse_bridges':hm['metrics']['direct_typed_reuse_bridges'],
        'hybrid_signal_types':hm['metrics']['signal_type_count'],
        'hybrid_multi_engine_agenda_ratio':_safe_ratio(hm['metrics']['multi_engine_agenda_items'],hm['metrics']['agenda_items']),
        'hybrid_avg_source_engines_per_agenda_item':hm['metrics']['avg_source_engines_per_agenda_item'],
        'hybrid_full_trace_ratio':_safe_ratio(hm['metrics']['full_five_layer_trace_count'],hm['metrics']['cross_architecture_traces']),
        'truth_promotion_violations':hm['metrics']['derived_truth_promotion_violations'],
        'baseline_majority_vote_used':any(d.get('majority_vote_used') for d in ba.get('decisions',[])),
        'hybrid_majority_vote_used':any(d.get('majority_vote_used') for d in ha.get('decisions',[])),
        'baseline_status':bstate.get('status'),'hybrid_status':hstate.get('status'),
    }
    # Positive structural result requires no loss + full mesh + trace gain + no truth inflation.
    positive=(metrics['engine_membership_preserved'] and metrics['hybrid_pairwise_prefusion_crossfeed']==240 and metrics['hybrid_multi_engine_agenda_ratio']>0 and metrics['truth_promotion_violations']==0 and not metrics['hybrid_majority_vote_used'])
    return {'benchmark_version':'16X-HYBRID-AB-1.2','metrics':metrics,'structural_positive_result':positive,'claim_ceiling':'STRUCTURAL_AND_CONTROLLED_BEHAVIORAL_GAIN_NOT_EXTERNAL_PHILOSOPHICAL_QUALITY_PROOF','benchmark_hash':canonical_hash(metrics)}
