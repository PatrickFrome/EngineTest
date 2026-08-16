from __future__ import annotations
from .util import canonical_hash

TEMPLATES={
 'HERMENEUTIC_AMBIGUITY':['engine_01','engine_03','engine_04','engine_14','engine_05'],
 'EVIDENCE_CONTRADICTION':['engine_07','engine_09','engine_06','engine_15','engine_02'],
 'HYPOTHESIS_EXPLOSION_CONTROL':['engine_15','engine_16','engine_04','engine_08','engine_07'],
 'HISTORICAL_SEMANTIC':['engine_05','engine_06','engine_03','engine_01','engine_14'],
 'WORKFLOW_REORGANIZATION':['engine_08','engine_10','engine_11','engine_12','engine_16'],
 'SOURCE_REGROUNDING':['engine_01','engine_03','engine_04','engine_07','engine_13'],
}
class CoalitionFactory:
    def build(self,routing,disagreements,scheduler_plan):
        active=set(routing['task_fingerprint'].get('active_domains',[])); selected=set(scheduler_plan.get('selected',[])); cs=[]
        names=[]
        if active & {'PHILOSOPHICAL_HERMENEUTICS','SEMANTIC_SCOPE','MULTI_PERSPECTIVE'}: names+=['HERMENEUTIC_AMBIGUITY','SOURCE_REGROUNDING']
        if active & {'EVIDENCE_RESEARCH','GRAPH_RELATIONAL'} or disagreements.get('conflict_count'): names+=['EVIDENCE_CONTRADICTION']
        if 'HYPOTHESIS_EXPERIMENT' in active: names+=['HYPOTHESIS_EXPLOSION_CONTROL']
        if 'MEMORY_LONGITUDINAL' in active: names+=['HISTORICAL_SEMANTIC']
        if 'WORKFLOW_ORCHESTRATION' in active: names+=['WORKFLOW_REORGANIZATION']
        if not names: names=['HERMENEUTIC_AMBIGUITY','EVIDENCE_CONTRADICTION']
        for name in dict.fromkeys(names):
            templ=TEMPLATES[name]; members=[e for e in templ if e in selected]
            if len(members)<3: members=list(dict.fromkeys(members+[e for e in templ if e not in members]))[:5]
            c={'coalition_id':'coal-'+canonical_hash({'name':name,'m':members})[:16],'kind':name,'members':members,'temporary':True,'dissolution_condition':'MARGINAL_GAIN_EXHAUSTED_OR_PROBLEM_RESOLVED','truth_authority':False}
            cs.append(c)
        return {'coalition_version':'16X-TEMPORARY-COALITIONS-2.0','coalitions':cs,'member_union':sorted({e for c in cs for e in c['members']}),'claim_ceiling':'COALITIONS_ORGANIZE_COMPUTATION_NOT_TRUTH'}
