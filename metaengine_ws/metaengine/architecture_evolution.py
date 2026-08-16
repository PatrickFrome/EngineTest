from __future__ import annotations
from .util import canonical_hash

class ArchitectureEvolutionEngine:
    def __init__(self,topology_library): self.library=topology_library
    def select(self,routing,disagreements,scheduler_plan,previous=None):
        cands=self.library.candidates(routing,disagreements,scheduler_plan)
        excluded=set((previous or {}).get('retired',[])+(previous or {}).get('quarantined',[]))
        eligible=[c for c in cands if c['topology_id'] not in excluded] or cands
        selected=eligible[0]
        mutation='INITIAL_TOPOLOGY_BIRTH'
        if previous:
            prev=previous.get('selected_topology_id')
            # Magentic-style progress-ledger replanning is a computational response to
            # a stalled round. It changes topology only; it cannot change claim status.
            if previous.get('frontier_replan_required'):
                alternatives=[c for c in eligible if c['topology_id']!=prev and c['expected_utility']>=max(0.0,eligible[0]['expected_utility']-.28)]
                if alternatives:
                    selected=sorted(alternatives,key=lambda c:(-c['diversity'],-c['expected_utility'],c['topology_id']))[0]
                    mutation='FRONTIER_REPLAN_TOPOLOGY'
            # Persistent disagreement actively perturbs topology instead of merely being logged.
            if mutation!='FRONTIER_REPLAN_TOPOLOGY' and disagreements.get('conflict_count',0)>0 and prev==selected['topology_id'] and len(cands)>1:
                alternatives=[c for c in eligible[1:] if c['expected_utility']>=max(0.0,cands[0]['expected_utility']-0.22)]
                if alternatives: selected=alternatives[0]
            if mutation!='FRONTIER_REPLAN_TOPOLOGY':
                if prev==selected['topology_id']: mutation='RETAIN_TOPOLOGY'
                elif disagreements.get('conflict_count',0)>0: mutation='MUTATE_TOPOLOGY_UNDER_DISAGREEMENT'
                else: mutation='MUTATE_TOPOLOGY_FOR_EXPECTED_GAIN'
        result={'evolution_version':'16X-ARCHITECTURE-EVOLUTION-2.3','selected_topology_id':selected['topology_id'],'selected':selected,'candidates':cands,'mutation':mutation,'quarantined':[],'retired':[],'claim_ceiling':'ARCHITECTURE_SELECTION_IS_COMPUTATIONAL_POLICY_NOT_EPISTEMIC_VERDICT'}
        result['architecture_hash']=canonical_hash({k:v for k,v in result.items() if k!='architecture_hash'}); return result
    def adjudicate_after_round(self,evolution,observed_outcome,false_confidence=False):
        x=dict(evolution); x['observed_outcome']=round(observed_outcome,4) if observed_outcome is not None else None
        if false_confidence: x['disposition']='QUARANTINE_ARCHITECTURE_FALSE_CONFIDENCE'; x['quarantined']=[x['selected_topology_id']]
        elif observed_outcome is None: x['disposition']='UNVERIFIED_RETAIN_NO_LEARNING'
        elif observed_outcome<.08: x['disposition']='RETIRE_ARCHITECTURE_NO_EXTERNAL_OUTCOME'; x['retired']=[x['selected_topology_id']]
        else: x['disposition']='RETAIN_FOR_TASK_CLASS'
        x['architecture_hash']=canonical_hash({k:v for k,v in x.items() if k!='architecture_hash'}); return x
