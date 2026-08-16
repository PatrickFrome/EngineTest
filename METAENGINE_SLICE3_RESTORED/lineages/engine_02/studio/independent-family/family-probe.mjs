import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { headingBoundedWindows, readDocxSegments, profileInterrogativeTexts } from "./family-signal-runtime.mjs";

function sha256(bytes){return createHash("sha256").update(bytes).digest("hex");}

export async function runIndependentFamilyProbe(docxFile, outputDirectory, options={}) {
  const source=path.resolve(docxFile);
  const bytes=await readFile(source);
  const segments=await readDocxSegments(source,{documentLanguage:options.documentLanguage ?? "und"});
  const sourceSegments=segments.filter((s)=>s.archive_state==="ACTIVE" && s.layer_routing?.label==="SOURCE" && s._text);
  const profile=profileInterrogativeTexts(sourceSegments.map((s)=>s._text));
  const windows=headingBoundedWindows(segments,{
    heading_level:Number(options.headingLevel ?? 1),
    include_layers:["SOURCE"],
    minimum_text_chars:Number(options.minimumTextChars ?? 30),
    maximum_window_paragraphs:Number(options.maximumWindowParagraphs ?? 8),
  });
  const familyCandidate=profile.processual_profile_hints.length ? {
    family_id:"PROCESSUAL_HERMENEUTIC_PROFILE",
    candidate:"PROCESSUAL_HERMENEUTIC_FAMILY_CANDIDATE",
    status:"EXPERIMENTAL_PROBE_NOT_SOURCE_BIRTH",
    profile_hints:profile.processual_profile_hints,
    active_signal_families:profile.active_signal_families.filter((x)=>["TEMPORALITY","EXPECTATION","ENACTMENT_PRACTICE","REPETITION_RHYTHM","MATERIAL_MEDIATION","ABSENCE_WITHDRAWAL","TRACE_DISCLOSURE","ADDRESS_RESPONSE"].includes(x)),
    epistemic_firewall:{
      source_birth_confirmed:false,
      promotion_forbidden:true,
      required_next_checks:["SOURCE_FORCED_MUTATION_TRACE","RIVAL_FAMILY_COMPARISON","NEGATIVE_CONTROL","CROSS_CORPUS_REGRESSION","SEMANTIC_ROLE_REVIEW"],
    },
  } : null;
  const result={
    probe_version:"STUDIO-INDEPENDENT-FAMILY-PROBE-0.7",
    generated_at:new Date().toISOString(),
    source:{basename:path.basename(source),sha256:sha256(bytes),raw_text_included:false},
    global_profile:profile,
    local_windows:windows.map((w)=>({
      window_id:w.window_id,heading:w.heading,paragraph_segment_ids:w.paragraph_segment_ids,paragraph_hashes:w.paragraph_hashes,
      operator_family:w.operator_family,source_operator_candidate:w.source_operator_candidate,active_signal_families:w.active_signal_families,
      profile_hints:w.profile_hints,signal_counts:w.signal_counts,
    })),
    family_candidate:familyCandidate,
    claim_ceiling:"INTERROGATIVE_FAMILY_PROBE_NOT_SOURCE_BIRTH_NOT_AUTHORIAL_ONTOLOGY_NOT_CORE_PROMOTION",
  };
  const out=path.resolve(outputDirectory);
  await mkdir(out,{recursive:false});
  const file=path.join(out,"independent_family_probe.json");
  await writeFile(file,`${JSON.stringify(result,null,2)}\n`,"utf8");
  return {result,output_dir:out,files:{result:file}};
}
