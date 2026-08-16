import { issue } from "./issues.mjs";

const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/;
const MODULE_KEYS = new Set(["em4", "kc4", "ind4", "id4", "ma4", "ge4", "bs4", "to4"]);

function recordText(record) {
  const parts = [
    record.from_node?.description,
    record.to_node?.description,
    record.transition?.bridge?.statement,
    record.extensions?.audit_semantics?.relation_rationale,
  ];
  return parts.filter(Boolean).join(" ").toLowerCase();
}

function sourceId(reference) {
  return reference.split("#", 1)[0];
}

function localSourceHash(id) {
  return id.match(/^LOCAL-SHA256-([a-f0-9]{64})$/i)?.[1]?.toLowerCase() ?? null;
}

function relationHeuristics(record, issues) {
  const rt = record.transition?.relation?.rt_id;
  const text = recordText(record);
  if (rt === "RT21" && !/(obligation|permission|duty|right|claim-right|normative|norm |обязан|должен|разреш|право|норматив)/i.test(text)) {
    issues.push(issue("REVIEW", "RT21_LEXICAL_MISMATCH", "/transition/relation/rt_id", "RT21 is normative obligation/permission, but no normative signal was found in the encoded transition."));
  }
  if (rt === "RT17" && !/(refer|reference|denot|expression|sign |symbol|обознач|рефер|знак |выражен)/i.test(text)) {
    issues.push(issue("REVIEW", "RT17_LEXICAL_MISMATCH", "/transition/relation/rt_id", "RT17 is reference/denotation, but no reference or sign relation was found."));
  }
  if (rt === "RT06") {
    const bridge = record.transition?.bridge ?? {};
    if (!(bridge.support_refs?.length) || !/(intervention|counterfactual|causal assumption|mechanism|интервен|контрфакт|причин)/i.test(text)) {
      issues.push(issue("REVIEW", "RT06_CAUSAL_EVIDENCE_WEAK", "/transition/bridge", "RT06 requires causal assumptions plus observational, interventional or counterfactual support."));
    }
  }
  if (rt === "RT07" && !/(ground|metaphysical priority|in virtue|в силу|основан|метафизическ)/i.test(text)) {
    issues.push(issue("REVIEW", "RT07_GROUNDING_RATIONALE_WEAK", "/transition/bridge", "RT07 requires a distinct metaphysical-grounding rationale."));
  }
  if (record.from_node?.kind === "ARTIFACT" && /(?<![\p{L}\p{N}_])(constitutes?|is identical|counts as|является|конституирует|тождествен)(?![\p{L}\p{N}_])/iu.test(record.from_node.description ?? "")) {
    issues.push(issue("REVIEW", "NODE_KIND_CLAIM_SUSPECT", "/from_node/kind", "The ARTIFACT description appears to encode a proposition rather than an artifact."));
  }
}

