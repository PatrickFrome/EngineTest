#!/usr/bin/env node

import { createEngine } from '../src/engine.mjs';
import { runLivingAnalysis } from '../src/living-analysis-declarative.mjs';

function valueAfter(args, flag) {
  const index = args.indexOf(flag);
  if (index < 0) return undefined;
  if (!args[index + 1]) throw new Error(`${flag} requires a value`);
  return args[index + 1];
}

async function main(argv) {
  const [command, ...args] = argv;
  if (!command || ['help', '--help', '-h'].includes(command)) {
    console.log('Usage: destruktion-declarative living-cycle <refinery-directory> --out <new-directory> [--seed <text>] [--max-families <n>] [--max-operators <n>] [--json]');
    return 0;
  }
  if (command !== 'living-cycle') throw new Error(`Unsupported declarative command: ${command}`);
  const out = valueAfter(args, '--out');
  if (!out) throw new Error('living-cycle requires --out <new-directory>');
  const seed = valueAfter(args, '--seed');
  const families = valueAfter(args, '--max-families');
  const operators = valueAfter(args, '--max-operators');
  const valued = new Set(['--out', '--seed', '--max-families', '--max-operators']);
  const excluded = new Set();
  for (let i = 0; i < args.length; i += 1) if (valued.has(args[i])) { excluded.add(i); excluded.add(i + 1); }
  const roots = args.filter((arg, index) => !excluded.has(index) && !arg.startsWith('--'));
  if (roots.length !== 1) throw new Error('living-cycle requires exactly one Corpus Refinery directory');
  const maximumFamilies = families === undefined ? undefined : Number(families);
  const maximumOperators = operators === undefined ? undefined : Number(operators);
  if (maximumFamilies !== undefined && !Number.isInteger(maximumFamilies)) throw new Error('--max-families must be an integer');
  if (maximumOperators !== undefined && !Number.isInteger(maximumOperators)) throw new Error('--max-operators must be an integer');
  const engine = await createEngine();
  const result = await runLivingAnalysis(engine, roots[0], out, {
    ...(seed !== undefined ? { seed } : {}),
    ...(maximumFamilies !== undefined ? { maximumFamilies } : {}),
    ...(maximumOperators !== undefined ? { maximumOperators } : {}),
  });
  if (args.includes('--json')) console.log(JSON.stringify({ output_dir: result.output_dir, run_id: result.analysis.run_id, validation: result.validation, sufficient_openness: result.analysis.sufficient_openness, runtime: result.analysis.operator_registry.runtime }, null, 2));
  else console.log([
    `LIVING DECLARATIVE CYCLE  run=${result.analysis.run_id}`,
    `runtime=${result.analysis.operator_registry.runtime}`,
    `constellations=${result.analysis.constellations.length} nodes=${result.analysis.graph.nodes.length} edges=${result.analysis.graph.edges.length}`,
    `sufficient_openness=${result.analysis.sufficient_openness.satisfied} output=${result.output_dir}`,
    `philosophical_field_note=${result.files.field_note}`,
    'Claim ceiling: traceable generative reconstruction only; declarative mutation does not imply truth or promotion.',
  ].join('\n'));
  return result.validation.conformant ? 0 : 1;
}

main(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (error) => {
  console.error(`DECLARATIVE FATAL: ${error.stack || error.message}`);
  process.exitCode = 2;
});
