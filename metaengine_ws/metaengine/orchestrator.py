from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from .util import canonical_hash,new_id,write_json,load_json
from .storage import LocalLedger
from .fusion import fuse
from .routing import CapabilityRouter
from .claims import ClaimGraphBuilder
from .disagreement import DisagreementEngine
from .arbitration import AdaptiveArbitrator
from .hybrid_mesh import ArchitectureInterweave
from .adapters.node_native import NodeNativeAdapter
from .adapters.reference import ReferenceAdapter
from .adapters.base import EngineContribution
from .adapters.registry import AdapterRegistry
from .biographies import EngineBiographyStore
from .epistemic_gain import ExpectedEpistemicGainScheduler
from .coalitions import CoalitionFactory
from .topology import ProductiveTopologyLibrary
from .architecture_evolution import ArchitectureEvolutionEngine
from .depth_budget import DepthBudgetController
from .transformation_graph import TransformationGraph
from .native_reentry_compiler import NativeReentryCompiler
from .state_cache import TypedStateCache
from .ecology_effects import evaluate_ecology_effects
from .self_organizing_metrics import evaluate_self_organization
from .frontier_control_plane import FrontierControlPlane
from .architecture_policy import ArchitecturePolicy,PolicyStore
from .dialectical_graph import DialecticalGraphBuilder
from .security import IMMUTABLE_GUARDRAIL_HASH,classify_untrusted_input
from .synthesis import AuditableSynthesizer
from .telemetry import TelemetryLedger
from .verifier_plane import ExternalVerifierPlane

