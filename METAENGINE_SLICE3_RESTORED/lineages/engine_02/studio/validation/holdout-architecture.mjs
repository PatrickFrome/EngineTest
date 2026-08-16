import { createHash } from 'node:crypto';
import { access, mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { profileInterrogativeTexts } from '../independent-family/family-signal-runtime.mjs';

const STATUSES = ['SUPPORTED','QUALIFIED','REJECTED','INSUFFICIENT'];
const HYPOTHESES = [
  {
    id: 'RELATION_GENESIS_APPLICABILITY',
    title: 'Relation-genesis applicability',
    statement: 'For this passage, a relation-genesis interrogation is locally warranted: analyzing difference, dependence, reciprocity, reference, system/field, priority, or differentiation adds a source-linked distinction rather than merely matching vocabulary.',
  },
  {
    id: 'PROCESSUAL_HERMENEUTIC_APPLICABILITY',
    title: 'Processual-hermeneutic applicability',
    statement: 'For this passage, a processual-hermeneutic interrogation is locally warranted: temporality, enactment/practice, repetition/rhythm, material mediation, absence/withdrawal, disclosure/trace, or address/response adds a source-linked distinction rather than merely matching vocabulary.',
  },
  {
    id: 'OPEN_SET_NECESSITY',
    title: 'Open-set necessity',
    statement: 'At least one central distinction in this passage is not adequately served by the frozen known operator families, so an open-set operator rival is necessary for analysis rather than optional novelty.',
  },
];
const DEVELOPMENT_EXCLUSIONS = ['Martin Heidegger','René Descartes','Baruch Spinoza','Aristotle','Ferdinand de Saussure'];

function sha256(value){return createHash('sha256').update(value).digest('hex');}
function jsonBytes(value){return Buffer.from(`${JSON.stringify(value,null,2)}\n`,'utf8');}
function nowIso(value){return value ?? new Date().toISOString().replace(/\.\d{3}Z$/u,'Z');}
async function exists(file){try{await access(file);return true;}catch{return false;}}
async function requireNewDirectory(directory){try{await stat(directory);throw new Error(`Output directory already exists: ${directory}`);}catch(error){if(error.code!=='ENOENT')throw error;}}
function canonical(value){if(Array.isArray(value))return value.map(canonical);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));return value;}
function canonicalHash(value){return sha256(JSON.stringify(canonical(value)));}
function unitId(excerptId,hypothesisId,excerptSha){return `HU-${sha256(`${excerptId}\n${hypothesisId}\n${excerptSha}`).slice(0,16).toUpperCase()}`;}
function predictionFor(hypothesisId, profile, sourceResistance){
  if(hypothesisId==='RELATION_GENESIS_APPLICABILITY'){
    const n=profile.relation_profile_hints.length;
    if(n>=2)return {status:'SUPPORTED',confidence:0.78,reason:`${n} frozen relation-profile hints fired on the preselected passage.`};
    if(n===1)return {status:'QUALIFIED',confidence:0.64,reason:'One frozen relation-profile hint fired; local applicability remains limited.'};
    return {status:'INSUFFICIENT',confidence:0.72,reason:'No frozen relation-profile hint fired; absence of lexical signal is not a semantic rejection.'};
  }
  if(hypothesisId==='PROCESSUAL_HERMENEUTIC_APPLICABILITY'){
    const n=profile.processual_profile_hints.length;
    if(n>=2)return {status:'SUPPORTED',confidence:0.78,reason:`${n} frozen processual-profile hints fired on the preselected passage.`};
    if(n===1)return {status:'QUALIFIED',confidence:0.64,reason:'One frozen processual-profile hint fired; local applicability remains limited.'};
    return {status:'INSUFFICIENT',confidence:0.72,reason:'No frozen processual-profile hint fired; absence of lexical signal is not a semantic rejection.'};
  }
  const open=sourceResistance?.open_set_status ?? sourceResistance?.open_set_candidate?.status ?? 'UNRESOLVED';
  if(open==='OPEN_SET_RIVAL_REQUIRED')return {status:'QUALIFIED',confidence:0.7,reason:'Frozen source-resistance runtime requires an open-set rival, but does not validate the rival as a source ontology.'};
  if(open==='NO_OPEN_SET_PRESSURE')return {status:'REJECTED',confidence:0.68,reason:'Frozen source-resistance runtime detected no open-set pressure in this passage.'};
  return {status:'INSUFFICIENT',confidence:0.65,reason:`Open-set runtime state ${open} does not resolve necessity.`};
}
function packet(manifest, label){
  return {
    packet_version:'DESTRUKTION-HOLDOUT-BLIND-PACKET-0.9', benchmark_id:manifest.benchmark_id, packet_id:`HOLDOUT-${label}-${sha256(`${manifest.benchmark_id}\n${label}`).slice(0,12).toUpperCase()}`,
    blinding:{dae_predictions_removed:true,dae_signal_counts_removed:true,open_set_runtime_state_removed:true,gold_removed:true},
    codebook:manifest.codebook,
    instructions:{source_review_required:true,rule:'Judge whether the architectural hypothesis is warranted by the passage, not whether its vocabulary occurs. SUPPORTED requires source-linked discriminative value; QUALIFIED requires a real but bounded contribution; REJECTED requires source-grounded counterevidence; INSUFFICIENT is abstention.'},
    units:manifest.units.map(u=>({unit_id:u.unit_id,excerpt_id:u.excerpt_id,source_id:u.source_id,author:u.author,title:u.work_title,excerpt_file:u.excerpt_file,excerpt_sha256:u.excerpt_sha256,hypothesis_id:u.hypothesis_id,hypothesis_title:u.hypothesis_title,statement:u.statement})),
    claim_ceiling:'BLIND_HOLDOUT_ANNOTATION_PACKET_NOT_GOLD_OR_DAE_OUTPUT',
  };
}
function annotationTemplate(packet,createdAt){return {annotation_version:'DESTRUKTION-HOLDOUT-ANNOTATION-0.9',benchmark_id:packet.benchmark_id,packet_id:packet.packet_id,coder:{id:'REPLACE_WITH_CODER_ID',independent_of_system_development:true,blinded_to_dae_predictions:true,source_access_attested:true},completed_at:createdAt,units:packet.units.map(u=>({unit_id:u.unit_id,status:null,confidence:null,evidence_refs:[],rationale:''})),claim_ceiling:'INDEPENDENT_HOLDOUT_CODER_JUDGMENT_NOT_ADJUDICATED_GOLD'};}
function goldTemplate(manifest,createdAt){return {gold_version:'DESTRUKTION-HOLDOUT-GOLD-0.9',benchmark_id:manifest.benchmark_id,adjudication:{curator_id:'REPLACE_WITH_CURATOR_ID',independent_of_system_development:true,predictions_hidden_until_gold_frozen:true,annotation_sha256:[]},frozen_at:createdAt,units:manifest.units.map(u=>({unit_id:u.unit_id,gold_status:null,evidence_refs:[],rationale:''})),claim_ceiling:'FROZEN_ADJUDICATED_HOLDOUT_GOLD_FOR_THIS_SAMPLE_ONLY'};}
function externalTemplate(manifest,createdAt){return {predictions_version:'DESTRUKTION-HOLDOUT-EXTERNAL-PREDICTIONS-0.9',benchmark_id:manifest.benchmark_id,system:{system_id:'REPLACE_WITH_SYSTEM_ID',name:'REPLACE_WITH_SYSTEM_NAME',model_or_version:'REPLACE_WITH_EXACT_VERSION',protocol_id:'REPLACE_WITH_FROZEN_PROTOCOL_ID'},independence:{dae_outputs_seen:false,gold_seen:false,annotation_seen:false},generated_at:createdAt,predictions:manifest.units.map(u=>({unit_id:u.unit_id,status:null,confidence:null})),claim_ceiling:'EXTERNAL_HOLDOUT_PREDICTIONS_NOT_GOLD'};}
function semanticChallengeTemplate(manifest,createdAt){const phenomena=['NEGATION','QUOTED_OPPONENT','ATTRIBUTION_SHIFT','MODALITY_WEAKENING','PARAPHRASE','TRANSLATION','DECOY_TERMINOLOGY']; return {challenge_version:'DESTRUKTION-HOLDOUT-SEMANTIC-CHALLENGE-0.9',benchmark_id:manifest.benchmark_id,author:{id:'REPLACE_WITH_INDEPENDENT_CHALLENGE_AUTHOR',independent_of_dae_development:true,dae_predictions_seen:false,gold_seen:false},created_at:createdAt,cases:phenomena.map((phenomenon,index)=>({case_id:`HCH-${String(index+1).padStart(3,'0')}-${phenomenon}`,phenomenon,anchor_unit_id:manifest.units[index].unit_id,variant_text:'REPLACE_WITH_INDEPENDENTLY_AUTHORED_VARIANT',expected_relation:['PARAPHRASE','TRANSLATION'].includes(phenomenon)?'PRESERVE_ARCHITECTURAL_JUDGMENT':'MUST_REASSESS_NOT_COPY_ANCHOR',allowed_statuses:['SUPPORTED','QUALIFIED','REJECTED','INSUFFICIENT'],rationale:'REPLACE_WITH_SOURCE_GROUNDED_EXPECTATION'})),claim_ceiling:'INDEPENDENT_SEMANTIC_STRESS_TEMPLATE_NOT_GOLD'};}

