from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path
from .replication_outbox import ReplicationOutbox

class ReplicationError(RuntimeError): pass

CANONICAL_CLOUD_BACKEND = 'supabase'

def _credential_env(backend: str) -> str:
    if backend != CANONICAL_CLOUD_BACKEND:
        raise ReplicationError(f'BACKEND_RETIRED_NO_READS_NO_WRITES:{backend}')
    return 'SUPABASE_DATABASE_URL'

def _psql(url: str, sql: str):
    exe=shutil.which('psql')
    if not exe: raise ReplicationError('psql is not installed; keep local ledger and retry replication later')
    env=dict(os.environ); env['PGDATABASE']=url
    cp=subprocess.run([exe,'-X','-v','ON_ERROR_STOP=1','-c',sql],text=True,capture_output=True,env=env)
    if cp.returncode: raise ReplicationError(cp.stderr.strip())
    return cp.stdout

def _q(x): return "'"+str(x).replace("'","''")+"'"
def _j(x): return _q(json.dumps(x,ensure_ascii=False,separators=(',',':')))+'::jsonb'
def _arr(xs):
    xs=list(xs or [])
    return 'ARRAY['+','.join(_q(x) for x in xs)+']::text[]' if xs else 'ARRAY[]::text[]'

def replicate_event(event: dict, backend: str):
    env=_credential_env(backend)
    url=os.getenv(env)
    if not url: return {'backend':backend,'status':'UNAVAILABLE_NO_CREDENTIAL','event_id':event['event_id']}
    sql=("INSERT INTO destruktion_meta.event_ledger(event_id,meta_run_id,engine_id,seq,event_type,payload,payload_hash,parent_event_ids) VALUES ("
         f"{_q(event['event_id'])},{_q(event['meta_run_id'])},{'NULL' if event.get('engine_id') is None else _q(event['engine_id'])},{int(event['seq'])},{_q(event['event_type'])},{_j(event.get('payload',{}))},{_q(event['payload_hash'])},{_arr(event.get('parent_event_ids',[]))}) "
         "ON CONFLICT(event_id) DO NOTHING;")
    _psql(url,sql)
    return {'backend':backend,'status':'REPLICATED','event_id':event['event_id'],'payload_hash':event['payload_hash']}

