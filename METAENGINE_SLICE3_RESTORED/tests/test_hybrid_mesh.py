import pathlib
from metaengine.hybrid_mesh import ArchitectureInterweave, ENGINE_PRIMITIVES, HYBRID_ORGANS
from metaengine.adapters.base import EngineContribution

ROOT=pathlib.Path(__file__).resolve().parents[1]

def fake(eid, canonical=None):
    return EngineContribution(eid,'COMPLETE',{},canonical or {})

def sample_contribs():
    cs=[]
    for i in range(1,17):
        eid=f'engine_{i:02d}'
        c={}
        if eid=='engine_05': c={'memory_updates':{'archival_count':1}}
        if eid=='engine_06': c={'graph':{'entities':['relation','difference'],'edges':[{'left':'relation','relation':'contrasts','right':'difference','evidence_unit':'0'}]}}
        if eid=='engine_07': c={'evidence':{'evidence_count':2,'hypothesis_slots':1}}
        if eid=='engine_08': c={'plan':{'manager_plan':[{'objective':'test','capability':'analysis','critical':False}]}}
        if eid=='engine_09': c={'research':{'research_gaps':['verify:difference']}}
        if eid=='engine_10': c={'workforce':{'workforce_tasks':[{'id':'0','description':'analysis','required_capability':'analysis'}]}}
        if eid=='engine_11': c={'workflow':{'events':[{'kind':'checkpoint'}]}}
        if eid=='engine_12': c={'durable_state':{'checkpoint':'x.json'}}
        if eid=='engine_13': c={'research_pipeline':{'planned_questions':['How does difference work?']}}
        if eid=='engine_14': c={'perspectives':{'perspectives':[{'name':'difference','rationale':'test'}]}}
        if eid=='engine_15': c={'research_tree':{'branch_seeds':['Difference may be relational.']}}
        if eid=='engine_16': c={'program_optimization':{'optimization_target':['evidence_fidelity']}}
        if eid in {'engine_01','engine_02','engine_03','engine_04'}:
            c={'claims':[{'proposition':'Difference is not exhausted by relation.','proposition_key':'difference-relation','stance':'PROPOSE','claim_type':'TEST','force':'HYPOTHETICAL','source_refs':['src#L1'],'evidence_strength':.5}]}
        cs.append(fake(eid,c))
    return cs

def routing():
    return {'assignments':[{'engine_id':f'engine_{i:02d}','role':'CORE' if i<=3 else 'RESERVE_REVIEW'} for i in range(1,17)]}

def test_complete_directed_pairwise_mesh():
    m=ArchitectureInterweave(ROOT).weave(sample_contribs(),routing(),'Difference and relation require evidence, memory, graphs and rival hypotheses.')
    assert m['metrics']['engine_coverage']==16
    assert m['metrics']['directed_pairwise_bridges']==240
    assert m['metrics']['all_16_have_15_incoming_and_outgoing_bridges'] is True

def test_every_engine_enters_at_least_one_hybrid_organ():
    covered={e for members in HYBRID_ORGANS.values() for e in members}
    assert covered==set(ENGINE_PRIMITIVES)

def test_mixing_does_not_promote_truth():
    m=ArchitectureInterweave(ROOT).weave(sample_contribs(),routing(),'Difference and relation.')
    assert m['metrics']['derived_truth_promotion_violations']==0
    assert all(a['truth_status']=='GENERATIVE_ONLY' for a in m['research_agenda'])

def test_hybrid_agenda_has_multiple_engine_origins():
    m=ArchitectureInterweave(ROOT).weave(sample_contribs(),routing(),'Difference relation evidence memory graph branch.')
    assert m['metrics']['multi_engine_agenda_items']>0
    assert m['metrics']['avg_source_engines_per_agenda_item']>=3
