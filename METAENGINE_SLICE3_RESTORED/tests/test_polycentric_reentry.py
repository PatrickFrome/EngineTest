from pathlib import Path
from metaengine.polycentric_reentry import _project, _round_novelty, ALL16
from metaengine.effects import evaluate_useful_effects
from metaengine.polycentric_metrics import evaluate_polycentric_extension

SRC="A concept is interpreted through relations and exclusions, while rival readings dispute its ontological priority. Evidence remains incomplete and the historical meaning changes across contexts."
MESH={'research_agenda':[{'agenda_id':'a','seed_text':'relation','seed_kind':'SOURCE_TERM','source_engines':['engine_06','engine_14','engine_15']}], 'metrics':{'derived_truth_promotion_violations':0}}
DIS={'conflicts':[{'disagreement_id':'d','kind':'MATERIAL','representative':'relation is primary / relation is not primary'}]}

def test_all16_have_distinct_architectural_projection():
    types={}
    for eid in ALL16:
        ps=_project(eid,SRC,MESH,DIS,None,1)
        assert ps
        assert all(p['stance']=='GENERATIVE_ONLY' for p in ps)
        types[eid]={p['claim_type'] for p in ps}
    assert 'CONCEPT_BIOGRAPHY_PROBE' in types['engine_05']
    assert 'GRAPH_CROSS_BRANCH_LINK' in types['engine_06']
    assert 'DISCRIMINATING_TEST' in types['engine_07']
    assert 'CRITICAL_POINT_REPLAN' in types['engine_08']
    assert 'RESEARCH_GAP_REOPEN' in types['engine_09']
    assert 'WORKFORCE_ROLE_MUTATION' in types['engine_10']
    assert 'WORKFLOW_ORDER_COUNTERFACTUAL' in types['engine_11']
    assert 'STATE_BRANCH_REPLAY' in types['engine_12']
    assert 'PLAN_EXECUTOR_EDITOR_TRIANGLE' in types['engine_13']
    assert 'PERSPECTIVE_EXPANSION' in types['engine_14']
    assert 'HYPOTHESIS_BRANCH_EXPANSION' in types['engine_15']
    assert 'SIGNATURE_MUTATION' in types['engine_16']

def test_round2_consumes_peer_returns():
    r1={'results':[]}
    for eid in ALL16:
        ps=_project(eid,SRC,MESH,DIS,None,1)
        r1['results'].append({'engine_id':eid,'generative_positions':ps})
    for eid in ALL16:
        ps=_project(eid,SRC,MESH,DIS,r1,2)
        assert any((p.get('metadata') or {}).get('peer_sources') for p in ps)

def test_novelty_gate_detects_repetition():
    a={'results':[{'engine_id':'engine_05','generative_positions':[{'claim_type':'X','proposition':'same text','metadata':{'peer_sources':['engine_01']}}]}]}
    b={'results':[{'engine_id':'engine_05','generative_positions':[{'claim_type':'X','proposition':'same text','metadata':{'peer_sources':['engine_01']}}]}]}
    n=_round_novelty(b,a)
    assert n['global_novelty'] < .5

def test_useful_effect_registry_is_safety_bounded():
    rounds=[]
    r1={'results':[]}
    for eid in ALL16:
        r1['results'].append({'engine_id':eid,'generative_positions':_project(eid,SRC,MESH,DIS,None,1)})
    r2={'results':[]}
    for eid in ALL16:
        r2['results'].append({'engine_id':eid,'generative_positions':_project(eid,SRC,MESH,DIS,r1,2)})
    poly={'rounds':[r1,r2],'metrics':{'truth_promotion_violations':0,'round_count':2,'all16_rounds':2,'total_generative_positions':96,'mean_round_novelty':.5},'graph':{'peer_return_edges':80,'reground_required_edges':96},'stop_reason':'ADAPTIVE_NOVELTY_STOP'}
    eff=evaluate_useful_effects(poly,{'metrics':{'derived_truth_promotion_violations':0}}, {})
    assert eff['metrics']['present_or_strong_effects'] >= 8
    assert eff['metrics']['derived_truth_promotion_violations']==0
    base={'hermeneutic_nonlinearity_proxy':.8,'epistemic_nonlinearity_proxy':.8,'depth_proxy':.8}
    ext=evaluate_polycentric_extension(poly,eff,{}, {},base)
    assert ext['extension_scores']['hermeneutic_extension']>0
    assert ext['epistemic_safety']['derived_truth_promotion_violations']==0
