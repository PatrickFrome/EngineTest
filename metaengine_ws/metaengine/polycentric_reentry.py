from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy
import json, math, re
from .util import canonical_hash, write_json
from .adapters.base import EngineContribution
from .core4_reentry import _project_core4, _gpos, _tokens, _salient_terms, _sentences, _entropy

ALL16=tuple(f'engine_{i:02d}' for i in range(1,17))

FOCUS={
 'engine_01':'Destabilize frame-atoms and presuppositions; preserve residuals and rival questions.',
 'engine_02':'Mutate operators reversibly; test local operator ecology and retirement conditions.',
 'engine_03':'Protect semantic differentials and detect losses introduced by canonicalization.',
 'engine_04':'Challenge attribution, polarity, scope and parse assumptions counterfactually.',
 'engine_05':'Track concept biography, remembered conflicts, forgetting conditions and path dependence.',
 'engine_06':'Regraph claims and hypotheses; inspect community boundaries and hidden cross-branch edges.',
 'engine_07':'Translate speculative branches into discriminating evidence tests and contradiction checks.',
 'engine_08':'Replan around critical points; delegate dissent and expose planning failure modes.',
 'engine_09':'Reopen research gaps, audit citation dependencies and challenge stopping criteria.',
 'engine_10':'Recompose the agent workforce; create dissent roles and alternate task decompositions.',
 'engine_11':'Counterfactually reorder workflow; test policy gates and sequential/parallel alternatives.',
 'engine_12':'Replay state branches from checkpoints; compare conditional routes and recoverability.',
 'engine_13':'Force planner/executor/editor disagreement; revise and withhold publication under unresolved pressure.',
 'engine_14':'Expand perspectives, regenerate questions and disrupt premature outline closure.',
 'engine_15':'Expand hypothesis branches, reverse pruning and oppose novelty to evidential constraint.',
 'engine_16':'Mutate typed signatures/objectives and preserve Pareto-nondominated rival programs.',
}

# Architecture-specific peer consumption. Round 2+ uses these peers as causal inputs, not just context.
PEER_TARGETS={
 'engine_01':['engine_02','engine_03','engine_04','engine_14'],
 'engine_02':['engine_01','engine_04','engine_07','engine_15','engine_16'],
 'engine_03':['engine_01','engine_04','engine_05','engine_06','engine_14'],
 'engine_04':['engine_01','engine_02','engine_03','engine_07','engine_16'],
 'engine_05':['engine_01','engine_03','engine_07','engine_12','engine_15'],
 'engine_06':['engine_03','engine_07','engine_09','engine_14','engine_15'],
 'engine_07':['engine_02','engine_06','engine_09','engine_15','engine_16'],
 'engine_08':['engine_01','engine_07','engine_09','engine_11','engine_12'],
 'engine_09':['engine_06','engine_07','engine_13','engine_14','engine_15'],
 'engine_10':['engine_08','engine_11','engine_12','engine_14','engine_15'],
 'engine_11':['engine_08','engine_10','engine_12','engine_13','engine_16'],
 'engine_12':['engine_05','engine_08','engine_11','engine_15','engine_16'],
 'engine_13':['engine_07','engine_09','engine_11','engine_14','engine_15'],
 'engine_14':['engine_01','engine_03','engine_09','engine_13','engine_15'],
 'engine_15':['engine_02','engine_04','engine_07','engine_14','engine_16'],
 'engine_16':['engine_04','engine_07','engine_12','engine_13','engine_15'],
}


def _peer_positions(prior_round, engine_id, limit=16):
    if not prior_round:return []
    targets=set(PEER_TARGETS.get(engine_id,[])); out=[]
    for r in prior_round.get('results',[]):
        if r.get('engine_id') not in targets: continue
        for p in r.get('generative_positions',[])[:5]:
            out.append({'engine_id':r['engine_id'],'claim_type':p.get('claim_type'),'proposition':p.get('proposition','')})
    return out[:limit]


def _polypos(engine_id, proposition, round_index, kind, anchors=None, primitive=None, peer_sources=None):
    p=_gpos(engine_id,proposition,round_index,kind,anchors,primitive)
    p['evidence_kind']='POLYCENTRIC_ARCHITECTURE_PROJECTION_DERIVED'
    p['metadata']['polycentric_reentry']=True
    p['metadata']['peer_sources']=sorted(set(peer_sources or []))
    p['claim_ceiling']='SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE'
    return p