export async function buildHoldoutArchitectureBenchmark(freezeFile, pipelineRoot, outputDirectory, options={}){
  const freezePath=path.resolve(freezeFile); const root=path.dirname(freezePath); const out=path.resolve(outputDirectory); const pipelines=path.resolve(pipelineRoot);
  await requireNewDirectory(out);
  const freeze=JSON.parse(await readFile(freezePath,'utf8'));
  if(freeze.selection_rule?.dae_involved_in_selection!==false)throw new Error('HOLDOUT_SELECTION_NOT_DAE_INDEPENDENT');
  const excerpts=freeze.sources.flatMap(source=>source.excerpts.map(excerpt=>({source,...excerpt})));
  if(excerpts.length<27)throw new Error(`HOLDOUT_EXCERPT_COUNT_TOO_SMALL:${excerpts.length}`);
  const duplicateHashes=excerpts.map(x=>x.sha256).filter((x,i,a)=>a.indexOf(x)!==i);
  if(duplicateHashes.length)throw new Error('HOLDOUT_DUPLICATE_EXCERPT_HASH');
  const developmentOverlap=freeze.sources.filter(s=>DEVELOPMENT_EXCLUSIONS.some(name=>name.toLowerCase()===String(s.author).toLowerCase()));
  if(developmentOverlap.length)throw new Error(`HOLDOUT_DEVELOPMENT_AUTHOR_OVERLAP:${developmentOverlap.map(x=>x.author).join(',')}`);
  const createdAt=nowIso(options.generatedAt); const observations=[]; const units=[]; const predictions=[];
  for(const item of excerpts.sort((a,b)=>a.excerpt_id.localeCompare(b.excerpt_id))){
    const excerptPath=path.join(root,item.file); const bytes=await readFile(excerptPath); const actual=sha256(bytes);
    if(actual!==item.sha256)throw new Error(`HOLDOUT_EXCERPT_FIXITY_FAILED:${item.excerpt_id}`);
    const text=bytes.toString('utf8'); const profile=profileInterrogativeTexts([text]);
    const bankPath=path.join(pipelines,item.excerpt_id,'refinery','hypothesis_bank.json');
    if(!(await exists(bankPath)))throw new Error(`HOLDOUT_PIPELINE_MISSING:${item.excerpt_id}`);
    const bankBytes=await readFile(bankPath); const bank=JSON.parse(bankBytes.toString('utf8')); const sr=bank.source_resistance ?? {};
    const obs={excerpt_id:item.excerpt_id,excerpt_sha256:item.sha256,hypothesis_bank_sha256:sha256(bankBytes),relation_profile_hints:profile.relation_profile_hints,processual_profile_hints:profile.processual_profile_hints,operator_family:profile.operator_family,signal_counts:profile.signal_counts,open_set_status:sr.open_set_status ?? sr.open_set_candidate?.status ?? 'UNRESOLVED',open_set_candidate:sr.open_set_candidate?.candidate ?? null,claim_ceiling:'DAE_ARCHITECTURAL_SIGNAL_OBSERVATION_NOT_GOLD'};
    observations.push(obs);
    for(const hypothesis of HYPOTHESES){
      const pred=predictionFor(hypothesis.id,profile,sr); const id=unitId(item.excerpt_id,hypothesis.id,item.sha256);
      units.push({unit_id:id,excerpt_id:item.excerpt_id,source_id:item.source.source_id,author:item.source.author,work_title:item.source.title,source_url:item.source.source_url,ebook_id:item.source.ebook_id,position_fraction:item.position_fraction,excerpt_file:item.file,excerpt_sha256:item.sha256,hypothesis_id:hypothesis.id,hypothesis_title:hypothesis.title,statement:hypothesis.statement});
      predictions.push({unit_id:id,status:pred.status,confidence:pred.confidence,reason:pred.reason});
    }
  }
  if(units.length<80)throw new Error(`HOLDOUT_UNIT_COUNT_UNDERPOWERED:${units.length}`);
  const seed={freeze_sha256:sha256(await readFile(freezePath)),excerpt_hashes:excerpts.map(x=>x.sha256).sort(),hypotheses:HYPOTHESES.map(x=>x.id)};
  const benchmarkId=`HB-${canonicalHash(seed).slice(0,16).toUpperCase()}`;
  const codebook={SUPPORTED:'Hypothesis is locally warranted and adds a source-linked distinction at the stated scale.',QUALIFIED:'A real source-linked contribution exists but requires explicit limitation of scope, modality, or family dominance.',REJECTED:'Source evidence or a decisive rival undermines the hypothesis for this passage.',INSUFFICIENT:'Available passage evidence does not justify support or rejection; abstain.'};
  const manifest={benchmark_version:'DESTRUKTION-HOLDOUT-ARCHITECTURE-0.9',benchmark_id:benchmarkId,generated_at:createdAt,task:'PASSAGE_LEVEL_ARCHITECTURAL_HYPOTHESIS_STATUS',unit_count:units.length,source_count:freeze.sources.length,excerpt_count:excerpts.length,hypotheses:HYPOTHESES,selection:{...freeze.selection_rule,frozen_source_manifest:path.basename(freezePath),development_author_exclusions:DEVELOPMENT_EXCLUSIONS,holdout_embargo:'NO_DAE_TUNING_MUTATION_OR_PROMOTION_ON_HOLDOUT_UNTIL_GOLD_AND_PRIMARY_EVALUATION_ARE_FROZEN'},codebook,units,blinding:{dae_predictions_sealed:true,two_independent_coders_minimum:true,gold_after_raw_annotations:true,external_system_predictions_before_gold:true},evaluation_plan:{minimum_units:80,minimum_independent_coders:2,minimum_gold_per_status_target:10,agreement_alpha_target:0.67,adversarial_semantic_suite_required:true,scalar_global_winner_forbidden:true},claim_ceiling:'FROZEN_HOLDOUT_DESIGN_NOT_EXTERNAL_VALIDATION_RESULT'};
  const dae={predictions_version:'DESTRUKTION-HOLDOUT-DAE-PREDICTIONS-0.9',benchmark_id:benchmarkId,sealed_before_labels:true,system:{system_id:'DAE_PRIMARY',engine_version:'0.10.0-alpha.1+STUDIO-0.9-HOLDOUT'},predictions,claim_ceiling:'FROZEN_DAE_HOLDOUT_PREDICTIONS_NOT_GOLD'};
  const obsPayload={observations_version:'DESTRUKTION-HOLDOUT-DAE-OBSERVATIONS-0.9',benchmark_id:benchmarkId,generated_at:createdAt,observations,claim_ceiling:'MACHINE_SIGNAL_TRACE_FOR_AUDIT_NOT_HUMAN_GOLD'};
  const pa=packet(manifest,'A'); const pb=packet(manifest,'B');
  await mkdir(path.join(out,'blind_packets'),{recursive:true}); await mkdir(path.join(out,'annotation_templates'),{recursive:true}); await mkdir(path.join(out,'templates'),{recursive:true});
  const files={manifest:jsonBytes(manifest),predictions:jsonBytes(dae),observations:jsonBytes(obsPayload),packetA:jsonBytes(pa),packetB:jsonBytes(pb),annotationA:jsonBytes(annotationTemplate(pa,createdAt)),annotationB:jsonBytes(annotationTemplate(pb,createdAt)),gold:jsonBytes(goldTemplate(manifest,createdAt)),external:jsonBytes(externalTemplate(manifest,createdAt)),challenge:jsonBytes(semanticChallengeTemplate(manifest,createdAt))};
  const lock={lock_version:'DESTRUKTION-HOLDOUT-LOCK-0.9',benchmark_id:benchmarkId,locked_at:createdAt,manifest_sha256:sha256(files.manifest),sealed_dae_predictions_sha256:sha256(files.predictions),dae_observations_sha256:sha256(files.observations),blind_packet_sha256:{A:sha256(files.packetA),B:sha256(files.packetB)},source_freeze_sha256:sha256(await readFile(freezePath)),claim_ceiling:'LOCAL_CRYPTOGRAPHIC_FIXITY_LOCK_NOT_PUBLIC_TIMESTAMP_AUTHORITY'};
  await Promise.all([
    writeFile(path.join(out,'holdout_manifest.json'),files.manifest,{flag:'wx'}),writeFile(path.join(out,'sealed_dae_predictions.json'),files.predictions,{flag:'wx'}),writeFile(path.join(out,'DAE_OBSERVATIONS.json'),files.observations,{flag:'wx'}),writeFile(path.join(out,'blind_packets','coder_A.json'),files.packetA,{flag:'wx'}),writeFile(path.join(out,'blind_packets','coder_B.json'),files.packetB,{flag:'wx'}),writeFile(path.join(out,'annotation_templates','coder_A.template.json'),files.annotationA,{flag:'wx'}),writeFile(path.join(out,'annotation_templates','coder_B.template.json'),files.annotationB,{flag:'wx'}),writeFile(path.join(out,'templates','gold.template.json'),files.gold,{flag:'wx'}),writeFile(path.join(out,'templates','external_system.template.json'),files.external,{flag:'wx'}),writeFile(path.join(out,'templates','semantic_challenge.template.json'),files.challenge,{flag:'wx'}),writeFile(path.join(out,'HOLDOUT_LOCK.json'),jsonBytes(lock),{flag:'wx'}),
  ]);
  const counts={}; for(const p of predictions)counts[p.status]=(counts[p.status]??0)+1;
  const status=`# Frozen architecture holdout ${benchmarkId}\n\nStatus: **SIZE_GATE_READY / BLOCKED_PENDING_INDEPENDENT_LABELS**.\n\n- Sources: ${freeze.sources.length}\n- Deterministically selected excerpts: ${excerpts.length}\n- Passage×hypothesis units: ${units.length}\n- DAE prediction distribution: ${Object.entries(counts).map(([k,v])=>`${k}=${v}`).join(', ')}\n- Selection used DAE outputs: **NO**\n- Development-author overlap: **0**\n- Gold present: **NO (template only)**\n- External comparator outputs present: **NO (template only)**\n\nHoldout embargo: do not tune operators, families, thresholds, mutation gates, or selection rules using these passages until raw coder annotations, adjudicated gold, and primary frozen evaluation are complete.\n\nClaim ceiling: \`${manifest.claim_ceiling}\`.\n`;
  await writeFile(path.join(out,'HOLDOUT_STATUS.md'),status,{flag:'wx'});
  return {manifest,dae,observations:obsPayload,lock,output_dir:out,prediction_counts:counts};
}

