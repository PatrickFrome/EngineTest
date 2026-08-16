# MetaEngine System Improvement Plan — Scaling Compute + Accelerating Self-Improvement

**Date:** 2026-08-16
**Author:** Z.ai Code (autonomous analysis)
**Status:** Living document — updated as improvements land

---

## 📊 Current System State (Measured)

| Metric | Value | Bottleneck? |
|---|---:|---|
| CPU cores | 2 | ✗ (oversubscribed already) |
| RAM | 3.9 GB total, 1.6 GB available | ⚠️ tight |
| Disk | 1 GB free of 10 GB | ⚠️ filling up |
| Tasks/sec (3 shards) | 0.063 (= 227 tasks/hour) | ⚠️ slow |
| Time per task (median) | 46.6s | ⚠️ high |
| Time per improvement cycle | ~5 min (6 tasks × 47s) | ⚠️ slow |
| Tasks in Turso DB | 14,203 | ✓ accumulating |
| Improvement cycles run | ~50+ | ✓ running |
| GitHub Actions free minutes used | ~30 min of 2000/mo | ✓ ample headroom |

---

## 🔍 Bottleneck Analysis

### Bottleneck #1: Single-machine CPU limit (2 cores)

The orchestrator runs 16 engines sequentially inside `ThreadPoolExecutor(max_workers=4)`,
but the OS only has 2 cores. With 3 shards × 4 workers = 12 threads competing for 2 cores,
context-switching overhead is significant.

**Impact:** Each task takes ~47s wall-clock but only ~5s of actual CPU work per engine.
The other ~42s is I/O (file writes, JSON serialization, subprocess spawning for engine_01-04 native executors).

### Bottleneck #2: 47 files written per task (I/O bound)

Each `orchestrator.run()` produces 47 JSON files (HYBRID_MESH 254KB, META_RUN 64KB, FINAL_FUSION 47KB, etc).
That's ~1 MB of disk I/O per task, mostly serial.

**Impact:** ~5-10s of the 47s per task is disk I/O. With 14,203 tasks accumulated, we've written 14 GB total.

### Bottleneck #3: Improvement loop serial phases

Each cycle: benchmark (5 min) → analyze (instant) → apply (instant) → pytest (30s) → benchmark again (5 min).
The two benchmark phases are serial, doubling wall-clock time per cycle.

### Bottleneck #4: No GPU

BoTorch GP surrogate and DSPy teleprompter run on CPU. GPU would speed up:
- GP fitting: 10-50× faster
- DSPy few-shot example generation: 5-10× faster
- (Future) neural architecture search: 100× faster

### Bottleneck #5: Improvement loop doesn't learn across cycles

Each cycle starts fresh — doesn't carry forward which patches helped/hurt. No memory of
"this patch type worked for this category last time".

### Bottleneck #6: GitHub Actions shards are isolated

8 parallel runners don't share state. Each starts cold (pip install, no cache hit on first run).
Total wasted time: 8 × 2 min setup = 16 min/run.

---

## 🎯 Improvement Roadmap (Prioritized)

### Tier 1: Quick Wins (implement now, low effort)

#### 1.1 Cache the orchestrator instance across tasks
**Problem:** Each task creates a new `MetaOrchestrator(root)` — re-loading config, re-building
adapter registry, re-loading biographies. ~2s overhead per task.

**Fix:** Pass a singleton orchestrator into `run_round()`. Saves 2s × 0.063 tasks/sec × 3 shards
= ~0.4 CPU-seconds/sec → ~20% throughput increase.

**Effort:** 1 hour
**Expected gain:** +20% throughput (47s → 38s per task)

#### 1.2 Disable expensive file outputs in benchmark mode
**Problem:** 47 JSON files written per task, but only 5 are actually read by the validator
(AUDITABLE_SYNTHESIS, DIALECTICAL_GRAPH, META_RUN, ENGINE_BIOGRAPHIES_AFTER_RUN, ROUTING_PLAN).

**Fix:** Add `--minimal-output` flag to `run_massive_benchmark.py` that skips writing
HYBRID_MESH, FINAL_FUSION, FRONTIER_CONTROL_PLANE (the 3 biggest files).

