import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { validateIndependentFamilyResult, validateEcologyDownstreamResult } from "./validator.mjs";

function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
function stableId(prefix, value) { return `${prefix}-${createHash("sha256").update(String(value)).digest("hex").slice(0, 14).toUpperCase()}`; }
function unique(values) { return [...new Set(values)]; }

function localStatus(decision) {
  if (decision === "SELECT_LOCAL_WINNER") return "QUALIFIED_LOCAL_ROUTING";
  if (decision === "LOCAL_COMPOSITION") return "QUALIFIED_LOCAL_COMPOSITION";
  if (decision === "KEEP_RIVALS_UNRESOLVED") return "RIVALS_UNRESOLVED";
  return "INSUFFICIENT_LOCAL_ROUTING";
}

function render(result) {
  const rows=result.expert_layer.local_adjudications.map((x)=>`| ${x.window_id} | ${x.heading} | ${x.epistemic_status} | ${x.selected_candidates.join(", ") || "—"} | ${x.residual_hints.join(", ") || "—"} |`).join("\n");
  const boundaries=result.boundaries.map((x)=>`| ${x.boundary_id} | ${x.boundary_type} | ${x.unresolved ? "open" : "resolved-local"} |`).join("\n");
  return `# Micro-local downstream integration\n\nOutcome: **${result.outcome}**  \nPolicy: **${result.integration_policy}**\n\n## Local expert routing\n\n| Window | Heading | Epistemic status | Operator(s) | Residual |\n|---|---|---|---|---|\n${rows}\n\n## Hermeneutic boundaries\n\n| Boundary | Type | State |\n|---|---|---|\n${boundaries}\n\n## Global synthesis gate\n\n**${result.expert_layer.global_adjudication.epistemic_status}**\n\n${result.expert_layer.global_adjudication.rationale}\n\n## Living graph\n\n- nodes: ${result.living_graph.nodes.length}\n- edges: ${result.living_graph.edges.length}\n- local residual nodes: ${result.summary.local_residual_nodes}\n- open boundaries preserved: ${result.summary.open_boundaries}\n- global thesis allowed: ${result.summary.global_thesis_allowed}\n\n## Claim ceiling\n\n${result.claim_ceiling}\n\nThe adapter preserves local routing and boundaries. It does not convert routing success into authorial, semantic or ontological validation.\n`;
}

