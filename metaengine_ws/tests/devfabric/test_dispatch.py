from pathlib import Path
import subprocess

from metaengine.devfabric.dispatch import CompetitiveDispatcher
from metaengine.devfabric.models import PrivacyClass,RiskClass,TaskEnvelope
from metaengine.devfabric.providers.base import ProviderDescriptor,HealthSnapshot,QuotaSnapshot
from metaengine.devfabric.providers.common import receipt_from_git
from metaengine.devfabric.worktrees import WorktreeManager

class FakeProvider:
    def __init__(self,pid): self.descriptor=ProviderDescriptor(pid,('CODE_GENERATOR',),False,'LOCAL_FREE',independence_group=pid)
    def health_check(self): return HealthSnapshot(True)
    def quota_snapshot(self): return QuotaSnapshot(True,None,False)
    def execute(self,task,workdir):
        (Path(workdir)/f'{self.descriptor.provider_id}.txt').write_text('candidate')
        return receipt_from_git(task=task,provider_id=self.descriptor.provider_id,workdir=Path(workdir))
    def cancel(self,task_id): return False

def repo(path):
    subprocess.run(['git','init','-q'],cwd=path,check=True); subprocess.run(['git','config','user.name','T'],cwd=path,check=True); subprocess.run(['git','config','user.email','t@x.invalid'],cwd=path,check=True)
    (path/'base.txt').write_text('base'); subprocess.run(['git','add','.'],cwd=path,check=True); subprocess.run(['git','commit','-qm','base'],cwd=path,check=True)

def task(): return TaskEnvelope.create(source_checkpoint_id='cp',source_tree_hash='x',objective='compete',acceptance_tests=('x',),allowed_paths=('*.txt',),forbidden_paths=('.git',),capabilities_required=('CODE_GENERATOR',),risk_class=RiskClass.LOW,privacy_class=PrivacyClass.P3)

def test_competitive_dispatch_uses_separate_worlds_and_leaves_controller_clean(tmp_path):
    root=tmp_path/'repo'; root.mkdir(); repo(root)
    dispatcher=CompetitiveDispatcher(WorktreeManager(root),max_parallel=2)
    batch=dispatcher.dispatch(task(),[FakeProvider('a'),FakeProvider('b')])
    assert {r.provider_id for r in batch.receipts}=={'a','b'}
    assert not (root/'a.txt').exists() and not (root/'b.txt').exists()
    assert batch.errors==()
    assert subprocess.run(['git','status','--porcelain'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()==''

def test_dispatch_records_hash_chained_journal_receipts(tmp_path):
    from metaengine.devfabric.journal import Journal

    root=tmp_path/'repo-journal'; root.mkdir(); repo(root)
    journal=Journal(tmp_path/'journal.sqlite')
    dispatcher=CompetitiveDispatcher(WorktreeManager(root),max_parallel=1,journal=journal)
    batch=dispatcher.dispatch(task(),[FakeProvider('journal-agent')])
    assert len(batch.receipts)==1
    assert journal.verify_chain()==[]
    kinds=[item.kind for item in journal.pending_outbox()]
    assert kinds==['TASK_DISPATCHED','CANDIDATE_RECEIVED']
