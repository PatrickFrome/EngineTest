from __future__ import annotations
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any
import re
from .util import canonical_hash, load_json
from .claims import extract_positions

ENGINE_PRIMITIVES = {
    'engine_01': ['HERMENEUTIC_DESTRUCTION','FRAME_ATOM','INTERROGATIVE_INDUCTION','EXPERT_LIVING_DUALITY'],
    'engine_02': ['OPEN_SET_OPERATOR_BIRTH','REVERSIBLE_MUTATION','OPERATOR_ECOLOGY','FORGETTING'],
    'engine_03': ['SHARED_SEMANTIC_BOUNDARY','CROSS_LINEAGE_DIFFERENTIAL','CANONICAL_NORMALIZATION','LINEAGE_FIXITY'],
    'engine_04': ['SEMANTIC_ROLE','SCOPE_LATTICE','PARSE_PROGRAM','COUNTERFACTUAL_GATE'],
    'engine_05': ['PERSISTENT_MEMORY','ARCHIVAL_RETRIEVAL','CONCEPT_BIOGRAPHY','CHECKPOINT_MEMORY'],
    'engine_06': ['KNOWLEDGE_GRAPH','COMMUNITY_STRUCTURE','LOCAL_GLOBAL_RETRIEVAL','GRAPH_CITATION'],
    'engine_07': ['EVIDENCE_LOOP','HYPOTHESIS_TESTING','TEST_DESIGN','CONTRADICTION_TRACKING'],
    'engine_08': ['MANAGER_PLANNER','SPECIALIST_DELEGATION','CRITICAL_POINT_GATE','CONTEXT_COMPACTION'],
    'engine_09': ['ADAPTIVE_RESEARCH','GAP_TRACKING','TOOL_ROUTING','CITATION_SYNTHESIS'],
    'engine_10': ['DYNAMIC_WORKFORCE','AGENT_SOCIETY','PARALLEL_DELEGATION','WORKER_MEMORY'],
    'engine_11': ['MULTI_AGENT_WORKFLOW','SEQUENTIAL_PARALLEL_COMPOSITION','POLICY_GATE','WORKFLOW_EVENTS'],
    'engine_12': ['DURABLE_STATE_GRAPH','CHECKPOINT_RESUME','CONDITIONAL_ROUTING','THREAD_STATE'],
    'engine_13': ['PLANNER_EXECUTOR_EDITOR','PARALLEL_RESEARCH','REVIEW_REVISION','PUBLICATION'],
    'engine_14': ['MULTI_PERSPECTIVE','QUESTION_PORTFOLIO','OUTLINE_SYNTHESIS','SOURCE_GROUNDED_WRITING'],
    'engine_15': ['RESEARCH_TREE','HYPOTHESIS_BRANCHING','EXPERIMENT_MANAGER','BRANCH_PRUNING','NOVELTY_SEARCH'],
    'engine_16': ['TYPED_SIGNATURES','PROGRAM_OPTIMIZATION','TRACE_LEARNING','PARETO_SELECTION'],
}

# Organs are intentionally overlapping. The point is not lanes but architectural cross-breeding:
# every organ uses primitives originating in multiple otherwise independent lineages.
HYBRID_ORGANS = {
    'SEMANTIC_DISCOVERY_CELL': ['engine_01','engine_02','engine_03','engine_04','engine_13','engine_14'],
    'EVIDENCE_GRAPH_CELL': ['engine_01','engine_03','engine_06','engine_07','engine_09','engine_13','engine_14'],
    'RESEARCH_SOCIETY_CELL': ['engine_05','engine_08','engine_09','engine_10','engine_11','engine_12','engine_13','engine_14'],
    'EVOLUTIONARY_LAB_CELL': ['engine_02','engine_04','engine_07','engine_08','engine_12','engine_15','engine_16'],
    'MEMORY_CONTINUITY_CELL': ['engine_03','engine_05','engine_06','engine_11','engine_12','engine_16'],
    'DIALECTICAL_FUSION_CELL': list(ENGINE_PRIMITIVES),
}

