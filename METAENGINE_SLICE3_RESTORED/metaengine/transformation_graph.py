from __future__ import annotations
from collections import defaultdict, deque
from .util import canonical_hash

class TransformationGraph:
    def __init__(self):
        self.nodes=[{'node_id':'SOURCE','type':'SOURCE','truth_effect':'PRIMARY_ONLY'}]; self.edges=[]; self._ids={'SOURCE'}; self._last_by_engine={}; self._last_topology=None; self.latest_by_engine={}; self.last_topology=None
    def add_node(self,node_type,label,engine_id=None,round_index=None,metadata=None):
        base={'type':node_type,'label':label,'engine_id':engine_id,'round':round_index,'metadata':metadata or {},'truth_effect':'NONE'}
        nid='tr-'+canonical_hash(base)[:18]
        if nid not in self._ids: self.nodes.append({'node_id':nid,**base}); self._ids.add(nid)
        return nid
    def edge(self,a,b,kind,metadata=None):
        e={'from':a,'to':b,'kind':kind,'metadata':metadata or {},'truth_effect':'NONE'}; sig=canonical_hash(e)
        if all(canonical_hash(x)!=sig for x in self.edges): self.edges.append(e)
    def seed_primary(self,contribs,mesh,disagreements):
        for c in sorted(contribs,key=lambda x:x.engine_id):
            nid=self.add_node('DIAGNOSTIC',f'{c.engine_id}:{c.status}',c.engine_id,0); self.edge('SOURCE',nid,'DIAGNOSES'); self.latest_by_engine[c.engine_id]=nid
        for c in disagreements.get('conflicts',[]):
            nid=self.add_node('CONTRADICTION',c.get('representative','conflict'),None,0,{'disagreement_id':c.get('disagreement_id')}); self.edge('SOURCE',nid,'EXPOSES_TENSION')
        for a in mesh.get('research_agenda',[])[:24]:
            nid=self.add_node('QUESTION',a.get('seed_text','agenda'),None,0,{'agenda_id':a.get('agenda_id')}); self.edge('SOURCE',nid,'GENERATES_QUESTION')
    def add_topology(self,topology_id,round_index,mutation):
        nid=self.add_node('ARCHITECTURE_TOPOLOGY',topology_id,None,round_index,{'mutation':mutation})
        if self._last_topology: self.edge(self._last_topology,nid,'MUTATES_TOPOLOGY')
        else: self.edge('SOURCE',nid,'REORGANIZES_COMPUTATION')
        self._last_topology=nid
        return nid
    def add_deep_result(self,result,round_index,topology_node=None):
        eid=result['engine_id']; root=self.add_node('NATIVE_REENTRY',f'{eid}:{result.get("compiled_mode")}',eid,round_index,{'receipt':result.get('receipt_hash')})
        self.edge('SOURCE',root,'REGROUND_REQUIRED')
        if topology_node: self.edge(topology_node,root,'SCHEDULES')
        prior_self=self._last_by_engine.get(eid)
        if prior_self: self.edge(prior_self,root,'REENTERS_AFTER')
        last=root
        for t in result.get('transformations',[]):
            nid=self.add_node(t['type'],t['label'],eid,round_index,t.get('metadata')); self.edge(root,nid,'TRANSFORMS')
            for src in t.get('peer_sources',[]):
                prior=self._last_by_engine.get(src)
                if prior: self.edge(prior,nid,'CHANGES_SPACE_OF',{'from_engine':src,'to_engine':eid})
                else:
                    pn=self.add_node('PEER_PRESSURE',src,src,max(0,round_index-1)); self.edge(pn,nid,'CHANGES_SPACE_OF',{'from_engine':src,'to_engine':eid})
            last=nid
        self._last_by_engine[eid]=last
        return root
    def metrics(self,unresolved_tensions=0):
        types=sorted({n['type'] for n in self.nodes}); pairs=sorted({(e.get('metadata',{}).get('from_engine'),e.get('metadata',{}).get('to_engine')) for e in self.edges if e.get('metadata',{}).get('from_engine') and e.get('metadata',{}).get('to_engine')})
        # Compute longest acyclic-by-round causal chain. Same/lower round backlinks are not used to inflate depth.
        round_of={n['node_id']:(n.get('round') if n.get('round') is not None else -1) for n in self.nodes}; round_of['SOURCE']=-1
        adj=defaultdict(list)
        for e in self.edges:
            a,b=e['from'],e['to']; ra,rb=round_of.get(a,-1),round_of.get(b,-1)
            if b=='SOURCE': continue
            if rb>=ra: adj[a].append(b)
        dist={'SOURCE':0}; ordered=sorted(self.nodes,key=lambda n:(round_of.get(n['node_id'],-1),n['node_id']))
        for n in ordered:
            a=n['node_id']; base=dist.get(a,0 if a=='SOURCE' else -10**6)
            if base<0: continue
            for b in adj.get(a,[]): dist[b]=max(dist.get(b,-1),base+1)
        return {'node_count':len(self.nodes),'edge_count':len(self.edges),'transformation_types':types,'type_diversity':round(len(types)/18,4),'causal_depth':max(dist.values(),default=0),'source_reground_count':sum(e['kind']=='REGROUND_REQUIRED' for e in self.edges),'peer_pairs':[list(p) for p in pairs],'unresolved_tensions':unresolved_tensions,'cycle_pressure':sum(1 for e in self.edges if e['kind'] in {'CHANGES_SPACE_OF','SELF_REVISION','MUTATES_TOPOLOGY'}),'topology_mutation_edges':sum(e['kind']=='MUTATES_TOPOLOGY' for e in self.edges)}
    def artifact(self,unresolved_tensions=0):
        m=self.metrics(unresolved_tensions); out={'graph_version':'16X-TRANSFORMATION-GRAPH-2.0','nodes':self.nodes,'edges':self.edges,'metrics':m,'claim_ceiling':'TRANSFORMATION_DEPTH_MEASURES_CAUSAL_REORGANIZATION_NOT_TRUTH'}; out['graph_hash']=canonical_hash({k:v for k,v in out.items() if k!='graph_hash'}); return out
