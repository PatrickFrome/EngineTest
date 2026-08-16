from __future__ import annotations
from .util import canonical_hash

POS={'SUPPORT','ASSERT','OBSERVE','ACCEPT','PROVISIONAL_SUPPORT'}
NEG={'REJECT','CONTRADICT','DENY'}

def _side(stance):
    if stance in POS:return 'POSITIVE'
    if stance in NEG:return 'NEGATIVE'
    if stance in {'QUALIFY','UNRESOLVED','ABSTAIN'}: return 'UNCERTAIN'
    return 'GENERATIVE'

class DisagreementEngine:
    def analyze(self, claim_graph, routing_plan=None, hybrid_mesh=None):
        conflicts=[]; tensions=[]
        roles={a['engine_id']:a['role'] for a in (routing_plan or {}).get('assignments',[])}
        for n in claim_graph.get('nodes',[]):
            sides={}
            for p in n['positions']:
                sides.setdefault(_side(p['stance']),[]).append(p)
            material=bool(sides.get('POSITIVE') and sides.get('NEGATIVE'))
            uncertainty=bool((sides.get('POSITIVE') or sides.get('NEGATIVE')) and sides.get('UNCERTAIN'))
            if not (material or uncertainty): continue
            engines=sorted({p['engine_id'] for ps in sides.values() for p in ps})
            core_challenger=any(roles.get(e) in {'CORE','CHALLENGER'} for e in engines)
            source_density=min(1.0,sum(1 for ps in sides.values() for p in ps if p.get('source_refs'))/max(1,sum(len(ps) for ps in sides.values())))
            severity=1.0 if material else 0.55
            breadth=min(1.0,len(engines)/4)
            tension=round(min(1.0,0.50*severity+0.28*breadth+0.12*(1-source_density)+0.10*(1 if core_challenger else 0)),4)
            cid='dsg-'+canonical_hash({'claim':n['claim_id'],'sides':sorted(sides)})[:18]
            conflicts.append({
                'disagreement_id':cid,'claim_id':n['claim_id'],'representative':n['representative'],
                'kind':'MATERIAL_STANCE_CONFLICT' if material else 'ASSERTION_UNCERTAINTY_CONFLICT',
                'engine_ids':engines,
                'positions':{k:[{'engine_id':p['engine_id'],'stance':p['stance'],'evidence_strength':p['evidence_strength'],'source_refs':p['source_refs']} for p in v] for k,v in sides.items()},
                'tension_score':tension,
                'resolution_state':'UNRESOLVED',
                'research_priority':'HIGH' if tension>=0.72 else ('MEDIUM' if tension>=0.5 else 'LOW'),
            })
            tensions.append(tension)
        return {
            'disagreement_version':'16X-DISAGREEMENT-1.2',
            'conflict_count':len(conflicts),'material_conflict_count':sum(c['kind']=='MATERIAL_STANCE_CONFLICT' for c in conflicts),
            'max_tension_score':max(tensions,default=0.0),'conflicts':sorted(conflicts,key=lambda c:(-c['tension_score'],c['disagreement_id'])),
            'hybrid_research_pressure':{'agenda_items':(hybrid_mesh or {}).get('metrics',{}).get('agenda_items',0),'cross_architecture_traces':(hybrid_mesh or {}).get('metrics',{}).get('cross_architecture_traces',0)},
            'policy':'DISAGREEMENT_IS_RESEARCH_SIGNAL_NOT_FUSION_FAILURE; HYBRID_MIXING_MAY_PRIORITIZE_RESEARCH_BUT_CANNOT_CREATE_CONFLICT',
            'map_hash':canonical_hash(conflicts),
        }
