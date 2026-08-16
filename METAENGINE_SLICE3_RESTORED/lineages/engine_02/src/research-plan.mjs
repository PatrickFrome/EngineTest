import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { readJson } from "./paths.mjs";

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function digest(plan) {
  return createHash("sha256").update(canonical(plan)).digest("hex");
}

function diff(before, after, at = "") {
  if (Object.is(before, after)) return [];
  if (Array.isArray(before) && Array.isArray(after)) {
    const output = [];
    const length = Math.max(before.length, after.length);
    for (let index = 0; index < length; index += 1) output.push(...diff(before[index], after[index], `${at}/${index}`));
    return output;
  }
  if (before && after && typeof before === "object" && typeof after === "object" && !Array.isArray(before) && !Array.isArray(after)) {
    const output = [];
    for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) output.push(...diff(before[key], after[key], `${at}/${key.replaceAll("~", "~0").replaceAll("/", "~1")}`));
    return output;
  }
  return [{ path: at || "/", frozen: before ?? null, current: after ?? null }];
}

export async function freezeResearchPlan(engine, planFile, lockFile) {
  const planPath = path.resolve(planFile);
  const output = path.resolve(lockFile);
  const plan = await readJson(planPath);
  const issues = engine.structural.validateResearchPlan(plan);
  if (issues.length) return { written: false, plan_file: planPath, lock_file: output, counts: countIssues(issues), issues };

  const blocked = Object.entries(plan.gates).filter(([, gate]) => gate.status !== "PASS").map(([name]) => name);
  const lock = {
    lock_version: "DAE-RESEARCH-LOCK-1.0",
    preregistration_id: plan.preregistration_id,
    canonical_sha256: digest(plan),
    frozen_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    timestamp_authority: "LOCAL_SYSTEM_CLOCK_UNTRUSTED",
    engine_version: engine.context.engineVersion,
    frozen_snapshot: plan,
    claim_ceiling: "LOCAL_CONTENT_INTEGRITY_NOT_PUBLIC_PREREGISTRATION",
  };
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, `${JSON.stringify(lock, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  return {
    written: true,
    plan_file: planPath,
    lock_file: output,
    preregistration_id: plan.preregistration_id,
    canonical_sha256: lock.canonical_sha256,
    blocked_gates: blocked,
    execution_status: blocked.length ? "FROZEN_BUT_BLOCKED" : "FROZEN_READY",
    claim_ceiling: lock.claim_ceiling,
    counts: { ERROR: 0, REVIEW: blocked.length ? blocked.length : 0, WARNING: 0, INFO: 0 },
    issues: blocked.map((name) => issue("REVIEW", "RESEARCH_GATE_BLOCKED", `/gates/${name}`, `Plan is frozen, but execution remains blocked by ${name}.`)),
  };
}

export async function verifyResearchPlan(engine, planFile, lockFile) {
  const planPath = path.resolve(planFile);
  const lockPath = path.resolve(lockFile);
  const [plan, lock] = await Promise.all([readJson(planPath), readJson(lockPath)]);
  const issues = [
    ...engine.structural.validateResearchPlan(plan),
    ...engine.structural.validateResearchPlanLock(lock),
  ];
  if (!issues.length && plan.preregistration_id !== lock.preregistration_id) {
    issues.push(issue("ERROR", "PLAN_ID_MISMATCH", "/preregistration_id", `Plan ${plan.preregistration_id} does not match lock ${lock.preregistration_id}.`));
  }
  const currentHash = digest(plan);
  const deviations = lock.frozen_snapshot ? diff(lock.frozen_snapshot, plan) : [];
  const unchanged = !issues.length && currentHash === lock.canonical_sha256;
  if (!unchanged && !issues.length) {
    issues.push(issue("REVIEW", "PREREGISTRATION_DEVIATION", "/", `${deviations.length} content deviation(s) from the frozen plan.`));
  }
  const sorted = sortIssues(issues);
  return {
    plan_file: planPath,
    lock_file: lockPath,
    preregistration_id: plan.preregistration_id ?? null,
    unchanged,
    frozen_sha256: lock.canonical_sha256 ?? null,
    current_sha256: currentHash,
    deviations,
    counts: countIssues(sorted),
    issues: sorted,
    claim_ceiling: "LOCAL_CONTENT_INTEGRITY_NOT_PUBLIC_PREREGISTRATION",
  };
}

export { canonical as canonicalizeResearchPlan };