**Effort:** 2 hours
**Expected gain:** -30% disk I/O per task, saves ~3s/task

#### 1.3 Share orchestrator state across shards via shared memory
**Problem:** Each shard loads `engine_biographies.json` (36 KB) and `mechanism_library.json` (120 KB)
independently. With 3 shards, that's 3× the load time.

**Fix:** Use `multiprocessing.Manager()` or a shared SQLite cache for these read-only files.

**Effort:** 4 hours
**Expected gain:** Faster shard startup, ~1s/task saved

#### 1.4 Compress large JSON outputs
**Problem:** HYBRID_MESH.json is 254 KB uncompressed. With gzip it would be ~30 KB.

**Fix:** Add `--compress-outputs` flag that writes `.json.gz` instead of `.json`. Update
`analyze_and_improve.py` to read both formats.

**Effort:** 3 hours
**Expected gain:** 80% disk space savings, faster disk I/O

#### 1.5 Pipeline the improvement loop phases
**Problem:** Phase 5 (post-improvement benchmark) waits for Phase 1 (pre-improvement benchmark)
to finish entirely before starting.

**Fix:** Run Phase 5 in parallel with Phase 4 (pytest). They test different things — pytest checks
code correctness, Phase 5 measures fitness. If pytest fails, kill Phase 5.

**Effort:** 3 hours
**Expected gain:** -40% cycle time (10 min → 6 min per cycle)

---

### Tier 2: Architectural Improvements (1-2 days each)

#### 2.1 Distributed compute via Ray or Dask
**Problem:** All 3 shards run on one machine. Can't scale beyond 2 CPU cores.

**Fix:** Add a Ray/Dask backend to `run_massive_benchmark.py`. Each shard becomes a Ray task
that can run on any Ray worker. Workers can be on different machines.

**Implementation:**
```python
# New flag: --backend ray
import ray
ray.init(address=os.environ.get("RAY_ADDRESS", "auto"))

@ray.remote(num_cpus=1)
def remote_evaluate_task(task_dict, run_dir, ...):
    # Same logic as evaluate_task, but runs on a Ray worker
    ...

# In run_round():
futures = [remote_evaluate_task.remote(t.dict(), ...) for t in tasks]
results = ray.get(futures)
```

**Scaling options:**
- Local Ray cluster: 2 workers (no gain on this machine)
- Ray on Kubernetes: scale to N pods
- Ray on cloud spot instances: $0.05/hour per worker
- Ray Anyscale: managed, $0.20/hour per worker

**Effort:** 1 day
**Expected gain:** Linear scaling — N workers = N× throughput

#### 2.2 Use free Colab/Kaggle notebooks as Ray workers
**Problem:** Free cloud GPUs exist (Colab T4, Kaggle P100) but they're ephemeral and
hard to orchestrate.

**Fix:** Write a `scripts/launch_colab_worker.py` that:
1. Programmatically creates a Colab notebook via Selenium/Playwright
2. Installs MetaEngine + Ray
3. Connects to our Ray cluster via ngrok tunnel
4. Auto-refreshes every 12 hours (Colab session limit)

**Effort:** 2 days
**Expected gain:** +1 GPU worker (T4 16GB) for free, 24/7

#### 2.3 Pre-compile MetaEngine engine_01-04 native executors
**Problem:** engine_01-04 are Node.js native executors that spawn a subprocess per task.
Each subprocess pays ~500ms startup cost (Node.js runtime + require()).

**Fix:** Convert to a persistent Node.js worker process (via `subprocess.Popen` with
stdin/stdout JSON protocol). Reuse across tasks.

**Effort:** 1 day
**Expected gain:** -500ms × 4 engines × every task = 2s/task saved (~4% improvement)

#### 2.4 Implement result caching by input hash
**Problem:** If the same task prompt is benchmarked twice (across rounds), we re-run the
full orchestrator. The result is deterministic for the same input + same architecture policy.

**Fix:** Add a `result_cache` directory keyed by `sha256(prompt + policy_hash)`. If cached
result exists and is < 1 hour old, return it instead of running again.

