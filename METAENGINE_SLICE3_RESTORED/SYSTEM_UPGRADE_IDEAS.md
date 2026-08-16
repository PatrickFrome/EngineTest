# MetaEngine System Upgrade Ideas — Compute + Self-Improvement Acceleration

**Date:** 2026-08-16
**Goal:** Maximize compute + accelerate self-improvement + auto-apply patches

---

## 📊 Current State (measured at 15:37 UTC)

| Metric | Value |
|---|---:|
| Running processes | 7 (4 shards + 3 agents) |
| RAM used | 3.4 GB / 3.9 GB (87%) ⚠️ |
| Disk used | 6.8 GB / 10 GB (73%) |
| Improvement cycles | 83 |
| PBT generation | 72 |
| Active learning observations | 864 |
| Best fitness (single task) | 0.9500 |
| Best fitness (cycle avg) | 0.7833 |
| Best PBT policy fitness | 0.8795 |
| Turso rows | 240,784 |
| Adaptation patches applied | 15 ✅ |

---

## 🚀 NEW Improvements (beyond Tier 1-3 already implemented)

### Tier 5: GPU + Cloud Compute (highest impact)

#### 5.1 Multi-GPU via Ray + Colab Pro (free $10/month credit)
**Status:** Ready to deploy

Colab Pro gives $10/month free credit = ~50 GPU-hours on T4 16GB.
With Ray distributed backend, we can connect 2-3 Colab sessions simultaneously.

**Action:**
1. User opens 2 Colab notebooks (each gets 1 T4 GPU)
2. Both connect to our Ray head via ngrok
3. BoTorch GP fitting runs on GPU → 50× faster

**Expected gain:** 50× faster GP fitting → 50× faster active learning convergence

#### 5.2 Modal Labs serverless GPU ($30 free credit)
**Status:** Code-ready, needs Modal account

Modal.com provides $30 free credit = ~100 GPU-hours on A10G (24GB VRAM).
Perfect for running PBT with 8 parallel policies, each on its own GPU.

```python
# scripts/modal_pbt_worker.py
import modal
app = modal.App("metaengine-pbt")
image = modal.Image.debian_slim().pip_install("botorch", "ray")

@app.function(image=image, gpu="A10G", timeout=3600)
def evaluate_policy(policy_dict):
    # Run one PBT policy evaluation on GPU
    ...
```

**Expected gain:** 8× parallel PBT evaluations, each 10× faster (GPU) = 80× total

#### 5.3 Lightning AI Studio (1 free A10G GPU, 24/7)
**Status:** Documented

studio.lightning.ai provides 1 free A10G GPU (24GB) running 24/7.
Can host a persistent Ray worker that never disconnects.

**Action:**
1. Sign up at studio.lightning.ai
2. Run `pip install ray botorch metaengine`
3. `ray start --address='<our-ngrok-url>'`
4. Persistent GPU worker, no 12h disconnect

**Expected gain:** Permanent GPU acceleration, no reconnection needed

---

### Tier 6: Algorithmic Improvements (no extra hardware)

#### 6.1 Speculative execution for improvement loop
**Status:** Concept

Currently: Phase 1 (benchmark) → Phase 2 (analyze) → Phase 3 (apply) → Phase 4+5 (validate)

**Idea:** Start Phase 2 (analyze) speculatively after 3 of 6 tasks complete in Phase 1.
If the partial analysis suggests no patches will be generated, abort Phase 1 early.

**Expected gain:** -30% cycle time (skip waiting for all 6 tasks if pattern is clear)

#### 6.2 Bayesian Optimization with cost-aware acquisition
**Status:** Concept

Current active learning uses qEI (maximizes information gain).
**Better:** Use qKnowledgeGradient with cost awareness — prefer tasks that are
fast to evaluate AND informative.

**Implementation:**
```python
from botorch.acquisition import qKnowledgeGradient
acq = qKnowledgeGradient(model, num_fantasies=64)
# Weight by inverse cost (fast tasks preferred)
cost = estimate_task_cost(task_features)
score = acq(x) / cost
```

**Expected gain:** 2× faster convergence by avoiding expensive low-info tasks

#### 6.3 Multi-fidelity optimization
**Status:** Concept

Run each task at multiple fidelity levels:
- Low fidelity: 2 engines, 1 round (fast, ~10s)
- Medium fidelity: 8 engines, 2 rounds (~30s)
- High fidelity: 16 engines, 4 rounds (~50s)

Use BoTorch's `MultiFidelityGP` to model fitness as function of (features, fidelity).
Prefer low-fidelity evaluations early, high-fidelity only for promising regions.

**Expected gain:** 5-10× more evaluations per unit time

#### 6.4 Population diversity maintenance in PBT
**Status:** Concept

Current PBT replaces bottom 25% with mutated offspring of top 25%.
**Problem:** Population can collapse to near-identical policies (premature convergence).

**Fix:** Add novelty search — also reward policies that are DIFFERENT from the rest:
```python
def fitness_with_novelty(policy, population):
    base_fitness = evaluate(policy)
    novelty = mean_distance(policy, population)
    return 0.8 * base_fitness + 0.2 * novelty
```

**Expected gain:** Better exploration, avoids local optima

---

### Tier 7: Code-level Optimizations

#### 7.1 Cython compilation of hot paths
**Status:** Documented

The dialectical graph builder runs ~1000 nodes per task in pure Python.
Compiling to Cython gives 5-10× speedup.

**Hot paths to compile:**
- `dialectical_graph.py` → `build_graph()` 
- `evidence_graph.py` → `build_evidence_graph_from_run()`
- `fusion.py` → `fuse()`

