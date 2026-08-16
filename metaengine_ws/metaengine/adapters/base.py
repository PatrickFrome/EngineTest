from dataclasses import dataclass, field
from typing import Any

@dataclass
class EngineContribution:
    engine_id:str
    status:str
    native:dict[str,Any]=field(default_factory=dict)
    canonical:dict[str,Any]=field(default_factory=dict)
    error:str|None=None
    adapter_kind:str='UNKNOWN'
    implementation_level:str='UNKNOWN'
    candidate_outputs:list[dict[str,Any]]=field(default_factory=list)
    evidence_refs:list[dict[str,Any]]=field(default_factory=list)
    execution_trace:list[dict[str,Any]]=field(default_factory=list)
    usage:dict[str,Any]=field(default_factory=dict)
    provenance:dict[str,Any]=field(default_factory=dict)

class Adapter:
    def __init__(self, record, root):
        self.record,self.root=record,root
    def run(self,input_path,out_dir,context):
        raise NotImplementedError
    def review(self,coordination,out_dir,context):
        conflicts=coordination.get('disagreements',{}).get('conflicts',[])
        assignments={a['engine_id']:a for a in coordination.get('routing_plan',{}).get('assignments',[])}
        mine=assignments.get(self.record['engine_id'],{})
        role=mine.get('role','RESERVE_REVIEW')
        selected=conflicts[:6] if role in ('CORE','CHALLENGER') else conflicts[:3]
        mesh=coordination.get('hybrid_mesh',{})
        reentry=coordination.get('core4_reentry',{})
        poly=coordination.get('polycentric_reentry',{})
        effects=coordination.get('useful_effects',{})
        ecology=coordination.get('self_organizing_ecology',{})
        transform=coordination.get('transformation_graph',{})
        agenda=[]
        for a in mesh.get('research_agenda',[]):
            if self.record['engine_id'] in a.get('source_engines',[]): agenda.append(a.get('agenda_id'))
        # Every engine also receives cross-bred agenda items for critique, even when it did not originate them.
        if not agenda: agenda=[a.get('agenda_id') for a in mesh.get('research_agenda',[])[:2]]
        state='CHALLENGE_UNRESOLVED' if selected and role=='CHALLENGER' else ('REVIEW_CONFLICTS' if selected else ('REVIEW_HYBRID_AGENDA' if agenda else 'ACKNOWLEDGED'))
        return {
            'engine_id':self.record['engine_id'],
            'review_state':state,
            'routing_role':role,
            'preserve_native':True,
            'conflict_count_seen':len(conflicts),
            'selected_disagreements':[c.get('disagreement_id') for c in selected],
            'hybrid_mesh_seen':bool(mesh),
            'selected_hybrid_agenda':agenda[:6],
            'pairwise_bridge_count_seen':mesh.get('metrics',{}).get('directed_pairwise_bridges',0),
            'core4_reentry_seen':bool(reentry),
            'core4_reentry_rounds':reentry.get('metrics',{}).get('recursive_rounds',0),
            'core4_return_edges_seen':reentry.get('metrics',{}).get('return_edge_count',0),
            'polycentric_reentry_seen':bool(poly),
            'polycentric_rounds_seen':poly.get('metrics',{}).get('round_count',0),
            'polycentric_peer_pairs_seen':poly.get('metrics',{}).get('peer_pair_coverage',0),
            'useful_effects_seen':effects.get('metrics',{}).get('present_or_strong_effects',0),
            'self_organizing_ecology_seen':bool(ecology),
            'selected_topology_seen':ecology.get('selected_topology_id'),
            'transformation_causal_depth_seen':transform.get('metrics',{}).get('causal_depth',0),
            'review_policy':'REQUEST_DISCRIMINATING_EVIDENCE; REVIEW_CROSS_BRED_AGENDA; DO_NOT_RESOLVE_BY_VOTE',
        }
