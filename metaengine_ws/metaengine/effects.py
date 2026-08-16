from __future__ import annotations
from collections import defaultdict
from .util import canonical_hash

EFFECTS={
 'E01_CORE4_REFLEXIVE_DESTABILIZATION':{
   'required_engines':{'engine_01','engine_02','engine_03','engine_04'},
   'required_any_types':{'SECOND_ORDER_DESTRUCTION','OPERATOR_ECOLOGY_PROBE','CROSS_LINEAGE_DIFFERENTIAL','COUNTERFACTUAL_GATE'},
   'description':'Core-4 turns peer readings back into frame/operator/semantic/scope problems rather than accepting fusion.'},
 'E02_MEMORY_HYSTERESIS':{
   'required_engines':{'engine_05'},'required_any_types':{'MEMORY_HYSTERESIS_GATE','FORGETTING_AUDIT','CONCEPT_BIOGRAPHY_PROBE'},
   'description':'Past conflicts and discarded branches remain historically retrievable instead of being overwritten by later consensus.'},
 'E03_GRAPH_EVIDENCE_COUPLING':{
   'required_engines':{'engine_06','engine_07'},'required_any_types':{'GRAPH_CROSS_BRANCH_LINK','DISCRIMINATING_TEST','EVIDENCE_CONTRADICTION_PROBE'},
   'description':'Graph structure is used to formulate discriminating evidence tests rather than merely visualize claims.'},
 'E04_HYPOTHESIS_EVIDENCE_TENSION':{
   'required_engines':{'engine_07','engine_15'},'required_any_types':{'HYPOTHESIS_BRANCH_EXPANSION','NEGATIVE_EVIDENCE_REQUEST','NOVELTY_EVIDENCE_TENSION'},
   'description':'Novel branches are preserved only together with explicit tests and negative-evidence requirements.'},
 'E05_ORCHESTRATION_REVERSIBILITY':{
   'required_engines':{'engine_08','engine_11','engine_12'},'required_any_types':{'CRITICAL_POINT_REPLAN','WORKFLOW_ORDER_COUNTERFACTUAL','STATE_BRANCH_REPLAY','CONDITIONAL_ROUTE_ALTERNATIVE'},
   'description':'Planning, workflow order and state transitions become replayable alternatives rather than a single fixed pipeline.'},
 'E06_RESEARCH_ANTI_CLOSURE':{
   'required_engines':{'engine_09','engine_13','engine_14'},'required_any_types':{'RESEARCH_GAP_REOPEN','STOPPING_CRITERION_CHALLENGE','PUBLICATION_WITHHOLD','PERSPECTIVE_EXPANSION','QUESTION_REFRAMING'},
   'description':'Perspective expansion and unresolved gaps can block premature publication/finalization.'},
 'E07_AGENT_SOCIETY_RECOMPOSITION':{
   'required_engines':{'engine_10','engine_08','engine_11'},'required_any_types':{'WORKFORCE_ROLE_MUTATION','DISSENT_AGENT_CREATION','PARALLEL_TASK_RECOMPOSITION'},
   'description':'The agent society is rebuilt around emergent disagreements instead of the initial decomposition.'},
 'E08_OPTIMIZATION_COUNTERFACTUAL_BALANCE':{
   'required_engines':{'engine_16','engine_04','engine_15'},'required_any_types':{'SIGNATURE_MUTATION','OPTIMIZATION_OBJECTIVE_CONFLICT','PARETO_NONDOMINANCE','COUNTERFACTUAL_GATE','NOVELTY_EVIDENCE_TENSION'},
   'description':'Optimization is constrained by counterfactual fragility and rival-preservation rather than a single scalar score.'},
 'E09_SEMANTIC_MEMORY_GRAPH_TRIAD':{
   'required_engines':{'engine_03','engine_05','engine_06'},'required_any_types':{'SEMANTIC_DIFFERENTIAL','CONCEPT_BIOGRAPHY_PROBE','GRAPH_CROSS_BRANCH_LINK'},
   'description':'Semantic differences acquire temporal memory and graph structure, making concept drift and boundary changes traceable.'},
 'E10_ADAPTIVE_RECURSION_STOP':{
   'required_engines':set(),'required_any_types':{'STOPPING_CRITERION_CHALLENGE'},
   'description':'Recursion continues only while a new round changes distinctions, dependencies or decision boundaries.'},
}


