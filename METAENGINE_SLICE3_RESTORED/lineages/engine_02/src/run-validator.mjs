import path from "node:path";
import { readJson } from "./paths.mjs";
import { countIssues, issue, sortIssues } from "./issues.mjs";

export async function validateRun(engine, runFile) {
  const absolute = path.resolve(runFile);
  const run = await readJson(absolute);
  const issues = [...engine.structural.validateRun(run)];
  if (issues.length) return finish(absolute, run.run_id ?? null, issues, []);

  const steps = [...run.execution].sort((a, b) => a.step - b.step);
  const seenSteps = new Set();
  let seenEM4 = false;
  let seenKC4 = false;
  let lastKC4 = -1;
  let lastIND4 = -1;

  for (let index = 0; index < steps.length; index += 1) {
    const entry = steps[index];
    const at = `/execution/${index}`;
    if (entry.step !== index + 1) issues.push(issue("ERROR", "DAG_STEP_SEQUENCE", `${at}/step`, `Expected contiguous step ${index + 1}, received ${entry.step}.`));
    if (seenSteps.has(entry.step)) issues.push(issue("ERROR", "DAG_DUPLICATE_STEP", `${at}/step`, `Execution step ${entry.step} is duplicated.`));
    seenSteps.add(entry.step);
    if (index > 0) {
      const previous = steps[index - 1];
      const comparable = previous.relata_stability_after !== "NOT_APPLICABLE" && entry.relata_stability_before !== "NOT_APPLICABLE";
      if (comparable && previous.relata_stability_after !== entry.relata_stability_before) {
        issues.push(issue("ERROR", "DAG_STABILITY_DISCONTINUITY", `${at}/relata_stability_before`, `Previous step ended ${previous.relata_stability_after}, but this step begins ${entry.relata_stability_before}.`));
      }
    }

    if (entry.module_id === "EM4") seenEM4 = true;
    if (entry.module_id === "KC4") {
      if (!seenEM4) issues.push(issue("ERROR", "DAG_EM4_REQUIRED", at, "KC4 cannot execute before EM4 in branch 4A."));
      seenKC4 = true;
      lastKC4 = index;
    }
    if (entry.module_id === "IND4") {
      if (!seenKC4) issues.push(issue("ERROR", "DAG_KC4_REQUIRED", at, "IND4 cannot execute before KC4 in branch 4A."));
      lastIND4 = index;
    }
    if (entry.module_id === "ID4") {
      if (!seenKC4) issues.push(issue("ERROR", "DAG_KC4_REQUIRED", at, "ID4 cannot execute before KC4 in branch 4A."));
      if (entry.relata_stability_before === "UNSTABLE" && lastIND4 < lastKC4) {
        issues.push(issue("ERROR", "DAG_IDENTITY_BEFORE_RELATA", at, "ID4 received unstable relata without an IND4 pass after the latest KC4 pass."));
      } else if (entry.relata_stability_before === "UNSTABLE") {
        issues.push(issue("REVIEW", "DAG_IDENTITY_ON_REMAINING_INSTABILITY", at, "IND4 preceded ID4, but relata remain unstable; only a qualified or underdetermined identity result is defensible."));
      }
      if (["UNRESOLVED", "NOT_APPLICABLE"].includes(entry.relata_stability_before)) {
        issues.push(issue("REVIEW", "DAG_STABILITY_UNRESOLVED", `${at}/relata_stability_before`, "ID4 requires an explicit stable/unstable relata decision."));
      }
    }
  }

  const recordResults = [];
  for (let index = 0; index < steps.length; index += 1) {
    const entry = steps[index];
    if (!entry.record_path) continue;
    const recordPath = path.resolve(path.dirname(absolute), entry.record_path);
    try {
      const record = await readJson(recordPath);
      const result = engine.validateRecord(record, recordPath);
      recordResults.push(result);
      if (record.record_id !== entry.record_id) issues.push(issue("ERROR", "RUN_RECORD_ID_MISMATCH", `/execution/${index}/record_id`, `Manifest says ${entry.record_id}, file contains ${record.record_id}.`));
      const moduleKey = Object.keys(record.extensions ?? {}).find((key) => ["em4", "kc4", "ind4", "id4"].includes(key));
      if (moduleKey?.toUpperCase() !== entry.module_id) issues.push(issue("ERROR", "RUN_MODULE_MISMATCH", `/execution/${index}/module_id`, `Manifest says ${entry.module_id}, record extension is ${moduleKey ?? "missing"}.`));
    } catch (error) {
      issues.push(issue("ERROR", "RUN_RECORD_READ", `/execution/${index}/record_path`, error.message));
    }
  }
  return finish(absolute, run.run_id, issues, recordResults);
}

