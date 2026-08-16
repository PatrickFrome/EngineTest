import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceDir = path.join(root, "vendor", "module4a", "fixtures_original");
const outputDir = path.join(root, "fixtures", "4a_repaired");
const timestamp = "2026-08-11T12:00:00Z";

const repairs = {
  "4A-EM4-ACCESS-BEING": {
    rt: "RT04",
    sources: ["W4A-KANT-A158-B197#A158-B197", "LEGACY-BR-A-2.22#access-being-control"],
    transitionRole: "INFERENCE_AUDIT",
    appliesTo: "FROM_CLAIM",
    rationale: "The audited source claim is a scoped necessary-condition claim; the blocked target illegitimately removes its domain restriction.",
    notes: ["RT05 was replaced by RT04 because the encoded claim concerns scoped necessity, not opportunity or enablement."],
    rivals: [
      {
        description: "The condition is necessary only for objecthood within the specified possible-experience framework.",
        relation_rt_id: "RT04",
        bridge: "Retain the explicit domain and modality.",
        discriminator: "Test whether the conclusion survives removal of the possible-experience index."
      }
    ]
  },
  "4A-EM4-HEIDEGGER-31": {
    rt: "RT05",
    sources: ["W4A-02#section-31", "LEGACY-BR-A-2.22#enablement"],
    transitionRole: "STATE_TRANSITION",
    appliesTo: "TRANSITION",
    rationale: "Projection opens or enables disclosed possibilities without being encoded as their sufficient cause, production or metaphysical ground.",
    notes: ["RT04 was replaced by RT05 because the record asserts enabling access rather than a fully specified necessary/sufficient condition."],
    rivalPatch: [
      { relation_rt_id: "RT05", discriminator: "Ask whether projection determines the disclosed possibility or only opens access to it." }
    ]
  },
  "4A-ID4-CONSTITUTION-NOT-IDENTITY": {
    rt: "RT09",
    sources: ["W4A-05#constitution-versus-identity", "LEGACY-BR-A-2.24#constitution-identity-gate"],
    transitionRole: "INFERENCE_AUDIT",
    appliesTo: "FROM_CLAIM",
    rationale: "RT09 applies to the source constitution claim; the record audits and withholds the attempted promotion from constitution to numerical identity.",
    notes: ["The from-node was retyped from ARTIFACT to CLAIM because its description is propositional."],
    fromClaim: true,
    objectRelata: [
      { relatum_id: "lump", description: "The coincident lump of matter at the indexed time.", kind: "ARTIFACT" },
      { relatum_id: "statue", description: "The statue constituted by the lump at the indexed time.", kind: "ARTIFACT" }
    ],
    rivalPatch: [
      { relation_rt_id: "RT03", discriminator: "Apply explicit identity criteria and persistence conditions." },
      { relation_rt_id: "RT08", discriminator: "Distinguish constitution from existential dependence and grounding." }
    ]
  },
  "4A-ID4-HEIDEGGER-BELONGING": {
    rt: "RT00",
    sources: ["W4A-04#belonging-together", "LEGACY-BR-A-2.24#explanandum-switch"],
    transitionRole: "INFERENCE_AUDIT",
    appliesTo: "UNRESOLVED",
    rationale: "The frozen registry has no justified generic relation for Heideggerian belonging-together; RT00 prevents a false promotion to reference or numerical identity.",
    notes: ["RT17 was removed because belonging-together is not a sign-reference or denotation relation."],
    rivals: [
      {
        description: "Treat belonging-together as a criterion of numerical identity or persistence.",
        relation_rt_id: "RT03",
        bridge: "Would require token/type and synchronic/diachronic identity criteria.",
        discriminator: "Test ordinary-entity identity cases; the Heideggerian explanandum switch should not supply their criterion."
      },
      {
        description: "Treat belonging-together as disclosure or access rather than identity.",
        relation_rt_id: "RT19",
        bridge: "Requires an account of what is disclosed to whom and under what conditions.",
        discriminator: "Separate disclosure vocabulary from a claim about identity."
      }
    ]
  },
  "4A-IND4-BIOLOGICAL-PLURALITY": {
    rt: "RT00",
    sources: ["W4A-08#plural-individuality-criteria", "LEGACY-BR-A-2.25#biological-stress-test"],
    transitionRole: "INFERENCE_AUDIT",
    appliesTo: "TO_CLAIM",
    rationale: "Physiological and evolutionary criteria select different candidate units; RT00 preserves underdetermination until the explanandum fixes a warranted relation type.",
    notes: ["RT21 was removed because biological individuality is not a normative obligation or permission relation."],
    rivals: [
      {
        description: "Physiological integration determines the relevant biological individual.",
        relation_rt_id: "RT14",
        bridge: "Specify integration, control and functional contribution criteria.",
        discriminator: "Compare explanatory performance on metabolic and immune-control cases."
      },
      {
        description: "Evolutionary lineage and fitness alignment determine the relevant biological individual.",
        relation_rt_id: "RT27",
        bridge: "Specify lineage, reproduction and selection-level criteria.",
        discriminator: "Compare explanatory performance on selection and reproduction cases."
      }
    ]
  },
  "4A-IND4-SIMONDON-PROCESS": {
    rt: "RT00",
    sources: ["W4A-09#individuation-summary", "LEGACY-BR-A-2.25#simondon-process-priority"],
    transitionRole: "STATE_TRANSITION",
    appliesTo: "TRANSITION",
    rationale: "The available orientation source does not establish an interventionist causal relation; RT00 preserves the ontogenetic reconstruction without counterfeit causal precision.",
    notes: ["RT06 was removed pending primary-text and causal-bridge evidence; W4A-09 remains orientation-only."],
    rivals: [
      {
        description: "Individuation is an intervention-sensitive causal production process.",
        relation_rt_id: "RT06",
        bridge: "Requires causal assumptions, mechanisms and counterfactual or intervention evidence.",
        discriminator: "Provide a model in which changes to the preindividual state yield discriminating outcome changes."
      },
      {
        description: "Individuation is a constitutive or ontogenetic reconstruction not reducible to causal production.",
        relation_rt_id: "RT09",
        bridge: "Requires bearer, product, identity and persistence criteria.",
        discriminator: "Separate constitution of the unit from causal generation of an event."
      }
    ],
    outcome: "UNDERDETERMINED"
  },
  "4A-KC4-HUSSERL-CONSTITUTION": {
    rt: "RT09",
    sources: ["W4A-01#constitution-objectivity", "HUSSERL-CM#sections-22-23-33-47-55"],
    transitionRole: "STATE_TRANSITION",
    appliesTo: "TRANSITION",
    rationale: "The record encodes constitution of stable intentional sense across modes of givenness; RT09 is retained without promotion to ontic production or metaphysical grounding.",
    notes: ["RT07 was replaced by RT09; a separate metaphysical-grounding claim would require its own bridge and record."],
    rivalPatch: [
      { relation_rt_id: "RT09", discriminator: "Distinguish sense/objectivity constitution from causal production and metaphysical priority." }
    ]
  },
  "4A-KC4-INSTITUTIONAL-STATUS": {
    rt: "RT09",
    sources: ["LEGACY-BR-A-2.23#institutional-status-stress-test", "W4A-05#constitution-contrast"],
    transitionRole: "STATE_TRANSITION",
    appliesTo: "TRANSITION",
    rationale: "A rule-governed practice constitutes and maintains a distinct institutional status; RT09 remains provisional and does not imply numerical identity or physical production.",
    notes: ["The ONTIC, SOCIAL and NORMATIVE dependence layers still require expert review as separate claims."],
    rivals: []
  }
};

