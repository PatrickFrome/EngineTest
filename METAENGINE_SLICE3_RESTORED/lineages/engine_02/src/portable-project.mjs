import { createHash } from "node:crypto";
import { lstat, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { countIssues, issue, sortIssues } from "./issues.mjs";
import { PROJECT_ROOT, readJson } from "./paths.mjs";

const MANIFEST_NAME = "PORTABLE_PROJECT.json";
const CONFIG_PATH = path.join("config", "portable_project.json");
const DOC_ROLES = new Set([
  "VISIBLE_BOOTSTRAP",
  "AGENTIC_RUNTIME_INSTRUCTIONS",
  "SELF_CONTAINED_CHAT_ENTRYPOINT",
  "NO_RUNTIME_ANALYSIS_CONTRACT",
  "CURRENT_PROJECT_STATE",
  "NATURAL_LANGUAGE_ROUTER",
]);
const FORBIDDEN_LOCAL_PATHS = [
  { code: "PORTABLE_WORKSPACE_PATH", regex: /(?:^|[\s`'"(])\/workspace\//m },
  { code: "PORTABLE_ROOT_PATH", regex: /(?:^|[\s`'"(])\/root\//m },
  { code: "PORTABLE_FILE_URI", regex: /file:\/\//i },
  { code: "PORTABLE_WINDOWS_ABSOLUTE_PATH", regex: /(?:^|[\s`'"(])[A-Za-z]:[\\/]/m },
];

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function safeRelative(candidate) {
  if (typeof candidate !== "string" || !candidate.length || path.isAbsolute(candidate) || candidate.includes("\0")) return false;
  const normalized = path.posix.normalize(candidate.replaceAll("\\", "/"));
  return normalized !== ".." && !normalized.startsWith("../") && normalized === candidate.replaceAll("\\", "/");
}

async function assetDescriptor(root, entry) {
  if (!safeRelative(entry.path)) throw new Error(`Unsafe portable asset path: ${entry.path}`);
  const file = path.join(root, entry.path);
  const info = await lstat(file);
  if (info.isSymbolicLink()) throw new Error(`Portable asset cannot be a symbolic link: ${entry.path}`);
  if (!info.isFile()) throw new Error(`Portable asset is not a regular file: ${entry.path}`);
  const bytes = await readFile(file);
  return { path: entry.path, role: entry.role, size_bytes: bytes.length, sha256: sha256(bytes) };
}

export async function buildPortableProjectManifest(engine, projectRoot = PROJECT_ROOT) {
  const root = path.resolve(projectRoot);
  const config = await readJson(path.join(root, CONFIG_PATH));
  const packageJson = await readJson(path.join(root, "package.json"));
  if (config.package_version !== packageJson.version) throw new Error(`Portable package version ${config.package_version} does not match package.json ${packageJson.version}.`);
  if (config.engine_version !== engine.context.engineVersion) throw new Error(`Portable engine version ${config.engine_version} does not match runtime ${engine.context.engineVersion}.`);
  const seen = new Set();
  const requiredAssets = [];
  for (const entry of config.required_asset_paths ?? []) {
    if (seen.has(entry.path)) throw new Error(`Duplicate portable asset: ${entry.path}`);
    seen.add(entry.path);
    requiredAssets.push(await assetDescriptor(root, entry));
  }
  const { required_asset_paths: _requiredAssetPaths, ...base } = config;
  const manifest = { ...base, required_assets: requiredAssets };
  const structuralIssues = engine.structural.validatePortableProject(manifest);
  if (structuralIssues.length) throw new Error(`Portable manifest is structurally invalid: ${JSON.stringify(structuralIssues, null, 2)}`);
  const bytes = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  return { root, manifest, bytes, sha256: sha256(bytes) };
}

export async function writePortableProjectManifest(engine, projectRoot = PROJECT_ROOT) {
  const built = await buildPortableProjectManifest(engine, projectRoot);
  const outputFile = path.join(built.root, MANIFEST_NAME);
  await writeFile(outputFile, built.bytes);
  const validation = await validatePortableProject(engine, built.root);
  if (!validation.conformant) throw new Error(`Generated portable project failed validation: ${JSON.stringify(validation.issues, null, 2)}`);
  return { ...built, output_file: outputFile, validation };
}

export async function validatePortableProject(engine, projectRoot = PROJECT_ROOT) {
  const root = path.resolve(projectRoot);
  const manifestFile = path.join(root, MANIFEST_NAME);
  const issues = [];
  let manifest;
  try {
    manifest = await readJson(manifestFile);
  } catch (error) {
    const sorted = sortIssues([issue("ERROR", "PORTABLE_MANIFEST_READ", "/", error.message)]);
    return { root, file: manifestFile, conformant: false, counts: countIssues(sorted), issues: sorted };
  }
  issues.push(...engine.structural.validatePortableProject(manifest));
  const packageJson = await readJson(path.join(root, "package.json"));
  if (manifest.package_version !== packageJson.version) issues.push(issue("ERROR", "PORTABLE_PACKAGE_VERSION", "/package_version", `Manifest ${manifest.package_version} differs from package.json ${packageJson.version}.`));
  if (manifest.engine_version !== engine.context.engineVersion) issues.push(issue("ERROR", "PORTABLE_ENGINE_VERSION", "/engine_version", `Manifest ${manifest.engine_version} differs from runtime ${engine.context.engineVersion}.`));
  for (const [field, candidate] of [["entrypoint", manifest.entrypoint], ["agent_instructions", manifest.agent_instructions]]) {
    if (!safeRelative(candidate)) issues.push(issue("ERROR", "PORTABLE_UNSAFE_PATH", `/${field}`, `${candidate} is not a safe relative path.`));
  }
  const assets = Array.isArray(manifest.required_assets) ? manifest.required_assets : [];
  const assetPaths = new Set();
  for (const [index, asset] of assets.entries()) {
    if (!safeRelative(asset.path)) {
      issues.push(issue("ERROR", "PORTABLE_UNSAFE_ASSET_PATH", `/required_assets/${index}/path`, `${asset.path} is not a safe relative path.`));
      continue;
    }
    if (assetPaths.has(asset.path)) issues.push(issue("ERROR", "PORTABLE_DUPLICATE_ASSET", `/required_assets/${index}/path`, `${asset.path} occurs more than once.`));
    assetPaths.add(asset.path);
    const file = path.join(root, asset.path);
    try {
      const info = await lstat(file);
      if (info.isSymbolicLink() || !info.isFile()) {
        issues.push(issue("ERROR", "PORTABLE_ASSET_NOT_REGULAR", `/required_assets/${index}`, `${asset.path} must be a regular non-symlink file.`));
        continue;
      }
      const bytes = await readFile(file);
      if (bytes.length !== asset.size_bytes) issues.push(issue("ERROR", "PORTABLE_ASSET_SIZE", `/required_assets/${index}/size_bytes`, `${asset.path} expected ${asset.size_bytes} bytes, found ${bytes.length}.`));
      const actualHash = sha256(bytes);
      if (actualHash !== asset.sha256) issues.push(issue("ERROR", "PORTABLE_ASSET_HASH", `/required_assets/${index}/sha256`, `${asset.path} fixity mismatch.`));
      if (DOC_ROLES.has(asset.role)) {
        const text = bytes.toString("utf8");
        for (const check of FORBIDDEN_LOCAL_PATHS) if (check.regex.test(text)) issues.push(issue("ERROR", check.code, `/required_assets/${index}`, `${asset.path} contains a host-specific path.`));
      }
    } catch (error) {
      issues.push(issue("ERROR", "PORTABLE_ASSET_MISSING", `/required_assets/${index}`, `${asset.path}: ${error.message}`));
    }
  }
  for (const [index, candidate] of (manifest.required_read_order ?? []).entries()) {
    if (candidate === MANIFEST_NAME) continue;
    if (!assetPaths.has(candidate)) issues.push(issue("ERROR", "PORTABLE_READ_ASSET_UNBOUND", `/required_read_order/${index}`, `${candidate} is not cryptographically bound as a required asset.`));
  }
  if (!assetPaths.has(manifest.entrypoint)) issues.push(issue("ERROR", "PORTABLE_ENTRYPOINT_UNBOUND", "/entrypoint", "The visible entrypoint must be a required hashed asset."));
  if (!assetPaths.has(manifest.agent_instructions)) issues.push(issue("ERROR", "PORTABLE_AGENT_INSTRUCTIONS_UNBOUND", "/agent_instructions", "Agent instructions must be a required hashed asset."));
  if (manifest.invariants?.mandatory_etymology !== true || manifest.output_contract?.mandatory_etymology !== true) issues.push(issue("ERROR", "PORTABLE_ETY_REQUIRED", "/invariants", "ETY-0.2 must be mandatory in every portable execution profile."));
  if (manifest.invariants?.mandatory_etymological_significance !== false) issues.push(issue("ERROR", "PORTABLE_ETY_SIGNIFICANCE", "/invariants/mandatory_etymological_significance", "Mandatory ETY execution cannot imply mandatory philosophical significance."));
  if (manifest.invariants?.document_only_may_claim_code_execution !== false) issues.push(issue("ERROR", "PORTABLE_PSEUDO_EXECUTION", "/invariants/document_only_may_claim_code_execution", "Document-only mode must never claim code execution."));
  if (!manifest.execution_profiles?.EXECUTION_AVAILABLE || !manifest.execution_profiles?.DOCUMENT_ONLY) issues.push(issue("ERROR", "PORTABLE_DUAL_RUNTIME_REQUIRED", "/execution_profiles", "Both engine-executed and document-only profiles are required."));
  const sorted = sortIssues(issues);
  const counts = countIssues(sorted);
  return { root, file: manifestFile, manifest, conformant: counts.ERROR === 0, counts, issues: sorted };
}

export function portableProjectCard(manifest) {
  return {
    title: manifest.title,
    portable_project_version: manifest.portable_project_version,
    engine_version: manifest.engine_version,
    entrypoint: manifest.entrypoint,
    default_language: manifest.default_language,
    execution_profiles: Object.fromEntries(Object.entries(manifest.execution_profiles).map(([key, value]) => [key, value.provenance_label])),
    supported_inputs: manifest.supported_inputs,
    mandatory_etymology: manifest.invariants.mandatory_etymology,
    primary_outputs: [manifest.output_contract.primary_living_output, manifest.output_contract.final_expert_output],
    current_state: manifest.current_state,
    claim_ceiling: manifest.claim_ceiling,
  };
}

export async function readPortableProjectManifest(projectRoot = PROJECT_ROOT) {
  return readJson(path.join(path.resolve(projectRoot), MANIFEST_NAME));
}