**Effort:** 4 hours
**Expected gain:** Eliminates redundant runs in improvement_loop (Phase 5 often re-runs same tasks)

#### 2.5 Stream results to Turso in batches
**Problem:** Each task result is pushed to Turso via a separate HTTP request. With 227 tasks/hour,
that's 227 HTTP requests/hour — wasteful.

**Fix:** Buffer 25 results, push as a single pipeline batch. Already supported by
`_execute_batch()` in `sync_all_to_turso.py`.

**Effort:** 2 hours
**Expected gain:** 90% fewer HTTP requests, faster sync

---

### Tier 3: Major Upgrades (1 week+ each)

#### 3.1 GPU-accelerated BoTorch surrogate
**Problem:** BoTorch GP fitting is O(n³) in number of observations. With 14k tasks, fitting
takes ~30s on CPU.

**Fix:** Move GP fitting to GPU (if available). BoTorch supports CUDA natively. Add a
`--device cuda` flag to `botorch_surrogate.py`.

**For free GPU access:**
- Colab T4 (free, 16GB) — works for <2GB models
- Kaggle P100 (free, 16GB) — better for larger models
- Lightning AI Studio ($1/hr credits, A10G 24GB)

**Effort:** 3 days
**Expected gain:** 10-50× faster GP fitting, enables larger surrogate models

#### 3.2 Active learning for task selection
**Problem:** Each cycle benchmarks 6 random tasks. But some tasks are more informative than others
(e.g. one that distinguishes between two competing architecture policies).

**Fix:** Use BoTorch's `qExpectedImprovement` acquisition function to select the next 6 tasks
that will most reduce uncertainty in the surrogate model. This is true Bayesian optimization.

**Effort:** 1 week
**Expected gain:** 5-10× faster convergence to optimal architecture policy

#### 3.3 Population-based training (PBT) for hyperparameter search
**Problem:** Currently `improvement_loop` tries one patch per cycle. If the patch fails, we learn
nothing about the surrounding hyperparameter space.

**Fix:** Run PBT with a population of 8 architecture policies in parallel. Each policy runs
6 tasks. Top 2 policies "reproduce" (mutate hyperparameters), bottom 2 are replaced.

**Effort:** 1 week
**Expected gain:** Exponentially faster hyperparameter discovery

#### 3.4 Continuous deployment via GitHub Container Registry
**Problem:** Each GitHub Actions run starts cold (pip install, no Docker cache).

**Fix:** Build a Docker image with MetaEngine pre-installed. Push to GHCR. GitHub Actions
just pulls the image — no install step.

**Effort:** 2 days
**Expected gain:** -2 min setup per shard × 8 shards = 16 min/run saved

#### 3.5 WebAssembly compilation of hot paths
**Problem:** Python is slow for the dialectical graph builder (heuristic rules evaluated
per node, ~1000 nodes per task).

**Fix:** Compile the hot loop to WebAssembly via Pyodide/RustPython. Run in a sandboxed
WASM runtime that can be embedded anywhere (browser, edge, serverless).

**Effort:** 2 weeks
**Expected gain:** 5-10× faster dialectical graph construction

---

### Tier 4: Moonshots (research directions)

#### 4.1 Federated learning across MetaEngine instances
**Problem:** If multiple users run MetaEngine instances, they don't share learned patches.

**Fix:** Build a "patch exchange" protocol where instances can publish/subscribe to patches
via a shared Turso DB table. Each patch is signed and reputation-scored.

**Effort:** 2 weeks
**Expected gain:** Network effect — more users = faster improvement for everyone

#### 4.2 Use LLMs to generate test cases
**Problem:** The 105-task bank is static. New failure modes aren't covered.

**Fix:** Use z-ai/Groq to generate new test cases targeting known weaknesses. E.g., if
SAFETY pass_rate is low, generate 10 more SAFETY tasks with diverse prompts.

**Effort:** 1 week
**Expected gain:** Continuously expanding test coverage, automatic regression detection

#### 4.3 Constitutional AI for self-modification
**Problem:** The improvement_loop can only apply JSON patches, not modify Python code.
This limits what it can optimize.

