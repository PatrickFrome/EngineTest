from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import itertools
from .util import load_json,write_json,canonical_hash
from .adapters.base import EngineContribution
from .hybrid_mesh import ArchitectureInterweave
from .claims import ClaimGraphBuilder
from .disagreement import DisagreementEngine
from .fusion import fuse

def load_primary(run_dir):
    run=Path(run_dir); cs=[]
    for p in sorted((run/'engines').glob('engine_*/CONTRIBUTION.json')):
        d=load_json(p); cs.append(EngineContribution(d['engine_id'],d['status'],d.get('native',{}),d.get('canonical',{}),d.get('error')))
    return cs,load_json(run/'ROUTING_PLAN.json')

def parallel_frozen_ablation(root,run_dir,source_path,out_path,order=2,workers=24):
    root=Path(root); cs,routing=load_primary(run_dir); text=Path(source_path).read_text(errors='ignore'); ids=[c.engine_id for c in cs]
    if order < 1 or order > len(ids):
        raise ValueError(f'order must be between 1 and {len(ids)}')
    subsets=[()] + [(x,) for x in ids] if order==1 else list(itertools.combinations(ids,order))
    mesh_builder=ArchitectureInterweave(root); claim=ClaimGraphBuilder(); dis=DisagreementEngine()
    def one(sub):
        keep=[c for c in cs if c.engine_id not in sub]; rr={**routing,'assignments':[a for a in routing['assignments'] if a['engine_id'] not in sub]}
        mesh=mesh_builder.weave(keep,rr,text); g=claim.build(keep,hybrid_mesh=mesh); dm=dis.analyze(g,rr,hybrid_mesh=mesh); f=fuse(keep)
        return {'disabled':list(sub),'remaining':len(keep),'claim_nodes':g['node_count'],'positions':g['position_count'],'edges':g['edge_count'],'conflicts':dm['conflict_count'],'bridge_contracts':mesh['metrics'].get('directed_pairwise_bridges',0),'active_possible_bridges':len(keep)*max(0,len(keep)-1),'agenda':mesh['metrics'].get('agenda_items',0),'failed':len(f['failed_engines']),'degraded':len(f['degraded_engines'])}
    rows=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(one,s) for s in subsets]): rows.append(fut.result())
    rows.sort(key=lambda r:r['disabled']); out={'matrix_version':'16X-FROZEN-PRIMARY-ABLATION-2.1','order':order,'test_count':len(rows),'workers':workers,'rows':rows,'claim_ceiling':'FROZEN_PRIMARY_COORDINATION_ABLATION; DOES_NOT REEXECUTE NATIVE ENGINES'}; out['matrix_hash']=canonical_hash(out); write_json(out_path,out); return out

def router_perturbation_matrix(router,base_text,out_path,count=1024,workers=32):
    from tempfile import TemporaryDirectory
    from pathlib import Path
    terms=['ontology','evidence','graph','memory','hypothesis','workflow','scope','optimization','perspective']
    def one(i):
        t=base_text+'\n'+' '.join(terms[(i+j)%len(terms)] for j in range(1+(i%5)))+f' token_{i}'
        fp=router.fingerprint(t); return {'i':i,'active':fp['active_domains'],'complexity':fp['complexity'],'id':fp['task_fingerprint_id']}
    with ThreadPoolExecutor(max_workers=workers) as pool: rows=list(pool.map(one,range(count)))
    out={'matrix_version':'16X-ROUTER-PERTURBATION-2.1','test_count':count,'unique_fingerprints':len({r['id'] for r in rows}),'domain_coverage':sorted({d for r in rows for d in r['active']}),'rows':rows}; out['matrix_hash']=canonical_hash(out); write_json(out_path,out); return out

def randomized_subset_matrix(root,run_dir,source_path,out_path,count=2048,workers=40,seed_offset=0):
    import random
    root=Path(root); cs,routing=load_primary(run_dir); text=Path(source_path).read_text(errors='ignore'); ids=[c.engine_id for c in cs]
    def one(i):
        j=i+int(seed_offset); rnd=random.Random(j*7919+17); k=1+(j%6); sub=tuple(sorted(rnd.sample(ids,k))); keep=[c for c in cs if c.engine_id not in sub]
        rr={**routing,'assignments':[a for a in routing['assignments'] if a['engine_id'] not in sub]}
        mesh=ArchitectureInterweave(root).weave(keep,rr,text); g=ClaimGraphBuilder().build(keep,hybrid_mesh=mesh); dm=DisagreementEngine().analyze(g,rr,hybrid_mesh=mesh); f=fuse(keep)
        return {'i':j,'disabled':list(sub),'remaining':len(keep),'claim_nodes':g['node_count'],'positions':g['position_count'],'edges':g['edge_count'],'conflicts':dm['conflict_count'],'active_possible_bridges':len(keep)*max(0,len(keep)-1),'agenda':mesh['metrics'].get('agenda_items',0),'truth_vote_used':False,'failed':len(f['failed_engines'])}
    with ThreadPoolExecutor(max_workers=workers) as pool: rows=list(pool.map(one,range(count)))
    out={'matrix_version':'16X-RANDOMIZED-FROZEN-SUBSET-2.1','test_count':count,'workers':workers,'seed_offset':int(seed_offset),'min_remaining':min(r['remaining'] for r in rows),'max_remaining':max(r['remaining'] for r in rows),'min_claim_nodes':min(r['claim_nodes'] for r in rows),'max_claim_nodes':max(r['claim_nodes'] for r in rows),'truth_vote_used_count':sum(r['truth_vote_used'] for r in rows),'rows':rows,'claim_ceiling':'RANDOMIZED_FROZEN_COORDINATION_STRESS; NO_NATIVE_REEXECUTION'}; out['matrix_hash']=canonical_hash(out); write_json(out_path,out); return out
