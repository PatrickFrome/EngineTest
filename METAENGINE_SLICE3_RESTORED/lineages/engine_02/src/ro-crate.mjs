import { createHash } from "node:crypto";
import { mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const EXCLUDED_DIRECTORIES = new Set(["node_modules", ".git"]);

function mediaType(name) {
  const extension = path.extname(name).toLowerCase();
  return ({
    ".json": "application/json",
    ".jsonld": "application/ld+json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".zip": "application/zip",
  })[extension] ?? "application/octet-stream";
}

async function filesUnder(root, current = root) {
  const output = [];
  for (const name of (await readdir(current)).sort()) {
    if (EXCLUDED_DIRECTORIES.has(name)) continue;
    const full = path.join(current, name);
    const info = await stat(full);
    if (info.isDirectory()) output.push(...await filesUnder(root, full));
    else if (info.isFile() && !["ro-crate-metadata.json", "RELEASE_MANIFEST.json"].includes(name)) output.push({ full, info });
  }
  return output;
}

export async function buildRoCrate(rootDirectory, options = {}) {
  const root = path.resolve(rootDirectory);
  const rootInfo = await stat(root);
  if (!rootInfo.isDirectory()) throw new Error(`RO-Crate root is not a directory: ${root}`);
  const files = await filesUnder(root);
  const fileEntities = [];
  for (const { full, info } of files) {
    const relative = path.relative(root, full).replaceAll(path.sep, "/");
    const bytes = await readFile(full);
    fileEntities.push({
      "@id": relative,
      "@type": "File",
      name: path.basename(relative),
      contentSize: String(info.size),
      encodingFormat: mediaType(relative),
      identifier: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
    });
  }
  const generatedAt = options.generatedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const engineVersion = options.engineVersion ?? "unknown";
  return {
    "@context": "https://w3id.org/ro/crate/1.3/context",
    "@graph": [
      {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        conformsTo: { "@id": "https://w3id.org/ro/crate/1.3" },
        about: { "@id": "./" },
      },
      {
        "@id": "./",
        "@type": "Dataset",
        name: options.name ?? path.basename(root),
        description: options.description ?? "Destruktion research object with executable validation, fixtures, reports and provenance.",
        dateModified: generatedAt,
        version: engineVersion,
        hasPart: fileEntities.map((entity) => ({ "@id": entity["@id"] })),
        mentions: [{ "@id": "#destruktion-engine" }, { "@id": "#crate-generation" }],
      },
      {
        "@id": "#destruktion-engine",
        "@type": "SoftwareApplication",
        name: "Destruktion Automation Engine",
        softwareVersion: engineVersion,
        applicationCategory: "Research validation software",
      },
      {
        "@id": "#crate-generation",
        "@type": "CreateAction",
        name: "Generate RO-Crate metadata",
        endTime: generatedAt,
        instrument: { "@id": "#destruktion-engine" },
        result: { "@id": "ro-crate-metadata.json" },
      },
      ...fileEntities,
    ],
  };
}

export async function writeRoCrate(rootDirectory, outputFile, options = {}) {
  const root = path.resolve(rootDirectory);
  const output = path.resolve(outputFile);
  if (path.dirname(output) !== root || path.basename(output) !== "ro-crate-metadata.json") {
    throw new Error("An attached RO-Crate metadata file must be named ro-crate-metadata.json in the crate root.");
  }
  const crate = await buildRoCrate(root, options);
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, `${JSON.stringify(crate, null, 2)}\n`, { encoding: "utf8", flag: options.overwrite ? "w" : "wx" });
  return { output_file: output, entities: crate["@graph"].length, payload_files: crate["@graph"].filter((entity) => entity["@type"] === "File").length, specification: "RO-Crate 1.3" };
}
