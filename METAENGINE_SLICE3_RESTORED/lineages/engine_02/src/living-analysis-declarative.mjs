import { projectPath } from './paths.mjs';
import {
  runLivingAnalysis as runCoreLivingAnalysis,
  validateLivingAnalysisFile,
} from './living-analysis.mjs';

export async function runLivingAnalysis(engine, refineryDirectory, outputDirectory, options = {}) {
  return runCoreLivingAnalysis(engine, refineryDirectory, outputDirectory, {
    ...options,
    registryFile: options.registryFile ?? process.env.DESTRUKTION_LIVING_DECLARATIVE_REGISTRY ?? projectPath('config', 'living_operator_registry.declarative.json'),
  });
}

export { validateLivingAnalysisFile };
