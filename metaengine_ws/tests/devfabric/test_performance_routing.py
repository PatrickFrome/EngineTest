from metaengine.devfabric.models import PrivacyClass,RiskClass,TaskEnvelope
from metaengine.devfabric.performance import PerformanceStore
from metaengine.devfabric.providers.base import ProviderDescriptor,HealthSnapshot,QuotaSnapshot
from metaengine.devfabric.router import DevFabricRouter


class P:
    def __init__(self,pid,external=False):
        self.descriptor=ProviderDescriptor(pid,('CODE_GENERATOR',),external,'LOCAL_FREE',effectiveness=0.0,independence_group=pid)
    def health_check(self): return HealthSnapshot(True,10)
    def quota_snapshot(self): return QuotaSnapshot(True,None,False)
    def execute(self,task,workdir): raise NotImplementedError
    def cancel(self,task_id): return False


def task(privacy=PrivacyClass.P0):
    return TaskEnvelope.create(source_checkpoint_id='cp',source_tree_hash='x',objective='route',acceptance_tests=('x',),allowed_paths=('*.py',),forbidden_paths=('.git',),capabilities_required=('CODE_GENERATOR',),risk_class=RiskClass.LOW,privacy_class=privacy)


def test_ewma_history_changes_worker_ordering(tmp_path):
    store=PerformanceStore(tmp_path/'performance.sqlite',alpha=0.5)
    for score in (0.9,1.0,0.8): store.record('b',quality=score,success=True)
    for score in (0.2,0.1,0.3): store.record('a',quality=score,success=False)
    assert store.rank(('a','b'))==('b','a')
    assert store.score('b') > store.score('a')


def test_performance_priors_do_not_bypass_privacy_policy(tmp_path):
    store=PerformanceStore(tmp_path/'performance.sqlite')
    for _ in range(5): store.record('remote',quality=1.0,success=True)
    router=DevFabricRouter(max_parallel=2, effectiveness_priors=store.priors())
    decision=router.route(task(PrivacyClass.P3),(P('remote',external=True),P('local',external=False)))
    assert decision.selected==('local',)
    assert 'remote' in decision.rejected