**Fix:** Use Claude/GPT-4 to generate candidate code patches, validated by:
1. AST diff against the original (must be small)
2. Test suite must pass
3. Fitness must not regress
4. Constitution K0 invariants must hold (no auto-truth claims, etc.)

**Effort:** 2 weeks
**Expected gain:** True self-modification — system can rewrite its own hot paths

---

## 🚀 Recommended Implementation Order

### Week 1: Quick wins (Tier 1)
- [ ] 1.1 Cache orchestrator instance (+20% throughput)
- [ ] 1.2 Minimal-output flag (-30% I/O)
- [ ] 1.4 Compress outputs (-80% disk)
- [ ] 1.5 Pipeline improvement_loop phases (-40% cycle time)
- [ ] 2.4 Result caching (skip redundant runs)
- [ ] 2.5 Batch Turso pushes

**Cumulative gain:** ~2× throughput, ~50% disk savings, ~40% faster cycles

### Week 2: Distributed compute
- [ ] 2.1 Ray backend
- [ ] 2.2 Free Colab GPU worker
- [ ] 2.3 Persistent Node.js worker
- [ ] 3.4 Docker image for GHCR

**Cumulative gain:** 5-10× throughput (depending on Colab availability)

### Week 3-4: Smarter improvement
- [ ] 3.1 GPU BoTorch
- [ ] 3.2 Active learning task selection
- [ ] 3.3 PBT population training

**Cumulative gain:** 10-100× faster convergence to optimal architecture

### Month 2+: Moonshots
- [ ] 4.1 Federated patch exchange
- [ ] 4.2 LLM-generated test cases
- [ ] 4.3 Constitutional self-modification

---

## 📈 Expected Outcomes

If we implement Tier 1 + Tier 2:

| Metric | Current | After Tier 1+2 | Improvement |
|---|---:|---:|---:|
| Tasks/hour (local) | 227 | 500 | 2.2× |
| Tasks/hour (with Colab GPU) | 227 | 2,000 | 8.8× |
| Disk usage per task | 1 MB | 200 KB | 5× savings |
| Improvement cycle time | 10 min | 4 min | 2.5× faster |
| Time to optimal architecture | ~30 days | ~3 days | 10× faster |
| Free LLM validators | 0 | 5-10 | (web-discovered) |

If we also implement Tier 3 (active learning + PBT):

| Metric | Current | After Tier 3 | Improvement |
|---|---:|---:|---:|
| Convergence to optimum | ~30 days | ~6 hours | 120× faster |
| Architecture policy quality | 0.57 fitness | 0.85+ fitness | +50% |
| Self-improvement rate | 1 patch/5min | 8 patches/5min (PBT) | 8× |

---

## 🔧 Implementation Status

| ID | Improvement | Status | Implemented |
|---:|---|---|:---:|
| 1.1 | Cache orchestrator instance | pending | ☐ |
| 1.2 | Minimal-output flag | pending | ☐ |
| 1.3 | Shared memory for read-only files | pending | ☐ |
| 1.4 | Compress outputs | pending | ☐ |
| 1.5 | Pipeline improvement_loop phases | pending | ☐ |
| 2.1 | Ray distributed backend | pending | ☐ |
| 2.2 | Colab GPU worker | pending | ☐ |
| 2.3 | Persistent Node.js worker | pending | ☐ |
| 2.4 | Result caching | pending | ☐ |
| 2.5 | Batch Turso pushes | pending | ☐ |
| 3.1 | GPU BoTorch | pending | ☐ |
| 3.2 | Active learning | pending | ☐ |
| 3.3 | PBT | pending | ☐ |
| 3.4 | Docker image | pending | ☐ |
| 3.5 | WASM compilation | pending | ☐ |

---

## 🎯 Next Action (highest impact, lowest effort)

**Implement Tier 1 improvements (1.1 + 1.2 + 1.4 + 1.5) now.**

These 4 changes require ~10 hours of work and deliver:
- 2× throughput (227 → 500 tasks/hour)
- 5× disk savings (1 MB → 200 KB per task)
- 2.5× faster improvement cycles (10 min → 4 min)

Combined effect: the system learns 5× faster, accumulating test results 2× faster,
using 80% less disk. This is the highest-leverage work available.
