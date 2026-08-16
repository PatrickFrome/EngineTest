import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceDoc = path.join(root, "vendor", "module4d", "source_document", "Destruktion_4.0_MODULE-MIGRATION-4D_0.1_Machenschaft-Technik-Gestell-Bestand-Ordering.docx");
const outputDir = path.join(root, "fixtures", "4d_candidates");
const sourceHash = createHash("sha256").update(await readFile(sourceDoc)).digest("hex");
const timestamp = "2026-08-11T12:30:00Z";

const ma4 = {
  module_id: "MA4",
  version: "0.1-engine-reconstruction",
  bearer_level: "BEINGNESS_HISTORY_DIAGNOSIS",
  makeability_dimensions: ["PRODUCIBILITY", "PLANABILITY", "CALCULABILITY", "MANIPULABILITY", "OBJECTIFIABILITY", "PROCEDURALIZATION"],
  calculability_relation: "MANIFESTATION",
  experience_relation: "Erlebnis is recorded as a source-linked correlate requiring separate reconstruction, not as a synonym.",
  causality_relation: "Causal dominance is part of the diagnosis but does not establish an interventionist RT06 claim.",
  human_agency_status: "NOT_PRIMARY",
  scope: "EPOCHAL",
  totalization_status: "EPOCHAL_SOURCE_CLAIM",
  counterprofile: "Local making, planning and calculation described without a history-of-being diagnosis.",
  discriminator: "Show a structured interpretation of beingness through makeability rather than the bare presence of human production.",
  revision_trigger: "Primary-text or comparative evidence showing that the profile adds no distinction beyond ordinary making and planning."
};

const geBase = {
  module_id: "GE4",
  version: "0.1-engine-reconstruction",
  disclosure_mode: ["CHALLENGING_FORTH", "ORDERING", "SECURING_AVAILABILITY"],
  ordering_signature: ["AVAILABILITY", "ORDERABILITY", "SUBSTITUTABILITY", "CALCULABILITY", "SECURING", "CHAINED_DEMAND"],
  human_position: ["CHALLENGER", "CHALLENGED_PARTICIPANT", "NOT_MERE_RESERVE"],
  target_domain: ["technology", "nature", "labor", "information", "institutions"],
  alternative_disclosure: "Artifact, design, mediation and governance descriptions may reveal typed mechanisms without an epochal diagnosis.",
  danger_status: "DANGER_SAVING_AMBIGUITY",
  counterprofile: "A heterogeneous technical practice with local ordering but effective alternatives, correction and non-resourceized relations.",
  discriminator: "Identify concrete availability, substitutability and demand-chain mechanisms plus countercases where the fit weakens.",
  revision_trigger: "The diagnosis fails to discriminate cases or merely redescribes every modern technology as Gestell."
};

const bsBase = {
  module_id: "BS4",
  version: "0.1-engine-reconstruction",
  availability: "Readiness and on-call status must be traced through an explicit operational demand chain.",
  substitutability: "Replacement is indexed to system function and may not erase object or agent differences outside that function.",
  demand_linkage: "The record must identify the order, schedule, allocation or dispatch relation that calls the entity into availability.",
  autonomy_shift: "Isolated objecthood recedes relative to system function without being declared metaphysically unreal.",
  context_dependence: "The same entity may be disclosed and handled differently in another practice.",
  reversibility: "Test whether redesign, withdrawal or practice change can alter resourceization without destroying the entity.",
  counterdescription: "Artifact/function/organization analysis may explain the case without a strong standing-reserve diagnosis.",
  discriminator: "Show availability, substitutability and demand linkage together; mere usefulness is insufficient.",
  revision_trigger: "A counterdescription explains the same operational facts with lower ontological cost or the relation changes across contexts."
};

