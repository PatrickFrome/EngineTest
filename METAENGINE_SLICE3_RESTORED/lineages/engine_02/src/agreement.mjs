import { createHash } from "node:crypto";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { readJson } from "./paths.mjs";

function annotationsFor(unit) {
  return Object.entries(unit.annotations)
    .filter(([, annotation]) => annotation?.dominant)
    .sort(([left], [right]) => left.localeCompare(right));
}

export function krippendorffAlphaNominal(units) {
  const coincidence = new Map();
  const add = (left, right, value) => {
    if (!coincidence.has(left)) coincidence.set(left, new Map());
    coincidence.get(left).set(right, (coincidence.get(left).get(right) ?? 0) + value);
  };
  let usableUnits = 0;
  for (const unit of units) {
    const values = annotationsFor(unit).map(([, annotation]) => annotation.dominant);
    if (values.length < 2) continue;
    usableUnits += 1;
    for (let left = 0; left < values.length; left += 1) {
      for (let right = 0; right < values.length; right += 1) {
        if (left !== right) add(values[left], values[right], 1 / (values.length - 1));
      }
    }
  }
  const categories = [...new Set([...coincidence.keys(), ...[...coincidence.values()].flatMap((row) => [...row.keys()])])].sort();
  const marginals = Object.fromEntries(categories.map((category) => [category, 0]));
  let n = 0;
  let observedDisagreementNumerator = 0;
  for (const left of categories) {
    for (const right of categories) {
      const value = coincidence.get(left)?.get(right) ?? 0;
      marginals[left] += value;
      n += value;
      if (left !== right) observedDisagreementNumerator += value;
    }
  }
  if (!n) return { alpha: null, usable_units: 0, categories, coincidence: {}, marginals, observed_disagreement: null, expected_disagreement: null };
  const observed = observedDisagreementNumerator / n;
  const expectedNumerator = categories.reduce((sum, category) => sum + marginals[category] * (n - marginals[category]), 0);
  const expected = n > 1 ? expectedNumerator / (n * (n - 1)) : 0;
  const alpha = expected === 0 ? (observed === 0 ? 1 : null) : 1 - observed / expected;
  const matrix = Object.fromEntries(categories.map((left) => [left, Object.fromEntries(categories.map((right) => [right, coincidence.get(left)?.get(right) ?? 0]))]));
  return { alpha, usable_units: usableUnits, categories, coincidence: matrix, marginals, observed_disagreement: observed, expected_disagreement: expected };
}

function multilabel(units) {
  let pairs = 0;
  let exact = 0;
  let f1Total = 0;
  for (const unit of units) {
    const entries = annotationsFor(unit);
    for (let left = 0; left < entries.length; left += 1) {
      for (let right = left + 1; right < entries.length; right += 1) {
        const a = new Set([entries[left][1].dominant, ...(entries[left][1].secondary ?? [])]);
        const b = new Set([entries[right][1].dominant, ...(entries[right][1].secondary ?? [])]);
        const intersection = [...a].filter((label) => b.has(label)).length;
        const score = a.size + b.size === 0 ? 1 : (2 * intersection) / (a.size + b.size);
        const same = a.size === b.size && intersection === a.size;
        pairs += 1;
        if (same) exact += 1;
        f1Total += score;
      }
    }
  }
  return { coder_pairs: pairs, exact_match: pairs ? exact / pairs : null, pairwise_f1: pairs ? f1Total / pairs : null };
}

function rng(seed) {
  let state = Number.parseInt(createHash("sha256").update(seed).digest("hex").slice(0, 8), 16) || 1;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
}

function percentile(values, probability) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position);
  const fraction = position - lower;
  return sorted[lower + 1] === undefined ? sorted[lower] : sorted[lower] + fraction * (sorted[lower + 1] - sorted[lower]);
}

function bootstrap(units, iterations, seed) {
  const random = rng(seed);
  const alpha = [];
  const exact = [];
  const f1 = [];
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const sample = Array.from({ length: units.length }, () => units[Math.floor(random() * units.length)]);
    const a = krippendorffAlphaNominal(sample).alpha;
    const m = multilabel(sample);
    if (Number.isFinite(a)) alpha.push(a);
    if (Number.isFinite(m.exact_match)) exact.push(m.exact_match);
    if (Number.isFinite(m.pairwise_f1)) f1.push(m.pairwise_f1);
  }
  const interval = (values) => [percentile(values, 0.025), percentile(values, 0.975)];
  return {
    requested_iterations: iterations,
    usable_iterations: { alpha: alpha.length, exact_match: exact.length, pairwise_f1: f1.length },
    alpha_ci95: interval(alpha),
    exact_match_ci95: interval(exact),
    pairwise_f1_ci95: interval(f1),
  };
}

