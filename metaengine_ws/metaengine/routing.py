from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from .util import canonical_hash, load_json

DOMAIN_SIGNALS = {
    'PHILOSOPHICAL_HERMENEUTICS': ['concept','ontology','hermeneut','phenomen','meaning','interpret','being','sein','beyng','heidegger','metaphys','relation','difference','subject','object'],
    'EVIDENCE_RESEARCH': ['evidence','source','citation','paper','study','research','verify','validation','literature','data'],
    'GRAPH_RELATIONAL': ['graph','relation','network','community','entity','edge','link','structure'],
    'MEMORY_LONGITUDINAL': ['memory','history','previous','longitudinal','biography','evolution','trajectory','archive'],
    'HYPOTHESIS_EXPERIMENT': ['hypothesis','experiment','test','counterfactual','branch','novel','prediction'],
    'WORKFLOW_ORCHESTRATION': ['workflow','agent','parallel','orchestrat','planner','delegate','checkpoint','route','task'],
    'SEMANTIC_SCOPE': ['quote','speaker','attribution','negation','modality','scope','pronoun','antecedent','discourse','parse'],
    'OPTIMIZATION': ['optimiz','metric','score','pareto','compile','tune','learn','trace'],
    'MULTI_PERSPECTIVE': ['perspective','rival','alternative','dissent','conflict','disagreement','debate','critique'],
}

CAPABILITY_DOMAIN_HINTS = {
    'PHILOSOPHICAL_HERMENEUTICS': ('FRAME_', 'INTERROGATIVE', 'ECOLOGY', 'OPERATOR', 'EXPERT_CYCLE', 'SEMANTIC_', 'DISCOURSE_', 'SCOPE_', 'PARSE_', 'COUNTERFACTUAL'),
    'EVIDENCE_RESEARCH': ('EVIDENCE', 'SOURCE_', 'LITERATURE', 'CITATION', 'VALIDATION', 'RESEARCH', 'GAP_', 'TEST_'),
    'GRAPH_RELATIONAL': ('GRAPH_', 'COMMUNITY_', 'RELATIONAL', 'CROSS_LINEAGE', 'SHARED_SEMANTIC'),
    'MEMORY_LONGITUDINAL': ('MEMORY', 'ARCHIVAL', 'BIOGRAPHY', 'CHECKPOINT'),
    'HYPOTHESIS_EXPERIMENT': ('HYPOTHESIS', 'EXPERIMENT', 'BRANCH', 'NOVELTY', 'COUNTERFACTUAL', 'TEST_'),
    'WORKFLOW_ORCHESTRATION': ('WORKFLOW', 'PLANNER', 'DELEGATION', 'ROUTING', 'STATE_GRAPH', 'CHECKPOINT', 'WORKFORCE', 'AGENT_'),
    'SEMANTIC_SCOPE': ('SEMANTIC_', 'DISCOURSE_', 'SCOPE_', 'PARSE_', 'COREFERENCE', 'ATTRIBUTION'),
    'OPTIMIZATION': ('OPTIMIZATION', 'PARETO', 'TRACE_', 'COMPILED', 'PROGRAM_'),
    'MULTI_PERSPECTIVE': ('PERSPECTIVE', 'CONTRADICTION', 'RIVAL', 'COMPETITION', 'CRITIQUE', 'DISSENT'),
}

ROLE_THRESHOLDS = ((0.58,'CORE'),(0.36,'SPECIALIST'),(0.20,'CHALLENGER'),(-1.0,'RESERVE_REVIEW'))

