from __future__ import annotations
from .util import canonical_hash

TOPOLOGIES={
 'HERMENEUTIC_SPIRAL':[['engine_01','engine_03','engine_04'],['engine_02','engine_14','engine_05'],['engine_07','engine_01','engine_04']],
 'EVIDENCE_FIRST':[['engine_07','engine_09','engine_06'],['engine_15','engine_16','engine_04'],['engine_01','engine_03']],
 'GRAPH_FIRST':[['engine_06','engine_05','engine_03'],['engine_14','engine_13','engine_07'],['engine_01','engine_04']],
 'ADVERSARIAL_FORK':[['engine_14','engine_15','engine_02'],['engine_04','engine_07','engine_03'],['engine_01','engine_09']],
 'MEMORY_GENEALOGY':[['engine_05','engine_06','engine_03'],['engine_01','engine_14'],['engine_04','engine_07']],
 'WORKFLOW_SWARM':[['engine_08','engine_10','engine_11','engine_12'],['engine_13','engine_16'],['engine_04','engine_07']],
}
DOMAIN_PREF={
 'PHILOSOPHICAL_HERMENEUTICS':'HERMENEUTIC_SPIRAL','SEMANTIC_SCOPE':'HERMENEUTIC_SPIRAL','EVIDENCE_RESEARCH':'EVIDENCE_FIRST','GRAPH_RELATIONAL':'GRAPH_FIRST','MEMORY_LONGITUDINAL':'MEMORY_GENEALOGY','WORKFLOW_ORCHESTRATION':'WORKFLOW_SWARM','MULTI_PERSPECTIVE':'ADVERSARIAL_FORK','HYPOTHESIS_EXPERIMENT':'ADVERSARIAL_FORK'
}

def _waves_from_scores(selection, width=3):
    ordered=[x['engine_id'] for x in sorted(selection,key=lambda x:(-x['utility'],-x['expected_gain'],x['engine_id']))]
    return [ordered[i:i+width] for i in range(0,len(ordered),width)] or [[]]

class ProductiveTopologyLibrary:
    def __init__(self,biographies): self.biographies=biographies
    def candidates(self,routing,disagreements,scheduler_plan):
        active=routing['task_fingerprint'].get('active_domains',[]); selected=set(scheduler_plan.get('selected',[])); out=[]
        tension=disagreements.get('max_tension_score',0.0)
        for tid,waves in TOPOLOGIES.items():
            domain_fit=sum(1 for d in active if DOMAIN_PREF.get(d)==tid)/max(1,len(active))
            coverage=len(selected & {e for w in waves for e in w})/max(1,len(selected))
            groups={min(3,(int(e.split('_')[1])-1)//4) for w in waves for e in w}
            diversity=len(groups)/4
            prior=self.biographies.topology_prior(tid)
            utility=min(1.0,.30*domain_fit+.24*coverage+.16*diversity+.15*tension+.15*prior)
            out.append({'topology_id':tid,'origin':'LIBRARY','waves':waves,'domain_fit':round(domain_fit,4),'selected_coverage':round(coverage,4),'diversity':round(diversity,4),'biography_prior':prior,'expected_utility':round(utility,4)})
        # Generated candidate: topology is synthesized from the current gain ranking instead of selected from a fixed list.
        dyn_waves=_waves_from_scores(scheduler_plan.get('selection',[]),3)
        dyn_members={e for w in dyn_waves for e in w}
        dyn_div=len({min(3,(int(e.split('_')[1])-1)//4) for e in dyn_members})/4 if dyn_members else 0
        dyn_prior=self.biographies.topology_prior('DYNAMIC_GAIN_TOPOLOGY')
        dyn_utility=min(1.0,.34*min(1,len(dyn_members)/8)+.22*dyn_div+.20*tension+.24*dyn_prior)
        out.append({'topology_id':'DYNAMIC_GAIN_TOPOLOGY','origin':'GENERATED_FROM_CURRENT_GAIN_RANKING','waves':dyn_waves,'domain_fit':0.0,'selected_coverage':1.0 if dyn_members else 0.0,'diversity':round(dyn_div,4),'biography_prior':dyn_prior,'expected_utility':round(dyn_utility,4)})
        # Generated disagreement topology: challenger/evidence/core4 first, then remaining selected engines.
        if disagreements.get('conflict_count',0):
            priority=['engine_04','engine_07','engine_03','engine_01','engine_02','engine_14','engine_09','engine_06']
            first=[e for e in priority if e in selected][:4]
            rest=[x['engine_id'] for x in scheduler_plan.get('selection',[]) if x['engine_id'] not in first]
            waves=[first]+[rest[i:i+3] for i in range(0,len(rest),3)]
            dd_prior=self.biographies.topology_prior('DISAGREEMENT_RESOLUTION_TOPOLOGY')
            dd_util=min(1.0,.38*tension+.24*min(1,disagreements.get('conflict_count',0)/3)+.20*min(1,len(first)/4)+.18*dd_prior)
            out.append({'topology_id':'DISAGREEMENT_RESOLUTION_TOPOLOGY','origin':'GENERATED_FROM_MATERIAL_DISAGREEMENT','waves':waves,'domain_fit':0.0,'selected_coverage':round(len(set(first+rest)&selected)/max(1,len(selected)),4),'diversity':1.0,'biography_prior':dd_prior,'expected_utility':round(dd_util,4)})
        return sorted(out,key=lambda x:(-x['expected_utility'],0 if x['origin'].startswith('GENERATED') else 1,x['topology_id']))
