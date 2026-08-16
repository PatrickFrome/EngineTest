from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy
import math, re
from .util import canonical_hash, write_json
from .adapters.base import EngineContribution

CORE4 = ('engine_01','engine_02','engine_03','engine_04')
FOCUS = {
    'engine_01': 'Interrogate frame atoms, exclusions, presuppositions, residuals, and rival questions. Do not close the problem.',
    'engine_02': 'Search for operator insufficiency, rival operator families, reversible mutations, and reasons to abstain or retire an operator.',
    'engine_03': 'Compare semantic boundaries across lineages, detect translation/canonicalization losses, and preserve irreducible differentials.',
    'engine_04': 'Test semantic role, discourse scope, rival parse programs, attribution/polarity, and counterfactual fragility of readings.',
}


def _tokens(s:str):
    return [x.lower() for x in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё][\wÀ-ÖØ-öø-ÿА-Яа-яЁё-]{3,}", s or '', flags=re.UNICODE)]


def _entropy(labels):
    c=Counter(labels); n=sum(c.values())
    if not n or len(c)<=1: return 0.0
    h=-sum((v/n)*math.log(v/n,2) for v in c.values())
    return h/math.log(len(c),2)



def _sentences(text:str):
    xs=[x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text or '') if x.strip()]
    return xs[:24]

def _salient_terms(text:str, limit=10):
    stop={'that','this','with','from','into','only','should','where','while','through','there','their','every','both','does','have','has','were','been','analysis','source','engine','original','derived','context','question','about','whether','develop','identify','build','maintain','preserve','generate','multiple','different','rather','remains','remain'}
    toks=[t for t in _tokens(text) if t not in stop and len(t)>4]
    priority={'relation','relations','difference','differences','ontology','ontological','meaning','being','semantic','social','technological','methodological','historical','hypothesis','hypotheses','evidence','contradiction','memory','concept','interpretation','scope','attribution','graph','community','experiment','counterfactual','dissent','conflict'}
    c=Counter(toks)
    ranked=sorted(c, key=lambda t:(0 if t in priority else 1,-c[t],t))
    return ranked[:limit]

def _gpos(engine_id, proposition, round_index, kind, anchors=None, lineage_primitive=None):
    return {
        'proposition':proposition,
        'proposition_key':None,
        'stance':'GENERATIVE_ONLY','claim_type':kind,'force':'GENERATIVE_ONLY',
        'source_refs':[],'evidence_kind':'CORE4_ARCHITECTURE_PROJECTION_DERIVED',
        'evidence_strength':0.12,
        'claim_ceiling':'SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE',
        'metadata':{'reentry_round':round_index,'provenance_class':'DERIVED_REENTRY_DOSSIER','anchors':anchors or [],'lineage_primitive':lineage_primitive}
    }