class MetaOrchestrator:
    """METAENGINE 2.3: outcome-gated ecology under an immutable evidence boundary."""
    def __init__(self,root,persist_biographies=True):
        self.root=Path(root); self.cfg=load_json(self.root/'config/meta_engine.json')
        self.persist_biographies=persist_biographies
        self.router=CapabilityRouter(self.root); self.claims=ClaimGraphBuilder(); self.disagreements=DisagreementEngine(); self.arbitrator=AdaptiveArbitrator(); self.interweave=ArchitectureInterweave(self.root); self.adapter_registry=AdapterRegistry()
        self.biographies=EngineBiographyStore(self.root,persist=persist_biographies); self.scheduler=ExpectedEpistemicGainScheduler(self.biographies); self.coalitions=CoalitionFactory(); self.topologies=ProductiveTopologyLibrary(self.biographies); self.evolution=ArchitectureEvolutionEngine(self.topologies); self.compiler=NativeReentryCompiler(self.root,self._adapter)
        self.policy_store=PolicyStore(self.root); self.verifier=ExternalVerifierPlane(); self.dialectical=DialecticalGraphBuilder()
    def _adapter(self,rec):
        lr=self.root/'lineages'/rec['engine_id']
        return self.adapter_registry.create(rec,lr)
    def _run_primary(self,inp,out,ctx,routing,ledger,state,max_workers):
        state['barrier']='PARALLEL_DIAGNOSTIC_PRIMARY'; write_json(out/'META_RUN.json',state)
        assignment={a['engine_id']:a for a in routing['assignments']}; contribs=[]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs={pool.submit(self._adapter(rec).run,inp,out/'engines'/rec['engine_id'],ctx):rec for rec in self.cfg['engines'] if assignment[rec['engine_id']]['scheduled']}
            for fut in as_completed(futs):
                rec=futs[fut]
                try:c=fut.result()
                except Exception as e:c=EngineContribution(rec['engine_id'],'FAILED',{}, {},repr(e))
                contribs.append(c); state['engine_states'][c.engine_id]={'status':c.status,'role':assignment[c.engine_id]['role'],'canonical':c.canonical,'error':c.error}
                write_json(out/'engines'/c.engine_id/'CONTRIBUTION.json',{'engine_id':c.engine_id,'status':c.status,'routing':assignment[c.engine_id],'native':c.native,'canonical':c.canonical,'error':c.error,'adapter_kind':c.adapter_kind,'implementation_level':c.implementation_level,'candidate_outputs':c.candidate_outputs,'evidence_refs':c.evidence_refs,'execution_trace':c.execution_trace,'usage':c.usage,'provenance':c.provenance})
                ledger.append(ctx['meta_run_id'],'ENGINE_DIAGNOSTIC_COMPLETE',{'status':c.status,'role':assignment[c.engine_id]['role'],'error':c.error},c.engine_id)
        return sorted(contribs,key=lambda x:x.engine_id)
    def _pressures(self,engine_id,mesh,disagreements,prior_results,tgraph,topology):
        p=[]
        for c in disagreements.get('conflicts',[])[:6]: p.append(f"conflict:{c.get('kind')}:{c.get('representative')}")
        for a in mesh.get('research_agenda',[])[:8]: p.append(f"agenda:{a.get('seed_kind')}:{a.get('seed_text')}")
        for rr in (prior_results or [])[-12:]:
            if rr.get('engine_id')!=engine_id:
                for t in rr.get('transformations',[])[:2]: p.append(f"{rr.get('engine_id')}:{t.get('type')}:{t.get('label')}")
        p.append(f"topology:{topology.get('selected_topology_id')}")
        tm=tgraph.metrics(disagreements.get('conflict_count',0))
        for t in tm.get('transformation_types',[])[-8:]: p.append(f"transformation_type:{t}")
        return p[:28]
    def run(self,input_path,out_dir,max_workers=16,experiment_policy=None):
        experiment_policy=dict(experiment_policy or {}); disabled=set(experiment_policy.get('disabled_engines',[])); inp=Path(input_path).resolve(); out=Path(out_dir); out.mkdir(parents=True,exist_ok=False)
        supplied_policy=experiment_policy.get('architecture_policy'); active_policy=ArchitecturePolicy.from_dict(supplied_policy) if supplied_policy else self.policy_store.active()
        data=inp.read_bytes(); source_text=inp.read_text(errors='ignore'); source_sha256=hashlib.sha256(data).hexdigest(); input_hash=canonical_hash({'bytes_sha256':source_sha256}); run_id=new_id('meta23'); ledger=LocalLedger(out/'ledger'); telemetry=TelemetryLedger(run_id); input_security=classify_untrusted_input(source_text); write_json(out/'INPUT_SECURITY_CLASSIFICATION.json',input_security)
        routing=self.router.plan(inp,'PARALLEL_EXPERIMENT_WORLD' if experiment_policy else 'FULL_16_DIAGNOSTIC_SPARSE_DEEP_SELF_ORGANIZING')
        if disabled:
            for a in routing['assignments']:
                if a['engine_id'] in disabled:
                    a['scheduled']=False; a['role']='EXPERIMENTALLY_ABLATED'; a['reasons'].append('parallel_experiment_ablation')
            routing['all_16_scheduled']=False
            routing['experimental_disabled_engines']=sorted(disabled)
            routing['plan_hash']=canonical_hash({k:v for k,v in routing.items() if k!='plan_hash'})
        write_json(out/'ROUTING_PLAN.json',routing)
        ctx={'meta_run_id':run_id,'input_hash':input_hash,'source_sha256':source_sha256,'engine_timeout':600,'routing_plan':routing,'experiment_policy':experiment_policy,'architecture_policy_hash':active_policy.policy_hash,'guardrail_hash':IMMUTABLE_GUARDRAIL_HASH,'verifier_version':'16X-EXTERNAL-OUTCOME-VERIFIER-2.3'}
        state={'meta_run_id':run_id,'engine_version':'2.3.0-alpha.1','input_hash':input_hash,'status':'RUNNING','barrier':'CAPABILITY_ROUTING','engine_states':{},'fusion':None,'claim_ceiling':'NATIVE_CLAIM_CEILINGS_PRESERVED','routing_plan_hash':routing['plan_hash'],'architecture_policy_hash':active_policy.policy_hash,'coordination':{}}
        write_json(out/'META_RUN.json',state); write_json(out/'ACTIVE_ARCHITECTURE_POLICY.json',active_policy.as_dict()); ledger.append(run_id,'RUN_STARTED',{'input_hash':input_hash,'engine_count':16-len(disabled),'controlled_policy_learning':True,'frontier_control_plane':True,'experimental_world':bool(experiment_policy),'disabled_engines':sorted(disabled),'architecture_policy_hash':active_policy.policy_hash}); telemetry.record('RUN_STARTED',architecture_policy_hash=active_policy.policy_hash)

        primary=self._run_primary(inp,out,ctx,routing,ledger,state,max_workers)
        state['barrier']='PRIMARY_INTERWEAVE'; write_json(out/'META_RUN.json',state)
        mesh=self.interweave.weave(primary,routing,source_text); write_json(out/'HYBRID_MESH_PRIMARY.json',mesh)
        graph=self.claims.build(primary,hybrid_mesh=mesh); write_json(out/'CLAIM_GRAPH_PRIMARY.json',graph)
        disagreement=self.disagreements.analyze(graph,routing,hybrid_mesh=mesh); write_json(out/'DISAGREEMENT_MAP_PRIMARY.json',disagreement)
        primary_arbitration=self.arbitrator.arbitrate(graph,disagreement,routing,[],hybrid_mesh=mesh); write_json(out/'ARBITRATION_PRIMARY.json',primary_arbitration)
        primary_fusion=fuse(primary); write_json(out/'PRIMARY_FUSION.json',primary_fusion)
        primary_snapshot={'claim_nodes':graph['node_count'],'claim_positions':graph['position_count'],'claim_edges':graph['edge_count'],'conflicts':disagreement['conflict_count'],'mesh_hash':mesh['mesh_hash']}; write_json(out/'PRIMARY_TRUTH_BEARING_SNAPSHOT.json',primary_snapshot)

        frontier=FrontierControlPlane(self.root)
        task_ledger=frontier.create_task_ledger(routing,disagreement,mesh,input_hash,{c.engine_id:c.status for c in primary})
        write_json(out/'frontier_control_plane'/'TASK_LEDGER.json',task_ledger)
        ledger.append(run_id,'FRONTIER_TASK_LEDGER_CREATED',{'task_ledger_hash':task_ledger['task_ledger_hash'],'workstream_count':len(task_ledger['workstreams']),'unknown_count':len(task_ledger['unknowns'])})

        tg=TransformationGraph(); tg.seed_primary(primary,mesh,disagreement); depth=DepthBudgetController(routing['task_fingerprint']['complexity']); cache_root=(out/'_typed_state_cache') if experiment_policy.get('cache_mode','shared')=='isolated' else (self.root/'storage/typed_state_cache'); cache=TypedStateCache(cache_root)
        scheduler_rounds=[]; architecture_history=[]; all_deep=[]; deep_contribs=[]; previous_metrics=None; previous_evolution=None; previous_results=[]; seen=set(); stop_reason='STOP_MAX_DEPTH_SAFETY'; last_coalitions={'coalitions':[]}; disagreement_reorganizations=0
        max_rounds=int(experiment_policy.get('max_rounds',active_policy.max_rounds))
        for round_index in range(1,max_rounds+1):
            state['barrier']=f'SELF_ORGANIZING_ROUND_{round_index}'; write_json(out/'META_RUN.json',state)
            budget=depth.next_budget(round_index)
            active_domains=set(routing['task_fingerprint'].get('active_domains',[]))
            core_required=[]
            if active_domains & {'PHILOSOPHICAL_HERMENEUTICS','SEMANTIC_SCOPE'}:
                core_required=['engine_01','engine_03','engine_04'] + (['engine_02'] if round_index>1 else [])
            frontier_required=frontier.required_engines(round_index,seen,disabled)
            core_required=list(dict.fromkeys(core_required+frontier_required))
            provisional=self.scheduler.allocate(routing,disagreement,budget,round_index,seen_engines=seen,required=core_required,max_engines=int(experiment_policy.get('max_deep_engines',active_policy.max_deep_engines)),excluded=disabled)
            evo=self.evolution.select(routing,disagreement,provisional,previous_evolution)
            forced=experiment_policy.get('forced_topology_id') or active_policy.topology_id
            if forced:
                match=next((c for c in evo['candidates'] if c['topology_id']==forced),None)
                if match:
                    evo=dict(evo); evo['selected_topology_id']=forced; evo['selected']=match; evo['mutation']='FORCED_EXPERIMENTAL_TOPOLOGY'; evo['architecture_hash']=canonical_hash({k:v for k,v in evo.items() if k!='architecture_hash'})
            if evo['mutation']=='MUTATE_TOPOLOGY_UNDER_DISAGREEMENT': disagreement_reorganizations+=1
            wave=evo['selected']['waves'][min(round_index-1,len(evo['selected']['waves'])-1)]
            required=list(wave)
            active=set(routing['task_fingerprint'].get('active_domains',[]))
            if round_index==1 and active & {'PHILOSOPHICAL_HERMENEUTICS','SEMANTIC_SCOPE'}:
                required=list(dict.fromkeys(['engine_01','engine_02','engine_03','engine_04']+required))
            final_sched=self.scheduler.allocate(routing,disagreement,budget,round_index,seen_engines=seen,required=required,max_engines=int(experiment_policy.get('max_deep_engines',active_policy.max_deep_engines)),excluded=disabled)
            coal=self.coalitions.build(routing,disagreement,final_sched); last_coalitions=coal
            frontier_plan=frontier.plan_round(round_index,final_sched,evo,input_hash)
            write_json(out/'frontier_control_plane'/f'ROUND_{round_index}_PLAN.json',frontier_plan)
            ledger.append(run_id,'FRONTIER_ROUND_PLANNED',{'round':round_index,'round_plan_hash':frontier_plan['round_plan_hash'],'handoff_count':len(frontier_plan['handoffs']),'replan_from_previous':frontier_plan['replan_from_previous']})
            topo_node=tg.add_topology(evo['selected_topology_id'],round_index,evo['mutation'])
            for c in coal['coalitions']:
                cn=tg.add_node('COALITION',c['kind'],None,round_index,{'members':c['members']}); tg.edge(topo_node,cn,'INSTANTIATES_COALITION')

            results=[]; round_contribs=[]; live_results=[]
            handoffs_by_engine={handoff['engine_id']:handoff for handoff in frontier_plan.get('handoffs',[])}
            selected_set=set(final_sched['selected'])
            execution_batches=[]
            for w in evo['selected'].get('waves',[]):
                batch=[eid for eid in w if eid in selected_set and all(eid not in b for b in execution_batches)]
                if batch: execution_batches.append(batch)
            remainder=[eid for eid in final_sched['selected'] if all(eid not in b for b in execution_batches)]
            if remainder: execution_batches.append(remainder)
            for batch_index,batch in enumerate(execution_batches,1):
                batch_results=[]
                with ThreadPoolExecutor(max_workers=min(max_workers,max(1,len(batch)))) as pool:
                    futs={}
                    for eid in batch:
                        pressures=self._pressures(eid,mesh,disagreement,previous_results+live_results,tg,evo)+frontier.pressure_lines(eid,frontier_plan)
                        handoff=handoffs_by_engine.get(eid)
                        key=cache.key(eid,input_hash,pressures,evo['selected_topology_id'],round_index,handoff=handoff,policy_hash=active_policy.policy_hash,adapter_snapshot=self._adapter(next(rec for rec in self.cfg['engines'] if rec['engine_id']==eid)).record.get('source_archive_sha256'),verifier_hash=ctx['verifier_version'],guardrail_hash=IMMUTABLE_GUARDRAIL_HASH); cached=cache.get(key)
                        if cached:
                            can=cached['canonical']; c=EngineContribution(eid,'DEEP_COMPLETE',{'cache_reuse':True},can,None); receipt=cached['receipt']; batch_results.append((c,receipt,True)); round_contribs.append(c)
                        else:
                            run_ctx={**ctx,'round_plan_hash':frontier_plan['round_plan_hash']}
                            futs[pool.submit(self.compiler.execute,inp,out/'deep_reentry'/f'round_{round_index}'/eid,eid,round_index,pressures,evo,coal,run_ctx,handoff)]=(eid,key)
                    for fut in as_completed(futs):
                        eid,key=futs[fut]
                        try:c,receipt=fut.result()
                        except Exception as e:
                            c=EngineContribution(eid,'FAILED',{}, {'claims':[],'self_organizing_generative_positions':[]},repr(e)); receipt={'engine_id':eid,'round':round_index,'compiled_mode':'FAILED','transformations':[],'receipt_hash':canonical_hash({'e':eid,'r':round_index,'err':repr(e)})}
                        cache.put(key,{'canonical':c.canonical,'receipt':receipt}); batch_results.append((c,receipt,False)); round_contribs.append(c)
                for c,receipt,cached in sorted(batch_results,key=lambda x:x[0].engine_id):
                    receipt=dict(receipt); receipt['execution_batch']=batch_index
                    live_results.append({'engine_id':c.engine_id,'transformations':receipt.get('transformations',[])})
                    results.append((c,receipt,cached))

            engine_rows=[]
            for c,receipt,cached in sorted(results,key=lambda x:(x[1].get('execution_batch',999),x[0].engine_id)):
                tg.add_deep_result({'engine_id':c.engine_id,'compiled_mode':receipt.get('compiled_mode'),'receipt_hash':receipt.get('receipt_hash'),'transformations':receipt.get('transformations',[])},round_index,topology_node=topo_node)
                spec=receipt.get('specialized_native') or {}; spec_executed=spec.get('exit_code') in (0,1,3) if spec else False; spec_ok=spec.get('exit_code')==0 if spec else False; spec_abstained=spec.get('exit_code') in (1,3) if spec else False
                expected=next((x['expected_gain'] for x in final_sched['selection'] if x['engine_id']==c.engine_id),None); cost=next((x['cost_units'] for x in final_sched['selection'] if x['engine_id']==c.engine_id),None)
                verified=self.verifier.evaluate(source_text,{'source_id':input_hash,'transformations':receipt.get('transformations',[])},None,receipt.get('guardrail_receipt'),receipt.get('usage'))
                verifier_report=verified.as_dict(); write_json(out/'verifier_plane'/f'round_{round_index}'/f'{c.engine_id}.json',verifier_report)
                row={'engine_id':c.engine_id,'status':c.status,'adapter_kind':c.adapter_kind,'implementation_level':c.implementation_level,'compiled_mode':receipt.get('compiled_mode'),'specialized_native_success':spec_ok,'specialized_native_executed':spec_executed,'specialized_native_abstained':spec_abstained,'cache_reused':cached,'transformations':receipt.get('transformations',[]),'source_reground_required':bool(receipt.get('source_reground_required',True)),'truth_promotion_allowed':bool(receipt.get('truth_promotion_allowed',False)),'predicted_gain':expected,'observed_outcome':verified.observed_outcome,'verification_status':verified.verification_status,'verifier_report':verifier_report,'cost_units_predicted':cost,'actual_usage':receipt.get('usage',{}),'receipt_hash':receipt.get('receipt_hash')}; engine_rows.append(row); all_deep.append(row)
            deep_contribs.extend(round_contribs); previous_results=engine_rows; seen.update(final_sched['selected'])
            mesh=self.interweave.weave(primary+deep_contribs,routing,source_text,preserve_agenda=mesh); graph=self.claims.build(primary,hybrid_mesh=mesh); disagreement=self.disagreements.analyze(graph,routing,hybrid_mesh=mesh)
            t_art=tg.artifact(disagreement.get('conflict_count',0)); current_metrics=t_art['metrics']; depth.consume(final_sched['spent_units']); depth_decision=depth.evaluate(current_metrics,previous_metrics)
            verified_outcomes=[x['observed_outcome'] for x in engine_rows if x.get('observed_outcome') is not None]; avg_outcome=(sum(verified_outcomes)/len(verified_outcomes)) if verified_outcomes else None; evo=self.evolution.adjudicate_after_round(evo,avg_outcome,false_confidence=mesh['metrics'].get('derived_truth_promotion_violations',0)>0)
            frontier_eval=frontier.evaluate_round(round_index,frontier_plan,engine_rows,current_metrics,depth_decision,evo)
            write_json(out/'frontier_control_plane'/f'ROUND_{round_index}_EVALUATION.json',frontier_eval)
            evo['frontier_replan_required']=frontier_eval['progress_ledger']['replan_required']; evo['frontier_progress_hash']=frontier_eval['progress_ledger']['progress_ledger_hash']; evo['architecture_hash']=canonical_hash({k:v for k,v in evo.items() if k!='architecture_hash'}); architecture_history.append(evo)
            rr={'round':round_index,'scheduler':final_sched,'coalitions':coal,'architecture':evo,'frontier_control':frontier_eval,'execution_batches':execution_batches,'engine_results':engine_rows,'transformation_metrics':current_metrics,'depth_decision':depth_decision}; scheduler_rounds.append(rr); write_json(out/'self_organizing_rounds'/f'ROUND_{round_index}.json',rr)
            ledger.append(run_id,'SELF_ORGANIZING_ROUND_COMPLETE',{'round':round_index,'selected':final_sched['selected'],'spent_units_predicted':final_sched['spent_units'],'observed_outcome':avg_outcome,'structural_diagnostic_gain':depth_decision['realized_marginal_gain'],'stop_decision':depth_decision['stop_decision'],'topology':evo['selected_topology_id'],'frontier_replan_required':evo['frontier_replan_required']}); telemetry.record('ROUND_COMPLETE',round=round_index,observed_outcome=avg_outcome,selected=final_sched['selected'])
            previous_metrics=current_metrics; previous_evolution=evo
            if round_index>=2 and depth_decision['stop_decision']!='CONTINUE': stop_reason=depth_decision['stop_decision']; break

        transform=tg.artifact(disagreement.get('conflict_count',0)); write_json(out/'TRANSFORMATION_GRAPH.json',transform)
        dialectical_graph=self.dialectical.build(source_text,source_sha256,active_policy); write_json(out/'DIALECTICAL_GRAPH.json',dialectical_graph)
        dialectical_verification=self.verifier.evaluate(source_text,dialectical_graph); write_json(out/'DIALECTICAL_GRAPH_VERIFICATION.json',dialectical_verification.as_dict())
        frontier_artifact=frontier.artifact(); write_json(out/'FRONTIER_CONTROL_PLANE.json',frontier_artifact)
        ecology={'ecology_version':'16X-FRONTIER-EVIDENCE-CONTROL-2.2','scheduler_rounds':scheduler_rounds,'architecture_history':architecture_history,'frontier_control_plane_hash':frontier_artifact['control_plane_hash'],'selected_topology_id':architecture_history[-1]['selected_topology_id'] if architecture_history else None,'coalitions':last_coalitions.get('coalitions',[]),'stop_reason':stop_reason,'depth_budget':{'initial':depth.total,'remaining':round(depth.remaining,3)},'cache':cache.metrics(),'disagreement_reorganizations':disagreement_reorganizations,'architecture_mutations':sum(1 for x in architecture_history if x['mutation'].startswith('MUTATE')),'truth_promotion_allowed_from_ecology':False,'claim_ceiling':'SELF_REORGANIZATION_CHANGES_COMPUTATIONAL_TOPOLOGY_NOT_TRUTH'}; ecology['ecology_hash']=canonical_hash({k:v for k,v in ecology.items() if k!='ecology_hash'}); write_json(out/'SELF_ORGANIZING_ECOLOGY.json',ecology)

        state['barrier']='FINAL_CLAIM_AND_DISAGREEMENT'; write_json(out/'META_RUN.json',state)
        write_json(out/'HYBRID_MESH.json',mesh); write_json(out/'CLAIM_GRAPH.json',graph); write_json(out/'DISAGREEMENT_MAP.json',disagreement)
        effects=evaluate_ecology_effects(ecology,transform,scheduler_rounds,self.biographies.snapshot(),mesh); write_json(out/'USEFUL_EFFECTS_2.0.json',effects); write_json(out/'USEFUL_EFFECTS_2.1.json',effects)
        metrics=evaluate_self_organization(transform,scheduler_rounds,architecture_history,mesh,graph); write_json(out/'SELF_ORGANIZING_METRICS.json',metrics)
        biography_snapshot=(self.biographies.snapshot() if experiment_policy.get('freeze_biography',False) else self.biographies.update(run_id,routing['task_fingerprint'],scheduler_rounds,effects,architecture_history[-1] if architecture_history else None)); write_json(out/'ENGINE_BIOGRAPHIES_AFTER_RUN.json',biography_snapshot)

        state['barrier']='CROSS_ENGINE_REVIEW'; write_json(out/'META_RUN.json',state)
        coordination={'routing_plan':routing,'hybrid_mesh':mesh,'claim_graph':graph,'disagreements':disagreement,'self_organizing_ecology':ecology,'frontier_control_plane':frontier_artifact,'transformation_graph':transform,'dialectical_graph':dialectical_graph,'architecture_policy':active_policy.as_dict(),'useful_effects':effects,'primary_fusion':primary_fusion}
        reviews=[]
        if not experiment_policy.get('skip_reviews',False):
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futs={pool.submit(self._adapter(rec).review,coordination,out/'reviews'/rec['engine_id'],ctx):rec for rec in self.cfg['engines'] if rec['engine_id'] not in disabled}
                for fut in as_completed(futs):
                    rec=futs[fut]
                    try:r=fut.result()
                    except Exception as e:r={'engine_id':rec['engine_id'],'review_state':'FAILED','error':repr(e)}
                    reviews.append(r); write_json(out/'reviews'/rec['engine_id']/'REVIEW.json',r); ledger.append(run_id,'ENGINE_CROSS_REVIEW_COMPLETE',r,rec['engine_id'])
        else:
            ledger.append(run_id,'EXPERIMENTAL_REVIEW_SKIPPED',{'reason':'high_volume_parallel_experiment','disabled_engines':sorted(disabled)})
        arbitration=self.arbitrator.arbitrate(graph,disagreement,routing,reviews,hybrid_mesh=mesh); write_json(out/'ARBITRATION.json',arbitration)
        auditable_synthesis=AuditableSynthesizer.synthesize(dialectical_graph,arbitration,dialectical_verification.as_dict()); write_json(out/'AUDITABLE_SYNTHESIS.json',auditable_synthesis)

        safety={'claim_node_delta_vs_primary':graph['node_count']-primary_snapshot['claim_nodes'],'native_position_delta_vs_primary':graph['position_count']-primary_snapshot['claim_positions'],'derived_truth_promotion_violations':mesh['metrics'].get('derived_truth_promotion_violations',0),'majority_vote_used':False,'all_16_primary_scheduled':routing['all_16_scheduled'],'deep_execution_is_sparse':sum(len(r['scheduler']['selected']) for r in scheduler_rounds)<16*max(1,len(scheduler_rounds))}; write_json(out/'EPISTEMIC_SAFETY_2.0.json',safety); write_json(out/'EPISTEMIC_SAFETY_2.1.json',safety)

        state['barrier']='FUSION_WITHOUT_ERASURE'; final=fuse(primary); final['cross_reviews']=sorted(reviews,key=lambda x:x['engine_id']); final['auditable_synthesis']=auditable_synthesis; final['epistemic_coordination']={'architecture_policy_hash':active_policy.policy_hash,'input_security_hash':input_security['classification_hash'],'dialectical_graph_hash':dialectical_graph['graph_hash'],'auditable_synthesis_hash':auditable_synthesis['synthesis_hash'],'dialectical_external_verification_status':dialectical_verification.verification_status,'self_organizing_ecology_hash':ecology['ecology_hash'],'frontier_control_plane_hash':frontier_artifact['control_plane_hash'],'frontier_candidate_count':len(frontier_artifact['candidate_archive']),'shadow_policy_candidate_count':len(frontier_artifact['policy_candidates']),'transformation_graph_hash':transform['graph_hash'],'claim_graph_hash':graph['graph_hash'],'disagreement_map_hash':disagreement['map_hash'],'arbitration_hash':arbitration['arbitration_hash'],'effects_hash':effects['effects_hash'],'metrics_hash':metrics['evaluation_hash'],'selected_topology':ecology['selected_topology_id'],'architecture_mutations':ecology['architecture_mutations'],'disagreement_reorganizations':ecology['disagreement_reorganizations'],'deep_rounds':len(scheduler_rounds),'deep_engine_executions':metrics['performance']['deep_engine_executions'],'sparse_deep_execution_ratio':metrics['performance']['sparse_deep_execution_ratio'],'transformation_causal_depth':transform['metrics']['causal_depth'],'source_reground_count':transform['metrics']['source_reground_count'],'hermeneutic_nonlinearity_proxy_diagnostic_only':metrics['hermeneutic_nonlinearity_proxy'],'epistemic_nonlinearity_proxy_diagnostic_only':metrics['epistemic_nonlinearity_proxy'],'depth_proxy_diagnostic_only':metrics['depth_proxy'],'majority_vote_used':False,'derived_truth_promotion_violations':safety['derived_truth_promotion_violations']}
        write_json(out/'FINAL_FUSION.json',final); state['fusion']=final; state['coordination']=final['epistemic_coordination']; state['status']='COMPLETE_WITH_DEGRADATION' if final['degraded_engines'] or final['failed_engines'] else ('COMPLETE_WITH_REFERENCE_SIMULATIONS' if final['reference_simulation_engines'] else 'COMPLETE'); state['barrier']='COMPLETE'; telemetry.record('RUN_COMPLETE',status=state['status']); telemetry_artifact=telemetry.write(out/'TELEMETRY.json'); state['telemetry_hash']=telemetry_artifact['telemetry_hash']; write_json(out/'META_RUN.json',state); ledger.append(run_id,'RUN_COMPLETE',{'status':state['status'],'topology':ecology['selected_topology_id'],'stop_reason':stop_reason,'architecture_policy_hash':active_policy.policy_hash})
        return state