def _coordination_sql(run_dir: Path):
    rd=Path(run_dir)
    state=json.loads((rd/'META_RUN.json').read_text()); routing=json.loads((rd/'ROUTING_PLAN.json').read_text())
    graph=json.loads((rd/'CLAIM_GRAPH.json').read_text()); dmap=json.loads((rd/'DISAGREEMENT_MAP.json').read_text()); arb=json.loads((rd/'ARBITRATION.json').read_text())
    mesh=json.loads((rd/'HYBRID_MESH.json').read_text()) if (rd/'HYBRID_MESH.json').exists() else None
    reentry=json.loads((rd/'CORE4_REENTRY.json').read_text()) if (rd/'CORE4_REENTRY.json').exists() else None
    nonlinear=json.loads((rd/'NONLINEARITY_EVALUATION.json').read_text()) if (rd/'NONLINEARITY_EVALUATION.json').exists() else None
    poly=json.loads((rd/'POLYCENTRIC_REENTRY.json').read_text()) if (rd/'POLYCENTRIC_REENTRY.json').exists() else None
    effects=json.loads((rd/'USEFUL_EFFECTS.json').read_text()) if (rd/'USEFUL_EFFECTS.json').exists() else None
    run_id=state['meta_run_id']; stmts=[]
    policy=json.loads((rd/'ACTIVE_ARCHITECTURE_POLICY.json').read_text()) if (rd/'ACTIVE_ARCHITECTURE_POLICY.json').exists() else None
    dialectical=json.loads((rd/'DIALECTICAL_GRAPH.json').read_text()) if (rd/'DIALECTICAL_GRAPH.json').exists() else None
    dialectical_verifier=json.loads((rd/'DIALECTICAL_GRAPH_VERIFICATION.json').read_text()) if (rd/'DIALECTICAL_GRAPH_VERIFICATION.json').exists() else None
    telemetry=json.loads((rd/'TELEMETRY.json').read_text()) if (rd/'TELEMETRY.json').exists() else None
    if policy:
        stmts.append("INSERT INTO destruktion_meta.architecture_policy(policy_hash,parent_policy_hash,generation,topology_id,status,guardrail_hash,verifier_hash,benchmark_hash,mutation_receipt,payload,self_modifying_code_allowed,truth_effect) VALUES ("
                     f"{_q(policy['policy_hash'])},{'NULL' if policy.get('parent_policy_hash') is None else _q(policy.get('parent_policy_hash'))},{int(policy.get('generation',0))},{_q(policy.get('topology_id',''))},{_q(policy.get('status','ACTIVE'))},{_q(policy.get('guardrail_hash',''))},{_q(policy.get('verifier_hash',''))},{_q(policy.get('benchmark_hash',''))},{_j(policy.get('mutation_receipt',{}))},{_j(policy)},false,'NONE') ON CONFLICT(policy_hash) DO NOTHING;")
    if dialectical:
        stmts.append("INSERT INTO destruktion_meta.dialectical_graph_ledger(meta_run_id,graph_hash,policy_hash,source_id,operators_realized,metrics,payload,truth_effect) VALUES ("
                     f"{_q(run_id)},{_q(dialectical.get('graph_hash',''))},{_q(dialectical.get('policy_hash',''))},{_q(dialectical.get('source_id',''))},{_arr(dialectical.get('operators_realized',[]))},{_j(dialectical.get('metrics',{}))},{_j(dialectical)},'NONE') ON CONFLICT(meta_run_id) DO UPDATE SET graph_hash=EXCLUDED.graph_hash,policy_hash=EXCLUDED.policy_hash,metrics=EXCLUDED.metrics,payload=EXCLUDED.payload;")
    if dialectical_verifier:
        stmts.append("INSERT INTO destruktion_meta.verifier_report_ledger(meta_run_id,verifier_hash,candidate_hash,verification_status,observed_outcome,promotion_eligible,metrics,hard_failures,payload) VALUES ("
                     f"{_q(run_id)},{_q(dialectical_verifier.get('verifier_hash',''))},{_q(dialectical_verifier.get('candidate_hash',''))},{_q(dialectical_verifier.get('verification_status',''))},{'NULL' if dialectical_verifier.get('observed_outcome') is None else float(dialectical_verifier.get('observed_outcome'))},{'true' if dialectical_verifier.get('promotion_eligible') else 'false'},{_j(dialectical_verifier.get('metrics',{}))},{_arr(dialectical_verifier.get('hard_failures',[]))},{_j(dialectical_verifier)}) ON CONFLICT(meta_run_id,verifier_hash) DO UPDATE SET verification_status=EXCLUDED.verification_status,observed_outcome=EXCLUDED.observed_outcome,metrics=EXCLUDED.metrics,payload=EXCLUDED.payload;")
    if telemetry:
        for event in telemetry.get('events',[]):
            stmts.append("INSERT INTO destruktion_meta.verifier_outcome_telemetry(event_hash,meta_run_id,parent_event_hash,event_kind,monotonic_seconds,usage,payload) VALUES ("
                         f"{_q(event.get('event_hash',''))},{_q(run_id)},{'NULL' if event.get('previous_event_hash') is None else _q(event.get('previous_event_hash'))},{_q(event.get('kind',''))},{float(event.get('monotonic_seconds',0))},{_j(event.get('usage',{}))},{_j(event)}) ON CONFLICT(event_hash) DO NOTHING;")
    stmts.append("INSERT INTO destruktion_meta.run_ledger(meta_run_id,input_hash,status,barrier,claim_ceiling,input_envelope,fusion,completed_at) VALUES ("
                 f"{_q(run_id)},{_q(state['input_hash'])},{_q(state['status'])},{_q(state['barrier'])},{_q(state.get('claim_ceiling',''))},'{{}}'::jsonb,{_j(state.get('fusion'))},now()) ON CONFLICT(meta_run_id) DO UPDATE SET status=EXCLUDED.status,barrier=EXCLUDED.barrier,fusion=EXCLUDED.fusion,completed_at=EXCLUDED.completed_at;")
    stmts.append("INSERT INTO destruktion_meta.routing_ledger(meta_run_id,plan_hash,mode,task_fingerprint,assignments,role_counts) VALUES ("
                 f"{_q(run_id)},{_q(routing['plan_hash'])},{_q(routing['mode'])},{_j(routing['task_fingerprint'])},{_j(routing['assignments'])},{_j(routing['role_counts'])}) ON CONFLICT(meta_run_id) DO UPDATE SET plan_hash=EXCLUDED.plan_hash,task_fingerprint=EXCLUDED.task_fingerprint,assignments=EXCLUDED.assignments,role_counts=EXCLUDED.role_counts;")
    if mesh:
        mm=mesh.get('metrics',{})
        stmts.append("INSERT INTO destruktion_meta.hybrid_mesh_ledger(meta_run_id,mesh_hash,mesh_version,engine_coverage,directed_pairwise_bridges,active_directed_pairwise_bridges,direct_typed_reuse_bridges,context_or_critique_bridges,signal_count,signal_type_count,metrics,claim_ceiling) VALUES ("
                     f"{_q(run_id)},{_q(mesh['mesh_hash'])},{_q(mesh['mesh_version'])},{int(mm.get('engine_coverage',0))},{int(mm.get('directed_pairwise_bridges',0))},{int(mm.get('active_directed_pairwise_bridges',0))},{int(mm.get('direct_typed_reuse_bridges',0))},{int(mm.get('context_or_critique_bridges',0))},{int(mm.get('signal_count',0))},{int(mm.get('signal_type_count',0))},{_j(mm)},{_q(mesh.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id) DO UPDATE SET mesh_hash=EXCLUDED.mesh_hash,metrics=EXCLUDED.metrics;")
        for b in mesh.get('pairwise_bridges',[]):
            stmts.append("INSERT INTO destruktion_meta.hybrid_bridge_ledger(meta_run_id,bridge_id,from_engine,to_engine,mode,direct_signal_types,source_signal_count,target_consumes,truth_promotion_allowed) VALUES ("
                         f"{_q(run_id)},{_q(b['bridge_id'])},{_q(b['from_engine'])},{_q(b['to_engine'])},{_q(b['mode'])},{_arr(b.get('direct_signal_types',[]))},{int(b.get('source_signal_count',0))},{_arr(b.get('target_consumes',[]))},{'true' if b.get('truth_promotion_allowed') else 'false'}) ON CONFLICT(meta_run_id,bridge_id) DO NOTHING;")
        for a in mesh.get('research_agenda',[]):
            stmts.append("INSERT INTO destruktion_meta.hybrid_agenda_ledger(meta_run_id,agenda_id,seed_kind,seed_text,source_engines,truth_status,payload) VALUES ("
                         f"{_q(run_id)},{_q(a['agenda_id'])},{_q(a.get('seed_kind',''))},{_q(a.get('seed_text',''))},{_arr(a.get('source_engines',[]))},{_q(a.get('truth_status','GENERATIVE_ONLY'))},{_j(a)}) ON CONFLICT(meta_run_id,agenda_id) DO UPDATE SET payload=EXCLUDED.payload,source_engines=EXCLUDED.source_engines;")
        for t in mesh.get('cross_architecture_traces',[]):
            stmts.append("INSERT INTO destruktion_meta.hybrid_trace_ledger(meta_run_id,trace_id,agenda_id,source_engines,cross_family_depth,truth_status,payload) VALUES ("
                         f"{_q(run_id)},{_q(t['trace_id'])},{_q(t.get('agenda_id',''))},{_arr(t.get('source_engines',[]))},{int(t.get('cross_family_depth',0))},{_q(t.get('truth_status','GENERATIVE_ONLY'))},{_j(t)}) ON CONFLICT(meta_run_id,trace_id) DO UPDATE SET payload=EXCLUDED.payload;")
    if reentry:
        rm=reentry.get('metrics',{}); hg=reentry.get('hermeneutic_graph',{})
        stmts.append("INSERT INTO destruktion_meta.core4_reentry_ledger(meta_run_id,reentry_hash,recursive_rounds,total_generative_positions,mean_core4_divergence,hermeneutic_cycle_count,hermeneutic_graph_hash,metrics,claim_ceiling) VALUES ("
                     f"{_q(run_id)},{_q(reentry['reentry_hash'])},{int(rm.get('recursive_rounds',0))},{int(rm.get('total_generative_positions',0))},{float(rm.get('mean_core4_divergence',0))},{int(rm.get('hermeneutic_cycle_count',0))},{_q(hg.get('graph_hash',''))},{_j(rm)},{_q(reentry.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id) DO UPDATE SET reentry_hash=EXCLUDED.reentry_hash,metrics=EXCLUDED.metrics;")
        import hashlib
        for rr in reentry.get('rounds',[]):
            for res in rr.get('results',[]):
                for i,p in enumerate(res.get('generative_positions',[])):
                    pid='prb-'+hashlib.sha256(json.dumps({'r':rr.get('round'),'e':res.get('engine_id'),'i':i,'p':p.get('proposition','')},sort_keys=True).encode()).hexdigest()[:20]
                    stmts.append("INSERT INTO destruktion_meta.core4_probe_ledger(meta_run_id,probe_id,engine_id,reentry_round,claim_type,proposition,payload,truth_effect) VALUES ("
                                 f"{_q(run_id)},{_q(pid)},{_q(res['engine_id'])},{int(rr.get('round',0))},{_q(p.get('claim_type',''))},{_q(p.get('proposition',''))},{_j(p)},{_q('NONE')}) ON CONFLICT(meta_run_id,probe_id) DO UPDATE SET payload=EXCLUDED.payload;")
        hgp=rd/'core4_reentry'/'HERMENEUTIC_REENTRY_GRAPH.json'
        if hgp.exists():
            hgd=json.loads(hgp.read_text())
            for i,e in enumerate(hgd.get('edges',[])):
                eid='heg-'+hashlib.sha256(json.dumps({'i':i,'e':e},sort_keys=True).encode()).hexdigest()[:20]
                stmts.append("INSERT INTO destruktion_meta.hermeneutic_edge_ledger(meta_run_id,edge_id,from_node,to_node,kind,payload,truth_effect) VALUES ("
                             f"{_q(run_id)},{_q(eid)},{_q(e.get('from',''))},{_q(e.get('to',''))},{_q(e.get('kind',''))},{_j(e)},{_q(e.get('truth_effect','NONE'))}) ON CONFLICT(meta_run_id,edge_id) DO UPDATE SET payload=EXCLUDED.payload;")
    if nonlinear:
        stmts.append("INSERT INTO destruktion_meta.nonlinearity_ledger(meta_run_id,evaluation_hash,metric_version,hermeneutic_nonlinearity,epistemic_nonlinearity,depth_proxy,delta_vs_baseline,epistemic_safety,components,raw,claim_ceiling) VALUES ("
                     f"{_q(run_id)},{_q(nonlinear['evaluation_hash'])},{_q(nonlinear.get('metric_version',''))},{float(nonlinear.get('hermeneutic_nonlinearity_proxy',0))},{float(nonlinear.get('epistemic_nonlinearity_proxy',0))},{float(nonlinear.get('depth_proxy',0))},{_j(nonlinear.get('delta_vs_1_2_equivalent',{}))},{_j(nonlinear.get('epistemic_safety',{}))},{_j(nonlinear.get('components',{}))},{_j(nonlinear.get('raw',{}))},{_q(nonlinear.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id) DO UPDATE SET evaluation_hash=EXCLUDED.evaluation_hash,hermeneutic_nonlinearity=EXCLUDED.hermeneutic_nonlinearity,epistemic_nonlinearity=EXCLUDED.epistemic_nonlinearity,depth_proxy=EXCLUDED.depth_proxy,delta_vs_baseline=EXCLUDED.delta_vs_baseline,epistemic_safety=EXCLUDED.epistemic_safety,components=EXCLUDED.components,raw=EXCLUDED.raw;")
    if poly:
        pm=poly.get('metrics',{})
        stmts.append("INSERT INTO destruktion_meta.polycentric_reentry_ledger(meta_run_id,reentry_hash,round_count,all16_rounds,total_generative_positions,unique_claim_types,peer_pair_coverage,mean_round_novelty,last_round_novelty,stop_reason,metrics,claim_ceiling) VALUES ("
                     f"{_q(run_id)},{_q(poly['reentry_hash'])},{int(pm.get('round_count',0))},{int(pm.get('all16_rounds',0))},{int(pm.get('total_generative_positions',0))},{int(pm.get('unique_claim_types',0))},{int(pm.get('peer_pair_coverage',0))},{float(pm.get('mean_round_novelty',0))},{float(pm.get('last_round_novelty',0))},{_q(poly.get('stop_reason',''))},{_j(pm)},{_q(poly.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id) DO UPDATE SET reentry_hash=EXCLUDED.reentry_hash,metrics=EXCLUDED.metrics,stop_reason=EXCLUDED.stop_reason;")
        for rr in poly.get('rounds',[]):
            stmts.append("INSERT INTO destruktion_meta.polycentric_round_ledger(meta_run_id,round_index,round_hash,scheduled_engines,global_novelty,novelty,metrics) VALUES ("
                         f"{_q(run_id)},{int(rr.get('round',0))},{_q(rr.get('round_hash',''))},{_arr(rr.get('scheduled_engines',[]))},{float((rr.get('novelty') or {}).get('global_novelty',0))},{_j(rr.get('novelty',{}))},{_j(rr.get('metrics',{}))}) ON CONFLICT(meta_run_id,round_index) DO UPDATE SET round_hash=EXCLUDED.round_hash,scheduled_engines=EXCLUDED.scheduled_engines,global_novelty=EXCLUDED.global_novelty,novelty=EXCLUDED.novelty,metrics=EXCLUDED.metrics;")
        pgp=rd/'polycentric_reentry'/'POLYCENTRIC_REENTRY_GRAPH.json'
        if pgp.exists():
            pg=json.loads(pgp.read_text())
            import hashlib
            for i,e in enumerate(pg.get('edges',[])):
                eid='peg-'+hashlib.sha256(json.dumps({'i':i,'e':e},sort_keys=True).encode()).hexdigest()[:20]
                stmts.append("INSERT INTO destruktion_meta.polycentric_edge_ledger(meta_run_id,edge_id,from_node,to_node,kind,payload,truth_effect) VALUES ("
                             f"{_q(run_id)},{_q(eid)},{_q(e.get('from',''))},{_q(e.get('to',''))},{_q(e.get('kind',''))},{_j(e)},{_q(e.get('truth_effect','NONE'))}) ON CONFLICT(meta_run_id,edge_id) DO UPDATE SET payload=EXCLUDED.payload;")
    if effects:
        for e in effects.get('effects',[]):
            stmts.append("INSERT INTO destruktion_meta.useful_effect_ledger(meta_run_id,effect_id,state,score,payload) VALUES ("
                         f"{_q(run_id)},{_q(e.get('effect_id',''))},{_q(e.get('state',''))},{float(e.get('score',0))},{_j(e)}) ON CONFLICT(meta_run_id,effect_id) DO UPDATE SET state=EXCLUDED.state,score=EXCLUDED.score,payload=EXCLUDED.payload;")
    # METAENGINE 2.0 self-reorganizing ecology ledgers.
    ecology20=json.loads((rd/'SELF_ORGANIZING_ECOLOGY.json').read_text()) if (rd/'SELF_ORGANIZING_ECOLOGY.json').exists() else None
    transform20=json.loads((rd/'TRANSFORMATION_GRAPH.json').read_text()) if (rd/'TRANSFORMATION_GRAPH.json').exists() else None
    bio20=json.loads((rd/'ENGINE_BIOGRAPHIES_AFTER_RUN.json').read_text()) if (rd/'ENGINE_BIOGRAPHIES_AFTER_RUN.json').exists() else None
    if ecology20:
        for rr in sorted((rd/'self_organizing_rounds').glob('ROUND_*.json')) if (rd/'self_organizing_rounds').exists() else []:
            rj=json.loads(rr.read_text()); ri=int(rj.get('round',0)); sch=rj.get('scheduler',{}); arc=rj.get('architecture',{}); coal=rj.get('coalitions',{}); dep=rj.get('depth_decision',{})
            stmts.append("INSERT INTO destruktion_meta.scheduler_round_ledger(meta_run_id,round_index,plan_hash,budget_units,spent_units,selected_engines,scores,selection,policy) VALUES ("
                         f"{_q(run_id)},{ri},{_q(sch.get('plan_hash',''))},{float(sch.get('budget_units',0))},{float(sch.get('spent_units',0))},{_arr(sch.get('selected',[]))},{_j(sch.get('scores',[]))},{_j(sch.get('selection',[]))},{_j({'policy':sch.get('policy','')})}) ON CONFLICT(meta_run_id,round_index) DO UPDATE SET plan_hash=EXCLUDED.plan_hash,budget_units=EXCLUDED.budget_units,spent_units=EXCLUDED.spent_units,selected_engines=EXCLUDED.selected_engines,scores=EXCLUDED.scores,selection=EXCLUDED.selection,policy=EXCLUDED.policy;")
            stmts.append("INSERT INTO destruktion_meta.topology_ledger(meta_run_id,round_index,architecture_hash,selected_topology_id,selected,candidates,mutation,disposition,realized_gain,claim_ceiling) VALUES ("
                         f"{_q(run_id)},{ri},{_q(arc.get('architecture_hash',''))},{_q(arc.get('selected_topology_id',''))},{_j(arc.get('selected',{}))},{_j(arc.get('candidates',[]))},{_j({'mutation':arc.get('mutation')})},{'NULL' if arc.get('disposition') is None else _q(arc.get('disposition'))},{'NULL' if arc.get('realized_gain') is None else float(arc.get('realized_gain'))},{_q(arc.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id,round_index) DO UPDATE SET architecture_hash=EXCLUDED.architecture_hash,selected_topology_id=EXCLUDED.selected_topology_id,selected=EXCLUDED.selected,candidates=EXCLUDED.candidates,mutation=EXCLUDED.mutation,disposition=EXCLUDED.disposition,realized_gain=EXCLUDED.realized_gain;")
            for ci,c in enumerate(arc.get('candidates',[])):
                cid=str(c.get('topology_id') or c.get('candidate_id') or f'candidate-{ci}')
                stmts.append("INSERT INTO destruktion_meta.architecture_candidate_ledger(meta_run_id,round_index,candidate_id,topology_id,utility,state,payload,truth_effect) VALUES ("
                             f"{_q(run_id)},{ri},{_q(cid)},{_q(str(c.get('topology_id',cid)))},{'NULL' if c.get('expected_utility') is None else float(c.get('expected_utility'))},{_q(str(c.get('state','CANDIDATE')))},{_j(c)},{_q('NONE')}) ON CONFLICT(meta_run_id,round_index,candidate_id) DO UPDATE SET utility=EXCLUDED.utility,state=EXCLUDED.state,payload=EXCLUDED.payload;")
            for ci,c in enumerate(coal.get('coalitions',[])):
                cid=str(c.get('coalition_id') or f'coal-{ci}')
                stmts.append("INSERT INTO destruktion_meta.coalition_ledger(meta_run_id,round_index,coalition_id,coalition_type,members,trigger,payload,truth_authority) VALUES ("
                             f"{_q(run_id)},{ri},{_q(cid)},{_q(str(c.get('kind','UNKNOWN')))},{_arr(c.get('members',[]))},{'NULL' if c.get('trigger') is None else _q(c.get('trigger'))},{_j(c)},{'true' if c.get('truth_authority') else 'false'}) ON CONFLICT(meta_run_id,round_index,coalition_id) DO UPDATE SET members=EXCLUDED.members,payload=EXCLUDED.payload,truth_authority=EXCLUDED.truth_authority;")
            stmts.append("INSERT INTO destruktion_meta.depth_budget_ledger(meta_run_id,round_index,realized_marginal_gain,stop_decision,remaining_budget,policy) VALUES ("
                         f"{_q(run_id)},{ri},{float(dep.get('realized_marginal_gain',0))},{_q(str(dep.get('stop_decision','')))},{float(dep.get('remaining_budget',0))},{_j(dep.get('policy',{}))}) ON CONFLICT(meta_run_id,round_index) DO UPDATE SET realized_marginal_gain=EXCLUDED.realized_marginal_gain,stop_decision=EXCLUDED.stop_decision,remaining_budget=EXCLUDED.remaining_budget,policy=EXCLUDED.policy;")
            for er in rj.get('engine_results',[]):
                eid=er.get('engine_id'); rp=rd/'deep_reentry'/f'round_{ri}'/str(eid)/'NATIVE_REENTRY_RECEIPT.json'
                if not eid or not rp.exists(): continue
                rc=json.loads(rp.read_text())
                sp=rc.get('specialized_native') or {}
                stmts.append("INSERT INTO destruktion_meta.native_reentry_receipt_ledger(meta_run_id,round_index,engine_id,receipt_hash,compiled_mode,status,specialized_native_executed,specialized_native_success,cache_reused,source_reground_required,payload) VALUES ("
                             f"{_q(run_id)},{ri},{_q(eid)},{_q(rc.get('receipt_hash',''))},{_q(str(rc.get('compiled_mode','')))},{_q(str(rc.get('adapter_status','')))},{'true' if sp else 'false'},{'true' if sp and sp.get('exit_code')==0 else 'false'},{'true' if er.get('cache_reused') else 'false'},{'true' if rc.get('source_reground_required',True) else 'false'},{_j(rc)}) ON CONFLICT(meta_run_id,round_index,engine_id) DO UPDATE SET receipt_hash=EXCLUDED.receipt_hash,compiled_mode=EXCLUDED.compiled_mode,status=EXCLUDED.status,specialized_native_executed=EXCLUDED.specialized_native_executed,specialized_native_success=EXCLUDED.specialized_native_success,cache_reused=EXCLUDED.cache_reused,payload=EXCLUDED.payload;")
    if transform20:
        for n in transform20.get('nodes',[]):
            tid=str(n.get('node_id') or n.get('id') or '')
            if not tid: continue
            ttype=str(n.get('transformation_type') or n.get('type') or n.get('kind') or 'STATE')
            stmts.append("INSERT INTO destruktion_meta.transformation_ledger(meta_run_id,transformation_id,engine_id,transformation_type,node_kind,payload,source_regrounded,truth_effect) VALUES ("
                         f"{_q(run_id)},{_q(tid)},{'NULL' if n.get('engine_id') is None else _q(n.get('engine_id'))},{_q(ttype)},{'NULL' if n.get('kind') is None else _q(n.get('kind'))},{_j(n)},{'true' if n.get('source_regrounded') else 'false'},{_q('NONE')}) ON CONFLICT(meta_run_id,transformation_id) DO UPDATE SET payload=EXCLUDED.payload;")
        for i,e in enumerate(transform20.get('edges',[])):
            import hashlib
            eid=str(e.get('edge_id') or 'tge-'+hashlib.sha256(json.dumps({'i':i,'e':e},sort_keys=True).encode()).hexdigest()[:20])
            frm=str(e.get('from') or e.get('from_node') or ''); to=str(e.get('to') or e.get('to_node') or '')
            stmts.append("INSERT INTO destruktion_meta.transformation_edge_ledger(meta_run_id,edge_id,from_node,to_node,kind,payload,truth_effect) VALUES ("
                         f"{_q(run_id)},{_q(eid)},{_q(frm)},{_q(to)},{_q(str(e.get('kind','CHANGES_SPACE_OF')))},{_j(e)},{_q(str(e.get('truth_effect','NONE')))}) ON CONFLICT(meta_run_id,edge_id) DO UPDATE SET payload=EXCLUDED.payload;")
    if bio20:
        import hashlib
        domains=(routing.get('task_fingerprint') or {}).get('active_domains',[]) or ['GENERAL']
        for eid,b in (bio20.get('engines') or {}).items():
            bh=hashlib.sha256(json.dumps(b,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            for dom in domains:
                stmts.append("INSERT INTO destruktion_meta.engine_biography_ledger(meta_run_id,engine_id,domain,task_fingerprint,biography,biography_hash,claim_ceiling) VALUES ("
                             f"{_q(run_id)},{_q(eid)},{_q(dom)},{_j(routing.get('task_fingerprint',{}))},{_j(b)},{_q(bh)},{_q(str(b.get('claim_ceiling','SCHEDULER_PRIOR_NOT_EPISTEMIC_AUTHORITY')))}) ON CONFLICT(meta_run_id,engine_id,domain) DO UPDATE SET biography=EXCLUDED.biography,biography_hash=EXCLUDED.biography_hash;")
    # METAENGINE 2.2 frontier evidence-control ledgers. Automated ranking is
    # persisted as a policy signal only and never as epistemic authority.
    frontier=json.loads((rd/'FRONTIER_CONTROL_PLANE.json').read_text()) if (rd/'FRONTIER_CONTROL_PLANE.json').exists() else None
    if frontier:
        task=frontier.get('task_ledger',{})
        stmts.append("INSERT INTO destruktion_meta.frontier_task_ledger(meta_run_id,task_ledger_hash,payload,claim_ceiling) VALUES ("
                     f"{_q(run_id)},{_q(task.get('task_ledger_hash',''))},{_j(task)},{_q(task.get('claim_ceiling',''))}) ON CONFLICT(meta_run_id) DO UPDATE SET task_ledger_hash=EXCLUDED.task_ledger_hash,payload=EXCLUDED.payload,claim_ceiling=EXCLUDED.claim_ceiling;")
        for plan_path in sorted((rd/'frontier_control_plane').glob('ROUND_*_PLAN.json')) if (rd/'frontier_control_plane').exists() else []:
            plan=json.loads(plan_path.read_text()); ri=int(plan.get('round',0))
            for handoff in plan.get('handoffs',[]):
                stmts.append("INSERT INTO destruktion_meta.frontier_handoff_ledger(meta_run_id,round_index,handoff_hash,engine_id,workstream_id,objective,budget_units,guardrails,payload) VALUES ("
                             f"{_q(run_id)},{ri},{_q(handoff.get('handoff_hash',''))},{_q(handoff.get('engine_id',''))},{_q(handoff.get('workstream_id',''))},{_q(handoff.get('objective',''))},{float(handoff.get('budget_units',0))},{_arr(handoff.get('guardrails',[]))},{_j(handoff)}) ON CONFLICT(meta_run_id,round_index,handoff_hash) DO UPDATE SET objective=EXCLUDED.objective,budget_units=EXCLUDED.budget_units,guardrails=EXCLUDED.guardrails,payload=EXCLUDED.payload;")
        for evaluation in frontier.get('rounds',[]):
            ri=int(evaluation.get('round',0)); progress=evaluation.get('progress_ledger',{}); pareto=set(evaluation.get('pareto_candidate_ids',[]))
            stmts.append("INSERT INTO destruktion_meta.frontier_progress_ledger(meta_run_id,round_index,progress_ledger_hash,selected_topology_id,replan_required,stop_recommended,reasons,metrics) VALUES ("
                         f"{_q(run_id)},{ri},{_q(progress.get('progress_ledger_hash',''))},{'NULL' if not progress.get('selected_topology_id') else _q(progress.get('selected_topology_id'))},{'true' if progress.get('replan_required') else 'false'},{'true' if progress.get('stop_recommended') else 'false'},{_arr(progress.get('reasons',[]))},{_j(progress)}) ON CONFLICT(meta_run_id,round_index) DO UPDATE SET progress_ledger_hash=EXCLUDED.progress_ledger_hash,selected_topology_id=EXCLUDED.selected_topology_id,replan_required=EXCLUDED.replan_required,stop_recommended=EXCLUDED.stop_recommended,reasons=EXCLUDED.reasons,metrics=EXCLUDED.metrics;")
            for candidate in evaluation.get('candidates',[]):
                cid=candidate.get('candidate_id','')
                stmts.append("INSERT INTO destruktion_meta.frontier_candidate_ledger(meta_run_id,candidate_id,round_index,engine_id,receipt_hash,ensemble_score,pareto_member,evaluator_scores,payload,truth_effect) VALUES ("
                             f"{_q(run_id)},{_q(cid)},{ri},{_q(candidate.get('engine_id',''))},{'NULL' if not candidate.get('receipt_hash') else _q(candidate.get('receipt_hash'))},{float(candidate.get('ensemble_score',0))},{'true' if cid in pareto else 'false'},{_j(candidate.get('evaluator_scores',{}))},{_j(candidate)},{_q('NONE')}) ON CONFLICT(meta_run_id,candidate_id) DO UPDATE SET ensemble_score=EXCLUDED.ensemble_score,pareto_member=EXCLUDED.pareto_member,evaluator_scores=EXCLUDED.evaluator_scores,payload=EXCLUDED.payload;")
        for policy in frontier.get('policy_candidates',[]):
            stmts.append("INSERT INTO destruktion_meta.frontier_policy_candidate_ledger(meta_run_id,policy_candidate_id,round_index,mutation,deployment_status,acceptance_gate,payload) VALUES ("
                         f"{_q(run_id)},{_q(policy.get('policy_candidate_id',''))},{int(policy.get('round',0))},{_q(policy.get('mutation',''))},{_q('SHADOW_ONLY')},{_q(policy.get('acceptance_gate',''))},{_j(policy)}) ON CONFLICT(meta_run_id,policy_candidate_id) DO UPDATE SET mutation=EXCLUDED.mutation,deployment_status=EXCLUDED.deployment_status,acceptance_gate=EXCLUDED.acceptance_gate,payload=EXCLUDED.payload;")
    for n in graph['nodes']:
        stmts.append("INSERT INTO destruktion_meta.claim_ledger(meta_run_id,claim_id,proposition_key,representative,engine_ids,source_refs,stances,max_evidence_strength,positions) VALUES ("
                     f"{_q(run_id)},{_q(n['claim_id'])},{_q(n['proposition_key'])},{_q(n['representative'])},{_arr(n['engine_ids'])},{_arr(n['source_refs'])},{_arr(n['stances'])},{float(n['max_evidence_strength'])},{_j(n['positions'])}) ON CONFLICT(meta_run_id,claim_id) DO UPDATE SET positions=EXCLUDED.positions,stances=EXCLUDED.stances,max_evidence_strength=EXCLUDED.max_evidence_strength;")
        for p in n['positions']:
            stmts.append("INSERT INTO destruktion_meta.claim_position_ledger(position_id,meta_run_id,claim_id,engine_id,stance,claim_type,force,proposition,source_refs,evidence_kind,evidence_strength,claim_ceiling,metadata) VALUES ("
                         f"{_q(p['position_id'])},{_q(run_id)},{_q(n['claim_id'])},{_q(p['engine_id'])},{_q(p['stance'])},{_q(p['claim_type'])},{_q(p['force'])},{_q(p['proposition'])},{_arr(p['source_refs'])},{_q(p['evidence_kind'])},{float(p['evidence_strength'])},{_q(p['claim_ceiling'])},{_j(p.get('metadata',{}))}) ON CONFLICT(position_id) DO NOTHING;")
    for i,e in enumerate(graph.get('edges',[])):
        eid='edge-'+str(i)+'-'+graph['graph_hash'][:12]
        md={k:v for k,v in e.items() if k not in ('from','to','kind')}
        stmts.append("INSERT INTO destruktion_meta.claim_edge_ledger(meta_run_id,edge_id,from_claim_id,to_claim_id,kind,metadata) VALUES ("
                     f"{_q(run_id)},{_q(eid)},{_q(e['from'])},{_q(e['to'])},{_q(e['kind'])},{_j(md)}) ON CONFLICT(meta_run_id,edge_id) DO NOTHING;")
    for c in dmap['conflicts']:
        stmts.append("INSERT INTO destruktion_meta.disagreement_ledger(disagreement_id,meta_run_id,claim_id,kind,engine_ids,tension_score,research_priority,resolution_state,positions) VALUES ("
                     f"{_q(c['disagreement_id'])},{_q(run_id)},{_q(c['claim_id'])},{_q(c['kind'])},{_arr(c['engine_ids'])},{float(c['tension_score'])},{_q(c['research_priority'])},{_q(c['resolution_state'])},{_j(c['positions'])}) ON CONFLICT(disagreement_id) DO UPDATE SET tension_score=EXCLUDED.tension_score,research_priority=EXCLUDED.research_priority,resolution_state=EXCLUDED.resolution_state,positions=EXCLUDED.positions;")
    for rf in sorted((rd/'reviews').glob('engine_*/REVIEW.json')):
        r=json.loads(rf.read_text())
        stmts.append("INSERT INTO destruktion_meta.review_ledger(meta_run_id,engine_id,review_state,routing_role,selected_disagreements,payload) VALUES ("
                     f"{_q(run_id)},{_q(r['engine_id'])},{_q(r['review_state'])},{_q(r.get('routing_role',''))},{_arr(r.get('selected_disagreements',[]))},{_j(r)}) ON CONFLICT(meta_run_id,engine_id) DO UPDATE SET review_state=EXCLUDED.review_state,routing_role=EXCLUDED.routing_role,selected_disagreements=EXCLUDED.selected_disagreements,payload=EXCLUDED.payload;")
    for d in arb['decisions']:
        stmts.append("INSERT INTO destruktion_meta.arbitration_ledger(meta_run_id,claim_id,state,reason,disagreement_id,majority_vote_used,decision) VALUES ("
                     f"{_q(run_id)},{_q(d['claim_id'])},{_q(d['state'])},{_q(d['reason'])},{'NULL' if not d.get('disagreement_id') else _q(d['disagreement_id'])},{'true' if d.get('majority_vote_used') else 'false'},{_j(d)}) ON CONFLICT(meta_run_id,claim_id) DO UPDATE SET state=EXCLUDED.state,reason=EXCLUDED.reason,disagreement_id=EXCLUDED.disagreement_id,majority_vote_used=EXCLUDED.majority_vote_used,decision=EXCLUDED.decision;")
    if (rd/'ledger/events.jsonl').exists():
        for line in (rd/'ledger/events.jsonl').read_text().splitlines():
            if not line.strip(): continue
            e=json.loads(line)
            stmts.append("INSERT INTO destruktion_meta.event_ledger(event_id,meta_run_id,engine_id,seq,event_type,payload,payload_hash,parent_event_ids) VALUES ("
                         f"{_q(e['event_id'])},{_q(e['meta_run_id'])},{'NULL' if e.get('engine_id') is None else _q(e['engine_id'])},{int(e['seq'])},{_q(e['event_type'])},{_j(e.get('payload',{}))},{_q(e['payload_hash'])},{_arr(e.get('parent_event_ids',[]))}) ON CONFLICT(event_id) DO NOTHING;")
    return stmts

def replicate_run(run_dir: str|Path, backend: str):
    env=_credential_env(backend)
    url=os.getenv(env)
    if not (Path(run_dir)/'META_RUN.json').exists() and not url:
        return {'backend':backend,'status':'UNAVAILABLE_NO_CREDENTIAL','run_dir':str(run_dir)}
    stmts=_coordination_sql(Path(run_dir)); outbox=ReplicationOutbox(run_dir); batch=outbox.stage(backend,stmts)
    if not url: return {'backend':backend,'status':'OUTBOXED_NO_CREDENTIAL','batch_hash':batch['batch_hash'],'statement_count':len(stmts),'run_dir':str(run_dir)}
    sql="BEGIN;\nSET LOCAL app.metaengine_writer = 'on';\n"+'\n'.join(stmts)+'\nCOMMIT;'
    try: _psql(url,sql)
    except Exception as exc:
        outbox.mark(batch['batch_hash'],backend,'FAILED',repr(exc)); raise
    outbox.mark(batch['batch_hash'],backend,'REPLICATED')
    return {'backend':backend,'status':'REPLICATED','batch_hash':batch['batch_hash'],'statement_count':len(stmts),'run_dir':str(run_dir)}