export async function auditHoldoutArchitectureBenchmark(directory){
  const root=path.resolve(directory); const required=['holdout_manifest.json','sealed_dae_predictions.json','DAE_OBSERVATIONS.json','HOLDOUT_LOCK.json','blind_packets/coder_A.json','blind_packets/coder_B.json'];
  const missing=[]; for(const rel of required)if(!(await exists(path.join(root,rel))))missing.push(rel);
  if(missing.length)return {status:'INVALID',issues:missing.map(x=>`MISSING:${x}`)};
  const [mb,pb,ob,lb,ab,bb]=await Promise.all(required.map(rel=>readFile(path.join(root,rel))));
  const [manifest,pred,obs,lock]=[mb,pb,ob,lb].map(b=>JSON.parse(b.toString('utf8'))); const issues=[];
  if(sha256(mb)!==lock.manifest_sha256)issues.push('MANIFEST_FIXITY_FAILED');
  if(sha256(pb)!==lock.sealed_dae_predictions_sha256)issues.push('PREDICTIONS_FIXITY_FAILED');
  if(sha256(ob)!==lock.dae_observations_sha256)issues.push('OBSERVATIONS_FIXITY_FAILED');
  if(sha256(ab)!==lock.blind_packet_sha256.A||sha256(bb)!==lock.blind_packet_sha256.B)issues.push('BLIND_PACKET_FIXITY_FAILED');
  if(manifest.unit_count!==manifest.units.length||manifest.units.length<80)issues.push('UNIT_COUNT_GATE_FAILED');
  const ids=manifest.units.map(x=>x.unit_id); if(new Set(ids).size!==ids.length)issues.push('DUPLICATE_UNIT_ID');
  if(pred.benchmark_id!==manifest.benchmark_id||obs.benchmark_id!==manifest.benchmark_id)issues.push('BENCHMARK_ID_MISMATCH');
  if(pred.predictions.length!==manifest.units.length||new Set(pred.predictions.map(x=>x.unit_id)).size!==manifest.units.length)issues.push('PREDICTION_UNIT_SET_FAILED');
  if(pred.predictions.some(x=>!STATUSES.includes(x.status)))issues.push('PREDICTION_STATUS_INVALID');
  if(manifest.selection?.dae_involved_in_selection!==false)issues.push('SELECTION_LEAKAGE');
  return {status:issues.length?'INVALID':'PASS',benchmark_id:manifest.benchmark_id,unit_count:manifest.units.length,source_count:manifest.source_count,excerpt_count:manifest.excerpt_count,issues,claim_ceiling:'HOLDOUT_FIXITY_AND_PROTOCOL_AUDIT_NOT_EXTERNAL_VALIDATION_RESULT'};
}

export { HYPOTHESES, DEVELOPMENT_EXCLUSIONS };
