from __future__ import annotations
import re
from collections import defaultdict
from .util import canonical_hash

POSITIVE={'SUPPORT','ASSERT','OBSERVE','ACCEPT','PROVISIONAL_SUPPORT'}
NEGATIVE={'REJECT','CONTRADICT','DENY'}
UNCERTAIN={'UNRESOLVED','QUALIFY','PROPOSE','ABSTAIN','QUESTION','GENERATIVE_ONLY'}

def _norm(s:str)->str:
    s=s.lower().strip()
    s=re.sub(r"[^\w\s-]"," ",s,flags=re.UNICODE)
    return re.sub(r"\s+"," ",s).strip()

def _base_key(text:str)->str:
    n=_norm(text)
    # Conservative lexical negation normalization is only a candidate key.
    n=re.sub(r"\b(?:not|no|never|cannot|can't|не|нет|никогда|нельзя)\b"," ",n)
    toks=[t for t in n.split() if len(t)>2]
    return ' '.join(toks[:48])

def _claim(position, engine_id, idx=0):
    text=str(position.get('proposition') or position.get('text') or position.get('description') or '').strip()
    if not text: return None
    pkey=position.get('proposition_key') or _base_key(text)
    return {
        'position_id':'pos-'+canonical_hash({'engine':engine_id,'i':idx,'text':text,'stance':position.get('stance')})[:20],
        'engine_id':engine_id,
        'proposition':text,
        'proposition_key':pkey,
        'stance':position.get('stance','UNRESOLVED'),
        'claim_type':position.get('claim_type','INTERPRETIVE'),
        'force':position.get('force','UNRESOLVED'),
        'source_refs':sorted(set(position.get('source_refs') or [])),
        'evidence_kind':position.get('evidence_kind','ENGINE_NATIVE_OR_DERIVED'),
        'evidence_strength':float(position.get('evidence_strength',0.25)),
        'claim_ceiling':position.get('claim_ceiling','PROPOSAL_UNTIL_EVIDENCE_AND_GATES'),
        'metadata':position.get('metadata',{}),
    }

def extract_positions(contrib):
    eid=contrib.engine_id; c=contrib.canonical or {}; out=[]
    for i,x in enumerate(c.get('claims',[]) if isinstance(c.get('claims'),list) else []):
        cl=_claim(x,eid,i)
        if cl: out.append(cl)
    # Preserve architecture-specific contributions as explicit non-truth proposals.
    if not out:
        if c.get('graph',{}).get('edges'):
            for i,e in enumerate(c['graph']['edges'][:16]):
                out.append(_claim({'proposition':f"{e.get('src')} {e.get('rel','relates_to')} {e.get('dst')}", 'stance':'OBSERVE','claim_type':'COMPUTED_SIGNAL','force':'GENERATIVE_ONLY','evidence_strength':0.35,'metadata':{'text_unit':e.get('text_unit')}},eid,i))
        elif c.get('research_tree',{}).get('branch_seeds'):
            for i,s in enumerate(c['research_tree']['branch_seeds'][:8]):
                out.append(_claim({'proposition':s,'stance':'PROPOSE','claim_type':'GENERATIVE_BRANCH','force':'GENERATIVE_ONLY','evidence_strength':0.15},eid,i))
        elif c.get('perspectives',{}).get('perspectives'):
            for i,p in enumerate(c['perspectives']['perspectives'][:8]):
                out.append(_claim({'proposition':f"Perspective candidate: {p.get('name')}", 'stance':'PROPOSE','claim_type':'PERSPECTIVE','force':'GENERATIVE_ONLY','evidence_strength':0.1},eid,i))
        elif c.get('research_pipeline',{}).get('planned_questions'):
            for i,q in enumerate(c['research_pipeline']['planned_questions'][:8]):
                out.append(_claim({'proposition':q,'stance':'QUESTION','claim_type':'RESEARCH_QUESTION','force':'QUESTION','evidence_strength':0.05},eid,i))
        elif c.get('research',{}).get('research_gaps'):
            for i,q in enumerate(c['research']['research_gaps'][:8]):
                out.append(_claim({'proposition':q,'stance':'QUESTION','claim_type':'RESEARCH_GAP','force':'QUESTION','evidence_strength':0.05},eid,i))
        elif c.get('plan',{}).get('manager_plan'):
            for i,q in enumerate(c['plan']['manager_plan'][:8]):
                out.append(_claim({'proposition':f"Workflow objective: {q.get('objective')}", 'stance':'PROPOSE','claim_type':'PROCEDURAL','force':'GENERATIVE_ONLY','evidence_strength':0.05},eid,i))
    return [x for x in out if x]