function codeCounts(units) {
  const annotations = {};
  const doubleCodedUnits = {};
  for (const unit of units) {
    const within = {};
    for (const [, annotation] of annotationsFor(unit)) {
      for (const label of new Set([annotation.dominant, ...(annotation.secondary ?? [])])) {
        annotations[label] = (annotations[label] ?? 0) + 1;
        within[label] = (within[label] ?? 0) + 1;
      }
    }
    for (const [label, count] of Object.entries(within)) if (count >= 2) doubleCodedUnits[label] = (doubleCodedUnits[label] ?? 0) + 1;
  }
  const sort = (value) => Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)));
  return { annotations: sort(annotations), double_coded_units: sort(doubleCodedUnits) };
}

export async function evaluateAgreement(engine, annotationFile) {
  const absolute = path.resolve(annotationFile);
  const payload = await readJson(absolute);
  return evaluateAgreementPayload(engine, payload, absolute);
}

export function evaluateAgreementPayload(engine, payload, file = "<memory>") {
  const issues = [...engine.structural.validateAnnotationSet(payload)];
  if (issues.length) return finish(file, payload, null, issues);

  const coderIds = payload.coders.map((coder) => coder.id);
  if (new Set(coderIds).size !== coderIds.length) issues.push(issue("ERROR", "DUPLICATE_CODER_ID", "/coders", "Coder identifiers must be unique."));
  for (const [index, coder] of payload.coders.entries()) {
    if (!coder.independent) issues.push(issue("ERROR", "CODER_NOT_INDEPENDENT", `/coders/${index}/independent`, `${coder.id} cannot contribute to inter-rater reliability as an explicitly non-independent coder.`));
  }
  const known = new Set(coderIds);
  for (const [index, unit] of payload.units.entries()) {
    for (const id of Object.keys(unit.annotations)) {
      if (!known.has(id)) issues.push(issue("ERROR", "UNKNOWN_CODER_IN_ANNOTATIONS", `/units/${index}/annotations/${id}`, `${id} is absent from the coder registry.`));
    }
    if (annotationsFor(unit).length < 2) issues.push(issue("WARNING", "UNIT_INSUFFICIENT_RATINGS", `/units/${index}`, "Unit has fewer than two non-missing dominant labels and does not contribute to alpha."));
  }
  if (issues.some((item) => item.severity === "ERROR")) return finish(file, payload, null, issues);

  const alpha = krippendorffAlphaNominal(payload.units);
  const multi = multilabel(payload.units);
  const boot = bootstrap(payload.units, payload.thresholds.bootstrap_iterations, payload.thresholds.seed);
  const counts = codeCounts(payload.units);
  for (const code of Object.keys(counts.annotations)) {
    const count = counts.double_coded_units[code] ?? 0;
    if (count < 20) issues.push(issue("WARNING", "RARE_CODE_UNDERPOWERED", `/codes/${code}`, `${code} has ${count} double-coded units; v3.8 requires at least 20 before confirmation.`));
  }
  const metrics = { nominal: alpha, multilabel: multi, bootstrap: boot, code_counts: counts };
  const failures = [];
  if (!Number.isFinite(alpha.alpha) || alpha.alpha < payload.thresholds.alpha_min) failures.push(`alpha ${alpha.alpha} < ${payload.thresholds.alpha_min}`);
  if (!Number.isFinite(boot.alpha_ci95[0]) || boot.alpha_ci95[0] < payload.thresholds.alpha_ci_lower_min) failures.push(`alpha CI lower ${boot.alpha_ci95[0]} < ${payload.thresholds.alpha_ci_lower_min}`);
  if (!Number.isFinite(multi.exact_match) || multi.exact_match < payload.thresholds.multilabel_match_min) failures.push(`multilabel match ${multi.exact_match} < ${payload.thresholds.multilabel_match_min}`);
  if (!Number.isFinite(multi.pairwise_f1) || multi.pairwise_f1 < payload.thresholds.multilabel_f1_min) failures.push(`multilabel F1 ${multi.pairwise_f1} < ${payload.thresholds.multilabel_f1_min}`);
  for (const failure of failures) issues.push(issue("REVIEW", "AGREEMENT_THRESHOLD_FAILED", "/thresholds", failure));
  return finish(file, payload, metrics, issues, failures.length ? "FAIL_THRESHOLD" : "PASS_THRESHOLD");
}

function finish(file, payload, metrics, issues, outcome = "INVALID") {
  const sorted = sortIssues(issues);
  if (sorted.some((item) => item.severity === "ERROR")) outcome = "INVALID";
  return {
    file,
    dataset_id: payload?.dataset_id ?? null,
    codebook_id: payload?.codebook_id ?? null,
    outcome,
    conformant: !sorted.some((item) => item.severity === "ERROR"),
    threshold_passed: outcome === "PASS_THRESHOLD",
    metrics,
    counts: countIssues(sorted),
    issues: sorted,
    claim_ceiling: "RELIABILITY_ONLY_NOT_VALIDITY_OR_SEMANTIC_TRUTH",
  };
}