export function validateSemantics(record, context) {
  const { aag, relationIds, extensionRegistry, sourceCatalog, policy } = context;
  const issues = [];
  const rtId = record.transition?.relation?.rt_id;
  const audit = record.audit ?? {};
  const active = new Set(audit.activated_operators ?? []);
  const extensions = record.extensions ?? {};
  const extensionKeys = Object.keys(extensions);
  const moduleKeys = extensionKeys.filter((key) => MODULE_KEYS.has(key));

  if (rtId && !relationIds.has(rtId)) {
    issues.push(issue("ERROR", "UNKNOWN_RELATION_ID", "/transition/relation/rt_id", `${rtId} is syntactically valid but absent from the frozen RT00–RT28 registry.`));
  }
  for (const [index, rival] of (record.rivals ?? []).entries()) {
    if (rival.relation_rt_id && !relationIds.has(rival.relation_rt_id)) {
      issues.push(issue("ERROR", "UNKNOWN_RIVAL_RELATION_ID", `/rivals/${index}/relation_rt_id`, `${rival.relation_rt_id} is absent from the frozen relation registry.`));
    }
  }

  if (policy.registered_extensions_only) {
    for (const key of extensionKeys) {
      if (!extensionRegistry.extensions[key]) {
        issues.push(issue("ERROR", "UNKNOWN_EXTENSION", `/extensions/${key}`, `Extension '${key}' is not registered with the automation engine.`));
      }
    }
  }
  if (moduleKeys.length > 1) {
    issues.push(issue("ERROR", "MULTIPLE_DOMAIN_MODULES", "/extensions", `A transition record may carry one domain module profile; found ${moduleKeys.join(", ")}.`));
  }
  if (policy.module_records_require_audit_semantics && moduleKeys.length === 1 && !extensions.audit_semantics) {
    issues.push(issue("ERROR", "AUDIT_SEMANTICS_REQUIRED", "/extensions", "Automated module validation requires the audit_semantics extension to disambiguate the transition role."));
  }

  if (policy.aag_invariants_required && (record.profile === "ANALYTIC" || record.profile === "VALIDATION" || record.audit)) {
    for (const invariant of aag.invariants) {
      if (!active.has(invariant)) issues.push(issue("ERROR", "AAG_INVARIANT_MISSING", "/audit/activated_operators", `Mandatory invariant ${invariant} is missing.`));
    }
  }
  for (const field of ["trv", "ncv", "rtr"]) {
    if ((record.profile === "ANALYTIC" || record.profile === "VALIDATION") && audit[field] === undefined) {
      issues.push(issue("ERROR", "AAG_PIPELINE_FIELD_MISSING", `/audit/${field}`, `AAG activation pipeline requires an explicit ${field.toUpperCase()} decision.`));
    }
  }
  for (const field of ["native_domain", "native_method"]) {
    if ((record.profile === "ANALYTIC" || record.profile === "VALIDATION") && !audit[field]) {
      issues.push(issue("WARNING", "DOMAIN_DEFERENCE_FIELD_MISSING", `/audit/${field}`, `Explicit ${field} improves Domain Deference and reviewability.`));
    }
  }

  if (policy.cross_field.o6_requires_rivals && active.has("O6") && !(record.rivals?.length)) {
    issues.push(issue("ERROR", "O6_RIVALS_REQUIRED", "/rivals", "O6 is active, but no rival reconstruction is encoded."));
  }
  if (policy.cross_field.o8_requires_positive && active.has("O8") && !record.positive) {
    issues.push(issue("ERROR", "O8_POSITIVE_REQUIRED", "/positive", "O8 is active, but no positive reconstruction is encoded."));
  }
  if (policy.cross_field.absent_bridge_forbids_accept && record.transition?.bridge?.status === "ABSENT" && record.outcome === "ACCEPT") {
    issues.push(issue("ERROR", "ABSENT_BRIDGE_ACCEPT", "/outcome", "A transition with an absent bridge cannot be accepted."));
  }
  if (policy.cross_field.absent_bridge_forbids_promotion && record.transition?.bridge?.status === "ABSENT" && record.transition?.promotion_flags?.length && ["ACCEPT", "QUALIFY"].includes(record.outcome)) {
    issues.push(issue("ERROR", "ABSENT_BRIDGE_PROMOTION", "/transition/promotion_flags", "A flagged promotion cannot survive an absent bridge with an accepting/qualifying outcome."));
  }
  if (policy.cross_field.rt00_forbids_accept && rtId === "RT00" && record.outcome === "ACCEPT") {
    issues.push(issue("ERROR", "RT00_ACCEPT", "/outcome", "An unresolved relation cannot receive ACCEPT in strict release mode."));
  }
  if (policy.cross_field.large_gap_forbids_accept && record.scale_check?.gap === "LARGE" && record.outcome === "ACCEPT") {
    issues.push(issue("ERROR", "LARGE_SCALE_GAP_ACCEPT", "/outcome", "A large support-to-target gap cannot receive ACCEPT."));
  }

  const provenance = record.provenance ?? {};
  for (const [field, required] of [
    ["agent", policy.provenance.require_agent],
    ["activity_id", policy.provenance.require_activity_id],
    ["timestamp", policy.provenance.require_timestamp],
  ]) {
    if (required && !provenance[field]) issues.push(issue("ERROR", "PROVENANCE_FIELD_MISSING", `/provenance/${field}`, `Strict release provenance requires ${field}.`));
  }
  if (provenance.timestamp && (!ISO_DATE_TIME.test(provenance.timestamp) || Number.isNaN(Date.parse(provenance.timestamp)))) {
    issues.push(issue("ERROR", "PROVENANCE_TIMESTAMP_INVALID", "/provenance/timestamp", "Timestamp must be an ISO-8601 UTC date-time ending in Z."));
  }
  if (!provenance.artifact_hash) {
    issues.push(issue(policy.provenance.artifact_hash_severity, "PROVENANCE_HASH_MISSING", "/provenance/artifact_hash", "No source/excerpt artifact hash is recorded; do not infer source-level reproducibility."));
  }
  for (const [index, reference] of (provenance.source_refs ?? []).entries()) {
    const id = sourceId(reference);
    const localHash = localSourceHash(id);
    if (policy.known_source_ids_required && !sourceCatalog.sources[id] && !localHash) {
      issues.push(issue("ERROR", "UNKNOWN_SOURCE_ID", `/provenance/source_refs/${index}`, `Source '${id}' is not present in the source catalog.`));
    }
    if (localHash && provenance.artifact_hash !== `sha256:${localHash}`) {
      issues.push(issue("ERROR", "LOCAL_SOURCE_HASH_MISMATCH", `/provenance/source_refs/${index}`, "The LOCAL-SHA256 source identifier does not match provenance.artifact_hash."));
    }
    if (!reference.includes("#")) {
      issues.push(issue(policy.provenance.locator_severity, "SOURCE_LOCATOR_MISSING", `/provenance/source_refs/${index}`, `Source '${id}' has no record-level locator.`));
    }
  }

  const semantics = extensions.audit_semantics;
  if (semantics) {
    if (["GOLD", "EXPERT_REVIEWED"].includes(semantics.semantic_review_status) && semantics.human_review_required) {
      issues.push(issue("ERROR", "REVIEW_STATUS_CONTRADICTION", "/extensions/audit_semantics", "A reviewed/gold fixture cannot simultaneously require unresolved human review."));
    }
    if (semantics.human_review_required || ["STRUCTURAL_ONLY", "REPAIRED_PENDING_EXPERT"].includes(semantics.semantic_review_status)) {
      issues.push(issue("REVIEW", "HUMAN_SEMANTIC_REVIEW", "/extensions/audit_semantics/semantic_review_status", `Fixture status is ${semantics.semantic_review_status}; deterministic checks do not establish philosophical correctness.`));
    }
  }

  if (extensions.ma4) {
    const profile = extensions.ma4;
    if (["EPOCHAL", "UNIVERSAL"].includes(profile.scope) && (!active.has("O5") || !active.has("O6"))) {
      issues.push(issue("ERROR", "MA4_TOTALIZATION_CONTROLS_REQUIRED", "/extensions/ma4/scope", "Epochal/universal Machenschaft claims require both O5 scope control and O6 rivals."));
    }
    if (["EPOCHAL_SOURCE_CLAIM", "STRONG_UNIVERSAL_CLAIM"].includes(profile.totalization_status)) {
      issues.push(issue("REVIEW", "MA4_TOTALIZATION_REVIEW", "/extensions/ma4/totalization_status", "Source reconstruction must be separated from endorsement of an epochal/universal meta-claim."));
    }
  }
  if (extensions.ge4) {
    const profile = extensions.ge4;
    if (["PLANETARY_SOURCE_CLAIM", "UNIVERSAL_META_CLAIM"].includes(profile.totalization_status)) {
      if (!record.scale_check?.applicable || !active.has("O5") || !active.has("O6")) {
        issues.push(issue("ERROR", "GE4_DISCRIMINATION_BURDEN_REQUIRED", "/extensions/ge4/totalization_status", "Planetary/universal Gestell claims require ScaleCheck plus O5 and O6."));
      }
      issues.push(issue("REVIEW", "GE4_TOTALIZATION_REVIEW", "/extensions/ge4/totalization_status", "A planetary source claim does not establish a successful universal meta-diagnosis."));
    }
    if (profile.totalization_status === "UNIVERSAL_META_CLAIM" && record.outcome === "ACCEPT") {
      issues.push(issue("ERROR", "GE4_UNIVERSAL_ACCEPT", "/outcome", "Universal Gestell meta-claims cannot receive ACCEPT before comparative TO4/BS4 discrimination."));
    }
  }
  if (extensions.bs4) {
    const profile = extensions.bs4;
    if (profile.resourceization_level === "STRONG_STANDING_RESERVE" && !active.has("O6")) {
      issues.push(issue("ERROR", "BS4_COUNTERDESCRIPTION_REQUIRED", "/extensions/bs4/resourceization_level", "Strong standing-reserve classification requires O6 and a live counterdescription."));
    }
    if (["QUALIFIED_RESERVE_PIECE", "CONTESTED"].includes(profile.human_case)) {
      issues.push(issue("REVIEW", "BS4_HUMAN_TENSION_REVIEW", "/extensions/bs4/human_case", "Human resourceization remains textually and operationally contested."));
    }
  }
  if (extensions.to4) {
    const profile = extensions.to4;
    if (profile.heideggerian_fit === "TOTAL_CLAIM_REQUIRES_REVIEW") {
      issues.push(issue("REVIEW", "TO4_TOTAL_FIT_REVIEW", "/extensions/to4/heideggerian_fit", "Total Heideggerian fit is a review trigger, not an automatic module result."));
    }
    if (profile.heideggerian_fit === "STRONG" && !active.has("O6")) {
      issues.push(issue("ERROR", "TO4_STRONG_FIT_RIVALS_REQUIRED", "/extensions/to4/heideggerian_fit", "Strong Heideggerian fit requires O6 and competing native design/governance accounts."));
    }
  }
  if (rtId === "RT00") {
    issues.push(issue("REVIEW", "RELATION_UNRESOLVED", "/transition/relation/rt_id", "RT00 correctly prevents forced typing, but requires expert adjudication before gold promotion."));
  }
  if (["CONTESTED", "UNRESOLVED"].includes(record.transition?.bridge?.status)) {
    issues.push(issue("REVIEW", "BRIDGE_REVIEW_REQUIRED", "/transition/bridge/status", `Bridge status is ${record.transition.bridge.status}.`));
  }

  relationHeuristics(record, issues);
  return issues;
}
