from __future__ import annotations
from .util import canonical_hash

PREDICTED_COST_UNITS={'engine_01':1.8,'engine_02':1.9,'engine_03':1.6,'engine_04':2.2,'engine_05':0.65,'engine_06':0.9,'engine_07':0.85,'engine_08':0.65,'engine_09':0.8,'engine_10':0.65,'engine_11':0.6,'engine_12':0.55,'engine_13':0.75,'engine_14':0.75,'engine_15':0.85,'engine_16':0.7}

class ExpectedEpistemicGainScheduler:
    def __init__(self, biographies): self.biographies=biographies
    def score(self, assignment, fingerprint, disagreements, round_index=1, seen_engines=None):
        eid=assignment['engine_id']; rel=float(assignment.get('relevance_score',0.0)); prior=self.biographies.contextual_prior(eid,fingerprint)
        tension=float(disagreements.get('max_tension_score',0.0)); conflict_count=disagreements.get('conflict_count',0)
        domains=set(fingerprint.get('active_domains',[])); caps=' '.join(assignment.get('capabilities',[]))
        pressure=0.0
        if conflict_count: pressure+=.22
        if 'SEMANTIC_SCOPE' in domains and any(x in caps for x in ('SEMANTIC','SCOPE','PARSE')): pressure+=.20
        if 'PHILOSOPHICAL_HERMENEUTICS' in domains and eid in {'engine_01','engine_02','engine_03','engine_04'}: pressure+=.24
        if 'EVIDENCE_RESEARCH' in domains and eid in {'engine_06','engine_07','engine_09','engine_13','engine_14'}: pressure+=.16
        if 'MEMORY_LONGITUDINAL' in domains and eid in {'engine_05','engine_06','engine_12'}: pressure+=.15
        if 'HYPOTHESIS_EXPERIMENT' in domains and eid in {'engine_07','engine_15','engine_16','engine_04'}: pressure+=.15
        # Independence is unknown until matched external ablations exist. A neutral prior avoids
        # rewarding an engine merely because the architecture declared it independent.
        independence=.5
        pair_synergy=self.biographies.pair_prior(eid,seen_engines or set())
        novelty=.16 if eid not in (seen_engines or set()) else max(.02,.12/round_index)
        expected=min(1.0,.28*rel+.18*prior+.15*independence+.14*tension+.12*pair_synergy+.13*min(1.0,pressure+novelty))
        cost=PREDICTED_COST_UNITS[eid]
        utility=expected/(.55+cost*.45)
        return {'engine_id':eid,'expected_gain':round(expected,4),'cost_units':cost,'predicted_cost_units':cost,'utility':round(utility,4),'components':{'relevance':rel,'biography_prior':prior,'independence_neutral_prior':independence,'tension':tension,'pressure':round(pressure,4),'pair_synergy':pair_synergy,'novelty':round(novelty,4)},'observed_cost':None}
    def allocate(self, routing, disagreements, budget_units, round_index=1, seen_engines=None, required=None, max_engines=9, excluded=None):
        fp=routing['task_fingerprint']; excluded=set(excluded or []); scored=[self.score(a,fp,disagreements,round_index,seen_engines) for a in routing['assignments'] if a['engine_id'] not in excluded]
        by={x['engine_id']:x for x in scored}; selected=[]; spent=0.0
        required=[e for e in dict.fromkeys(required or []) if e not in excluded and e in by]
        for eid in required:
            x=by[eid]
            if spent+x['cost_units']<=budget_units*1.25: selected.append(x); spent+=x['cost_units']
        for x in sorted(scored,key=lambda z:(-z['utility'],-z['expected_gain'],z['engine_id'])):
            if x in selected or len(selected)>=max_engines: continue
            if spent+x['cost_units']<=budget_units: selected.append(x); spent+=x['cost_units']
        # Preserve independent challenge early, but do not silently blow the deep-compute budget.
        min_engines=4 if round_index==1 else (3 if round_index==2 else 2)
        for x in sorted(scored,key=lambda z:(-z['utility'],z['engine_id'])):
            if len(selected)>=min_engines: break
            if x in selected: continue
            if spent+x['cost_units']<=budget_units*1.10:
                selected.append(x); spent+=x['cost_units']
        plan={'scheduler_version':'16X-PREDICTED-ALLOCATION-2.3','round':round_index,'budget_units':budget_units,'spent_units':round(spent,3),'selected':[x['engine_id'] for x in selected],'scores':scored,'selection':[x for x in selected],'policy':'FULL_16_DIAGNOSTIC_PARTICIPATION_PLUS_SPARSE_DEEP_EXECUTION; PREDICTED_GAIN_AND_COST_ARE_PREEXECUTION_HEURISTICS_NOT_OBSERVED_OUTCOMES'}
        plan['plan_hash']=canonical_hash({k:v for k,v in plan.items() if k!='plan_hash'}); return plan
