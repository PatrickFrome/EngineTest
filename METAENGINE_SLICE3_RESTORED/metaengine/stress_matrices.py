from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .state_cache import TypedStateCache
from .biographies import EngineBiographyStore
from .epistemic_gain import ExpectedEpistemicGainScheduler
from .topology import ProductiveTopologyLibrary
from .architecture_evolution import ArchitectureEvolutionEngine
from .util import canonical_hash,write_json

def cache_key_stress(root,out_path,count=4096,workers=48):
    cache=TypedStateCache(Path(root)/'storage'/'_stress_cache_keys')
    def one(i):
        eid=f'engine_{(i%16)+1:02d}'; pressures=[f'p:{i}',f'q:{i%31}']; return i,cache.key(eid,f'input-{i%257}',pressures,f'TOPO-{i%7}',1+(i%4))
    with ThreadPoolExecutor(max_workers=workers) as pool: rows=list(pool.map(one,range(count)))
    keys=[k for _,k in rows]; dup_test=cache.key('engine_01','same',['x'],'T',1)==cache.key('engine_01','same',['x'],'T',1)
    out={'matrix_version':'16X-CACHE-KEY-STRESS-2.1','test_count':count,'unique_keys':len(set(keys)),'collisions':count-len(set(keys)),'deterministic_duplicate_equal':dup_test,'workers':workers,'claim_ceiling':'CACHE_INTEGRITY_TEST_NOT_SEMANTIC_EQUIVALENCE'}; out['matrix_hash']=canonical_hash(out); write_json(out_path,out); return out

def topology_screen(root,router_texts,out_path,count=1024,workers=32):
    from .routing import CapabilityRouter
    root=Path(root); router=CapabilityRouter(root); bio=EngineBiographyStore(root,persist=False); sched=ExpectedEpistemicGainScheduler(bio); lib=ProductiveTopologyLibrary(bio); evo=ArchitectureEvolutionEngine(lib)
    texts=list(router_texts)
    def one(i):
        text=texts[i%len(texts)]+f'\nSynthetic architecture pressure {i}: '+(' conflict evidence graph scope memory hypothesis workflow ' if i%2 else ' ontology perspective optimization ')
        fp=router.fingerprint(text)
        routing={'task_fingerprint':fp,'assignments':[]}
        for rec in router.plan_text(text)['assignments'] if hasattr(router,'plan_text') else []: routing['assignments'].append(rec)
        # plan_text is not part of 2.1 router; construct engine assignments via a temporary compatible projection.
        if not routing['assignments']:
            for eid in sorted(router.by_engine):
                score,reasons=router._engine_score(eid,fp); routing['assignments'].append({'engine_id':eid,'relevance_score':score,'capabilities':router.caps.get(eid,[]),'role':'SPECIALIST','scheduled':True,'reasons':reasons})
        dm={'conflict_count':i%4,'max_tension_score':round((i%11)/10,2)}
        sp=sched.allocate(routing,dm,6.4,1,max_engines=8); ev=evo.select(routing,dm,sp,None)
        return {'i':i,'selected':ev['selected_topology_id'],'candidate_count':len(ev['candidates']),'utility':ev['selected']['expected_utility'],'conflicts':dm['conflict_count']}
    with ThreadPoolExecutor(max_workers=workers) as pool: rows=list(pool.map(one,range(count)))
    freq={}
    for r in rows: freq[r['selected']]=freq.get(r['selected'],0)+1
    out={'matrix_version':'16X-TOPOLOGY-SCREEN-2.1','test_count':count,'workers':workers,'selection_frequency':freq,'topologies_observed':sorted(freq),'rows':rows,'claim_ceiling':'STRUCTURAL_TOPOLOGY_SCREENING_NOT_EXTERNAL_QUALITY_VALIDATION'}; out['matrix_hash']=canonical_hash(out); write_json(out_path,out); return out