class CapabilityRouter:
    """Deterministic routing that never drops a lineage in FULL_16X mode.

    Routing changes responsibility and review depth, not schedule membership.
    """
    def __init__(self, root: Path):
        self.root = Path(root)
        self.meta = load_json(self.root/'config/meta_engine.json')
        self.registry = load_json(self.root/'config/capability_registry.json')
        self.by_engine = {e['engine_id']: e for e in self.meta['engines']}
        self.caps = {}
        for rec in self.registry['capabilities']:
            self.caps.setdefault(rec['provider'], []).append(rec['capability'])

    def fingerprint(self, text: str) -> dict:
        low = text.lower()
        token_count = len(re.findall(r"\w+", text, flags=re.UNICODE))
        scores = {}
        matched = {}
        for domain, terms in DOMAIN_SIGNALS.items():
            hits = [t for t in terms if t in low]
            matched[domain] = hits
            raw = len(hits) / max(2, min(8, len(terms)))
            scores[domain] = round(min(1.0, raw + (0.08 if len(text) > 1200 and hits else 0)), 4)
        active = [d for d,s in sorted(scores.items(), key=lambda kv:(-kv[1],kv[0])) if s > 0]
        if not active:
            active = ['MULTI_PERSPECTIVE']
            scores['MULTI_PERSPECTIVE'] = 0.15
        complexity = min(1.0, 0.12 + token_count/2500 + 0.07*len(active))
        return {
            'task_fingerprint_id':'tfp-'+canonical_hash({'scores':scores,'n':token_count})[:16],
            'token_count': token_count,
            'domain_scores': scores,
            'matched_signals': matched,
            'active_domains': active,
            'complexity': round(complexity,4),
        }

    def _engine_score(self, engine_id: str, fingerprint: dict) -> tuple[float,list[str]]:
        caps = self.caps.get(engine_id, [])
        reasons=[]; total=0.0; denom=0.0
        for domain, ds in fingerprint['domain_scores'].items():
            if ds <= 0: continue
            denom += ds
            hints = CAPABILITY_DOMAIN_HINTS.get(domain, ())
            matches = [c for c in caps if any(h in c for h in hints)]
            if matches:
                coverage = min(1.0, 0.34 + 0.18*len(matches))
                total += ds*coverage
                reasons.append(f"{domain}:{','.join(matches[:3])}")
        rec=self.by_engine[engine_id]
        # Native Destruktion lineages are always relevant as epistemic challengers.
        if engine_id in {'engine_01','engine_02','engine_03','engine_04'}:
            total += 0.12
        # Degraded historical evidence lowers authority but never scheduling.
        if rec.get('native_test',{}).get('failed',0):
            total *= 0.88
            reasons.append('degraded_native_reproducibility_penalty')
        score = total/max(0.55,denom) if denom else total
        return round(min(1.0,score),4), reasons

    def plan(self, input_path: str|Path, mode: str='FULL_16X') -> dict:
        p=Path(input_path); text=p.read_text(errors='ignore')
        fp=self.fingerprint(text)
        assignments=[]
        for eid in sorted(self.by_engine):
            score,reasons=self._engine_score(eid,fp)
            role=next(role for threshold,role in ROLE_THRESHOLDS if score>=threshold)
            assignments.append({
                'engine_id':eid,
                'scheduled':True,
                'role':role,
                'relevance_score':score,
                'review_priority':round(min(1.0,score + (0.18 if role=='CHALLENGER' else 0.06)),4),
                'core4_recursive_reentry':eid in {'engine_01','engine_02','engine_03','engine_04'},
                'capabilities':self.caps.get(eid,[]),
                'reasons':reasons or ['coverage_as_independent_parallel_lineage'],
            })
        # Guarantee challenger diversity even on tightly matched tasks.
        if not any(a['role']=='CHALLENGER' for a in assignments):
            candidates=sorted(assignments,key=lambda a:(a['relevance_score'],a['engine_id']))
            for a in candidates[:2]: a['role']='CHALLENGER'; a['reasons'].append('forced_epistemic_challenger_diversity')
        counts={r:sum(1 for a in assignments if a['role']==r) for r in ('CORE','SPECIALIST','CHALLENGER','RESERVE_REVIEW')}
        return {
            'routing_version':'16X-FRONTIER-EVIDENCE-CONTROL-2.2',
            'mode':mode,
            'all_16_scheduled':len(assignments)==16 and all(a['scheduled'] for a in assignments),
            'task_fingerprint':fp,
            'assignments':assignments,
            'role_counts':counts,
            'invariants':{
                'routing_changes_responsibility_not_membership':True,
                'no_engine_dropped_in_full_16x':True,
                'degraded_lineage_never_silently_promoted':True,
                'engines_01_04_have_priority_for_schema_valid_specialized_reentry':True,
                'all_16_receive_diagnostic_primary':True,
                'deep_rounds_are_expected_gain_and_budget_gated':True,
            },
            'plan_hash':canonical_hash({'mode':mode,'fp':fp,'assignments':assignments}),
        }
