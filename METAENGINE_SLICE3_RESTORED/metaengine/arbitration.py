from __future__ import annotations
from .util import canonical_hash

POS={'SUPPORT','ASSERT','OBSERVE','ACCEPT','PROVISIONAL_SUPPORT'}
NEG={'REJECT','CONTRADICT','DENY'}

class AdaptiveArbitrator:
    """Evidence- and dissent-aware arbitration. Never uses simple majority as truth."""
    def arbitrate(self, claim_graph, disagreements, routing_plan, reviews=None, hybrid_mesh=None):
        conflicts_by_claim={c['claim_id']:c for c in disagreements.get('conflicts',[])}
        decisions=[]
        for n in claim_graph.get('nodes',[]):
            c=conflicts_by_claim.get(n['claim_id'])
            ps=n['positions']; refs=sorted({r for p in ps for r in p.get('source_refs',[])})
            evidence=max((p.get('evidence_strength',0) for p in ps),default=0)
            truth_positions=[p for p in ps if p['stance'] in POS|NEG]
            generative_only=bool(ps) and not truth_positions
            if c and c['kind']=='MATERIAL_STANCE_CONFLICT':
                state='UNRESOLVED_RESEARCH_PRIORITY'
                reason='material_dissent_blocks_promotion_regardless_of_vote_count'
            elif c:
                state='QUALIFIED_UNRESOLVED'
                reason='assertion_uncertainty_requires_targeted_evidence'
            elif generative_only:
                state='GENERATIVE_ONLY'
                reason='no_truth_bearing_position_present'
            elif truth_positions and refs and evidence>=0.65:
                state='PROVISIONALLY_SUPPORTED'
                reason='source_grounded_without_material_dissent'
            elif truth_positions and refs:
                state='SUPPORTED_BUT_REVIEW_REQUIRED'
                reason='source_refs_present_but_evidence_below_promotion_threshold'
            elif truth_positions:
                state='INSUFFICIENT_EVIDENCE'
                reason='truth_bearing_position_without_source_grounding'
            else:
                state='ABSTAIN'
                reason='no_eligible_position'
            decisions.append({
                'claim_id':n['claim_id'],'state':state,'reason':reason,
                'engine_ids':n['engine_ids'],'source_refs':refs,'max_evidence_strength':evidence,
                'disagreement_id':c['disagreement_id'] if c else None,
                'majority_vote_used':False,
            })
        high=[c for c in disagreements.get('conflicts',[]) if c['research_priority']=='HIGH']
        assignments={a['engine_id']:a for a in routing_plan.get('assignments',[])}
        followups=[]
        for c in high:
            candidates=sorted(assignments.values(),key=lambda a:(0 if a['role']=='CHALLENGER' else 1,-a['review_priority'],a['engine_id']))
            followups.append({'disagreement_id':c['disagreement_id'],'objective':'seek discriminating evidence or preserve unresolved rival','priority':'HIGH','engines':[a['engine_id'] for a in candidates[:6]],'stop_condition':'evidence_resolves_dependency_or_abstention_persists'})
        hybrid_followups=[]
        if hybrid_mesh:
            for a in hybrid_mesh.get('research_agenda',[])[:8]:
                if len(a.get('source_engines',[]))>=3:
                    hybrid_followups.append({'agenda_id':a.get('agenda_id'),'objective':'cross-engine discriminate or elaborate agenda item without truth promotion','engines':a.get('source_engines',[])[:8],'truth_status':'GENERATIVE_ONLY'})
        return {
            'arbitration_version':'16X-ADAPTIVE-ARBITRATION-1.2',
            'decision_count':len(decisions),'decisions':decisions,'followup_portfolio':followups,'hybrid_followup_portfolio':hybrid_followups,
            'policy':{'majority_is_not_truth':True,'material_dissent_blocks_promotion':True,'source_grounding_required_for_support':True,'abstention_is_valid':True},
            'arbitration_hash':canonical_hash({'decisions':decisions,'followups':followups,'hybrid_followups':hybrid_followups}),
        }