def evaluate_useful_effects(polycentric, mesh=None, claim_graph=None):
    positions=[]; engine_types=defaultdict(set); peer_pairs=set()
    for rr in (polycentric or {}).get('rounds',[]):
        for r in rr.get('results',[]):
            eid=r.get('engine_id')
            for p in r.get('generative_positions',[]):
                t=p.get('claim_type')
                if t:engine_types[eid].add(t)
                positions.append((eid,t,p))
                for src in (p.get('metadata') or {}).get('peer_sources',[]) or []:
                    peer_pairs.add((src,eid))
    all_types={t for _,t,_ in positions if t}
    active_engines={e for e,_,_ in positions}
    records=[]
    for effect_id,spec in EFFECTS.items():
        req=spec['required_engines']; tset=spec['required_any_types']
        engine_cov=(len(req & active_engines)/len(req)) if req else 1.0
        type_cov=len(tset & all_types)/max(1,len(tset))
        # Causal peer mixing matters: effects involving multiple engines score higher when peer-return edges exist among them.
        relevant_pairs={(a,b) for a,b in peer_pairs if (not req or (a in req and b in req))}
        possible=max(1,len(req)*(len(req)-1)) if len(req)>1 else 1
        peer_cov=min(1.0,len(relevant_pairs)/possible) if len(req)>1 else (1.0 if peer_pairs else 0.5)
        if effect_id=='E10_ADAPTIVE_RECURSION_STOP':
            pm=(polycentric or {}).get('metrics',{})
            narrowed=any((rr.get('metrics',{}).get('scheduled_engine_count',16)<16) for rr in (polycentric or {}).get('rounds',[])[2:])
            score=1.0 if pm.get('adaptive_stop_used') else (0.72 if narrowed else 0.25)
        else:
            score=round(0.35*engine_cov+0.40*type_cov+0.25*peer_cov,4)
        state='STRONG' if score>=0.72 else ('PRESENT' if score>=0.48 else ('WEAK' if score>=0.28 else 'ABSENT'))
        records.append({'effect_id':effect_id,'state':state,'score':score,'engine_coverage':round(engine_cov,4),'type_coverage':round(type_cov,4),'peer_causal_coverage':round(peer_cov,4),'description':spec['description'],'observed_types':sorted(tset & all_types),'required_engines':sorted(req)})
    strong=sum(r['state']=='STRONG' for r in records); present=sum(r['state'] in ('STRONG','PRESENT') for r in records)
    out={'effect_registry_version':'16X-USEFUL-EFFECTS-1.4','effects':records,'metrics':{'effect_count':len(records),'strong_effects':strong,'present_or_strong_effects':present,'effect_activation_rate':round(present/max(1,len(records)),4),'active_engine_count':len(active_engines),'peer_pair_coverage':len(peer_pairs),'unique_generative_claim_types':len(all_types),'derived_truth_promotion_violations':(polycentric or {}).get('metrics',{}).get('truth_promotion_violations',0)+(mesh or {}).get('metrics',{}).get('derived_truth_promotion_violations',0)},'claim_ceiling':'USEFUL_EFFECTS_ARE_ARCHITECTURAL_AND_PROCEDURAL_OBSERVATIONS_NOT_EXTERNAL_SEMANTIC_VALIDATION'}
    out['effects_hash']=canonical_hash({k:v for k,v in out.items() if k!='effects_hash'})
    return out
