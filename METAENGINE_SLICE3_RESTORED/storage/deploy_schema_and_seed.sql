CREATE SCHEMA IF NOT EXISTS destruktion_meta;
CREATE TABLE IF NOT EXISTS destruktion_meta.engine_registry (
  engine_id text PRIMARY KEY, ordinal integer NOT NULL UNIQUE, name text NOT NULL, version text NOT NULL,
  lineage_policy text NOT NULL, status text NOT NULL, source_archive text NOT NULL, source_sha256 text NOT NULL,
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb, native_test jsonb NOT NULL DEFAULT '{}'::jsonb, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  registered_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.run_ledger (
  meta_run_id text PRIMARY KEY, input_hash text NOT NULL, status text NOT NULL, barrier text NOT NULL,
  claim_ceiling text NOT NULL, input_envelope jsonb NOT NULL DEFAULT '{}'::jsonb, fusion jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS destruktion_meta.engine_run_ledger (
  meta_run_id text NOT NULL, engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id), wave integer NOT NULL,
  status text NOT NULL, input_hash text NOT NULL, output_hash text, native_output jsonb, canonical_output jsonb, error jsonb,
  started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
  PRIMARY KEY(meta_run_id, engine_id, wave)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.event_ledger (
  event_id text PRIMARY KEY, meta_run_id text NOT NULL, engine_id text, seq bigint NOT NULL,
  event_type text NOT NULL, payload jsonb NOT NULL DEFAULT '{}'::jsonb, payload_hash text NOT NULL,
  parent_event_ids text[] NOT NULL DEFAULT ARRAY[]::text[], created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(meta_run_id, seq)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.artifact_ledger (
  artifact_id text PRIMARY KEY, meta_run_id text NOT NULL, engine_id text, kind text NOT NULL, uri text NOT NULL,
  sha256 text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.conflict_ledger (
  conflict_id text PRIMARY KEY, meta_run_id text NOT NULL, dimension text NOT NULL, engine_ids text[] NOT NULL,
  description jsonb NOT NULL, resolution_state text NOT NULL DEFAULT 'UNRESOLVED', resolution jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz
);
CREATE TABLE IF NOT EXISTS destruktion_meta.checkpoint_ledger (
  checkpoint_id text PRIMARY KEY, meta_run_id text NOT NULL, barrier text NOT NULL, state_hash text NOT NULL,
  state jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.memory_ledger (
  memory_id text PRIMARY KEY, subject_type text NOT NULL, subject_id text NOT NULL, version integer NOT NULL,
  content jsonb NOT NULL, content_hash text NOT NULL, parent_memory_id text, mutation_receipt jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(subject_type,subject_id,version)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.sync_receipt (
  receipt_id text PRIMARY KEY, event_id text NOT NULL, backend text NOT NULL, backend_ref text,
  status text NOT NULL, remote_hash text, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(event_id,backend)
);
CREATE INDEX IF NOT EXISTS idx_dm_event_run ON destruktion_meta.event_ledger(meta_run_id,seq);
CREATE INDEX IF NOT EXISTS idx_dm_engine_run ON destruktion_meta.engine_run_ledger(meta_run_id,status);
CREATE INDEX IF NOT EXISTS idx_dm_conflict_run ON destruktion_meta.conflict_ledger(meta_run_id,resolution_state);
CREATE TABLE IF NOT EXISTS destruktion_meta.core4_reentry_ledger (
  meta_run_id text PRIMARY KEY,
  reentry_hash text NOT NULL,
  recursive_rounds integer NOT NULL,
  total_generative_positions integer NOT NULL,
  mean_core4_divergence double precision NOT NULL,
  hermeneutic_cycle_count integer NOT NULL,
  hermeneutic_graph_hash text NOT NULL,
  metrics jsonb NOT NULL,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.core4_probe_ledger (
  meta_run_id text NOT NULL,
  probe_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  reentry_round integer NOT NULL,
  claim_type text NOT NULL,
  proposition text NOT NULL,
  payload jsonb NOT NULL,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, probe_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hermeneutic_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_node text NOT NULL,
  to_node text NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, edge_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.nonlinearity_ledger (
  meta_run_id text PRIMARY KEY,
  evaluation_hash text NOT NULL,
  metric_version text NOT NULL,
  hermeneutic_nonlinearity double precision NOT NULL,
  epistemic_nonlinearity double precision NOT NULL,
  depth_proxy double precision NOT NULL,
  delta_vs_baseline jsonb NOT NULL DEFAULT '{}'::jsonb,
  epistemic_safety jsonb NOT NULL DEFAULT '{}'::jsonb,
  components jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dm_core4_probe_engine_round ON destruktion_meta.core4_probe_ledger(meta_run_id,engine_id,reentry_round);
CREATE INDEX IF NOT EXISTS idx_dm_herm_edge_kind ON destruktion_meta.hermeneutic_edge_ledger(meta_run_id,kind);

-- Epistemic Coordination 1.1
CREATE TABLE IF NOT EXISTS destruktion_meta.routing_ledger (
  meta_run_id text PRIMARY KEY,
  plan_hash text NOT NULL,
  mode text NOT NULL,
  task_fingerprint jsonb NOT NULL,
  assignments jsonb NOT NULL,
  role_counts jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_ledger (
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  proposition_key text NOT NULL,
  representative text NOT NULL,
  engine_ids text[] NOT NULL DEFAULT ARRAY[]::text[],
  source_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
  stances text[] NOT NULL DEFAULT ARRAY[]::text[],
  max_evidence_strength double precision NOT NULL DEFAULT 0,
  positions jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY(meta_run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_position_ledger (
  position_id text PRIMARY KEY,
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  stance text NOT NULL,
  claim_type text NOT NULL,
  force text NOT NULL,
  proposition text NOT NULL,
  source_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
  evidence_kind text NOT NULL,
  evidence_strength double precision NOT NULL,
  claim_ceiling text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS destruktion_meta.claim_edge_ledger (
  meta_run_id text NOT NULL,
  edge_id text NOT NULL,
  from_claim_id text NOT NULL,
  to_claim_id text NOT NULL,
  kind text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, edge_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.disagreement_ledger (
  disagreement_id text PRIMARY KEY,
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  kind text NOT NULL,
  engine_ids text[] NOT NULL,
  tension_score double precision NOT NULL,
  research_priority text NOT NULL,
  resolution_state text NOT NULL,
  positions jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.review_ledger (
  meta_run_id text NOT NULL,
  engine_id text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  review_state text NOT NULL,
  routing_role text,
  selected_disagreements text[] NOT NULL DEFAULT ARRAY[]::text[],
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, engine_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.arbitration_ledger (
  meta_run_id text NOT NULL,
  claim_id text NOT NULL,
  state text NOT NULL,
  reason text NOT NULL,
  disagreement_id text,
  majority_vote_used boolean NOT NULL DEFAULT false,
  decision jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, claim_id)
);
CREATE INDEX IF NOT EXISTS idx_dm_claim_run ON destruktion_meta.claim_ledger(meta_run_id);
CREATE INDEX IF NOT EXISTS idx_dm_claim_position_run_engine ON destruktion_meta.claim_position_ledger(meta_run_id,engine_id);
CREATE INDEX IF NOT EXISTS idx_dm_disagreement_run_priority ON destruktion_meta.disagreement_ledger(meta_run_id,research_priority,resolution_state);
CREATE INDEX IF NOT EXISTS idx_dm_arbitration_run_state ON destruktion_meta.arbitration_ledger(meta_run_id,state);

-- Interwoven Architecture 1.2
CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_mesh_ledger (
  meta_run_id text PRIMARY KEY,
  mesh_hash text NOT NULL,
  mesh_version text NOT NULL,
  engine_coverage integer NOT NULL,
  directed_pairwise_bridges integer NOT NULL,
  active_directed_pairwise_bridges integer NOT NULL,
  direct_typed_reuse_bridges integer NOT NULL,
  context_or_critique_bridges integer NOT NULL,
  signal_count integer NOT NULL,
  signal_type_count integer NOT NULL,
  metrics jsonb NOT NULL,
  claim_ceiling text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_bridge_ledger (
  meta_run_id text NOT NULL,
  bridge_id text NOT NULL,
  from_engine text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  to_engine text NOT NULL REFERENCES destruktion_meta.engine_registry(engine_id),
  mode text NOT NULL,
  direct_signal_types text[] NOT NULL DEFAULT ARRAY[]::text[],
  source_signal_count integer NOT NULL,
  target_consumes text[] NOT NULL DEFAULT ARRAY[]::text[],
  truth_promotion_allowed boolean NOT NULL DEFAULT false,
  PRIMARY KEY(meta_run_id, bridge_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_agenda_ledger (
  meta_run_id text NOT NULL,
  agenda_id text NOT NULL,
  seed_kind text NOT NULL,
  seed_text text NOT NULL,
  source_engines text[] NOT NULL DEFAULT ARRAY[]::text[],
  truth_status text NOT NULL,
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, agenda_id)
);

CREATE TABLE IF NOT EXISTS destruktion_meta.hybrid_trace_ledger (
  meta_run_id text NOT NULL,
  trace_id text NOT NULL,
  agenda_id text NOT NULL,
  source_engines text[] NOT NULL DEFAULT ARRAY[]::text[],
  cross_family_depth integer NOT NULL,
  truth_status text NOT NULL,
  payload jsonb NOT NULL,
  PRIMARY KEY(meta_run_id, trace_id)
);

CREATE INDEX IF NOT EXISTS idx_dm_hybrid_bridge_run_pair ON destruktion_meta.hybrid_bridge_ledger(meta_run_id,from_engine,to_engine);
CREATE INDEX IF NOT EXISTS idx_dm_hybrid_agenda_run ON destruktion_meta.hybrid_agenda_ledger(meta_run_id);
CREATE INDEX IF NOT EXISTS idx_dm_hybrid_trace_run ON destruktion_meta.hybrid_trace_ledger(meta_run_id);

-- Engine registry seed
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_01',1,'Destruktion COMPLETE 0.13 — frame-atom externalization','0.13.0-alpha.1','IMMUTABLE_NATIVE_LINEAGE','DEGRADED_HISTORICAL_EVIDENCE','Engine_1.zip','f8bfd30ae447edffcb72059b3576ab79df73230ec856bf5677d73cf4335f2c87','["frame_atom_externalization", "interrogative_induction", "micro_local_ecology", "operator_competition", "cross_corpus_transfer", "expert_cycle"]'::jsonb,'{"native": "DEGRADED_HISTORICAL_EVIDENCE", "passed": 94, "failed": 2, "note": "two release-evidence tests reference missing historical src/engine.mjs"}'::jsonb,'{"focus": null, "stages": [], "claim_ceiling": "NATIVE_CLAIM_CEILING_PRESERVED"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_02',2,'Destruktion integrated 0.10 — open-set/operator evolution','0.10.0-alpha.1','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','Engine_2.zip','faec0824fc7d55993ef0eeb6e7c3d81f78a6cd5cae1a969c0d60ef4f3d4823f1','["open_set_operator_discovery", "reversible_operator_mutation", "operator_evolution", "external_validation_protocol", "micro_local_operator_ecology"]'::jsonb,'{"native": "PASS", "passed": 129, "failed": 0}'::jsonb,'{"focus": null, "stages": [], "claim_ceiling": "NATIVE_CLAIM_CEILING_PRESERVED"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_03',3,'Destruktion UNIFIED 0.15 — shared semantic boundary','0.15.0-alpha.1','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','Engine_3.zip','0f1e29abaacd44d57fb765d3a40d31722e663342012b312acdf3211bab476eee','["shared_semantic_boundary", "cross_lineage_differential", "native_output_retention", "lineage_fixity", "canonical_normalization"]'::jsonb,'{"native": "PASS", "passed": 18, "failed": 0}'::jsonb,'{"focus": null, "stages": [], "claim_ceiling": "NATIVE_CLAIM_CEILING_PRESERVED"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_04',4,'Destruktion portable 0.16 — parse-program synthesis','0.16.0-alpha.1','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','Engine_4.zip','3874f34d7f747a1a4b8e22a8c44ab92c06f0701d91a4a57c4bc6a7c40034d75f','["semantic_role", "semantic_scope", "discourse_uncertainty", "nested_scope_lattice", "multi_expert_adjudication", "source_parse_birth", "parse_program_synthesis", "counterfactual_regression"]'::jsonb,'{"native": "PASS", "passed": 120, "failed": 0}'::jsonb,'{"focus": null, "stages": [], "claim_ceiling": "NATIVE_CLAIM_CEILING_PRESERVED"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_05',5,'Letta / MemGPT lineage','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_5.zip','39e645345b469084574d7d301f6c465ec88aa13c56301cc3c942106887bb50d3','["persistent_memory", "shared_memory", "archival_retrieval", "concept_biography", "checkpoint_memory"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "stateful agents with layered persistent memory, shared memory, archival retrieval and agent-managed context", "stages": ["LOAD_AGENT", "ASSEMBLE_ACTIVE_CONTEXT", "REASON", "USE_TOOLS", "READ_OR_WRITE_MEMORY", "COMPACT_OR_ARCHIVE", "PERSIST_STATE", "NEXT_CONVERSATION"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_06',6,'Microsoft GraphRAG','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_6.zip','b9dca4a8d01f5d32f31201091ceccb1e396cb6b78b86116d8f3dd92a52642f3d','["graph_extraction", "community_structure", "local_global_drift_retrieval", "graph_citations"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "graph extraction, community structure and graph-aware local/global/DRIFT retrieval over large corpora", "stages": ["LOAD_DOCUMENTS", "CHUNK", "EXTRACT_GRAPH_AND_CLAIMS", "EMBED", "DETECT_COMMUNITIES", "GENERATE_REPORTS", "SELECT_QUERY_MODE", "ASSEMBLE_CONTEXT", "REASON", "CITE_GRAPH_AND_TEXT"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_07',7,'FutureHouse / PaperQA2 / Robin','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_7.zip','97f7d2afe9aab48fcbf1ee8aaa4b07ff97ce5ef9003b15885d49add261ac3826','["scientific_evidence", "hypothesis_loop", "test_design", "contradiction_tracking"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "evidence-centric scientific literature research plus an iterative hypothesis–experiment–analysis loop", "stages": ["QUEST", "LITERATURE_SEARCH", "EVIDENCE_GATHER", "SOURCE_EVALUATION", "SYNTHESIS", "HYPOTHESIS", "TEST_OR_DATA", "ANALYSIS", "UPDATE_HYPOTHESES", "FOLLOW_UP_OR_REPORT"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_08',8,'Microsoft Magentic-One / MagenticLite','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_8.zip','90fb8e5bf9def305e051b6f280f3f4c94a3461d1fb2ef79e775f1ef6ab119e15','["manager_planner", "specialist_delegation", "critical_point_gate", "context_compaction"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "manager-led specialist orchestration evolving toward a compact planner/coder/delegator plus browser agent, context harness and human critical-point control", "stages": ["USER_TASK", "INCREMENTAL_PLAN", "SELECT_TOOL_OR_AGENT", "EXECUTE_IN_SANDBOX", "OBSERVE_RESULT", "COMPACT_CONTEXT", "CHECK_CRITICAL_POINT", "REPLAN_OR_CONTINUE", "VERIFY", "COMPLETE"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_09',9,'OpenAI Deep Research public-interface architecture','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_9.zip','98d5d57af08f94ee66c6c1f77cdbce3bb623dfa5567749c8ed8d35c31b12b01a','["adaptive_research", "gap_tracking", "tool_routing", "citation_synthesis"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "adaptive long-horizon research over web, files, MCP data and code analysis with citation-rich synthesis", "stages": ["HIGH_LEVEL_QUERY", "INITIAL_PLAN", "SEARCH_OR_FILE_OR_MCP", "READ_EVIDENCE", "IDENTIFY_GAPS", "PIVOT_OR_ANALYZE_WITH_CODE", "ITERATE", "CITATION_AUDIT", "SYNTHESIZE"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_10',10,'CAMEL / OWL','1.1-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_10.zip','763118458bf587499961b1681fa20653b394dbb94a5735ae7186109cd18a7853','["dynamic_workforce", "agent_society", "parallel_delegation", "worker_memory"]'::jsonb,'{"native": "PASS", "passed": 3, "failed": 0}'::jsonb,'{"focus": "agent societies, role-playing collaboration, dynamic workforce orchestration and tool-rich specialist execution", "stages": ["TASK_INTAKE", "DECOMPOSE", "MATCH_WORKERS", "PARALLEL_OR_ROLEPLAY_EXECUTION", "TOOL_USE", "COLLECT_RESULTS", "CRITIQUE_OR_REASSIGN", "MERGE_WITH_DISSENT", "LEARN_WORKFLOW", "END"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_11',11,'Microsoft Agent Framework','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_11.zip','a5f769eb722e3defd3d548954a2d50d30161a9d9c2b38d7c89d3552d2148f93b','["multi_agent_workflow", "sequential_parallel_composition", "policy_gate", "workflow_events"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "production-grade multi-agent workflows, state, checkpoints, observability and governance", "stages": ["REQUEST", "POLICY_MIDDLEWARE", "SELECT_WORKFLOW", "ORCHESTRATE_AGENTS", "TOOL_CALLS", "STATE_UPDATE", "CHECKPOINT", "HUMAN_GATE_IF_NEEDED", "OBSERVE", "COMPLETE"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_12',12,'LangGraph','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_12.zip','284a7a6f1845171c82b6e1fdc88c95d42ee2d223be0a472dac3c7f92195d2de8','["durable_state_graph", "checkpoint_resume", "conditional_routing", "thread_state"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "durable stateful graph orchestration with explicit control, persistence and interrupts", "stages": ["REQUEST", "LOAD_THREAD_STATE", "ROUTE", "RUN_NODE_OR_SUBGRAPH", "MERGE_STATE", "CHECKPOINT", "OPTIONAL_INTERRUPT", "LOOP_OR_END", "PERSIST_LONG_TERM_MEMORY"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_13',13,'GPT Researcher','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_13.zip','8cb5b966ba0d3276b397d96b73daf88ed535ad421cb942591dbc79360df0f929','["planner_executor_editor", "parallel_research", "review_revision", "publication"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "planner–executor research with source tracking, aggregation and publishing", "stages": ["QUERY", "AGENT_FACTORY", "PLAN", "PARALLEL_RESEARCH", "SOURCE_SUMMARIES", "FILTER", "EDITORIAL_OUTLINE", "DRAFT", "REVIEW", "REVISION", "PUBLISH"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_14',14,'Stanford STORM / Co-STORM','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_14.zip','6b2031df2adaf15fd6b2aa2146798c67328d77d99ed7638d7deb33c7ab3e1fd6','["multi_perspective_research", "question_generation", "outline_synthesis", "source_grounded_writing"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "multi-perspective knowledge curation and grounded long-form synthesis", "stages": ["INTAKE", "PERSPECTIVE_DISCOVERY", "QUESTION_PORTFOLIO", "RETRIEVAL", "GROUNDED_DIALOGUE", "KNOWLEDGE_STORE", "OUTLINE", "SECTION_WRITING", "POLISH", "AUDIT"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_15',15,'Sakana AI Scientist-v2','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_15.zip','767dd75fa79217faa7315af80bc06aabf6b62ff03c72beb7981095c0f4af691a','["research_tree", "hypothesis_branching", "experiment_manager", "branch_pruning", "novelty_search"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "open-ended autonomous research via progressive agentic tree search and experiment management", "stages": ["IDEATE", "ROOT_BRANCHES", "SELECT_BRANCH", "EXPAND_HYPOTHESIS", "RUN_EXPERIMENT", "ANALYZE", "UPDATE_TREE", "PRUNE_OR_BRANCH", "REPEAT_WITH_BUDGET", "WRITE", "REVIEW"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;
INSERT INTO destruktion_meta.engine_registry(engine_id,ordinal,name,version,lineage_policy,status,source_archive,source_sha256,capabilities,native_test,metadata) VALUES ('engine_16',16,'DSPy','1.0-clean-room','IMMUTABLE_NATIVE_LINEAGE','ACTIVE','engine_16.zip','db1ec8b9858f8619a17f3857f25ac784263666455a2336c2c5cc2451daafafe4','["typed_signatures", "program_optimization", "trace_learning", "pareto_candidate_selection"]'::jsonb,'{"native": "PASS", "passed": 2, "failed": 0}'::jsonb,'{"focus": "declarative, evaluable and optimizable language-model programs", "stages": ["DECLARE_SIGNATURES", "COMPOSE_MODULES", "RUN_BASELINE", "EVALUATE", "COLLECT_TRACES", "OPTIMIZER_PROPOSES_CANDIDATES", "VALIDATE_CANDIDATES", "SELECT_PARETO_OR_BEST", "FREEZE_COMPILED_PROGRAM"], "claim_ceiling": "PROPOSAL_UNTIL_EVIDENCE_AND_GATES"}'::jsonb) ON CONFLICT(engine_id) DO UPDATE SET name=EXCLUDED.name,version=EXCLUDED.version,status=EXCLUDED.status,source_sha256=EXCLUDED.source_sha256,capabilities=EXCLUDED.capabilities,native_test=EXCLUDED.native_test,metadata=EXCLUDED.metadata;CREATE TABLE IF NOT EXISTS destruktion_meta.routing_ledger (

-- 1.4 polycentric adaptive re-entry ledgers
CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_reentry_ledger (
  meta_run_id text PRIMARY KEY, reentry_hash text NOT NULL, round_count integer NOT NULL,
  all16_rounds integer NOT NULL, total_generative_positions integer NOT NULL,
  unique_claim_types integer NOT NULL, peer_pair_coverage integer NOT NULL,
  mean_round_novelty double precision NOT NULL, last_round_novelty double precision NOT NULL,
  stop_reason text NOT NULL, metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  claim_ceiling text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_round_ledger (
  meta_run_id text NOT NULL, round_index integer NOT NULL, round_hash text NOT NULL,
  scheduled_engines text[] NOT NULL, global_novelty double precision NOT NULL,
  novelty jsonb NOT NULL DEFAULT '{}'::jsonb, metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, round_index)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.useful_effect_ledger (
  meta_run_id text NOT NULL, effect_id text NOT NULL, state text NOT NULL,
  score double precision NOT NULL, payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(meta_run_id, effect_id)
);
CREATE TABLE IF NOT EXISTS destruktion_meta.polycentric_edge_ledger (
  meta_run_id text NOT NULL, edge_id text NOT NULL, from_node text NOT NULL, to_node text NOT NULL,
  kind text NOT NULL, payload jsonb NOT NULL DEFAULT '{}'::jsonb, truth_effect text NOT NULL DEFAULT 'NONE',
  PRIMARY KEY(meta_run_id, edge_id)
);
CREATE INDEX IF NOT EXISTS idx_dm_poly_round_novelty ON destruktion_meta.polycentric_round_ledger(meta_run_id,global_novelty);
CREATE INDEX IF NOT EXISTS idx_dm_effect_state ON destruktion_meta.useful_effect_ledger(meta_run_id,state);
