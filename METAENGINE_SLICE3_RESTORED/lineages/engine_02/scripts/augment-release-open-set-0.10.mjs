import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const readJson = async (rel) => JSON.parse(await fs.readFile(path.join(root, rel), "utf8"));
const writeJson = async (rel, value) => fs.writeFile(path.join(root, rel), `${JSON.stringify(value, null, 2)}\n`, "utf8");

const bank = await readJson("experiments/open-set-hermeneutics-0.10/refinery/hypothesis_bank.json");
const ecology = await readJson("experiments/open-set-hermeneutics-0.10/micro_local_ecology_result.json");
const receipt = await readJson("experiments/open-set-hermeneutics-0.10/mutation/mutation_receipt.json");
const baseline = await readJson("experiments/open-set-hermeneutics-0.10/baseline-living/living_analysis.json");
const mutant = await readJson("experiments/open-set-hermeneutics-0.10/mutant-living/living_analysis.json");
const pkg = await readJson("package.json");
const portable = await readJson("PORTABLE_PROJECT.json");
const validation = await readJson("VALIDATION_REPORT.json");
const release = await readJson("RELEASE_MANIFEST.json");

const open = bank.source_resistance?.open_set_candidate;
if (!open || open.family !== "UNKNOWN_OPERATOR_FAMILY") throw new Error("0.10 open-set candidate evidence missing.");
if (receipt.decision?.decision !== "ACCEPTED_CANDIDATE" || receipt.runtime_reachability !== "FULL") throw new Error("0.10 executable ADD_OPERATOR gate not satisfied.");
if (bank.source_resistance?.operator_candidate?.profile_hints?.length) throw new Error("Descartes 0.10 control unexpectedly activates a known profile.");

const openNodes = (run) => run.graph.nodes.filter((node) => String(node.generated_by ?? "").includes("F-OPEN-")).length;
const stage = {
  stage: "OPEN_SET_HERMENEUTIC_DISCOVERY_AND_MICRO_LOCAL_ECOLOGY",
  source_resistance_status: bank.source_resistance.status,
  known_profile_hints: bank.source_resistance.operator_candidate.profile_hints,
  open_set_status: bank.source_resistance.open_set_status,
  candidate: open.candidate,
  micro_local_counts: ecology.counts,
  mutation_engine_version: receipt.mutation_engine_version,
  mutation_decision: receipt.decision.decision,
  runtime_reachability: receipt.runtime_reachability,
  executable_behavior_changed: receipt.executable_probe.behavior_changed,
  baseline: { constellations: baseline.constellations.length, nodes: baseline.graph.nodes.length, edges: baseline.graph.edges.length, open_family_nodes: openNodes(baseline) },
  mutant: { constellations: mutant.constellations.length, nodes: mutant.graph.nodes.length, edges: mutant.graph.edges.length, open_family_nodes: openNodes(mutant) },
  claim_ceiling: "OPEN_SET_EXECUTABLE_OPERATOR_DISCOVERY_CONFORMANCE_NOT_EXTERNAL_PHILOSOPHICAL_OR_SEMANTIC_VALIDATION"
};

validation.engine_version = pkg.version;
validation.open_set_hermeneutics_0_10 = stage;
validation.portable_project_current = { version: portable.portable_project_version, required_assets: portable.required_assets.length };
release.release = `Destruktion Automation Engine ${pkg.version}`;
release.package_version = pkg.version;
release.open_set_hermeneutics_0_10 = stage;
release.next_gate = "0.11 ADVERSARIAL_SEMANTIC_ROLE_AND_ANTI_SELF_CONFIRMATION";

await writeJson("VALIDATION_REPORT.json", validation);
await writeJson("RELEASE_MANIFEST.json", release);
console.log(`0.10 release augmentation: ${stage.candidate}; windows=${stage.micro_local_counts.windows}; runtime=${stage.runtime_reachability}`);
