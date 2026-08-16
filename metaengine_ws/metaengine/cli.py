from pathlib import Path
import argparse,json
from .orchestrator import MetaOrchestrator
from .routing import CapabilityRouter
from .replication import replicate_run
from .biographies import EngineBiographyStore
from .topology import TOPOLOGIES
from .frontier_control_plane import PATTERN_SOURCES
from .parallel_ecology import ParallelExperimentalEcology, ExperimentCase, write_variants, single_ablation_cases, pair_ablation_cases, topology_cases
from .architecture_policy import PolicyStore
from .worldbench import EvolutionCampaign

def main():
    p=argparse.ArgumentParser(prog='destruktion-meta16'); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('run'); s.add_argument('input'); s.add_argument('--out',required=True); s.add_argument('--max-workers',type=int,default=16)
    r=sub.add_parser('route'); r.add_argument('input')
    rp=sub.add_parser('replicate'); rp.add_argument('run_dir'); rp.add_argument('--backend',choices=['supabase'],default='supabase')
    sub.add_parser('engines'); sub.add_parser('capabilities'); sub.add_parser('biographies'); sub.add_parser('topologies'); sub.add_parser('frontier-patterns')
    pb=sub.add_parser('parallel-benchmark'); pb.add_argument('inputs',nargs='+'); pb.add_argument('--out',required=True); pb.add_argument('--world-workers',type=int,default=8); pb.add_argument('--inner-workers',type=int,default=2); pb.add_argument('--batch-size',type=int,default=4)
    pw=sub.add_parser('parallel-worlds'); pw.add_argument('input'); pw.add_argument('--out',required=True); pw.add_argument('--worlds',type=int,default=24); pw.add_argument('--world-workers',type=int,default=8); pw.add_argument('--inner-workers',type=int,default=2); pw.add_argument('--batch-size',type=int,default=4)
    pa=sub.add_parser('parallel-ablation'); pa.add_argument('input'); pa.add_argument('--out',required=True); pa.add_argument('--order',type=int,choices=[1,2],default=1); pa.add_argument('--limit',type=int); pa.add_argument('--world-workers',type=int,default=8); pa.add_argument('--inner-workers',type=int,default=2); pa.add_argument('--batch-size',type=int,default=4)
    pt=sub.add_parser('parallel-topologies'); pt.add_argument('input'); pt.add_argument('--out',required=True); pt.add_argument('--repeats',type=int,default=4); pt.add_argument('--world-workers',type=int,default=8); pt.add_argument('--inner-workers',type=int,default=2); pt.add_argument('--batch-size',type=int,default=4)
    ev=sub.add_parser('evolve'); ev.add_argument('--out',required=True); ev.add_argument('--generations',type=int,default=3); ev.add_argument('--candidates',type=int,default=24); ev.add_argument('--world-workers',type=int,default=8); ev.add_argument('--seeds',type=int,nargs='+',default=[17,43]); ev.add_argument('--cases-per-suite',type=int,default=8)
    sub.add_parser('active-policy')
    rb=sub.add_parser('rollback-policy'); rb.add_argument('policy_hash'); rb.add_argument('--reason',required=True)
    a=p.parse_args(); root=Path(__file__).resolve().parents[1]
    if a.cmd=='run': print(json.dumps(MetaOrchestrator(root).run(a.input,a.out,a.max_workers),ensure_ascii=False,indent=2))
    elif a.cmd=='route': print(json.dumps(CapabilityRouter(root).plan(a.input),ensure_ascii=False,indent=2))
    elif a.cmd=='replicate':
        print(json.dumps([replicate_run(a.run_dir,a.backend)],ensure_ascii=False,indent=2))
    elif a.cmd=='engines': print((root/'config/meta_engine.json').read_text())
    elif a.cmd=='capabilities': print((root/'config/capability_registry.json').read_text())
    elif a.cmd=='biographies': print(json.dumps(EngineBiographyStore(root).snapshot(),ensure_ascii=False,indent=2))
    elif a.cmd=='topologies': print(json.dumps(TOPOLOGIES,ensure_ascii=False,indent=2))
    elif a.cmd=='frontier-patterns': print(json.dumps(PATTERN_SOURCES,ensure_ascii=False,indent=2))
    elif a.cmd=='parallel-benchmark':
        cases=[ExperimentCase(f'bench_{i:03d}',str(Path(x).resolve()),'BENCHMARK',{'freeze_biography':True,'cache_mode':'isolated'}) for i,x in enumerate(a.inputs)]
        print(json.dumps(ParallelExperimentalEcology(root).run(cases,a.out,a.world_workers,a.inner_workers,a.batch_size)['summary'],ensure_ascii=False,indent=2))
    elif a.cmd=='parallel-worlds':
        variants=write_variants(a.input,Path(a.out).with_name(Path(a.out).name+'_variants'),a.worlds); cases=[ExperimentCase(f'world_{i:03d}',str(p),'PERTURBATION_WORLD',{'freeze_biography':True,'cache_mode':'isolated'}) for i,p in enumerate(variants)]
        print(json.dumps(ParallelExperimentalEcology(root).run(cases,a.out,a.world_workers,a.inner_workers,a.batch_size)['summary'],ensure_ascii=False,indent=2))
    elif a.cmd=='parallel-ablation':
        cases=single_ablation_cases(a.input) if a.order==1 else pair_ablation_cases(a.input,a.limit)
        print(json.dumps(ParallelExperimentalEcology(root).run(cases,a.out,a.world_workers,a.inner_workers,a.batch_size)['summary'],ensure_ascii=False,indent=2))
    elif a.cmd=='parallel-topologies':
        print(json.dumps(ParallelExperimentalEcology(root).run(topology_cases(a.input,a.repeats),a.out,a.world_workers,a.inner_workers,a.batch_size)['summary'],ensure_ascii=False,indent=2))
    elif a.cmd=='evolve':
        print(json.dumps(EvolutionCampaign(root).run(a.out,a.generations,a.candidates,a.world_workers,tuple(a.seeds),a.cases_per_suite),ensure_ascii=False,indent=2))
    elif a.cmd=='active-policy': print(json.dumps(PolicyStore(root).active().as_dict(),ensure_ascii=False,indent=2))
    elif a.cmd=='rollback-policy': print(json.dumps(PolicyStore(root).rollback(a.policy_hash,a.reason).as_dict(),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
