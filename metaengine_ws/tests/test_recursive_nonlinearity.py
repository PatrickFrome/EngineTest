from pathlib import Path
from metaengine.core4_reentry import _project_core4, CORE4
from metaengine.nonlinearity import evaluate_nonlinearity
from metaengine.hybrid_mesh import ArchitectureInterweave
from metaengine.adapters.base import EngineContribution

ROOT=Path(__file__).resolve().parents[1]
SRC="A concept may be constituted through relations and exclusions, yet not every difference is reducible to relation. A rival interpretation denies that relation has ontological priority."

def empty_mesh():
    return {'research_agenda':[{'agenda_id':'a','seed_text':'relation','seed_kind':'SOURCE_TERM','source_engines':['engine_06','engine_14','engine_15']}], 'metrics':{'derived_truth_promotion_violations':0,'avg_source_engines_per_agenda_item':3,'full_five_layer_trace_count':1,'cross_architecture_traces':1},'cross_architecture_traces':[{'cross_family_depth':6}]}

def test_core4_architectures_generate_distinct_probe_types():
    mesh=empty_mesh(); d={'conflicts':[]}
    types={}
    for eid in CORE4:
        ps=_project_core4(eid,SRC,mesh,d,None,1)
        assert ps
        assert all(p['stance']=='GENERATIVE_ONLY' and p['evidence_kind']=='CORE4_ARCHITECTURE_PROJECTION_DERIVED' for p in ps)
        types[eid]={p['claim_type'] for p in ps}
    assert types['engine_01'] != types['engine_02'] != types['engine_03']
    assert 'SCOPE_LATTICE_PROBE' in types['engine_04'] or 'ATTRIBUTION_SCOPE_PROBE' in types['engine_04']

def test_second_round_reads_peer_returns():
    mesh=empty_mesh(); d={'conflicts':[]}
    r1={'results':[]}
    for eid in CORE4:
        r1['results'].append({'engine_id':eid,'generative_positions':_project_core4(eid,SRC,mesh,d,None,1)})
    p1=_project_core4('engine_01',SRC,mesh,d,r1,2)
    p2=_project_core4('engine_02',SRC,mesh,d,r1,2)
    p3=_project_core4('engine_03',SRC,mesh,d,r1,2)
    p4=_project_core4('engine_04',SRC,mesh,d,r1,2)
    assert any(p['claim_type']=='SECOND_ORDER_DESTRUCTION' for p in p1)
    assert any(p['claim_type']=='OPERATOR_ECOLOGY_PROBE' for p in p2)
    assert any(p['claim_type']=='CROSS_LINEAGE_DIFFERENTIAL' for p in p3)
    assert any(p['claim_type']=='COUNTERFACTUAL_GATE' for p in p4)

def test_nonlinearity_proxy_increases_without_truth_promotion():
    graph={'nodes':[{'claim_id':'x'}],'node_count':1,'edge_count':1,'provenance_complete':True}
    dis={'conflict_count':0,'conflicts':[]}
    arb={'decisions':[{'state':'GENERATIVE_ONLY','majority_vote_used':False}]}
    mesh=empty_mesh()
    base=evaluate_nonlinearity(mesh,graph,dis,arb,None)
    reentry={'metrics':{'recursive_rounds':2,'truth_promotion_violations':0,'hermeneutic_cycle_count':8},'return_edges':[{}]*12,'rounds':[{'results':[{'engine_id':e,'generative_position_count':2,'generative_positions':[{'claim_type':'INTERROGATIVE_FRAME_ATOM' if e=='engine_01' else ('OPERATOR_MUTATION_CANDIDATE' if e=='engine_02' else ('SEMANTIC_DIFFERENTIAL' if e=='engine_03' else 'COUNTERFACTUAL_GATE'))}]} for e in CORE4],'metrics':{'pairwise_mean_divergence':.7,'generative_positions':8}}]}
    cur=evaluate_nonlinearity(mesh,graph,dis,arb,reentry)
    assert cur['hermeneutic_nonlinearity_proxy']>base['hermeneutic_nonlinearity_proxy']
    assert cur['epistemic_nonlinearity_proxy']>base['epistemic_nonlinearity_proxy']
    assert cur['depth_proxy']>base['depth_proxy']

def test_hybrid_mesh_accepts_reentry_probes_without_truth_promotion():
    cs=[]
    for i in range(1,17):
        eid=f'engine_{i:02d}'; c={}
        if eid=='engine_01': c={'reentry_round':1,'reentry_generative_positions':[{'proposition':'What does relation exclude?','claim_type':'INTERROGATIVE_FRAME_ATOM','metadata':{'reentry_round':1}}]}
        cs.append(EngineContribution(eid,'COMPLETE',{},c))
    routing={'assignments':[{'engine_id':f'engine_{i:02d}','role':'RESERVE_REVIEW'} for i in range(1,17)]}
    m=ArchitectureInterweave(ROOT).weave(cs,routing,SRC)
    assert m['metrics']['reentry_probe_signals']==1
    assert m['metrics']['derived_truth_promotion_violations']==0
    assert any(a['seed_kind']=='REENTRY_PROBE' for a in m['research_agenda'])