TARGET_CONSUMPTION = {
    'engine_01': ['CLAIM','QUESTION','CONFLICT','GRAPH','BRANCH','MEMORY','REENTRY_PROBE'],
    'engine_02': ['CONFLICT','GAP','BRANCH','PROGRAM','CLAIM','REENTRY_PROBE'],
    'engine_03': ['CLAIM','GRAPH','MEMORY','PLAN','CONFLICT','PROGRAM','REENTRY_PROBE'],
    'engine_04': ['CLAIM','CONFLICT','QUESTION','PROGRAM','BRANCH','REENTRY_PROBE'],
    'engine_05': ['CLAIM','GRAPH','QUESTION','BRANCH','DECISION','PLAN'],
    'engine_06': ['CLAIM','QUESTION','EVIDENCE','MEMORY','GAP','BRANCH'],
    'engine_07': ['CLAIM','EVIDENCE','QUESTION','GAP','BRANCH','CONFLICT'],
    'engine_08': ['QUESTION','GAP','PLAN','CONFLICT','BRANCH','PROGRAM'],
    'engine_09': ['QUESTION','GAP','GRAPH','EVIDENCE','CONFLICT','MEMORY'],
    'engine_10': ['QUESTION','GAP','PLAN','BRANCH','PROGRAM','MEMORY'],
    'engine_11': ['PLAN','QUESTION','BRANCH','PROGRAM','CONFLICT','MEMORY'],
    'engine_12': ['PLAN','BRANCH','PROGRAM','MEMORY','CONFLICT','DECISION'],
    'engine_13': ['QUESTION','EVIDENCE','GRAPH','CONFLICT','PERSPECTIVE','BRANCH'],
    'engine_14': ['PERSPECTIVE','QUESTION','EVIDENCE','GRAPH','CONFLICT','MEMORY'],
    'engine_15': ['QUESTION','GAP','EVIDENCE','CONFLICT','PROGRAM','GRAPH'],
    'engine_16': ['PROGRAM','TRACE','CONFLICT','EVIDENCE','BRANCH','DECISION'],
}


def _text_tokens(text:str):
    return [x.lower() for x in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё][\wÀ-ÖØ-öø-ÿА-Яа-яЁё-]{3,}", text, flags=re.UNICODE)]


def _signal(sig_type, engine_id, payload, truth_status='GENERATIVE_ONLY', source_refs=None, tags=None):
    obj={
        'signal_type':sig_type,
        'source_engine':engine_id,
        'payload':payload,
        'truth_status':truth_status,
        'source_refs':sorted(set(source_refs or [])),
        'tags':sorted(set(tags or [])),
    }
    obj['signal_id']='sig-'+canonical_hash(obj)[:20]
    return obj


