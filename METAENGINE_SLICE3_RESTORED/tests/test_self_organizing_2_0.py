from pathlib import Path
from metaengine.biographies import EngineBiographyStore
from metaengine.epistemic_gain import ExpectedEpistemicGainScheduler
from metaengine.coalitions import CoalitionFactory
from metaengine.topology import ProductiveTopologyLibrary
from metaengine.architecture_evolution import ArchitectureEvolutionEngine
from metaengine.depth_budget import DepthBudgetController
from metaengine.transformation_graph import TransformationGraph
from metaengine.native_reentry_compiler import _semantic_manifest

ROOT=Path(__file__).resolve().parents[1]

def fake_routing():
    assigns=[]
    for i in range(1,17):
        eid=f'engine_{i:02d}'; assigns.append({'engine_id':eid,'relevance_score':.55 if i<=4 else .3,'capabilities':['SEMANTIC_SCOPE' if i==4 else 'EVIDENCE'],'role':'SPECIALIST','scheduled':True})
    return {'task_fingerprint':{'active_domains':['PHILOSOPHICAL_HERMENEUTICS','SEMANTIC_SCOPE'],'complexity':.6},'assignments':assigns}

def test_scheduler_is_sparse_but_keeps_diagnostic_assumption():
    b=EngineBiographyStore(ROOT); s=ExpectedEpistemicGainScheduler(b); p=s.allocate(fake_routing(),{'conflict_count':1,'max_tension_score':.8},7.0,1,required=['engine_01','engine_03','engine_04'])
    assert 4 <= len(p['selected']) < 16
    assert {'engine_01','engine_03','engine_04'} <= set(p['selected'])

def test_disagreement_can_mutate_topology():
    b=EngineBiographyStore(ROOT); lib=ProductiveTopologyLibrary(b); ev=ArchitectureEvolutionEngine(lib); sched=ExpectedEpistemicGainScheduler(b).allocate(fake_routing(),{'conflict_count':1,'max_tension_score':.8},7.0)
    a=ev.select(fake_routing(),{'conflict_count':1,'max_tension_score':.8},sched,None)
    b2=ev.select(fake_routing(),{'conflict_count':1,'max_tension_score':.8},sched,a)
    assert b2['mutation'] in {'MUTATE_TOPOLOGY_UNDER_DISAGREEMENT','RETAIN_TOPOLOGY'}
    if a['selected_topology_id']==b2['selected_topology_id']:
        assert not [c for c in b2['candidates'][1:] if c['expected_utility'] >= b2['candidates'][0]['expected_utility']-.22]

def test_transformation_graph_requires_regrounding():
    g=TransformationGraph(); g.add_deep_result({'engine_id':'engine_04','compiled_mode':'SPECIALIZED_NATIVE_SUBCOMMAND','receipt_hash':'x','transformations':[{'type':'PARSE','label':'rival parse','peer_sources':['engine_01']}]},1)
    a=g.artifact(1); assert a['metrics']['source_reground_count']>=1; assert all(e['truth_effect']=='NONE' for e in a['edges'])

def test_depth_budget_stops_echo():
    d=DepthBudgetController(.5); a={'transformation_types':['A'],'peer_pairs':[],'source_reground_count':1,'unresolved_tensions':1,'node_count':10}; b=dict(a)
    assert d.evaluate(a,None)['stop_decision']=='CONTINUE'
    assert d.evaluate(b,a)['stop_decision']=='STOP_RECURSIVE_ECHO'

def test_semantic_manifest_is_strict_native_shape():
    m=_semantic_manifest('Thinking discloses existence. Mind remains contested.','M')
    assert m['cases'][0]['segments'][0]['segment_id'].startswith('OX-P')
    assert 'claim_ceiling' not in m

def test_coalitions_are_temporary_and_non_authoritative():
    sched={'selected':['engine_01','engine_03','engine_04','engine_14','engine_05']}; c=CoalitionFactory().build(fake_routing(),{'conflict_count':1},sched)
    assert c['coalitions']; assert all(x['temporary'] and not x['truth_authority'] for x in c['coalitions'])


def test_depth_budget_prefers_marginal_stop_over_hard_budget():
    d=DepthBudgetController(.2)
    a={'transformation_types':['A'],'peer_pairs':[['engine_01','engine_02']],'source_reground_count':2,'unresolved_tensions':1,'node_count':20,'causal_depth':3,'topology_mutation_edges':1}
    b=dict(a)
    d.consume(d.total)
    r=d.evaluate(b,a)
    assert r['stop_decision'] in {'STOP_RECURSIVE_ECHO','STOP_MARGINAL_GAIN'}
    assert r['stop_decision']!='STOP_BUDGET_EXHAUSTED'

def test_later_scheduler_rounds_do_not_force_four_engines_over_budget():
    b=EngineBiographyStore(ROOT); s=ExpectedEpistemicGainScheduler(b)
    p=s.allocate(fake_routing(),{'conflict_count':0,'max_tension_score':0.0},2.8,3,required=[],max_engines=8)
    assert len(p['selected']) < 16
    assert p['spent_units'] <= 2.8*1.10 + 1e-9