export async function validateRun4d(engine, runFile) {
  const absolute = path.resolve(runFile);
  const run = await readJson(absolute);
  const issues = [...engine.structural.validateRun4d(run)];
  if (issues.length) return finish(absolute, run.run_id ?? null, issues, []);

  const steps = [...run.execution].sort((a, b) => a.step - b.step);
  const seenSteps = new Set();
  let latestMA4 = -1;
  let latestTO4Discrimination = -1;
  let latestBS4Discrimination = -1;

  for (let index = 0; index < steps.length; index += 1) {
    const entry = steps[index];
    const at = `/execution/${index}`;
    if (entry.step !== index + 1) issues.push(issue("ERROR", "DAG4D_STEP_SEQUENCE", `${at}/step`, `Expected contiguous step ${index + 1}, received ${entry.step}.`));
    if (seenSteps.has(entry.step)) issues.push(issue("ERROR", "DAG4D_DUPLICATE_STEP", `${at}/step`, `Execution step ${entry.step} is duplicated.`));
    seenSteps.add(entry.step);

    if (entry.module_id === "MA4") latestMA4 = index;
    if (entry.module_id === "TO4" && ["DISCRIMINATION", "COUNTERPROFILE"].includes(entry.phase)) latestTO4Discrimination = index;
    if (entry.module_id === "BS4" && ["DISCRIMINATION", "COUNTERPROFILE"].includes(entry.phase)) latestBS4Discrimination = index;

    if (entry.module_id === "TO4" && entry.phase === "FINALIZATION" && ["EPOCHAL", "UNIVERSAL"].includes(entry.scope)) {
      issues.push(issue("ERROR", "DAG4D_TO4_CANNOT_TOTALIZE", at, "Concrete TO4 analysis cannot itself finalize an epochal/universal Gestell diagnosis."));
    }
    if (entry.module_id === "GE4" && entry.phase === "FINALIZATION" && ["EPOCHAL", "UNIVERSAL"].includes(entry.scope)) {
      if (latestMA4 < 0) issues.push(issue("ERROR", "DAG4D_MA4_RECONSTRUCTION_REQUIRED", at, "Epochal/universal GE4 finalization requires prior MA4 diachronic reconstruction."));
      if (latestTO4Discrimination < 0) issues.push(issue("ERROR", "DAG4D_TO4_DISCRIMINATION_REQUIRED", at, "High-level Gestell finalization requires prior concrete TO4 discrimination."));
      if (latestBS4Discrimination < 0) issues.push(issue("ERROR", "DAG4D_BS4_DISCRIMINATION_REQUIRED", at, "High-level Gestell finalization requires prior contextual BS4 discrimination/counterprofile."));
      if (!["EXPLICIT", "CONTESTED"].includes(entry.bridge_status)) issues.push(issue("ERROR", "DAG4D_DIACHRONIC_BRIDGE_REQUIRED", `${at}/bridge_status`, "Machenschaft/Gestell lineage requires an explicit or contested diachronic bridge; synonymy is forbidden."));
      issues.push(issue("REVIEW", "DAG4D_TOTALIZATION_REVIEW", at, "Passing workflow order does not establish the truth of an epochal/universal Gestell diagnosis."));
    }
  }

  const recordResults = [];
  const allowedKeys = ["ma4", "ge4", "bs4", "to4"];
  for (let index = 0; index < steps.length; index += 1) {
    const entry = steps[index];
    if (!entry.record_path) continue;
    const recordPath = path.resolve(path.dirname(absolute), entry.record_path);
    try {
      const record = await readJson(recordPath);
      const result = engine.validateRecord(record, recordPath);
      recordResults.push(result);
      if (record.record_id !== entry.record_id) issues.push(issue("ERROR", "RUN4D_RECORD_ID_MISMATCH", `/execution/${index}/record_id`, `Manifest says ${entry.record_id}, file contains ${record.record_id}.`));
      const moduleKey = Object.keys(record.extensions ?? {}).find((key) => allowedKeys.includes(key));
      if (moduleKey?.toUpperCase() !== entry.module_id) issues.push(issue("ERROR", "RUN4D_MODULE_MISMATCH", `/execution/${index}/module_id`, `Manifest says ${entry.module_id}, record extension is ${moduleKey ?? "missing"}.`));
    } catch (error) {
      issues.push(issue("ERROR", "RUN4D_RECORD_READ", `/execution/${index}/record_path`, error.message));
    }
  }
  return finish(absolute, run.run_id, issues, recordResults);
}

function finish(file, runId, runIssues, recordResults) {
  const issues = sortIssues(runIssues);
  const counts = countIssues(issues);
  const recordErrors = recordResults.reduce((sum, result) => sum + result.counts.ERROR, 0);
  const recordReviews = recordResults.reduce((sum, result) => sum + result.counts.REVIEW, 0);
  return {
    file,
    run_id: runId,
    conformant: counts.ERROR === 0 && recordErrors === 0,
    review_required: counts.REVIEW > 0 || recordReviews > 0,
    counts,
    issues,
    record_results: recordResults,
  };
}
