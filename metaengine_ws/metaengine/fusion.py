from __future__ import annotations
from collections import Counter, defaultdict

def fuse(contribs):
    status=Counter(c.status for c in contribs)
    completed=[c.engine_id for c in contribs if c.status=='COMPLETE']
    degraded=[c.engine_id for c in contribs if c.status=='DEGRADED']
    failed=[c.engine_id for c in contribs if c.status=='FAILED']
    simulations=[c.engine_id for c in contribs if c.adapter_kind=='REFERENCE_SIMULATION' or c.status=='REFERENCE_SIMULATION_COMPLETE']
    real_executors=[c.engine_id for c in contribs if c.implementation_level=='REAL_EXECUTOR']
    # Capability-preserving fusion: every canonical contribution is retained by provider.
    complementary={c.engine_id:c.canonical for c in contribs}
    conflicts=[]
    # Structural conflicts are explicit when providers disagree about run success.
    if failed or degraded:
        conflicts.append({'dimension':'execution_status','complete':completed,'degraded':degraded,'failed':failed,'resolution':'UNRESOLVED_OPERATIONAL_DIFFERENCE'})
    return {
      'policy':'FUSION_WITHOUT_ERASURE','status_counts':dict(status),'complete_engines':completed,'degraded_engines':degraded,'failed_engines':failed,'reference_simulation_engines':simulations,'real_executor_engines':real_executors,
      'consensus_core':{'all_16_scheduled':len(contribs)==16,'native_outputs_retained':True,'majority_is_not_truth':True},
      'complementary_extensions':complementary,'conflicts':conflicts,
      'abstentions':[c.engine_id for c in contribs if c.status in ('ABSTAIN','UNRESOLVED')],
      'claim_ceiling':'META_SYNTHESIS_COORDINATES_NATIVE_RESULTS; DOES_NOT CREATE TRUTH BY VOTE'
    }
