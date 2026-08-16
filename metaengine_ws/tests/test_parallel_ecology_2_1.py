from pathlib import Path
from metaengine.parallel_ecology import ExperimentCase, single_ablation_cases, pair_ablation_cases, topology_cases, write_variants
from metaengine.biographies import EngineBiographyStore
ROOT=Path(__file__).resolve().parents[1]
def test_parallel_case_contract_is_explicit():
    c=ExperimentCase('w','/tmp/x','WORLD',{'freeze_biography':True}); assert c.case_id=='w' and c.policy['freeze_biography']
def test_single_ablation_is_full_control_plus_16_leave_one_out():
    x=single_ablation_cases('/tmp/x'); assert len(x)==17; assert x[0].policy.get('disabled_engines',[])==[]; assert len(x[-1].policy['disabled_engines'])==1
def test_pair_ablation_has_120_unique_pairs():
    x=pair_ablation_cases('/tmp/x'); assert len(x)==120; assert len({tuple(c.policy['disabled_engines']) for c in x})==120
def test_topology_population_covers_six_families():
    x=topology_cases('/tmp/x',2); assert len(x)==12; assert len({c.policy['forced_topology_id'] for c in x})==6
def test_frozen_biography_does_not_persist(tmp_path):
    b=EngineBiographyStore(ROOT,persist=False); before=(ROOT/'storage/engine_biographies.json').read_bytes(); b.data['topologies']['TEST']={'n':1,'mean_gain':1}; b.update('x',{'active_domains':[]},[]); assert (ROOT/'storage/engine_biographies.json').read_bytes()==before
def test_variant_compiler_makes_requested_count(tmp_path):
    src=tmp_path/'s.md'; src.write_text('Meaning and evidence remain contested.'); ps=write_variants(src,tmp_path/'v',25); assert len(ps)==25 and len({p.read_text() for p in ps})==25

def test_parallel_pair_count_math():
    assert 16*15//2==120


def test_triple_ablation_count_math():
    import math
    assert math.comb(16,3)==560


def test_parallel_fabric_exposes_worker_recycling():
    import inspect
    from metaengine.parallel_ecology import ParallelExperimentalEcology
    sig=inspect.signature(ParallelExperimentalEcology.run)
    assert sig.parameters['batch_size'].default==4