function orderedOperators(values) {
  return [...new Set(["O0", "O1", "O4", "O9", ...values])].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
}

function applyRepair(record, sourceArtifactHash) {
  const repair = repairs[record.record_id];
  if (!repair) throw new Error(`No repair specification for ${record.record_id}`);
  record.transition.relation.rt_id = repair.rt;
  if (repair.outcome) record.outcome = repair.outcome;
  record.provenance = {
    source_refs: repair.sources,
    method_version: "CORE 4.0.0-alpha.1 + MODULE-4A-0.2-repair + DAE-0.1",
    agent: "automation-repair-pass",
    derived_from: [`MODULE-MIGRATION-4A-0.1/${record.record_id}`],
    activity_id: "MODULE-MIGRATION-4A-0.2-SEMANTIC-REPAIR",
    timestamp,
    artifact_hash: `sha256:${sourceArtifactHash}`
  };
  record.audit.activated_operators = orderedOperators(record.audit.activated_operators ?? []);

  if (repair.fromClaim) {
    record.from_node.kind = "CLAIM";
    record.from_node.claim_facets = {
      basis: ["MIXED"],
      force: "ASSERTED",
      normativity: "DESCRIPTIVE"
    };
    delete record.from_node.object_type;
  }
  if (repair.rivals !== undefined) record.rivals = repair.rivals;
  if (repair.rivalPatch) {
    record.rivals = (record.rivals ?? []).map((rival, index) => ({ ...rival, ...(repair.rivalPatch[index] ?? {}) }));
  }

  record.extensions.audit_semantics = {
    schema_version: "0.1",
    transition_role: repair.transitionRole,
    relation_applies_to: repair.appliesTo,
    relation_rationale: repair.rationale,
    semantic_review_status: "REPAIRED_PENDING_EXPERT",
    human_review_required: true,
    ...(repair.objectRelata ? { object_relata: repair.objectRelata } : {}),
    review_notes: repair.notes
  };
  return record;
}

await mkdir(outputDir, { recursive: true });
const files = (await readdir(sourceDir)).filter((name) => name.endsWith(".json")).sort();
for (const file of files) {
  const sourceBytes = await readFile(path.join(sourceDir, file));
  const record = JSON.parse(sourceBytes.toString("utf8"));
  const sourceArtifactHash = createHash("sha256").update(sourceBytes).digest("hex");
  const repaired = applyRepair(record, sourceArtifactHash);
  await writeFile(path.join(outputDir, file), `${JSON.stringify(repaired, null, 2)}\n`, "utf8");
}
console.log(`Generated ${files.length} repaired fixtures in ${outputDir}`);