export function buildEcologyDownstream(ecology, engineVersion = "0.10.0-alpha.1") {
  const nodes=[];
  const edges=[];
  const operatorNodes=new Set();
  let edgeCounter=1;
  const inquiryByWindow=new Map();

  for (const window of ecology.windows) {
    const qid=stableId("DLQ", `${window.window_id}|${window.paragraph_hashes.join("|")}`);
    inquiryByWindow.set(window.window_id,qid);
    nodes.push({
      node_id: qid,
      node_type:"LOCAL_INQUIRY",
      window_id:window.window_id,
      selector_ids:window.paragraph_segment_ids,
      proposition:`Which local interrogative regime preserves the source-linked distinctions of ${window.heading} with the lowest distortion?`,
      claim_ceiling:"QUESTION_NOT_VERDICT",
    });
    for (const selected of window.selected_candidates) {
      const oid=`OP-${selected}`;
      if (!operatorNodes.has(oid)) {
        operatorNodes.add(oid);
        nodes.push({node_id:oid,node_type:"SOURCE_BORN_OPERATOR",window_id:null,selector_ids:[],proposition:selected,claim_ceiling:"ROUTING_OPERATOR_NOT_ONTOLOGY"});
      }
      edges.push({edge_id:`DLE-${String(edgeCounter++).padStart(4,"0")}`,from:qid,to:oid,relation:"LOCALLY_TESTS"});
    }
    if (window.decision==="ABSTAIN_UNRESOLVED" || window.residual_hints.length || window.unserved_signal_families.length) {
      const rid=stableId("DLR", `${window.window_id}|${window.residual_hints.join("|")}|${window.unserved_signal_families.join("|")}|${window.decision}`);
      nodes.push({
        node_id:rid,node_type:"LOCAL_RESIDUAL",window_id:window.window_id,selector_ids:window.paragraph_segment_ids,
        proposition:window.decision==="ABSTAIN_UNRESOLVED" ? "Local routing remains ABSTAIN_UNRESOLVED." : `Unserved local distinctions remain: ${unique([...window.residual_hints,...window.unserved_signal_families]).join(", ")}.`,
        claim_ceiling:"RESIDUAL_REOPENS_QUESTION_NOT_EVIDENCE_OF_TRUTH",
      });
      edges.push({edge_id:`DLE-${String(edgeCounter++).padStart(4,"0")}`,from:qid,to:rid,relation:"OPENS_RESIDUAL"});
    }
  }

  for (const boundary of ecology.boundaries) {
    const bid=`BOUNDARY-${boundary.boundary_id}`;
    nodes.push({
      node_id:bid,node_type:"HERMENEUTIC_BOUNDARY",window_id:null,selector_ids:[],
      proposition:`${boundary.boundary_type}: ${boundary.from_window_id} → ${boundary.to_window_id}`,
      claim_ceiling:boundary.unresolved ? "OPEN_BOUNDARY_MUST_NOT_BE_SYNTHESIZED_AWAY" : "BOUNDARY_DESCRIPTOR_NOT_GLOBAL_THEORY",
    });
    const from=inquiryByWindow.get(boundary.from_window_id);
    const to=inquiryByWindow.get(boundary.to_window_id);
    if (from) edges.push({edge_id:`DLE-${String(edgeCounter++).padStart(4,"0")}`,from,to:bid,relation:"ENDS_AT_BOUNDARY"});
    if (to) edges.push({edge_id:`DLE-${String(edgeCounter++).padStart(4,"0")}`,from:bid,to,relation:"REOPENS_AS"});
  }

  const localAdjudications=ecology.windows.map((window)=>({
    window_id:window.window_id,
    heading:window.heading,
    epistemic_status:localStatus(window.decision),
    selected_candidates:window.selected_candidates,
    profile_hints:window.profile_hints,
    residual_hints:window.residual_hints,
    unserved_signal_families:window.unserved_signal_families,
    warrant:window.decision==="ABSTAIN_UNRESOLVED"
      ? "No available source-born operator is locally warranted; abstention is retained as information."
      : "Routing is qualified only by source-linked distinction gain and distortion loss; it is not a truth verdict.",
    claim_ceiling:"LOCAL_ROUTING_ADJUDICATION_NOT_AUTHORIAL_ONTOLOGY_OR_EXTERNAL_SEMANTIC_VALIDATION",
  }));

  const globalAbstain=ecology.synthesis.decision==="PRESERVE_POLYPHONIC_LOCALITY"
    || ecology.boundaries.some((b)=>b.unresolved)
    || new Set(ecology.windows.map((w)=>w.operator_family)).size>1;
  const globalAdjudication={
    epistemic_status:globalAbstain ? "POLYPHONIC_GLOBAL_ABSTENTION" : "QUALIFIED_SINGLE_REGIME_REUSE",
    thesis_allowed:false,
    global_selected_candidates:globalAbstain ? [] : ecology.synthesis.global_selected_candidates,
    rationale:globalAbstain
      ? "Distinct local operator regimes or unresolved windows are present; a single global operator would erase source-linked heterogeneity."
      : "One routing regime recurs locally, but downstream reuse remains non-promoting and does not license a philosophical thesis.",
  };
  const distinctFamilies=new Set(ecology.windows.map((w)=>w.operator_family).filter((x)=>!["GENERIC_SOURCE_FORCED_REVISION","MULTI_FAMILY_LOCAL_PROFILE"].includes(x)));
  return {
    result_version:"DAE-ECOLOGY-DOWNSTREAM-RESULT-1.0",
    engine_version:engineVersion,
    generated_at:new Date().toISOString(),
    outcome:"PRESERVES_MICRO_LOCAL_ECOLOGY_DOWNSTREAM",
    integration_policy:"WINDOW_OPERATOR_RESIDUAL_BOUNDARY_PROVENANCE_PRESERVED_THROUGH_LIVING_AND_EXPERT_LAYERS",
    source_ecology_sha256:"",
    source_corpus_id:ecology.source.corpus_id,
    living_graph:{nodes,edges,raw_text_included:false},
    expert_layer:{local_adjudications:localAdjudications,global_adjudication:globalAdjudication},
    boundaries:ecology.boundaries,
    summary:{
      windows:ecology.windows.length,
      local_adjudications:localAdjudications.length,
      local_residual_nodes:nodes.filter((n)=>n.node_type==="LOCAL_RESIDUAL").length,
      open_boundaries:ecology.boundaries.filter((b)=>b.unresolved).length,
      distinct_operator_families_observed:distinctFamilies.size,
      global_thesis_allowed:false,
    },
    claim_ceiling:"DOWNSTREAM_PRESERVATION_OF_LOCAL_ROUTING_AND_BOUNDARIES_NOT_EXTERNAL_SEMANTIC_VALIDATION_OR_CORE_PROMOTION",
  };
}

export async function runEcologyDownstream(ecologyFile, outputDirectory, options={}) {
  const file=path.resolve(ecologyFile);
  const bytes=await readFile(file);
  const ecology=JSON.parse(bytes.toString("utf8"));
  const sourceIssues=await validateIndependentFamilyResult(ecology);
  if (sourceIssues.length) throw new Error(`Independent-family ecology input invalid: ${JSON.stringify(sourceIssues,null,2)}`);
  const result=buildEcologyDownstream(ecology, options.engineVersion ?? ecology.engine_version);
  result.source_ecology_sha256=sha256(bytes);
  const issues=await validateEcologyDownstreamResult(result);
  if (issues.length) throw new Error(`Ecology downstream result invalid: ${JSON.stringify(issues,null,2)}`);
  const out=path.resolve(outputDirectory);
  await mkdir(out,{recursive:false});
  const files={
    result:path.join(out,"ecology_downstream_result.json"),
    report:path.join(out,"ECOLOGY_DOWNSTREAM_REPORT.md"),
    living:path.join(out,"ECOLOGY_LIVING_GRAPH.json"),
    expert:path.join(out,"ECOLOGY_EXPERT_LAYER.json"),
  };
  await Promise.all([
    writeFile(files.result,`${JSON.stringify(result,null,2)}\n`,"utf8"),
    writeFile(files.report,render(result),"utf8"),
    writeFile(files.living,`${JSON.stringify(result.living_graph,null,2)}\n`,"utf8"),
    writeFile(files.expert,`${JSON.stringify(result.expert_layer,null,2)}\n`,"utf8"),
  ]);
  return {result,output_dir:out,files};
}