const toBase = {
  module_id: "TO4",
  version: "0.1-engine-reconstruction",
  criteria_tradeoffs: "Competing goals and their decision procedure must be explicit; no hidden aggregate optimum is assumed.",
  human_roles: ["designer", "operator", "governor", "affected party", "reviewer"],
  governance: "Rules, review, escalation, appeal and accountability are encoded separately from technical operation.",
  control_responsibility: "Trace information, decision rights, intervention capacity and forward-looking responsibility.",
  value_status: "MIXED",
  corrigibility: "Testing, monitoring, reversal, appeal and redesign are distinct channels whose effective operation must be checked.",
  discriminator: "Show what a Gestell diagnosis explains beyond the native design, artifact, value and governance account.",
  revision_trigger: "Native analysis exhausts the explanatory work or formal governance does not translate into effective control."
};

function rivals(...items) {
  return items.map(([description, rt, discriminator]) => ({ description, relation_rt_id: rt, bridge: "Requires an independent bridge.", discriminator }));
}

const definitions = [
  {
    id: "4D-MA4-GA65-MACHENSCHAFT", module: "ma4", rt: "RT18",
    from: "GA65 section 61 rejects ordinary malicious human scheming as the operative meaning of Machenschaft in the Seinsfrage.",
    to: "Machenschaft is reconstructed as an interpretation of beingness through makeability, presence, objectifiability and related calculability structures.",
    sources: ["W4D-01#GA65-61-p126", "W4D-02#GA65-61-p127"], bridge: "EXPLICIT", outcome: "QUALIFY",
    operators: ["O0", "O1", "O3", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C2", g_target: "G3", gap: "SMALL", bridge_burden: "Textual reconstruction does not by itself establish a universal ontology of modernity." },
    rivalData: rivals(
      ["Machenschaft means malicious human plotting or domination.", "RT25", "Test whether the source bearer is human conduct or a beingness interpretation."],
      ["Human making causally produces the diagnosed historical disclosure.", "RT06", "Require causal assumptions and evidence rather than lexical proximity to machen."]
    ),
    rationale: "RT18 classifies the source-governed semantic constraint on Machenschaft; it does not turn the term into a causal or moral predicate.",
    profile: ma4
  },
  {
    id: "4D-GE4-GA7-INSTRUMENTAL-FIREWALL", module: "ge4", rt: "RT00",
    from: "The instrumental-anthropological description of technology is correct within its stated scope.",
    to: "Therefore that description exhausts the essence-question and no disclosure or ordering analysis is required.",
    sources: ["W4D-03#GA7-pp7-8", "W4D-04#GA7-pp20-22"], bridge: "ABSENT", outcome: "BLOCK",
    operators: ["O0", "O1", "O3", "O4", "O5", "O6", "O9"], promotion: ["RELATION", "SCOPE"],
    scale: { applicable: true, c_support: "C2", g_target: "G4", gap: "LARGE", bridge_burden: "A correct local definition needs a separate argument to become an exhaustive essence claim." },
    rivalData: rivals(
      ["Instrumental definition is locally correct but non-exhaustive.", "RT02", "Keep definition and scope explicit."],
      ["Gestell introduces a disclosure/manifestation explanandum distinct from instrumentality.", "RT19", "Identify the ordering signature and alternative disclosure mode."]
    ),
    rationale: "RT00 blocks an unsupported transition from a scoped instrumental definition to an exhaustive essence conclusion.",
    profile: { ...geBase, totalization_status: "CONTESTED" }
  },
  {
    id: "4D-BS4-AIRLINER-STANDING-RESERVE", module: "bs4", rt: "RT00",
    from: "An aircraft is maintained on-call, dispatchable, replaceable by function and embedded in an operational demand chain.",
    to: "Within that indexed system relation the aircraft is disclosed as a strong standing-reserve rather than merely an isolated object.",
    sources: ["W4D-05#aircraft-standing-reserve"], bridge: "CONTESTED", outcome: "QUALIFY",
    operators: ["O0", "O1", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C2", g_target: "G2", gap: "NONE", bridge_burden: "Do not promote one operational relation to the entity's exhaustive mode of being." },
    rivalData: rivals(
      ["The case is fully explained by functional role in an aviation system.", "RT14", "Compare explanatory gain beyond role, inputs and outputs."],
      ["The case is an institutional asset/status relation rather than standing-reserve.", "RT13", "Trace office, ownership and entry/exit criteria separately."]
    ),
    rationale: "The frozen registry has no generic resourceization RT; RT00 prevents false precision while BS4 encodes the contextual profile.",
    profile: { ...bsBase, resourceization_level: "STRONG_STANDING_RESERVE", human_case: "NOT_HUMAN" }
  },
  {
    id: "4D-BS4-HUMAN-RESOURCEIZATION-TENSION", module: "bs4", rt: "RT00",
    from: "GA7 says the human, as originally challenged into ordering, never becomes merely standing-reserve.",
    to: "GA79 says the human can be a qualified Bestand-Stück in a way explicitly different from a machine.",
    sources: ["W4D-05#human-not-mere-reserve", "W4D-06#qualified-Bestand-Stueck"], bridge: "CONTESTED", outcome: "UNDERDETERMINED",
    operators: ["O0", "O1", "O3", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C2", g_target: "G3", gap: "SMALL", bridge_burden: "Preserve textual tension and test concrete substitutability, scheduling and replacement mechanisms." },
    rivalData: rivals(
      ["Heidegger excludes humans from standing-reserve without qualification.", "RT02", "Test both source passages and the force of 'merely'."],
      ["Heidegger reduces humans to machines in standing-reserve.", "RT03", "Test the explicit denial of simple human-machine identity."]
    ),
    rationale: "RT00 preserves a genuine cross-text tension instead of forcing identity, contradiction or harmonization before expert review.",
    profile: { ...bsBase, resourceization_level: "CONTESTED", human_case: "CONTESTED" }
  },
  {
    id: "4D-GE4-PLANETARY-TOTALIZATION", module: "ge4", rt: "RT15",
    from: "GA79 uses explicitly universal and planetary language for Ge-Stell and ordered replaceability.",
    to: "The text supports the claim that Heidegger advances a planetary diagnosis, while success of the universal meta-diagnosis remains unestablished.",
    sources: ["W4D-06#planetary-totality"], bridge: "EXPLICIT", outcome: "QUALIFY",
    operators: ["O0", "O1", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C2", g_target: "G5", gap: "LARGE", bridge_burden: "Textual evidence establishes Heidegger's scope, not comparative adequacy across all technological domains." },
    rivalData: rivals(
      ["The source establishes only Heidegger's universalizing intention.", "RT15", "Separate source attribution from world-level confirmation."],
      ["Independent heterogeneous analyses may converge only on local or regional ordering profiles.", "RT27", "Run cross-domain TO4 and BS4 discriminators plus countercases."]
    ),
    rationale: "RT15 records evidential support for a textual attribution while ScaleCheck blocks promotion to a validated universal diagnosis.",
    profile: { ...geBase, totalization_status: "PLANETARY_SOURCE_CLAIM", target_domain: ["all present beings", "planetary technology", "labor", "nature"] }
  },
  {
    id: "4D-TO4-DESIGN-MULTICRITERIA", module: "to4", rt: "RT15",
    from: "Engineering design uses plural requirements, multi-criteria trade-offs, prototypes, lifecycle analysis and iterative correction.",
    to: "These features support treating calculation as one ordering dimension rather than an automatically total and univocal design essence.",
    sources: ["W4D-08#engineering-design-and-values"], bridge: "EXPLICIT", outcome: "QUALIFY",
    operators: ["O0", "O1", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C3", g_target: "G3", gap: "NONE", bridge_burden: "A native counterprofile limits totalization but does not refute every Gestell hypothesis." },
    rivalData: rivals(
      ["Optimization and standardization instantiate a strong ordering profile.", "RT14", "Trace concrete objectives and their system effects."],
      ["Plural trade-offs and corrigibility defeat a single total metric.", "RT15", "Check whether alternatives and revisions operate in practice."]
    ),
    rationale: "RT15 expresses evidential support from a native engineering counterprofile without turning design practice into a metaphysical refutation.",
    profile: { ...toBase, system: "Contemporary engineering design process", mode: ["DESIGN", "OPERATION"], goals_functions: "Translate plural needs into revisable requirements, artifacts and lifecycle decisions.", ordering_dimensions: ["CALCULATION", "OPTIMIZATION", "STANDARDIZATION", "MONITORING"], heideggerian_fit: "PARTIAL" }
  },
  {
    id: "4D-TO4-AI-GOVERNANCE-CORRIGIBILITY", module: "to4", rt: "RT15",
    from: "AI governance frameworks specify multiple lifecycle criteria, oversight, accountability, robustness, privacy, transparency, fairness and correction processes.",
    to: "Their presence supports a counterdimension to total uncontestable ordering, while their effective operation remains an empirical question.",
    sources: ["W4D-09#trustworthiness-criteria", "W4D-10#organizational-governance"], bridge: "CONTESTED", outcome: "QUALIFY",
    operators: ["O0", "O1", "O4", "O5", "O6", "O7", "O9"],
    scale: { applicable: true, c_support: "C2", g_target: "G3", gap: "SMALL", bridge_burden: "Formal standards must not be promoted to effective oversight without operational evidence." },
    rivalData: rivals(
      ["Governance standards create real correction and accountability channels.", "RT10", "Test implementation, escalation and reversal in operation."],
      ["Governance is aspirational while optimization and monitoring remain dominant.", "RT11", "Compare formal policy with actual determination patterns and outcomes."]
    ),
    rationale: "RT15 is provisional because standards support a governance claim but do not by themselves prove implemented corrigibility.",
    profile: { ...toBase, system: "AI lifecycle governance", mode: ["AI", "ORGANIZATION", "OPERATION"], goals_functions: "Govern development and use through plural trustworthiness and accountability criteria.", ordering_dimensions: ["MONITORING", "PREDICTION", "AUTOMATION", "CONTROL", "STANDARDIZATION"], value_status: "VALUE_SENSITIVE_DESIGN", heideggerian_fit: "PARTIAL" }
  },
  {
    id: "4D-GE4-DANGER-AMBIVALENCE", module: "ge4", rt: "RT15",
    from: "GA7 states that the dangerous is not technology as such and links danger to the possible exhaustion of revealing by ordering while preserving a saving ambiguity.",
    to: "The source supports interpreting danger as a disclosure-mode claim rather than an automatic negative value attached to machines or engineering.",
    sources: ["W4D-05#danger-and-saving-ambiguity"], bridge: "EXPLICIT", outcome: "QUALIFY",
    operators: ["O0", "O1", "O3", "O4", "O6", "O7", "O9"],
    rivalData: rivals(
      ["Heidegger's claim is simple moral rejection of machines.", "RT21", "Locate the source of normativity and distinguish devices from revealing mode."],
      ["Danger and saving ambiguity concern competing disclosure possibilities.", "RT19", "Reconstruct what is disclosed and what remains occluded."]
    ),
    rationale: "RT15 supports a controlled textual attribution; the record does not convert Heidegger's danger/saving language into engineering policy.",
    profile: { ...geBase, totalization_status: "EPOCHAL_SOURCE_CLAIM", danger_status: "DANGER_SAVING_AMBIGUITY" }
  },
  {
    id: "4D-TO4-RESPONSIBILITY-MANY-HANDS", module: "to4", rt: "RT00",
    from: "Complex technical systems distribute information, control and contribution across many human and organizational roles.",
    to: "Therefore no assignable or forward-looking responsibility can exist.",
    sources: ["W4D-08#responsibility-and-many-hands"], bridge: "ABSENT", outcome: "BLOCK",
    operators: ["O0", "O1", "O3", "O4", "O5", "O6", "O7", "O9"], promotion: ["RELATION", "NORM", "SCOPE"],
    scale: { applicable: true, c_support: "C2", g_target: "G4", gap: "LARGE", bridge_burden: "Trace actual control, knowledge, role, institutional and remedial standing before inferring a responsibility gap." },
    rivalData: rivals(
      ["Many hands create a practical attribution problem but not necessary responsibilitylessness.", "RT21", "Specify duties, standing, control and forward-looking allocation."],
      ["Institutional roles and governance can distribute responsibility without reducing it to one causal contributor.", "RT13", "Trace office/person separation, entry/exit and decision rights."]
    ),
    rationale: "RT00 blocks a promotion from distributed control to a universal absence of responsibility; normative and institutional bridges remain separate.",
    profile: { ...toBase, system: "Complex sociotechnical responsibility network", mode: ["ORGANIZATION", "INFRASTRUCTURE", "OPERATION"], goals_functions: "Coordinate distributed design, operation, oversight and remediation.", ordering_dimensions: ["ALLOCATION", "MONITORING", "CONTROL", "AUTOMATION"], heideggerian_fit: "PARTIAL" }
  }
];

function makeRecord(definition) {
  const sourceRef = definition.sources[0];
  const force = definition.outcome === "BLOCK" ? "HYPOTHETICAL" : "CONDITIONAL";
  return {
    record_id: definition.id,
    api_version: "TRC-0.3",
    profile: "ANALYTIC",
    provenance: {
      source_refs: definition.sources,
      method_version: "CORE 4.0.0-alpha.1 + MODULE-4D-0.1-DOCX-RECONSTRUCTION + DAE-0.1",
      agent: "dae-4d-reconstruction-pass",
      derived_from: ["MODULE-MIGRATION-4D-0.1-DOCX"],
      activity_id: "MODULE-MIGRATION-4D-0.1-ENGINE-RECONSTRUCTION",
      timestamp,
      artifact_hash: `sha256:${sourceHash}`
    },
    from_node: {
      node_id: "A",
      kind: "CLAIM",
      description: definition.from,
      claim_facets: { basis: ["TXT"], force: "ASSERTED", normativity: "UNRESOLVED" },
      support_refs: [sourceRef]
    },
    to_node: {
      node_id: "B",
      kind: "CLAIM",
      description: definition.to,
      claim_facets: { basis: ["MIXED"], force, normativity: "UNRESOLVED" },
      support_refs: definition.sources
    },
    transition: {
      inference_mode: definition.rt === "RT15" ? "RECONSTRUCTIVE" : "UNRESOLVED",
      relation: { rt_id: definition.rt },
      bridge: {
        status: definition.bridge,
        statement: definition.rationale,
        support_refs: definition.sources,
        discriminator: definition.profile.discriminator
      },
      ...(definition.promotion ? { promotion_flags: definition.promotion } : {})
    },
    scale_check: definition.scale ?? { applicable: false },
    audit: {
      native_domain: definition.module === "to4" ? "philosophy of technology / engineering and governance" : "Heidegger studies / philosophy of technology",
      native_method: definition.module === "to4" ? "artifact, design, value, governance and responsibility analysis" : "primary-text reconstruction plus typed technology discrimination",
      activated_operators: definition.operators,
      trv: ["PROMOTION", "UNDERDETERMINATION", "HETEROGENEITY"],
      ncv: ["EXPLICIT_MACHINERY", "DISCRIMINATOR", "SCOPE_CONTROL", "RIVAL_HANDLING"],
      rtr: "HIGH",
      cost_note: "Module schemas were reconstructed from the supplied DOCX because the asserted JSON toolkit was not provided."
    },
    rivals: definition.rivalData,
    extensions: {
      [definition.module]: definition.profile,
      audit_semantics: {
        schema_version: "0.1",
        transition_role: "INFERENCE_AUDIT",
        relation_applies_to: definition.rt === "RT15" ? "TRANSITION" : definition.bridge === "ABSENT" ? "FROM_CLAIM" : "UNRESOLVED",
        relation_rationale: definition.rationale,
        semantic_review_status: "STRUCTURAL_ONLY",
        human_review_required: true,
        review_notes: [
          "Original 4D JSON records and schemas were not attached; this record is an engine reconstruction from the DOCX specification.",
          "Verify source passages, relation type, unitization and module field values before expert promotion."
        ]
      }
    },
    outcome: definition.outcome,
    open_questions: ["Does the module discriminator add explanatory value beyond the strongest native counterprofile?"]
  };
}

await mkdir(outputDir, { recursive: true });
for (const definition of definitions) {
  const record = makeRecord(definition);
  await writeFile(path.join(outputDir, `${record.record_id}.json`), `${JSON.stringify(record, null, 2)}\n`, "utf8");
}
console.log(`Generated ${definitions.length} reconstructed 4D candidate fixtures in ${outputDir}`);
