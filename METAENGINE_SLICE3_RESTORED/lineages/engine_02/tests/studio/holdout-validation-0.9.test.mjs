import test from 'node:test';
import assert from 'node:assert/strict';
import { cp, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildHoldoutArchitectureBenchmark, auditHoldoutArchitectureBenchmark } from '../../studio/validation/holdout-architecture.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const FIXTURE=path.join(ROOT,'experiments','external-validation-0.9');
const FREEZE=path.join(FIXTURE,'HOLDOUT_SOURCE_FREEZE.json');
const PIPELINES=path.join(FIXTURE,'holdout-pipelines');
const FROZEN=path.join(FIXTURE,'frozen-architecture-holdout');
async function readJson(p){return JSON.parse(await readFile(p,'utf8'));}

test('0.9 frozen holdout contains 81 passage×hypothesis units without DAE selection', async()=>{
  const d=await readJson(path.join(FROZEN,'holdout_manifest.json'));
  assert.equal(d.unit_count,81); assert.equal(d.excerpt_count,27); assert.equal(d.source_count,9);
  assert.equal(d.selection.dae_involved_in_selection,false);
  assert.equal(new Set(d.units.map(x=>x.unit_id)).size,81);
  assert.deepEqual([...new Set(d.units.map(x=>x.hypothesis_id))].sort(),['OPEN_SET_NECESSITY','PROCESSUAL_HERMENEUTIC_APPLICABILITY','RELATION_GENESIS_APPLICABILITY']);
});

test('0.9 frozen holdout audit passes and predictions cover all four statuses', async()=>{
  const a=await auditHoldoutArchitectureBenchmark(FROZEN); assert.equal(a.status,'PASS');
  const p=await readJson(path.join(FROZEN,'sealed_dae_predictions.json')); const statuses=new Set(p.predictions.map(x=>x.status));
  assert.deepEqual([...statuses].sort(),['INSUFFICIENT','QUALIFIED','REJECTED','SUPPORTED']);
});

test('0.9 holdout lock detects post-freeze DAE prediction mutation', async()=>{
  const t=await mkdtemp(path.join(os.tmpdir(),'dae-holdout-tamper-'));
  try { await cp(FROZEN,t,{recursive:true}); const f=path.join(t,'sealed_dae_predictions.json'); const p=await readJson(f); p.predictions[0].status='REJECTED'; await writeFile(f,`${JSON.stringify(p,null,2)}\n`); const a=await auditHoldoutArchitectureBenchmark(t); assert.equal(a.status,'INVALID'); assert(a.issues.includes('PREDICTIONS_FIXITY_FAILED')); }
  finally { await rm(t,{recursive:true,force:true}); }
});

test('0.9 builder rejects DAE-involved passage selection before reading pipelines', async()=>{
  const t=await mkdtemp(path.join(os.tmpdir(),'dae-holdout-leak-'));
  try { const f=path.join(t,'freeze.json'); const d=await readJson(FREEZE); d.selection_rule.dae_involved_in_selection=true; await writeFile(f,JSON.stringify(d)); await assert.rejects(()=>buildHoldoutArchitectureBenchmark(f,PIPELINES,path.join(t,'out')),/HOLDOUT_SELECTION_NOT_DAE_INDEPENDENT/); }
  finally { await rm(t,{recursive:true,force:true}); }
});

test('0.9 builder rejects development-author overlap', async()=>{
  const t=await mkdtemp(path.join(os.tmpdir(),'dae-holdout-overlap-'));
  try { const f=path.join(t,'freeze.json'); const d=await readJson(FREEZE); d.sources[0].author='Martin Heidegger'; await writeFile(f,JSON.stringify(d)); await assert.rejects(()=>buildHoldoutArchitectureBenchmark(f,PIPELINES,path.join(t,'out')),/HOLDOUT_DEVELOPMENT_AUTHOR_OVERLAP/); }
  finally { await rm(t,{recursive:true,force:true}); }
});

test('0.9 rebuild from frozen excerpts and real refinery observations is deterministic at unit/prediction level', async()=>{
  const t=await mkdtemp(path.join(os.tmpdir(),'dae-holdout-rebuild-'));
  try { const out=path.join(t,'benchmark'); const r=await buildHoldoutArchitectureBenchmark(FREEZE,PIPELINES,out,{generatedAt:'2026-08-11T20:00:00Z'}); const frozen=await readJson(path.join(FROZEN,'sealed_dae_predictions.json')); assert.equal(r.manifest.unit_count,81); assert.deepEqual(r.dae.predictions,frozen.predictions); assert.equal((await auditHoldoutArchitectureBenchmark(out)).status,'PASS'); }
  finally { await rm(t,{recursive:true,force:true}); }
});
