from __future__ import annotations
from pathlib import Path
from collections import defaultdict
from .util import canonical_hash, load_json, write_json

DOMAINS=('PHILOSOPHICAL_HERMENEUTICS','EVIDENCE_RESEARCH','GRAPH_RELATIONAL','MEMORY_LONGITUDINAL','HYPOTHESIS_EXPERIMENT','WORKFLOW_ORCHESTRATION','SEMANTIC_SCOPE','OPTIMIZATION','MULTI_PERSPECTIVE')

class EngineBiographyStore:
    """Persistent empirical biographies, never global authority weights.

    A biography records context-specific marginal usefulness and failure modes.  It is a scheduler
    prior only; it cannot promote a claim or override source-grounded disagreement.
    """
    def __init__(self, root, persist=True):
        self.root=Path(root); self.persist=persist; self.path=self.root/'storage/engine_biographies.json'
        meta=load_json(self.root/'config/meta_engine.json')
        if self.path.exists():
            self.data=load_json(self.path)
        else:
            engines={}
            for e in meta['engines']:
                engines[e['engine_id']]={
                    'engine_id':e['engine_id'],'observations':0,'domains':{},'effects':{},'failure_modes':{},
                    'pair_synergy':{},'mean_realized_gain':0.5,'mean_cost':1.0,'last_runs':[],
                    'claim_ceiling':'SCHEDULER_PRIOR_NOT_EPISTEMIC_AUTHORITY'
                }
            self.data={'biography_version':'16X-ENGINE-BIOGRAPHIES-2.0','engines':engines,'topologies':{},'claim_ceiling':'EMPIRICAL_SPECIALIZATION_MEMORY_NOT_TRUTH_WEIGHT'}
            if self.persist: write_json(self.path,self.data)

    def contextual_prior(self, engine_id, fingerprint):
        b=self.data['engines'][engine_id]; obs=b.get('observations',0)
        active=fingerprint.get('active_domains',[])
        vals=[]
        for d in active:
            rec=b.get('domains',{}).get(d)
            if rec and rec.get('n',0): vals.append(rec.get('mean_gain',0.5))
        learned=sum(vals)/len(vals) if vals else b.get('mean_realized_gain',0.5)
        confidence=min(1.0,obs/24)
        return round(0.5*(1-confidence)+learned*confidence,4)

    def pair_prior(self, engine_id, peers):
        b=self.data['engines'][engine_id]; vals=[]
        for peer in peers or []:
            r=b.get('pair_synergy',{}).get(peer)
            if r and r.get('n',0): vals.append(r.get('mean_gain',0.5))
        return round(sum(vals)/len(vals),4) if vals else 0.5

    def topology_prior(self, topology_id):
        r=self.data.get('topologies',{}).get(topology_id,{})
        return round(r.get('mean_gain',0.5) if r.get('n',0) else 0.5,4)

    def update(self, run_id, fingerprint, scheduler_rounds, useful_effects=None, topology=None):
        active=fingerprint.get('active_domains',[]) or ['MULTI_PERSPECTIVE']
        effect_by_engine=defaultdict(list)
        for e in (useful_effects or {}).get('effects',[]):
            for eid in e.get('engine_ids',[]): effect_by_engine[eid].append(e.get('strength_score',0.0))
        accepted_observations=0
        for rr in scheduler_rounds:
            verified_rows=[rec for rec in rr.get('engine_results',[]) if rec.get('verification_status')=='EXTERNALLY_VERIFIED' and rec.get('observed_outcome') is not None]
            for rec in verified_rows:
                eid=rec['engine_id']; b=self.data['engines'][eid]
                g=float(rec['observed_outcome']); usage=rec.get('actual_usage') or {}; cost=usage.get('cost_usd'); cost=float(cost) if cost is not None else None; n=b.get('observations',0); accepted_observations+=1
                b['observations']=n+1; b['mean_realized_gain']=round((b.get('mean_realized_gain',0.5)*n+g)/(n+1),4)
                if cost is not None: b['mean_cost']=round((b.get('mean_cost',1.0)*n+cost)/(n+1),4)
                for d in active:
                    dr=b.setdefault('domains',{}).setdefault(d,{'n':0,'mean_gain':0.5})
                    dn=dr['n']; dr['n']=dn+1; dr['mean_gain']=round((dr['mean_gain']*dn+g)/(dn+1),4)
                for fx in effect_by_engine.get(eid,[]):
                    er=b.setdefault('effects',{}).setdefault('architectural_effect',{'n':0,'mean':0.0}); en=er['n']; er['n']=en+1; er['mean']=round((er['mean']*en+fx)/(en+1),4)
                if rec.get('status') not in ('COMPLETE','DEEP_COMPLETE'):
                    fm=rec.get('status','UNKNOWN'); b.setdefault('failure_modes',{})[fm]=b.setdefault('failure_modes',{}).get(fm,0)+1
                b.setdefault('last_runs',[]).append({'run_id':run_id,'round':rr.get('round'),'observed_outcome':g,'cost_usd':cost,'verifier_hash':rec.get('verifier_report',{}).get('verifier_hash')})
                b['last_runs']=b['last_runs'][-20:]
            # Pair synergy records context-specific co-selection benefit, never truth authority.
            rows=verified_rows
            for a in rows:
                for z in rows:
                    if a['engine_id']==z['engine_id']: continue
                    b=self.data['engines'][a['engine_id']]; peer=z['engine_id']; gain=min(float(a['observed_outcome']),float(z['observed_outcome']))
                    pr=b.setdefault('pair_synergy',{}).setdefault(peer,{'n':0,'mean_gain':0.5}); pn=pr['n']; pr['n']=pn+1; pr['mean_gain']=round((pr['mean_gain']*pn+gain)/(pn+1),4)
        if topology:
            tid=topology.get('selected_topology_id'); realized=topology.get('observed_outcome')
            if tid and realized is not None:
                r=self.data.setdefault('topologies',{}).setdefault(tid,{'n':0,'mean_gain':0.5}); n=r['n']; r['n']=n+1; r['mean_gain']=round((r['mean_gain']*n+realized)/(n+1),4)
        self.data['last_update_gate']={'accepted_external_observations':accepted_observations,'unverified_observations_ignored':sum(len(rr.get('engine_results',[])) for rr in scheduler_rounds)-accepted_observations,'policy':'ONLY_EXTERNALLY_VERIFIED_OUTCOMES_UPDATE_BIOGRAPHIES'}
        self.data['biography_hash']=canonical_hash({k:v for k,v in self.data.items() if k!='biography_hash'})
        if self.persist: write_json(self.path,self.data)
        return self.snapshot()

    def snapshot(self):
        out={**self.data}; out['biography_hash']=canonical_hash({k:v for k,v in out.items() if k!='biography_hash'}); return out
