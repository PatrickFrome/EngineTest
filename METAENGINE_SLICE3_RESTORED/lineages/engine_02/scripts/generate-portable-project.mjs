import { createEngine } from "../src/engine.mjs";
import { writePortableProjectManifest } from "../src/portable-project.mjs";

const engine = await createEngine();
const result = await writePortableProjectManifest(engine);
console.log(`Portable project manifest: ${result.output_file}`);
console.log(`assets=${result.manifest.required_assets.length} sha256=${result.sha256} conformant=${result.validation.conformant}`);