**Action:**
```bash
pip install cython
# Add setup.py with cythonize()
python setup.py build_ext --inplace
```

**Expected gain:** 5-10× faster dialectical graph construction

#### 7.2 Async I/O for file operations
**Status:** Concept

Each task writes 47 JSON files synchronously. With asyncio + aiofiles,
we can write them concurrently.

```python
import aiofiles
import asyncio

async def write_all_outputs(outputs: dict[str, Any], out_dir: Path):
    tasks = []
    for name, data in outputs.items():
        tasks.append(write_json_async(out_dir / f"{name}.json", data))
    await asyncio.gather(*tasks)
```

**Expected gain:** -3s per task (parallel file writes)

#### 7.3 Pickle instead of JSON for large outputs
**Status:** Concept

JSON serialization is slow for large dicts (HYBRID_MESH 254KB).
Pickle is 5-10× faster + smaller.

```python
import pickle
# Write: pickle.dump(data, f, protocol=5)  # protocol 5 = fastest
# Read: pickle.load(f)
```

**Expected gain:** 5-10× faster serialization for large outputs

---

### Tier 8: Auto-Patch Application (IMPLEMENTED ✅)

#### 8.1 Patch Applier (DONE)
**Status:** ✅ Implemented + tested

`metaengine/patch_applier.py` reads JSON patches from `adaptation_patches/`
and modifies actual Python source code:

- AMPLIFY_RULE → inserts new method into `dspy_amplify.py`
- MECHANISM_HYPOTHESIS → adds mechanism loader to `mechanism_library.py`
- ROUTING_HINT → adds routing config to `learned_router.py`
- BIOGRAPHY_DELTA → updates `engine_biographies.json`
- PROVIDER_ADDITION → adds provider to `multi_provider_validator.py`

**Safety features:**
- Backs up original file before modification
- Runs pytest after applying — if fails, rolls back ALL patches
- Tracks applied patches in `storage/patch_applier_state.json`
- Idempotent (won't re-apply same patch)

**Usage:**
```bash
# Apply all pending patches
bash scripts/apply_all_patches.sh

# Dry-run (show what would change)
bash scripts/apply_all_patches.sh --dry-run

# Rollback a specific patch
bash scripts/apply_all_patches.sh --rollback <patch_id>
```

**Result:** 15 patches applied successfully, all tests pass, git-committed.

#### 8.2 Continuous auto-apply (NEXT)
**Status:** Next step

Integrate patch_applier into the improvement_loop so patches are applied
automatically after each cycle (if tests pass).

```python
# In improvement_loop.py, after Phase 6 (publish):
if cycle.accepted and cycle.patches_applied > 0:
    from metaengine.patch_applier import apply_all_patches
    result = apply_all_patches(run_tests_after=True)
    if result["tests_passed"]:
        _log(f"[auto-apply] {result['applied']} patches applied to source code")
    else:
        _log(f"[auto-apply] tests failed — patches rolled back")
```

**Expected gain:** Patches become permanent code changes automatically

---

## 📈 Projected Gains Summary

| Improvement | Effort | Expected Gain |
|---|---|---|
| 5.1 Colab Pro multi-GPU | 1 hour | 50× GP fitting |
| 5.2 Modal serverless GPU | 2 hours | 80× PBT parallelism |
| 5.3 Lightning AI persistent GPU | 1 hour | Permanent GPU acceleration |
| 6.1 Speculative execution | 4 hours | -30% cycle time |
| 6.2 Cost-aware qEI | 1 day | 2× convergence |
| 6.3 Multi-fidelity optimization | 3 days | 5-10× evaluations |
| 6.4 Novelty search in PBT | 1 day | Better exploration |
| 7.1 Cython hot paths | 2 days | 5-10× graph building |
| 7.2 Async file I/O | 1 day | -3s/task |
| 7.3 Pickle serialization | 4 hours | 5-10× faster serialization |
| 8.1 Patch applier ✅ | DONE | Patches → source code |
| 8.2 Continuous auto-apply | 2 hours | Fully autonomous upgrades |

---

## 🎯 Recommended Next Steps (priority order)

### Immediate (today)
1. ✅ **Patch applier** — DONE, 15 patches applied
2. **Continuous auto-apply** — integrate into improvement_loop (2h work)
3. **Colab GPU** — user opens notebook, gets 50× GP fitting (1h setup)

### This week
4. **Modal serverless GPU** — $30 free credit, 80× PBT parallelism
5. **Cython compilation** — 5-10× faster dialectical graph
6. **Pickle serialization** — 5-10× faster file I/O

### Next month
7. **Multi-fidelity optimization** — 5-10× more evaluations
8. **Novelty search in PBT** — better exploration
9. **Lightning AI persistent GPU** — 24/7 GPU acceleration

---

## 🔧 How to Use the Patch Applier

```bash
# See what patches would be applied (no changes)
cd METAENGINE_SLICE3_RESTORED
bash scripts/apply_all_patches.sh --dry-run

# Apply all pending patches (with pytest validation)
bash scripts/apply_all_patches.sh

# Apply without running tests (faster, riskier)
bash scripts/apply_all_patches.sh --no-tests

# Rollback a specific patch
bash scripts/apply_all_patches.sh --rollback <patch_id>
```

The applier:
1. Reads all JSON files from `metaengine/adaptation_patches/`
2. For each patch, modifies the corresponding Python source file
3. Creates a backup in `storage/patch_backups/`
4. Runs pytest to validate
5. If tests fail, restores all backups (full rollback)
6. Commits changes to git with descriptive message
7. Pushes to GitHub

**Applied patches are tracked in `storage/patch_applier_state.json`** —
re-running won't apply the same patch twice (idempotent).