def _project_other(engine_id, original_text, mesh, disagreements, prior_round, round_index):
    terms=_salient_terms(original_text,12); sents=_sentences(original_text)
    peers=_peer_positions(prior_round,engine_id); peer_ids=sorted(set(x['engine_id'] for x in peers))
    peer_types=Counter(x['claim_type'] for x in peers if x.get('claim_type'))
    conflicts=(disagreements or {}).get('conflicts',[])[:6]
    agenda=(mesh or {}).get('research_agenda',[])[:12]
    seed=terms[0] if terms else (agenda[0].get('seed_text','problem') if agenda else 'problem')
    out=[]
    if engine_id=='engine_05':
        out.append(_polypos(engine_id,f"Concept-biography probe: preserve how '{seed}' changes across rival readings rather than overwriting earlier states.",round_index,'CONCEPT_BIOGRAPHY_PROBE',terms[:4],'CONCEPT_BIOGRAPHY+PERSISTENT_MEMORY',peer_ids))
        if conflicts or peer_types:
            out.append(_polypos(engine_id,'Memory-hysteresis gate: retain unresolved conflicts and retired alternatives as historical state so later consensus cannot erase the path by which it arose.',round_index,'MEMORY_HYSTERESIS_GATE',terms[:3],'ARCHIVAL_RETRIEVAL+CHECKPOINT_MEMORY',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Forgetting audit: identify which prior branch may be safely compressed and which must remain retrievable because a peer still depends on it.',round_index,'FORGETTING_AUDIT',terms[:3],'PERSISTENT_MEMORY',peer_ids))
    elif engine_id=='engine_06':
        out.append(_polypos(engine_id,f"Graph-topology probe: represent '{seed}' and its rival interpretations as distinct nodes; search for cross-branch edges hidden by linear exposition.",round_index,'GRAPH_CROSS_BRANCH_LINK',terms[:5],'KNOWLEDGE_GRAPH+COMMUNITY_STRUCTURE',peer_ids))
        out.append(_polypos(engine_id,'Community-boundary challenge: test whether the apparent conceptual community is an artifact of shared vocabulary rather than shared inferential role.',round_index,'COMMUNITY_BOUNDARY_CHALLENGE',terms[:4],'COMMUNITY_STRUCTURE+CROSS_LINEAGE_DIFFERENTIAL',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Topology counterexample: add the strongest peer-generated dissent as an edge and test whether community structure changes materially.',round_index,'TOPOLOGY_COUNTEREXAMPLE',terms[:3],'LOCAL_GLOBAL_RETRIEVAL',peer_ids))
    elif engine_id=='engine_07':
        out.append(_polypos(engine_id,'Discriminating-test conversion: turn the strongest rival interpretations into observations that would differentiate them rather than merely restating disagreement.',round_index,'DISCRIMINATING_TEST',terms[:4],'HYPOTHESIS_TESTING+TEST_DESIGN',peer_ids))
        out.append(_polypos(engine_id,'Contradiction audit: search for evidence that simultaneously supports one branch and weakens another; preserve underdetermination if no discriminator exists.',round_index,'EVIDENCE_CONTRADICTION_PROBE',terms[:4],'CONTRADICTION_TRACKING+SCIENTIFIC_EVIDENCE',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Negative-evidence request: identify the observation whose absence would count against the most generatively attractive branch.',round_index,'NEGATIVE_EVIDENCE_REQUEST',terms[:3],'SCIENTIFIC_EVIDENCE',peer_ids))
    elif engine_id=='engine_08':
        out.append(_polypos(engine_id,'Critical-point replan: move unresolved high-tension nodes ahead of low-information synthesis tasks.',round_index,'CRITICAL_POINT_REPLAN',terms[:3],'MANAGER_PLANNER+CRITICAL_POINT_GATE',peer_ids))
        out.append(_polypos(engine_id,'Dissent delegation: assign an independent specialist to attack the current leading architecture instead of optimizing its execution.',round_index,'SPECIALIST_DISAGREEMENT_DELEGATION',terms[:3],'SPECIALIST_DELEGATION',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Context-compaction residue check: before compressing the recursive state, mark differences whose removal would change a peer conclusion.',round_index,'CONTEXT_COMPACTION_RESIDUE',terms[:3],'CONTEXT_COMPACTION',peer_ids))
    elif engine_id=='engine_09':
        out.append(_polypos(engine_id,'Research-gap reopening: treat unresolved cross-engine tensions as active gaps even if a majority already converged.',round_index,'RESEARCH_GAP_REOPEN',terms[:3],'ADAPTIVE_RESEARCH+GAP_TRACKING',peer_ids))
        out.append(_polypos(engine_id,'Citation-dependency probe: map each high-impact derived claim to the primary-source evidence it would need before promotion.',round_index,'CITATION_DEPENDENCY_PROBE',terms[:4],'CITATION_SYNTHESIS',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Stopping-criterion challenge: continue research only if the new round changes a decision boundary, evidence request, or rival reading.',round_index,'STOPPING_CRITERION_CHALLENGE',terms[:3],'ADAPTIVE_RESEARCH',peer_ids))
    elif engine_id=='engine_10':
        out.append(_polypos(engine_id,'Workforce role mutation: create temporary roles around the current disagreement topology rather than preserving the initial agent decomposition.',round_index,'WORKFORCE_ROLE_MUTATION',terms[:3],'DYNAMIC_WORKFORCE+AGENT_SOCIETY',peer_ids))
        out.append(_polypos(engine_id,'Dissent-agent creation: instantiate an adversarial worker whose success criterion is preservation of a neglected alternative.',round_index,'DISSENT_AGENT_CREATION',terms[:3],'AGENT_SOCIETY',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Parallel-task recomposition: regroup tasks according to newly discovered dependencies instead of the original plan tree.',round_index,'PARALLEL_TASK_RECOMPOSITION',terms[:3],'PARALLEL_DELEGATION',peer_ids))
    elif engine_id=='engine_11':
        out.append(_polypos(engine_id,'Workflow-order counterfactual: compare critique-before-synthesis against synthesis-before-critique and preserve order-sensitive outcomes.',round_index,'WORKFLOW_ORDER_COUNTERFACTUAL',terms[:3],'SEQUENTIAL_PARALLEL_COMPOSITION',peer_ids))
        out.append(_polypos(engine_id,'Policy-gate challenge: block transitions that convert generative outputs into asserted claims without an evidence-bearing event.',round_index,'POLICY_GATE_CHALLENGE',terms[:3],'POLICY_GATE',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Sequential/parallel alternative: reroute only dependencies that became serial through the previous round while retaining independent branches in parallel.',round_index,'SEQUENTIAL_PARALLEL_ALTERNATIVE',terms[:3],'MULTI_AGENT_WORKFLOW',peer_ids))
    elif engine_id=='engine_12':
        out.append(_polypos(engine_id,'State-branch replay: checkpoint before a controversial interpretive commitment and replay from an alternate route.',round_index,'STATE_BRANCH_REPLAY',terms[:3],'DURABLE_STATE_GRAPH+CHECKPOINT_RESUME',peer_ids))
        out.append(_polypos(engine_id,'Checkpoint divergence: compare post-checkpoint states and preserve the branch if downstream conclusions materially differ.',round_index,'CHECKPOINT_DIVERGENCE',terms[:3],'THREAD_STATE',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Conditional-route alternative: select the next architecture from unresolved state rather than from the original static workflow.',round_index,'CONDITIONAL_ROUTE_ALTERNATIVE',terms[:3],'CONDITIONAL_ROUTING',peer_ids))
    elif engine_id=='engine_13':
        out.append(_polypos(engine_id,'Planner/executor/editor triangle: require the editor to challenge both the research plan and the executor evidence before publication.',round_index,'PLAN_EXECUTOR_EDITOR_TRIANGLE',terms[:3],'PLANNER_EXECUTOR_EDITOR+REVIEW_REVISION',peer_ids))
        out.append(_polypos(engine_id,'Revision pressure: rewrite the provisional synthesis around the strongest unresolved objection rather than appending a disclaimer.',round_index,'REVISION_PRESSURE',terms[:3],'REVIEW_REVISION',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Publication withhold: do not finalize a claim while its decisive evidence dependency remains missing or scope-contested.',round_index,'PUBLICATION_WITHHOLD',terms[:3],'PUBLICATION',peer_ids))
    elif engine_id=='engine_14':
        out.append(_polypos(engine_id,'Perspective expansion: create a viewpoint that is not reducible to any current cluster and ask what it makes visible or invisible.',round_index,'PERSPECTIVE_EXPANSION',terms[:4],'MULTI_PERSPECTIVE',peer_ids))
        out.append(_polypos(engine_id,'Question reframing: replace a consensus-seeking question with one that discriminates between incompatible interpretations.',round_index,'QUESTION_REFRAMING',terms[:3],'QUESTION_PORTFOLIO',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Outline disruption: reorganize the emerging account around unresolved conceptual tensions rather than the chronology of engine outputs.',round_index,'OUTLINE_DISRUPTION',terms[:3],'OUTLINE_SYNTHESIS',peer_ids))
    elif engine_id=='engine_15':
        out.append(_polypos(engine_id,'Hypothesis-branch expansion: spawn branches from unresolved semantic/operator/scope distinctions, not only from topical variation.',round_index,'HYPOTHESIS_BRANCH_EXPANSION',terms[:4],'HYPOTHESIS_BRANCHING+RESEARCH_TREE',peer_ids))
        out.append(_polypos(engine_id,'Prune reversal: temporarily restore a rejected branch if a later engine introduces evidence or a distinction that changes its failure condition.',round_index,'PRUNE_REVERSAL',terms[:3],'BRANCH_PRUNING',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Novelty/evidence tension: preserve a novel branch only if its discriminating evidence requirements are explicit.',round_index,'NOVELTY_EVIDENCE_TENSION',terms[:3],'NOVELTY_SEARCH+EXPERIMENT_MANAGER',peer_ids))
    elif engine_id=='engine_16':
        out.append(_polypos(engine_id,'Signature mutation: change the program signature when the current output schema collapses an unresolved distinction.',round_index,'SIGNATURE_MUTATION',terms[:3],'TYPED_SIGNATURES',peer_ids))
        out.append(_polypos(engine_id,'Optimization-objective conflict: treat evidence fidelity, rival preservation and compactness as separate objectives rather than a single score.',round_index,'OPTIMIZATION_OBJECTIVE_CONFLICT',terms[:3],'PROGRAM_OPTIMIZATION',peer_ids))
        if round_index>1:
            out.append(_polypos(engine_id,'Pareto nondominance: preserve multiple candidate workflows when no program improves evidence fidelity, dissent retention and complexity simultaneously.',round_index,'PARETO_NONDOMINANCE',terms[:3],'PARETO_SELECTION+TRACE_LEARNING',peer_ids))
    return out[:8]


def _project(engine_id, original_text, mesh, disagreements, prior_round, round_index):
    if engine_id in {'engine_01','engine_02','engine_03','engine_04'}:
        ps=_project_core4(engine_id,original_text,mesh,disagreements,prior_round,round_index)
        for p in ps:
            p['metadata']['polycentric_reentry']=True
            p['metadata']['peer_sources']=sorted(set(x['engine_id'] for x in _peer_positions(prior_round,engine_id)))
        return ps
    return _project_other(engine_id,original_text,mesh,disagreements,prior_round,round_index)


def _lexical_divergence(a,b):
    A=set(_tokens(a)); B=set(_tokens(b)); u=A|B
    return 1-(len(A&B)/len(u) if u else 1.0)


def _round_novelty(current, previous=None):
    if not previous:
        return {'global_novelty':1.0,'type_novelty':1.0,'lexical_novelty':1.0,'peer_uptake':0.0,'per_engine':{r['engine_id']:1.0 for r in current.get('results',[])}}
    prev_by={r['engine_id']:r for r in previous.get('results',[])}
    scores={}; new_types_total=0; type_total=0; lex=[]; peer=[]
    prev_types_global={p.get('claim_type') for r in previous.get('results',[]) for p in r.get('generative_positions',[])}
    cur_types_global={p.get('claim_type') for r in current.get('results',[]) for p in r.get('generative_positions',[])}
    new_types_total=len(cur_types_global-prev_types_global); type_total=max(1,len(cur_types_global))
    for r in current.get('results',[]):
        p=prev_by.get(r['engine_id'],{})
        ct={x.get('claim_type') for x in r.get('generative_positions',[])}
        pt={x.get('claim_type') for x in p.get('generative_positions',[])}
        text=' '.join(x.get('proposition','') for x in r.get('generative_positions',[]))
        ptext=' '.join(x.get('proposition','') for x in p.get('generative_positions',[]))
        tn=len(ct-pt)/max(1,len(ct)); ld=_lexical_divergence(text,ptext)
        cur_peers={src for x in r.get('generative_positions',[]) for src in ((x.get('metadata') or {}).get('peer_sources') or [])}
        prev_peers={src for x in p.get('generative_positions',[]) for src in ((x.get('metadata') or {}).get('peer_sources') or [])}
        pu=len(cur_peers-prev_peers)/max(1,len(cur_peers)) if cur_peers else 0.0
        scores[r['engine_id']]=round(0.35*tn+0.35*ld+0.30*pu,4); lex.append(ld); peer.append(pu)
    type_n=new_types_total/type_total; lex_n=sum(lex)/max(1,len(lex)); peer_u=sum(peer)/max(1,len(peer))
    return {'global_novelty':round(0.35*type_n+0.35*lex_n+0.30*peer_u,4),'type_novelty':round(type_n,4),'lexical_novelty':round(lex_n,4),'peer_uptake':round(peer_u,4),'per_engine':scores}


class PolycentricRecursiveReentry:
    """Runs a provenance-firewalled recursive return across all 16 architectures.

    Rounds 1 and 2 include all sixteen lineages. A third round is optional and admitted only when
    round-2 novelty is above threshold; only the most novelty-producing lineages re-enter round 3.
    No derived output can enter the truth-bearing claim graph.
    """
    def __init__(self,root,adapter_factory):
        self.root=Path(root); self.adapter_factory=adapter_factory
        self.records={r['engine_id']:r for r in json.loads((self.root/'config/meta_engine.json').read_text())['engines']}

    def _dossier(self,original_text,mesh,claim_graph,disagreements,prior_round,engine_id,round_index):
        peers=_peer_positions(prior_round,engine_id,20)
        lines=[
          '# POLYCENTRIC_DERIVED_REENTRY_DOSSIER','',
          '## PROVENANCE FIREWALL',
          'Only ORIGINAL_SOURCE is primary evidence. HYBRID_AGENDA, DISAGREEMENTS and PEER_RETURNS are derived/generative context.',
          'Derived material may change questions, workflows, graphs, memory, hypotheses, operators or parses but may not promote a truth claim without regrounding.',
          '',f'## ROUND {round_index}',f'## ENGINE {engine_id}',f'## ARCHITECTURE_DIRECTIVE\n{FOCUS[engine_id]}','',
          '## ORIGINAL_SOURCE',original_text,'','## HYBRID_AGENDA']
        for a in (mesh or {}).get('research_agenda',[])[:12]:
            lines.append(f"- {a.get('agenda_id')}: {a.get('seed_kind')} :: {a.get('seed_text')} :: sources={','.join(a.get('source_engines',[]))}")
        lines += ['','## DISAGREEMENTS']
        cs=(disagreements or {}).get('conflicts',[])[:8]
        lines += [f"- {c.get('disagreement_id')}: {c.get('kind')} :: {c.get('representative')}" for c in cs] or ['- NONE_MATERIAL_AT_THIS_STAGE']
        lines += ['','## PEER_RETURNS']
        lines += [f"- [{p['engine_id']}] {p['claim_type']}: {p['proposition']}" for p in peers] or ['- NONE_FIRST_ROUND']
        lines += ['','## REQUIRED_BEHAVIOR','- preserve source/derived separation;','- react through the native architectural function of this engine;','- do not reward agreement;','- generate a discriminating transformation or explicit abstention;','- require return to ORIGINAL_SOURCE before promotion.']
        return '\n'.join(lines)+'\n'

    def _downgrade(self,raw,round_index,projected):
        c=deepcopy(raw.canonical or {}); gen=[]
        for p in c.get('claims') or []:
            q=deepcopy(p); q.setdefault('metadata',{})['native_reentry_stance']=q.get('stance'); q['metadata']['reentry_round']=round_index; q['metadata']['polycentric_reentry']=True; q['metadata']['provenance_class']='POLYCENTRIC_DERIVED_REENTRY'
            q['stance']='GENERATIVE_ONLY'; q['force']='GENERATIVE_ONLY'; q['evidence_kind']='DERIVED_REENTRY_NOT_PRIMARY_EVIDENCE'; q['evidence_strength']=min(float(q.get('evidence_strength',0.0)),0.18); q['claim_ceiling']='SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE'; gen.append(q)
        gen.extend(projected); c['claims']=[]; c['polycentric_generative_positions']=gen; c['polycentric_round']=round_index; c['truth_promotion_allowed']=False; c['claim_ceiling']='SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE'
        return EngineContribution(raw.engine_id,raw.status,raw.native,c,raw.error),gen

    def run_round(self,original_input,out_dir,mesh,claim_graph,disagreements,prior_round,round_index,context,selected=None,max_workers=16):
        out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); text=Path(original_input).read_text(errors='ignore')
        selected=tuple(selected or ALL16); jobs={}
        with ThreadPoolExecutor(max_workers=min(max_workers,len(selected))) as pool:
            for eid in selected:
                dossier=self._dossier(text,mesh,claim_graph,disagreements,prior_round,eid,round_index)
                dp=out/eid/'REENTRY_DOSSIER.md'; dp.parent.mkdir(parents=True,exist_ok=True); dp.write_text(dossier)
                jobs[pool.submit(self.adapter_factory(self.records[eid]).run,dp,out/eid/'native_run',{**context,'polycentric_reentry':True,'reentry_round':round_index})]=eid
            results=[]; contribs=[]
            for fut in as_completed(jobs):
                eid=jobs[fut]
                try:raw=fut.result()
                except Exception as e:raw=EngineContribution(eid,'FAILED',{}, {'claims':[]},repr(e))
                projected=_project(eid,text,mesh,disagreements,prior_round,round_index)
                dc,gen=self._downgrade(raw,round_index,projected); contribs.append(dc)
                peer_sources=sorted({s for p in gen for s in ((p.get('metadata') or {}).get('peer_sources') or [])})
                results.append({'engine_id':eid,'status':raw.status,'generative_position_count':len(gen),'generative_positions':gen[:40],'claim_types':sorted({p.get('claim_type') for p in gen if p.get('claim_type')}),'peer_sources':peer_sources,'peer_source_count':len(peer_sources),'native_canonical_keys':sorted((raw.canonical or {}).keys()),'native_error':raw.error})
        artifact={'version':'16X-POLYCENTRIC-REENTRY-1.4','round':round_index,'scheduled_engines':list(selected),'results':sorted(results,key=lambda x:x['engine_id']),'claim_ceiling':'ALL_DERIVED_REENTRY_OUTPUTS_GENERATIVE_ONLY_UNTIL_PRIMARY_SOURCE_REGROUND'}
        artifact['metrics']={'scheduled_engine_count':len(selected),'complete':sum(r['status']=='COMPLETE' for r in results),'generative_positions':sum(r['generative_position_count'] for r in results),'claim_type_count':len({t for r in results for t in r['claim_types']}),'peer_pair_coverage':len({(src,r['engine_id']) for r in results for src in r['peer_sources']}),'all_16_participated':len(selected)==16 and set(selected)==set(ALL16),'truth_promotion_violations':0}
        artifact['round_hash']=canonical_hash({k:v for k,v in artifact.items() if k!='round_hash'}); write_json(out/'POLYCENTRIC_REENTRY_ROUND.json',artifact)
        return artifact,contribs

    def run(self,original_input,out_dir,mesh,claim_graph,disagreements,context,min_rounds=2,max_rounds=3,novelty_threshold=0.22,round3_engine_threshold=0.30):
        out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); rounds=[]; contribs=[]; prior=None; selected=ALL16; stopped='MAX_ROUNDS_REACHED'
        for r in range(1,max_rounds+1):
            if r>min_rounds and not selected: stopped='ADAPTIVE_NOVELTY_STOP'; break
            art,cs=self.run_round(original_input,out/f'round_{r}',mesh,claim_graph,disagreements,prior,r,context,selected=selected)
            novelty=_round_novelty(art,prior); art['novelty']=novelty; write_json(out/f'round_{r}'/'POLYCENTRIC_REENTRY_ROUND.json',art)
            rounds.append(art); contribs.extend(cs)
            if r>=min_rounds:
                if novelty['global_novelty'] < novelty_threshold:
                    selected=(); stopped='ADAPTIVE_NOVELTY_STOP'
                else:
                    ranked=[(score,eid) for eid,score in novelty['per_engine'].items() if score>=round3_engine_threshold]
                    ranked=sorted(ranked,reverse=True)[:8]
                    selected=tuple(sorted(eid for _,eid in ranked))
                    if not selected: stopped='ADAPTIVE_NOVELTY_STOP'
            prior=art
        # Build polycentric return/reground graph.
        nodes=[{'node_id':'ORIGINAL_SOURCE','kind':'PRIMARY_SOURCE'}]; edges=[]; by_round_engine={}
        for rr in rounds:
            for res in rr['results']:
                ids=[]
                for i,p in enumerate(res['generative_positions']):
                    nid='prg-'+canonical_hash({'r':rr['round'],'e':res['engine_id'],'i':i,'p':p.get('proposition','')})[:20]
                    ids.append(nid); nodes.append({'node_id':nid,'kind':'POLYCENTRIC_GENERATIVE_PROBE','round':rr['round'],'engine_id':res['engine_id'],'claim_type':p.get('claim_type'),'truth_effect':'NONE'})
                    edges.append({'from':'ORIGINAL_SOURCE','to':nid,'kind':'PROBLEMATIZES' if rr['round']==1 else 'REGROUND_CONTEXT','truth_effect':'NONE'})
                    edges.append({'from':nid,'to':'ORIGINAL_SOURCE','kind':'REGROUND_REQUIRED','truth_effect':'NONE'})
                by_round_engine[(rr['round'],res['engine_id'])]=ids
        for rr in rounds[1:]:
            prev=rr['round']-1
            for res in rr['results']:
                dstids=by_round_engine.get((rr['round'],res['engine_id']),[])
                if not dstids:continue
                for src in res.get('peer_sources',[]):
                    srcids=by_round_engine.get((prev,src),[])
                    if srcids:edges.append({'from':srcids[0],'to':dstids[0],'kind':'POLYCENTRIC_PEER_RETURN','from_engine':src,'to_engine':res['engine_id'],'truth_effect':'NONE'})
        graph={'graph_version':'16X-POLYCENTRIC-RETURN-GRAPH-1.4','nodes':nodes,'edges':edges,'node_count':len(nodes),'edge_count':len(edges),'reground_required_edges':sum(e['kind']=='REGROUND_REQUIRED' for e in edges),'peer_return_edges':sum(e['kind']=='POLYCENTRIC_PEER_RETURN' for e in edges),'claim_ceiling':'CYCLE_DENSITY_AND_RECURSION_ARE_NOT_TRUTH'}
        graph['graph_hash']=canonical_hash({k:v for k,v in graph.items() if k!='graph_hash'}); write_json(out/'POLYCENTRIC_REENTRY_GRAPH.json',graph)
        summary={'version':'16X-POLYCENTRIC-ADAPTIVE-REENTRY-1.4','rounds':rounds,'graph':{'path':'POLYCENTRIC_REENTRY_GRAPH.json','graph_hash':graph['graph_hash'],'node_count':graph['node_count'],'edge_count':graph['edge_count'],'peer_return_edges':graph['peer_return_edges'],'reground_required_edges':graph['reground_required_edges']},'stop_reason':stopped,'metrics':{'round_count':len(rounds),'all16_rounds':sum(r['metrics']['all_16_participated'] for r in rounds),'total_generative_positions':sum(r['metrics']['generative_positions'] for r in rounds),'unique_claim_types':len({t for r in rounds for res in r['results'] for t in res['claim_types']}),'peer_pair_coverage':len({(src,res['engine_id']) for r in rounds for res in r['results'] for src in res['peer_sources']}),'mean_round_novelty':round(sum(r['novelty']['global_novelty'] for r in rounds)/max(1,len(rounds)),4),'last_round_novelty':rounds[-1]['novelty']['global_novelty'] if rounds else 0,'truth_promotion_violations':0,'adaptive_stop_used':stopped=='ADAPTIVE_NOVELTY_STOP'},'claim_ceiling':'POLYCENTRIC_RECURSION_MEASURES_CROSS_ARCHITECTURE_TRANSFORMATION_NOT_EXTERNAL_PHILOSOPHICAL_CORRECTNESS'}
        summary['reentry_hash']=canonical_hash({k:v for k,v in summary.items() if k!='reentry_hash'}); write_json(out/'POLYCENTRIC_REENTRY.json',summary)
        return summary,contribs
