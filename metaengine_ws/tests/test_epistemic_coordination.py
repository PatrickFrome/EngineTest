import json, pathlib
from metaengine.routing import CapabilityRouter
from metaengine.claims import ClaimGraphBuilder
from metaengine.disagreement import DisagreementEngine
from metaengine.arbitration import AdaptiveArbitrator
from metaengine.adapters.base import EngineContribution

ROOT=pathlib.Path(__file__).resolve().parents[1]

def contrib(eid, stance, text='A relation is constitutive.', key='relation-constitutive', refs=None, strength=.8):
    return EngineContribution(eid,'COMPLETE',{}, {'claims':[{
        'proposition':text,'proposition_key':key,'stance':stance,'claim_type':'INTERPRETIVE','force':'ASSERTED',
        'source_refs':refs or ['src#L1'],'evidence_strength':strength,'evidence_kind':'TEST'
    }]})

def test_router_keeps_all_16_scheduled_and_assigns_roles():
    plan=CapabilityRouter(ROOT).plan(ROOT/'examples/sample_input.md')
    assert plan['all_16_scheduled'] is True
    assert len(plan['assignments'])==16
    assert all(x['scheduled'] for x in plan['assignments'])
    assert any(x['role']=='CHALLENGER' for x in plan['assignments'])

def test_claim_graph_retains_engine_and_source_provenance():
    g=ClaimGraphBuilder().build([contrib('engine_01','SUPPORT'),contrib('engine_07','SUPPORT')])
    assert g['node_count']==1
    n=g['nodes'][0]
    assert n['engine_ids']==['engine_01','engine_07']
    assert n['source_refs']==['src#L1']
    assert len(n['positions'])==2

def test_disagreement_is_material_not_majority_vote():
    cs=[contrib('engine_01','SUPPORT'),contrib('engine_02','SUPPORT'),contrib('engine_03','SUPPORT'),contrib('engine_07','REJECT')]
    g=ClaimGraphBuilder().build(cs)
    plan=CapabilityRouter(ROOT).plan(ROOT/'examples/sample_input.md')
    d=DisagreementEngine().analyze(g,plan)
    assert d['material_conflict_count']==1
    assert d['conflicts'][0]['resolution_state']=='UNRESOLVED'
    a=AdaptiveArbitrator().arbitrate(g,d,plan,[])
    assert a['decisions'][0]['state']=='UNRESOLVED_RESEARCH_PRIORITY'
    assert a['decisions'][0]['majority_vote_used'] is False

def test_generative_only_cannot_be_promoted_to_support():
    c=EngineContribution('engine_15','COMPLETE',{}, {'claims':[{
      'proposition':'Try a speculative branch','proposition_key':'branch-x','stance':'PROPOSE','claim_type':'GENERATIVE_BRANCH','force':'GENERATIVE_ONLY','source_refs':[],'evidence_strength':.1
    }]})
    g=ClaimGraphBuilder().build([c]); plan=CapabilityRouter(ROOT).plan(ROOT/'examples/sample_input.md'); d=DisagreementEngine().analyze(g,plan)
    a=AdaptiveArbitrator().arbitrate(g,d,plan,[])
    assert a['decisions'][0]['state']=='GENERATIVE_ONLY'

def test_config_coordination_invariants():
    c=json.loads((ROOT/'config/meta_engine.json').read_text())
    assert c['version']=='2.3.0-alpha.1'
    assert c['invariants']['routing_changes_role_not_membership'] is True
    assert c['invariants']['material_disagreement_blocks_promotion'] is True
    assert c['invariants']['all_16_receive_two_polycentric_recursive_rounds'] is True
    assert c['invariants']['peer_presence_alone_does_not_count_as_novelty'] is True

def test_replication_without_credentials_is_explicit(monkeypatch):
    from metaengine.replication import replicate_run
    monkeypatch.delenv('SUPABASE_DATABASE_URL',raising=False)
    r=replicate_run(ROOT/'examples','supabase')
    assert r['status']=='UNAVAILABLE_NO_CREDENTIAL'