def _project_core4(engine_id, original_text, mesh, disagreements, prior_round, round_index):
    sents=_sentences(original_text); terms=_salient_terms(original_text,12)
    agenda=[a.get('seed_text','') for a in mesh.get('research_agenda',[])[:10] if a.get('seed_text')]
    conflicts=[c.get('representative','') for c in disagreements.get('conflicts',[])[:6]]
    prior=[]
    if prior_round:
        for r in prior_round.get('results',[]):
            if r.get('engine_id')!=engine_id:
                prior.extend([p.get('proposition','') for p in r.get('generative_positions',[])[:4]])
    out=[]
    if engine_id=='engine_01':
        anchors=(terms[:4] or agenda[:4])
        for a in anchors[:4]:
            out.append(_gpos(engine_id,f"Frame-atom probe: what is excluded, presupposed, or made invisible when '{a}' becomes the unit of interpretation?",round_index,'INTERROGATIVE_FRAME_ATOM',[a],'FRAME_ATOM+INTERROGATIVE_INDUCTION'))
        if any(re.search(r'\b(not|denies|rival|yet|however|не|отрица)\b',x,re.I) for x in sents):
            out.append(_gpos(engine_id,"Residual probe: preserve the source's negative or rival formulation as a possible irreducible remainder rather than absorbing it into the dominant frame.",round_index,'RESIDUAL_RIVAL_PROBE',terms[:3],'HERMENEUTIC_DESTRUCTION'))
        if prior:
            out.append(_gpos(engine_id,f"Second-order destruction: what common presupposition is shared by these peer returns — {prior[0][:180]} / {prior[1][:180] if len(prior)>1 else 'UNAVAILABLE'}?",round_index,'SECOND_ORDER_DESTRUCTION',terms[:2],'EXPERT_LIVING_DUALITY'))
    elif engine_id=='engine_02':
        candidates=[]
        txt=' '.join(sents).lower()
        if any(w in txt for w in ['relation','depend','difference','связ','отнош','различ']): candidates += ['RELATIONAL_CONSTITUTION','NONREDUCTIVE_DIFFERENCE']
        if any(w in txt for w in ['change','history','early','late','time','измен','истор']): candidates += ['TEMPORAL_TRANSFORMATION']
        if any(w in txt for w in ['evidence','studies','contradict','effect','доказ','исслед']): candidates += ['EVIDENCE_CONFLICT_ECOLOGY']
        if not candidates: candidates=['UNKNOWN_OPERATOR_FAMILY','ABSTAIN_OPERATOR_PRESSURE']
        for c in list(dict.fromkeys(candidates))[:4]:
            out.append(_gpos(engine_id,f"Reversible operator hypothesis: test {c} against the source, while retaining an explicit retirement condition if it collapses a rival distinction.",round_index,'OPERATOR_MUTATION_CANDIDATE',terms[:4], 'OPEN_SET_OPERATOR_BIRTH+REVERSIBLE_MUTATION'))
        if prior:
            out.append(_gpos(engine_id,"Operator-ecology probe: treat disagreement among Core-4 returns as evidence that operator selection itself may be local rather than global.",round_index,'OPERATOR_ECOLOGY_PROBE',terms[:3],'OPERATOR_ECOLOGY'))
    elif engine_id=='engine_03':
        pairs=[]
        if len(terms)>=2:
            for i in range(0,min(6,len(terms)-1),2): pairs.append((terms[i],terms[i+1]))
        for a,b in pairs[:3]:
            out.append(_gpos(engine_id,f"Semantic-boundary differential: do not canonicalize '{a}' and '{b}' into one shared label until their local inferential roles are shown equivalent.",round_index,'SEMANTIC_DIFFERENTIAL',[a,b],'SHARED_SEMANTIC_BOUNDARY+CROSS_LINEAGE_DIFFERENTIAL'))
        if agenda:
            out.append(_gpos(engine_id,f"Canonicalization-loss probe: compare the source term '{terms[0] if terms else agenda[0]}' against the hybrid agenda label '{agenda[0]}' and preserve any residue that the shared schema cannot express.",round_index,'CANONICALIZATION_RESIDUE',terms[:2],'CANONICAL_NORMALIZATION+LINEAGE_FIXITY'))
        if prior:
            out.append(_gpos(engine_id,f"Cross-lineage differential: Core-4 peers generated incompatible descriptive vocabularies; preserve the difference between '{prior[0][:120]}' and '{prior[-1][:120]}' before fusion.",round_index,'CROSS_LINEAGE_DIFFERENTIAL',terms[:2],'CROSS_LINEAGE_DIFFERENTIAL'))
    elif engine_id=='engine_04':
        for sent in sents[:6]:
            low=sent.lower()
            if re.search(r'\b(rival|critics?|argues?|denies?|claims?|according|оппонент|критик|утвержда|отрица)\b',low):
                out.append(_gpos(engine_id,f"Attribution-scope probe: keep this proposition inside a rival/attributed voice unless an explicit authorial reset occurs: {sent[:220]}",round_index,'ATTRIBUTION_SCOPE_PROBE',_salient_terms(sent,4),'SEMANTIC_ROLE+SCOPE_LATTICE'))
            if re.search(r'\b(not|no|never|cannot|may|might|must|should|не|нет|может|долж)\b',low):
                out.append(_gpos(engine_id,f"Polarity/modality parse probe: compare rival scope parses before using this clause as operator evidence: {sent[:220]}",round_index,'SCOPE_LATTICE_PROBE',_salient_terms(sent,4),'SCOPE_LATTICE'))
        if not out:
            out.append(_gpos(engine_id,"Parse-program abstention: no strong attribution/polarity/scope cue is present; do not invent a deep parse solely to increase complexity.",round_index,'PARSE_ABSTENTION',terms[:3],'PARSE_PROGRAM'))
        if prior:
            out.append(_gpos(engine_id,"Counterfactual gate: invert or remove the cue that licenses each peer reading; quarantine any interpretation that survives a structure-changing perturbation unchanged.",round_index,'COUNTERFACTUAL_GATE',terms[:3],'COUNTERFACTUAL_GATE'))
    return out[:8]