class ClaimGraphBuilder:
    def build(self, contributions, hybrid_mesh=None):
        positions=[]
        for c in sorted(contributions,key=lambda x:x.engine_id):
            positions.extend(extract_positions(c))
        groups=defaultdict(list)
        for p in positions: groups[p['proposition_key']].append(p)
        nodes=[]
        for key,ps in sorted(groups.items()):
            engines=sorted({p['engine_id'] for p in ps})
            refs=sorted({r for p in ps for r in p['source_refs']})
            max_ev=max((p['evidence_strength'] for p in ps),default=0.0)
            stances=sorted({p['stance'] for p in ps})
            representative=max(ps,key=lambda p:(len(p['source_refs']),p['evidence_strength'],len(p['proposition'])))['proposition']
            nid='clm-'+canonical_hash({'key':key})[:20]
            nodes.append({'claim_id':nid,'proposition_key':key,'representative':representative,'engine_ids':engines,'source_refs':refs,'positions':ps,'stances':stances,'max_evidence_strength':round(max_ev,4)})
        # Similar/source-linked edges are informative, never truth-producing.
        edges=[]
        by_ref=defaultdict(list)
        for n in nodes:
            for r in n['source_refs']: by_ref[r].append(n['claim_id'])
        seen=set()
        for r,ids in by_ref.items():
            ids=sorted(set(ids))
            for i in range(len(ids)):
                for j in range(i+1,len(ids)):
                    k=(ids[i],ids[j],'SHARED_SOURCE_REF')
                    if k not in seen:
                        edges.append({'from':ids[i],'to':ids[j],'kind':'SHARED_SOURCE_REF','source_ref':r}); seen.add(k)
        # Hybrid architecture mixing may add informative graph edges, but never new truth-bearing positions.
        # Claims remain native; the mesh only records that different native claims participate in the
        # same cross-engine research agenda.
        hybrid_edge_count=0
        if hybrid_mesh:
            signal_by_id={x.get('signal_id'):x for x in hybrid_mesh.get('signals',[])}
            node_by_key={n['proposition_key']:n['claim_id'] for n in nodes}
            for a in hybrid_mesh.get('research_agenda',[]):
                ids=[]
                for sid in a.get('claim_links',[]):
                    sig=signal_by_id.get(sid) or {}
                    prop=str((sig.get('payload') or {}).get('proposition') or '')
                    if prop:
                        nid=node_by_key.get(_base_key(prop))
                        if nid: ids.append(nid)
                ids=sorted(set(ids))
                for i in range(len(ids)):
                    for j in range(i+1,len(ids)):
                        k=(ids[i],ids[j],'HYBRID_AGENDA_LINK')
                        if k not in seen:
                            edges.append({'from':ids[i],'to':ids[j],'kind':'HYBRID_AGENDA_LINK','agenda_id':a.get('agenda_id'),'truth_effect':'NONE'}); seen.add(k); hybrid_edge_count+=1
        return {
            'graph_version':'16X-CLAIM-GRAPH-1.2',
            'node_count':len(nodes),'position_count':len(positions),'edge_count':len(edges),
            'nodes':nodes,'edges':edges,'hybrid_agenda_edge_count':hybrid_edge_count,
            'provenance_complete':all(p['engine_id'] for p in positions),
            'claim_ceiling':'CLAIM_GRAPH_PRESERVES_POSITIONS; IT DOES_NOT CONVERT AGGREGATION INTO TRUTH',
            'graph_hash':canonical_hash({'nodes':nodes,'edges':edges}),
        }