def _signals_from_contribution(c):
    eid=c.engine_id; can=c.canonical or {}; out=[]
    # Native Destruktion claims become bounded CLAIM signals. Their original stance is retained.
    for p in extract_positions(c):
        out.append(_signal('CLAIM',eid,{
            'proposition':p['proposition'],'stance':p['stance'],'force':p['force'],
            'evidence_strength':p['evidence_strength'],'claim_type':p['claim_type']
        }, truth_status='NATIVE_POSITION', source_refs=p['source_refs'], tags=['native-position']))
    for p in can.get('reentry_generative_positions',[]) if isinstance(can.get('reentry_generative_positions'),list) else []:
        out.append(_signal('REENTRY_PROBE',eid,{
            'proposition':p.get('proposition',''),'round':(p.get('metadata') or {}).get('reentry_round'),
            'native_reentry_stance':(p.get('metadata') or {}).get('native_reentry_stance'),'claim_type':p.get('claim_type')
        },truth_status='SECOND_ORDER_GENERATIVE',source_refs=[],tags=['core4-reentry','derived-dossier']))
    for p in can.get('polycentric_generative_positions',[]) if isinstance(can.get('polycentric_generative_positions'),list) else []:
        out.append(_signal('REENTRY_PROBE',eid,{
            'proposition':p.get('proposition',''),'round':(p.get('metadata') or {}).get('reentry_round'),
            'native_reentry_stance':(p.get('metadata') or {}).get('native_reentry_stance'),'claim_type':p.get('claim_type'),
            'peer_sources':(p.get('metadata') or {}).get('peer_sources',[])
        },truth_status='SECOND_ORDER_GENERATIVE',source_refs=[],tags=['polycentric-reentry','derived-dossier']))
    for p in can.get('self_organizing_generative_positions',[]) if isinstance(can.get('self_organizing_generative_positions'),list) else []:
        out.append(_signal('REENTRY_PROBE',eid,{
            'proposition':p.get('proposition',''),'round':(p.get('metadata') or {}).get('reentry_round'),
            'claim_type':p.get('claim_type'),'peer_sources':(p.get('metadata') or {}).get('peer_sources',[]),
            'compiled_native_mode':can.get('compiled_native_mode')
        },truth_status='SECOND_ORDER_GENERATIVE',source_refs=[],tags=['self-organizing-reentry','derived-dossier','native-compiled']))
    if eid=='engine_05':
        out.append(_signal('MEMORY',eid,can.get('memory_updates',{}),tags=['persistent']))
    elif eid=='engine_06':
        g=can.get('graph',{})
        for edge in g.get('edges',[])[:64]: out.append(_signal('GRAPH',eid,edge,tags=['graph-edge']))
        if g.get('entities'): out.append(_signal('GRAPH',eid,{'entities':g['entities']},tags=['entity-index']))
    elif eid=='engine_07':
        out.append(_signal('EVIDENCE',eid,can.get('evidence',{}),tags=['evidence-loop']))
    elif eid=='engine_08':
        for p in can.get('plan',{}).get('manager_plan',[]): out.append(_signal('PLAN',eid,p,tags=['manager-plan']))
    elif eid=='engine_09':
        for g in can.get('research',{}).get('research_gaps',[]): out.append(_signal('GAP',eid,{'gap':g},tags=['adaptive-gap']))
    elif eid=='engine_10':
        for t in can.get('workforce',{}).get('workforce_tasks',[]): out.append(_signal('PLAN',eid,t,tags=['workforce-task']))
    elif eid=='engine_11':
        for ev in can.get('workflow',{}).get('events',[]): out.append(_signal('TRACE',eid,ev,tags=['workflow-event']))
    elif eid=='engine_12':
        out.append(_signal('MEMORY',eid,can.get('durable_state',{}),tags=['durable-checkpoint']))
    elif eid=='engine_13':
        for q in can.get('research_pipeline',{}).get('planned_questions',[]): out.append(_signal('QUESTION',eid,{'question':q},tags=['research-question']))
    elif eid=='engine_14':
        for p in can.get('perspectives',{}).get('perspectives',[]): out.append(_signal('PERSPECTIVE',eid,p,tags=['perspective']))
    elif eid=='engine_15':
        for b in can.get('research_tree',{}).get('branch_seeds',[]): out.append(_signal('BRANCH',eid,{'hypothesis':b},tags=['research-branch']))
    elif eid=='engine_16':
        po=can.get('program_optimization',{})
        out.append(_signal('PROGRAM',eid,po,tags=['optimization-program']))
    # Every engine also emits an architecture primitive signal, so its design enters the mesh even
    # when the compact reference run produced no truth-bearing content.
    out.append(_signal('ARCHITECTURE',eid,{'primitives':ENGINE_PRIMITIVES[eid]},tags=['architecture-primitive']))
    return out


def _bridge_mode(source_signal_types, target):
    consumes=set(TARGET_CONSUMPTION[target])
    direct=sorted(set(source_signal_types)&consumes)
    if direct: return 'DIRECT_TYPED_REUSE',direct
    # Complete connectivity is not pretended to be direct semantic compatibility. When types do not
    # match, the target receives a provenance-preserving critique/context projection only.
    return 'CONTEXT_OR_CRITIQUE_PROJECTION',[]