class Core4RecursiveReentry:
    """Runs Engines 1–4 again on explicitly DERIVED re-entry dossiers.

    The added material is never treated as primary source evidence. Native outputs from re-entry are
    downgraded to SECOND_ORDER_GENERATIVE and can only create questions, alternatives, return edges,
    and research priorities until independently re-grounded on the original source.
    """
    def __init__(self, root, adapter_factory):
        self.root=Path(root); self.adapter_factory=adapter_factory
        self.records={r['engine_id']:r for r in __import__('json').loads((self.root/'config/meta_engine.json').read_text())['engines']}

    def _dossier(self, original_text, mesh, claim_graph, disagreements, prior_round, engine_id, round_index):
        agenda=mesh.get('research_agenda',[])[:12]
        conflicts=disagreements.get('conflicts',[])[:8]
        prior=[]
        if prior_round:
            for r in prior_round.get('results',[]):
                if r.get('engine_id')!=engine_id:
                    for p in r.get('generative_positions',[])[:6]: prior.append(f"- [{r['engine_id']}] {p.get('proposition','')}")
        lines=[
            '# DERIVED_REENTRY_DOSSIER',
            '',
            '## PROVENANCE FIREWALL',
            'The ORIGINAL_SOURCE block below is the only primary source material.',
            'Everything under HYBRID_AGENDA, DISAGREEMENTS, PRIOR_CORE4_RETURNS, and FOCUS_DIRECTIVE is derived/generative context.',
            'Do not treat derived context as evidence for truth. Use it only to generate rival readings, questions, operator/parse alternatives, and abstentions.',
            '',
            f'## ROUND {round_index}',
            f'## FOCUS_DIRECTIVE {engine_id}',
            FOCUS[engine_id],
            '',
            '## ORIGINAL_SOURCE',
            original_text,
            '',
            '## HYBRID_AGENDA',
        ]
        for a in agenda:
            lines.append(f"- {a.get('agenda_id')}: {a.get('seed_kind')} :: {a.get('seed_text')} :: sources={','.join(a.get('source_engines',[]))}")
        lines += ['', '## DISAGREEMENTS']
        if conflicts:
            for c in conflicts: lines.append(f"- {c.get('disagreement_id')}: {c.get('kind')} :: {c.get('representative')}")
        else: lines.append('- NONE_MATERIAL_AT_THIS_STAGE: search for latent alternatives without inventing contradiction.')
        lines += ['', '## PRIOR_CORE4_RETURNS']
        lines += prior or ['- NONE_FIRST_ROUND']
        lines += ['', '## REQUIRED_REENTRY_BEHAVIOR',
                  '- preserve unresolved rivals when source underdetermines;',
                  '- distinguish source-grounded observation from derived hypothesis;',
                  '- create at least one counter-reading or explicit abstention when warranted;',
                  '- return to ORIGINAL_SOURCE for every discriminating test;',
                  '- do not infer truth from agreement among engines.']
        return '\n'.join(lines)+'\n'

    def _downgrade(self, contribution:EngineContribution, round_index:int, projected_positions=None):
        c=deepcopy(contribution.canonical or {})
        native_claims=c.get('claims') or []
        gen=[]
        for p in native_claims:
            q=deepcopy(p)
            q.setdefault('metadata',{})['native_reentry_stance']=q.get('stance')
            q['metadata']['reentry_round']=round_index
            q['metadata']['provenance_class']='DERIVED_REENTRY_DOSSIER'
            q['stance']='GENERATIVE_ONLY'
            q['force']='GENERATIVE_ONLY'
            q['evidence_kind']='DERIVED_REENTRY_NOT_PRIMARY_EVIDENCE'
            q['evidence_strength']=min(float(q.get('evidence_strength',0.0)),0.2)
            q['claim_ceiling']='SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE'
            gen.append(q)
        gen.extend(projected_positions or [])
        c['claims']=[]  # never enter truth-bearing native claim graph
        c['reentry_generative_positions']=gen
        c['reentry_round']=round_index
        c['truth_promotion_allowed']=False
        c['claim_ceiling']='SECOND_ORDER_GENERATIVE_UNTIL_REGROUNDED_ON_ORIGINAL_SOURCE'
        return EngineContribution(contribution.engine_id, contribution.status, contribution.native, c, contribution.error), gen

    def run_round(self, original_input, out_dir, mesh, claim_graph, disagreements, prior_round, round_index, context, max_workers=4):
        out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
        original_text=Path(original_input).read_text(errors='ignore')
        jobs={}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for eid in CORE4:
                dossier=self._dossier(original_text,mesh,claim_graph,disagreements,prior_round,eid,round_index)
                dp=out/eid/'REENTRY_DOSSIER.md'; dp.parent.mkdir(parents=True,exist_ok=True); dp.write_text(dossier)
                adapter=self.adapter_factory(self.records[eid])
                jobs[pool.submit(adapter.run,dp,out/eid/'native_run',{**context,'reentry_round':round_index,'derived_reentry':True})]=eid
            results=[]; contribs=[]
            for fut in as_completed(jobs):
                eid=jobs[fut]
                try: raw=fut.result()
                except Exception as e: raw=EngineContribution(eid,'FAILED',{}, {'claims':[]},repr(e))
                projected=_project_core4(eid,original_text,mesh,disagreements,prior_round,round_index)
                downgraded,gen=self._downgrade(raw,round_index,projected_positions=projected); contribs.append(downgraded)
                text=' '.join(p.get('proposition','') for p in gen)
                native_intake={'available':False}
                bp=out/eid/'native_run'/'native'/'analysis_bundle.json'
                if bp.exists():
                    try:
                        import json
                        bd=json.loads(bp.read_text())
                        native_intake={'available':True,'bundle_version':bd.get('bundle_version'),'unit_count':bd.get('unit_count',0),'candidate_record_count':bd.get('candidate_record_count',0),'claim_ceiling':bd.get('claim_ceiling')}
                    except Exception:
                        native_intake={'available':False,'parse_error':True}
                results.append({
                    'engine_id':eid,'status':raw.status,'generative_position_count':len(gen),'architecture_projection_count':len(projected),
                    'generative_positions':gen[:32], 'novel_tokens':sorted(set(_tokens(text)))[:80],
                    'native_reentry_intake':native_intake,'native_error':raw.error,
                })
        # Cross-core4 divergence is desirable only as generative multiplicity, never as truth evidence.
        token_sets={r['engine_id']:set(r['novel_tokens']) for r in results}
        pairwise=[]
        for i,a in enumerate(CORE4):
            for b in CORE4[i+1:]:
                A=token_sets.get(a,set()); B=token_sets.get(b,set()); union=A|B
                j=len(A&B)/len(union) if union else 1.0
                pairwise.append({'a':a,'b':b,'lexical_jaccard':round(j,4),'divergence':round(1-j,4)})
        artifact={
            'version':'16X-CORE4-REENTRY-1.3','round':round_index,'results':sorted(results,key=lambda x:x['engine_id']),
            'metrics':{
                'core4_complete':sum(r['status']=='COMPLETE' for r in results),
                'generative_positions':sum(r['generative_position_count'] for r in results),
                'pairwise_mean_divergence':round(sum(x['divergence'] for x in pairwise)/max(1,len(pairwise)),4),
                'engine_output_entropy':round(_entropy([r['engine_id'] for r in results for _ in range(max(1,r['generative_position_count']))]),4),
                'truth_promotion_violations':0,
            },
            'pairwise_core4_divergence':pairwise,
            'claim_ceiling':'DERIVED_REENTRY_OUTPUTS_ARE_SECOND_ORDER_GENERATIVE_NOT_PRIMARY_EVIDENCE',
        }
        artifact['round_hash']=canonical_hash({k:v for k,v in artifact.items() if k!='round_hash'})
        write_json(out/'CORE4_REENTRY_ROUND.json',artifact)
        return artifact, contribs

    def run(self, original_input, out_dir, mesh, claim_graph, disagreements, context, rounds=2):
        previous=None; all_rounds=[]; all_contribs=[]
        current_mesh=mesh; current_graph=claim_graph; current_dis=disagreements
        for r in range(1,rounds+1):
            art,contribs=self.run_round(original_input,Path(out_dir)/f'round_{r}',current_mesh,current_graph,current_dis,previous,r,context)
            all_rounds.append(art); all_contribs.extend(contribs); previous=art
        # Return-edge matrix: each core engine reads outputs from all other core engines on round > 1.
        return_edges=[]
        if rounds>1:
            for dst in CORE4:
                for src in CORE4:
                    if src!=dst:
                        return_edges.append({'from_engine':src,'to_engine':dst,'kind':'CORE4_REENTRY_RETURN','round_from':1,'round_to':2,'truth_effect':'NONE'})
        # Explicit hermeneutic return graph. The cycle closes only as a REGROUND_REQUIRED edge back to
        # the original source; recursive interpretation may deepen a problem but cannot certify itself.
        hnodes=[{'node_id':'ORIGINAL_SOURCE','kind':'PRIMARY_SOURCE'}]; hedges=[]; pos_by_round_engine={}
        for rr in all_rounds:
            for res in rr.get('results',[]):
                ids=[]
                for i,p in enumerate(res.get('generative_positions',[])):
                    nid='hrg-'+canonical_hash({'r':rr['round'],'e':res['engine_id'],'i':i,'p':p.get('proposition','')})[:20]
                    ids.append(nid); hnodes.append({'node_id':nid,'kind':'GENERATIVE_PROBE','round':rr['round'],'engine_id':res['engine_id'],'claim_type':p.get('claim_type'),'proposition':p.get('proposition'),'truth_effect':'NONE'})
                    if rr['round']==1: hedges.append({'from':'ORIGINAL_SOURCE','to':nid,'kind':'PROBLEMATIZES','truth_effect':'NONE'})
                    else: hedges.append({'from':nid,'to':'ORIGINAL_SOURCE','kind':'REGROUND_REQUIRED','truth_effect':'NONE'})
                pos_by_round_engine[(rr['round'],res['engine_id'])]=ids
        if rounds>1:
            for dst in CORE4:
                dstids=pos_by_round_engine.get((2,dst),[])
                for src in CORE4:
                    if src==dst: continue
                    srcids=pos_by_round_engine.get((1,src),[])
                    if srcids and dstids:
                        hedges.append({'from':srcids[0],'to':dstids[0],'kind':'CROSS_ENGINE_RETURN','from_engine':src,'to_engine':dst,'truth_effect':'NONE'})
            # Within-lineage self-return is also explicit, but remains generative.
            for eid in CORE4:
                a=pos_by_round_engine.get((1,eid),[]); b=pos_by_round_engine.get((2,eid),[])
                if a and b: hedges.append({'from':a[0],'to':b[0],'kind':'SELF_REENTRY_TRANSFORMATION','engine_id':eid,'truth_effect':'NONE'})
        hgraph={'graph_version':'16X-HERMENEUTIC-RETURN-GRAPH-1.3','nodes':hnodes,'edges':hedges,'node_count':len(hnodes),'edge_count':len(hedges),'closed_reground_cycles':sum(1 for e in hedges if e['kind']=='REGROUND_REQUIRED'),'claim_ceiling':'CYCLES_REQUIRE_RETURN_TO_PRIMARY_SOURCE; CYCLE_DENSITY_IS_NOT_TRUTH'}
        hgraph['graph_hash']=canonical_hash({k:v for k,v in hgraph.items() if k!='graph_hash'})
        write_json(Path(out_dir)/'HERMENEUTIC_REENTRY_GRAPH.json',hgraph)
        summary={
            'version':'16X-RECURSIVE-HERMENEUTIC-REENTRY-1.3','round_count':rounds,'rounds':all_rounds,'return_edges':return_edges,'hermeneutic_graph':{'path':'HERMENEUTIC_REENTRY_GRAPH.json','graph_hash':hgraph['graph_hash'],'node_count':hgraph['node_count'],'edge_count':hgraph['edge_count'],'closed_reground_cycles':hgraph['closed_reground_cycles']},
            'metrics':{
                'recursive_rounds':rounds,'return_edge_count':len(return_edges),
                'total_generative_positions':sum(x['metrics']['generative_positions'] for x in all_rounds),
                'mean_core4_divergence':round(sum(x['metrics']['pairwise_mean_divergence'] for x in all_rounds)/max(1,len(all_rounds)),4),
                'truth_promotion_violations':0,
                'all_core4_participated_each_round':all(x['metrics']['core4_complete']==4 for x in all_rounds),
                'hermeneutic_cycle_count':hgraph['closed_reground_cycles'],
                'hermeneutic_graph_edges':hgraph['edge_count'],
            },
            'claim_ceiling':'RECURSIVE_REENTRY_MEASURES_GENERATIVE_TRANSFORMATION_NOT_EXTERNAL_SEMANTIC_CORRECTNESS',
        }
        summary['reentry_hash']=canonical_hash({k:v for k,v in summary.items() if k!='reentry_hash'})
        write_json(Path(out_dir)/'CORE4_REENTRY.json',summary)
        return summary,all_contribs