class ArchitectureInterweave:
    """Cross-breeds all 16 architectures without modifying native lineages.

    It creates a typed signal bus, a complete directed bridge matrix (16*15), overlapping hybrid
    organs, and composite traces. Derived artifacts are GENERATIVE_ONLY until independently
    supported by native evidence; mixing is never allowed to manufacture truth.
    """
    def __init__(self,root):
        self.root=Path(root)
        self.cfg=load_json(self.root/'config/meta_engine.json')

    def weave(self, contributions, routing_plan, source_text='', preserve_agenda=None):
        signals=[]
        for c in sorted(contributions,key=lambda x:(x.engine_id,str((x.canonical or {}).get('reentry_round',0)))):
            if c.engine_id in ENGINE_PRIMITIVES:
                signals.extend(_signals_from_contribution(c))
        # Multiple recursive contributions from the same lineage may repeat architecture primitives; dedupe by content hash.
        signals=list({s['signal_id']:s for s in signals}.values())
        signal_types_by_engine=defaultdict(set)
        for s in signals: signal_types_by_engine[s['source_engine']].add(s['signal_type'])
        contributing_engines=set(signal_types_by_engine)

        bridges=[]
        for src in sorted(ENGINE_PRIMITIVES):
            for dst in sorted(ENGINE_PRIMITIVES):
                if src==dst: continue
                mode,direct=_bridge_mode(signal_types_by_engine[src],dst)
                bridge={
                    'from_engine':src,'to_engine':dst,'mode':mode,'direct_signal_types':direct,
                    'source_signal_count':sum(1 for s in signals if s['source_engine']==src),
                    'target_consumes':TARGET_CONSUMPTION[dst],
                    'preserve_source_provenance':True,'truth_promotion_allowed':False,
                }
                bridge['bridge_id']='brg-'+canonical_hash(bridge)[:18]
                bridges.append(bridge)

        # Composite agenda: perspectives + explicit research questions + research gaps.
        perspectives=[s for s in signals if s['signal_type']=='PERSPECTIVE']
        questions=[s for s in signals if s['signal_type']=='QUESTION']
        gaps=[s for s in signals if s['signal_type']=='GAP']
        graph=[s for s in signals if s['signal_type']=='GRAPH']
        evidence=[s for s in signals if s['signal_type']=='EVIDENCE']
        branches=[s for s in signals if s['signal_type']=='BRANCH']
        plans=[s for s in signals if s['signal_type']=='PLAN']
        programs=[s for s in signals if s['signal_type']=='PROGRAM']
        claims=[s for s in signals if s['signal_type']=='CLAIM']
        probes=[s for s in signals if s['signal_type']=='REENTRY_PROBE']
        memory=[s for s in signals if s['signal_type']=='MEMORY']

        source_terms=Counter(_text_tokens(source_text))
        salient=[w for w,_ in sorted(source_terms.items(), key=lambda kv:(-kv[1],kv[0]))[:16]]
        agenda=[]
        seeds=[]
        for p in perspectives[:8]: seeds.append(('PERSPECTIVE',str(p['payload'].get('name','')),p))
        for q in questions[:8]: seeds.append(('QUESTION',str(q['payload'].get('question','')),q))
        for g in gaps[:8]: seeds.append(('GAP',str(g['payload'].get('gap','')),g))
        for rp in probes[:16]: seeds.append(('REENTRY_PROBE',str(rp['payload'].get('proposition','')),rp))
        # Ensure source-driven seeds exist even when a reference adapter is sparse.
        for t in salient[:6]: seeds.append(('SOURCE_TERM',t,None))
        seen=set()
        for kind,text,s in seeds:
            k=text.lower().strip()
            if not k or k in seen: continue
            seen.add(k)
            related_graph=[]
            for gs in graph:
                ps=str(gs['payload']).lower()
                if any(tok in ps for tok in _text_tokens(text)[:3]): related_graph.append(gs['signal_id'])
            related_claims=[]
            for cs in claims:
                prop=str(cs['payload'].get('proposition','')).lower()
                if any(tok in prop for tok in _text_tokens(text)[:3]): related_claims.append(cs['signal_id'])
            related_branches=[]
            for bs in branches:
                hyp=str(bs['payload'].get('hypothesis','')).lower()
                if any(tok in hyp for tok in _text_tokens(text)[:3]): related_branches.append(bs['signal_id'])
            item={
                'agenda_id':'agd-'+canonical_hash({'kind':kind,'text':text})[:18],
                'seed_kind':kind,'seed_text':text,
                'origin_signal_id':s['signal_id'] if s else None,
                'graph_links':related_graph[:8], 'claim_links':related_claims[:8], 'branch_links':related_branches[:8],
                'evidence_slots':[x['signal_id'] for x in evidence[:3]],
                'workflow_plans':[x['signal_id'] for x in plans[:4]],
                'optimization_programs':[x['signal_id'] for x in programs[:2]],
                'memory_context':[x['signal_id'] for x in memory[:3]],
                'truth_status':'GENERATIVE_ONLY',
            }
            item['source_engines']=sorted({
                *([s['source_engine']] if s else []),
                *[next(x['source_engine'] for x in signals if x['signal_id']==sid) for sid in item['graph_links']+item['claim_links']+item['branch_links']+item['evidence_slots']+item['workflow_plans']+item['optimization_programs']+item['memory_context']]
            })
            agenda.append(item)
            agenda_limit=32 if probes else 20
            if len(agenda)>=agenda_limit: break

        # Monotonic mixing invariant: a later recursive weave may add agenda items but must not evict
        # structurally valid agenda items from the immediately preceding architecture state merely
        # because more re-entry probes were generated. Existing items are retained by agenda_id.
        if preserve_agenda:
            merged={a.get('agenda_id'):dict(a) for a in (preserve_agenda.get('research_agenda',[]) or []) if a.get('agenda_id')}
            list_fields=('graph_links','claim_links','branch_links','evidence_slots','workflow_plans','optimization_programs','memory_context','source_engines')
            for a in agenda:
                aid=a.get('agenda_id')
                if aid in merged:
                    z=merged[aid]
                    # Preserve all previous structural links and add new ones; new recursion may enrich but never evict.
                    for f in list_fields:
                        z[f]=sorted(set((z.get(f) or [])+(a.get(f) or [])))
                    for k,v in a.items():
                        if k not in list_fields and k not in z: z[k]=v
                    merged[aid]=z
                else:
                    merged[aid]=a
            agenda=list(merged.values())

        # Research traces explicitly braid mechanisms from all architecture families. Missing links are
        # represented as UNAVAILABLE rather than fabricated content.
        traces=[]
        roles={a['engine_id']:a.get('role') for a in routing_plan.get('assignments',[])}
        for i,a in enumerate(agenda[:12]):
            trace={
                'trace_id':'hyb-'+canonical_hash({'agenda':a['agenda_id'],'i':i})[:18],
                'agenda_id':a['agenda_id'],
                'semantic_discovery':{'engines':['engine_01','engine_02','engine_03','engine_04'],'state':'AVAILABLE'},
                'perspective_questioning':{'engines':['engine_13','engine_14'],'state':'AVAILABLE' if perspectives or questions else 'SPARSE'},
                'evidence_graphing':{'engines':['engine_06','engine_07','engine_09'],'state':'AVAILABLE' if (graph and evidence) else 'SPARSE'},
                'memory_continuity':{'engines':['engine_05','engine_12'],'state':'AVAILABLE' if memory else 'SPARSE'},
                'orchestration_society':{'engines':['engine_08','engine_10','engine_11','engine_12'],'state':'AVAILABLE' if plans else 'SPARSE'},
                'evolutionary_search':{'engines':['engine_02','engine_04','engine_15','engine_16'],'state':'AVAILABLE' if (branches and programs) else 'SPARSE'},
                'review_publication':{'engines':['engine_01','engine_03','engine_07','engine_13','engine_14'],'state':'AVAILABLE'},
                'routing_roles':roles,
                'source_engines':a['source_engines'],
                'truth_status':'GENERATIVE_ONLY_UNTIL_NATIVE_EVIDENCE_GATE',
            }
            trace['cross_family_depth']=sum(1 for v in trace.values() if isinstance(v,dict) and v.get('engines'))
            traces.append(trace)

        organ_records=[]
        for name,members in HYBRID_ORGANS.items():
            member_signals=[s for s in signals if s['source_engine'] in members]
            organ_records.append({
                'organ_id':name,'member_engines':members,'member_count':len(members),
                'primitive_count':sum(len(ENGINE_PRIMITIVES[e]) for e in members),
                'signal_types':sorted({s['signal_type'] for s in member_signals}),
                'signal_count':len(member_signals),
                'all_native_lineages_preserved':True,
            })

        in_degree=Counter(b['to_engine'] for b in bridges); out_degree=Counter(b['from_engine'] for b in bridges)
        direct_bridges=sum(1 for b in bridges if b['mode']=='DIRECT_TYPED_REUSE')
        multi_engine_agenda=sum(1 for a in agenda if len(a['source_engines'])>=3)
        avg_sources=round(sum(len(a['source_engines']) for a in agenda)/max(1,len(agenda)),4)
        trace_complete=sum(1 for t in traces if all(t[k]['state']=='AVAILABLE' for k in ['semantic_discovery','evidence_graphing','memory_continuity','orchestration_society','evolutionary_search']))
        metrics={
            'engine_coverage':len(contributing_engines),
            'directed_pairwise_bridges':len(bridges),
            'active_directed_pairwise_bridges':sum(1 for b in bridges if b['source_signal_count']>0),
            'expected_directed_pairwise_bridges':16*15,
            'architecture_primitive_instances':sum(len(v) for v in ENGINE_PRIMITIVES.values()),
            'direct_typed_reuse_bridges':direct_bridges,
            'context_or_critique_bridges':len(bridges)-direct_bridges,
            'min_in_degree':min(in_degree.values(),default=0),'max_in_degree':max(in_degree.values(),default=0),
            'min_out_degree':min(out_degree.values(),default=0),'max_out_degree':max(out_degree.values(),default=0),
            'hybrid_organs':len(organ_records),
            'signal_count':len(signals),'signal_type_count':len({s['signal_type'] for s in signals}),'reentry_probe_signals':len(probes),
            'agenda_items':len(agenda),'multi_engine_agenda_items':multi_engine_agenda,'avg_source_engines_per_agenda_item':avg_sources,
            'cross_architecture_traces':len(traces),'full_five_layer_trace_count':trace_complete,
            'derived_truth_promotion_violations':sum(1 for a in agenda if a['truth_status']!='GENERATIVE_ONLY') + sum(1 for t in traces if not str(t['truth_status']).startswith('GENERATIVE_ONLY')),
            'all_16_have_15_incoming_and_outgoing_bridges':all(in_degree[e]==15 and out_degree[e]==15 for e in ENGINE_PRIMITIVES),
        }
        result={
            'mesh_version':'16X-SELF-REORGANIZING-INTERWOVEN-ARCHITECTURE-2.0',
            'principle':'NATIVE_LINEAGES_IMMUTABLE; ARCHITECTURES_CROSS_BRED_THROUGH_TYPED_SHARED_STATE; MIXING_CANNOT_CREATE_TRUTH',
            'engine_primitives':ENGINE_PRIMITIVES,'hybrid_organs':organ_records,'signals':signals,
            'pairwise_bridges':bridges,'research_agenda':agenda,'cross_architecture_traces':traces,'metrics':metrics,
            'claim_ceiling':'SELF_REORGANIZING_STRUCTURAL_INTEGRATION_NOT_EXTERNAL_QUALITY_VALIDATION',
        }
        result['mesh_hash']=canonical_hash({k:v for k,v in result.items() if k!='mesh_hash'})
        return result
