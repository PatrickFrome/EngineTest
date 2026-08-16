# Research Report: AI Self-Improvement & Reasoning Enhancement Techniques (2024–2026)

**Task ID:** research-self-improvement
**Agent:** general-purpose research sub-agent
**Date:** 2025
**Scope:** Mapping state-of-the-art self-improvement techniques onto MetaEngine's existing modules (`tiered_fitness`, `real_recursive`, `amplify_distill`, `multi_model_router`, `event_publisher`).

---

## Source disclosure

The `web_search` function returned HTTP 429 (rate-limited) for every attempted query during this run. All citations below are therefore drawn from the agent's training-knowledge of the literature through approximately early 2025. Where I am uncertain about an exact arXiv ID or year, I flag it. Treat specific citation details as **directionally correct, not bibliographically verified** — the mechanisms and design lessons are robust; the exact paper numbers may need re-confirmation against arXiv/Google Scholar before publication.

Key papers referenced (from memory, may need URL verification):

- STaR — Zelikman et al., 2022, NeurIPS ("STaR: Bootstrapping Reasoning With Reasoning")
- STaR+ / Quiet-STaR — Zelikman et al., 2023–2024
- Self-Rewarding Language Models — Yuan et al., 2024, ICML
- SPIN (Self-Play Fine-Tuning) — Chen et al., 2024
- rStar-Math — Gou et al., 2024–2025 (Microsoft Research Asia)
- AlphaCodium — Ridnik et al., 2024
- Self-Discover — Zhou et al., 2024, ICLR
- Tree of Thoughts — Yao et al., 2023, NeurIPS
- Graph of Thoughts — Besta et al., 2023, AAAI 2024
- Self-Consistency — Wang et al., 2022, ICLR 2023
- ReAct — Yao et al., 2022, ICLR 2023
- Reflexion — Shinn et al., 2023, NeurIPS
- Constitutional AI — Bai et al., 2022 (Anthropic)
- Self-Refine — Madaan et al., 2023, NeurIPS
- "LLMs Cannot Self-Correct Reasoning Yet" — Huang et al., 2023, EMNLP findings
- CRITIC — Gou et al., 2024, ICLR
- "Let's Verify Step by Step" (PRMs) — Lightman et al., 2023, ICLR 2024
- "Language Models (Mostly) Know What They Know" — Kadavath et al., 2022 (Anthropic)
- "Language Models Don't Always Say What They Think" — Turpin et al., 2023, ACL
- Surrogate-Assisted Evolutionary Optimization survey — Jin, 2011, IEEE EC
- RETRO — Borgeaud et al., 2022 (DeepMind)
- Voyager — Wang et al., 2023
- Generative Agents — Park et al., 2023, UIST
- MAML — Finn et al., 2017
- Prioritized Experience Replay — Schaul et al., 2015, ICLR

---

## Executive summary

MetaEngine has built a working recursive improvement flywheel (`real_recursive.py`), a 3-tier fitness evaluator (`tiered_fitness.py`) with an online-learning L0 surrogate, an IDA cycle (`amplify_distill.py`) with 7 weighted rules, a multi-model router with cost-aware failover, and an event publisher for real-time observability. The constitution (K0 anchor, `truth_effect=NONE`, no auto-promotion, no code modification, bounded RSI) is preserved through all of this. The Phase-68 measured improvement of +0.0147 over 2 generations (1.0167×) is real but small.

The biggest gaps relative to 2024–2025 SOTA, in priority order:

1. **L2 evaluator is too coarse.** A substring match on `17*23=391` cannot tell *reasoning quality* — only *outcome correctness*. SOTA systems use Process Reward Models (PRMs) and faithfulness probes. Without these, the flywheel can only optimize "gets the answer right" not "reasons correctly."
2. **No reject-sampling filter in the distillation step.** STaR, Self-Rewarding LM, and rStar-Math all only retain generations that pass an external check. MetaEngine's `distill` extracts insights from whatever ran, including failures.
3. **No convergence criterion.** `real_recursive.run()` runs for N generations unconditionally. STaR-style loops terminate when self-improvement signal falls below a threshold or when quality distribution stops shifting.
4. **No exploration in L2 candidate selection.** L2 budget is consumed top-down by highest L0 score. This is pure exploitation. Active-learning / Bayesian-optimization surrogate selection would extract ~2–3× more signal per L2 call.
5. **L0 surrogate has no uncertainty estimate.** The 4-feature linear model returns a point estimate. Can't do UCB / EI acquisition, can't tell when to defer to L1/L2.
6. **L1 "constitution check" is a static range check.** Constitutional AI's actual innovation is *model-generated self-critique against principles*. MetaEngine's L1 is closer to a validator than a constitution.
7. **Distillation history is flat, not retrievable.** N4 persists insights to a JSON list but they don't inform subsequent runs except as raw history. Voyager-style skill libraries or RETRO-style retrieval would turn history into a usable memory.
8. **No multi-step reasoning architecture.** `max_deep_engines` is parallel sampling — a crude Self-Consistency. No Tree-of-Thoughts, no Reflexion loop, no ReAct grounding.

The 14 recommendations below are organized by topic then consolidated into a per-module table at the end.

---

## 1. Self-improvement flywheels

### Key papers & core mechanisms

**STaR (Zelikman et al., 2022, NeurIPS; arXiv:2203.14465)** — *Bootstrap reasoning with reasoning*. Loop: (1) prompt model with question, (2) sample a chain-of-thought (CoT) and answer, (3) keep only CoTs that produce the *correct* answer (reject-sampling filter using ground truth), (4) fine-tune the model on the kept CoTs, (5) repeat on harder questions. The key insight is the **external correctness signal** — without it, the loop degenerates. STaR+ adds *rationalization*: if the model got the answer wrong, give it a hint and let it produce a CoT that does reach the right answer — then train on that. This is the "I know the answer, let me reconstruct why" pattern.

**Self-Rewarding Language Models (Yuan et al., 2024, ICML; arXiv:2401.10020)** — The model itself acts as a judge over its own outputs to generate preference pairs, then trains via DPO. The striking empirical finding: judge quality and generation quality **co-improve** across iterations — a positive feedback loop. Divergence risk: if the judge becomes systematically biased (e.g., prefers verbose answers), DPO amplifies that bias each iteration → reward hacking.

**SPIN (Self-Play Fine-Tuning, Chen et al., 2024, arXiv:2401.01335)** — The model plays against itself: an *opponent* (current model) generates responses, the *protagonist* (model being trained) must distinguish them from human data via a binary classifier head. Fixed point of the iteration: protagonist converges when it can no longer distinguish its own outputs from human data — i.e., the model's distribution matches the human distribution. Clean convergence criterion.

**rStar-Math (Gou et al., 2024–2025; arXiv:2501.04519)** — Small LLMs (7B) can self-improve to o1-level math reasoning via a 3-component loop: (a) **MCTS rollouts** with Code-augmented CoT (test Python code in the CoT), (b) **Process Reward Model (PRM)** trained on the rollout data itself, (c) **self-annotation** that filters rollouts using execution feedback as ground truth. The PRM is the key — it provides per-step reward, not just outcome reward. Critical design: PRM training is bootstrapped from *execution verification* (Python actually runs), so it doesn't drift.

**AlphaCodium (Ridnik et al., 2024, arXiv:2404.18463)** — Code generation as iterative TDD: (1) generate solution + public tests, (2) run tests, (3) reflect on failures, (4) patch. Repeat. The external ground truth is **test execution**. Divergence mode: weak tests → false-positive passes → learning from accidentally-correct solutions.

**Self-Discover (Zhou et al., 2024, ICLR; arXiv:2310.00668)** — Rather than a fixed reasoning template, the model *discovers* its own task-specific reasoning structure by composing atomic reasoning modules (e.g., "divide and conquer," "critical thinking," "reflection"). Stage 1: select + adapt modules for the task. Stage 2: apply the composed structure to instances. Reduces reasoning errors because the structure is task-appropriate, not generic.

### Convergence vs divergence — what makes it work

**Convergence drivers:**
- **External ground truth at the loop's terminus.** STaR uses correct answers; rStar-Math uses code execution; AlphaCodium uses tests. Without this, the loop optimizes a model of the world, not the world.
- **Reject-sampling filter.** Only keep generations that pass the external check. The signal-to-noise ratio of training data is the bottleneck.
- **Bounded correction / monotonic improvement requirement.** STaR only fine-tunes when the new model is *strictly better* than the old on held-out tasks (otherwise rollback).
- **Diversity preservation.** SPIN explicitly preserves the human distribution as a fixed point — preventing mode collapse.
- **PRM over ORM (outcome reward model).** Per-step rewards converge faster and more stably than outcome-only rewards (Lightman et al., 2023).

**Divergence drivers:**
- **Self-reward without grounding.** Self-Rewarding LM diverges if the judge is biased — the bias compounds.
- **Greedy self-distillation.** Training on your own argmax outputs → distribution sharpens → mode collapse. ("Curse of self-distillation," Godey et al., 2024.)
- **No exploration.** Pure exploitation of current best → stuck in local optimum.
- **PRM drift.** If the PRM is trained on noisy step labels, it can drift to reward the wrong things. rStar-Math mitigates this by anchoring PRM training to execution feedback.
- **Verifier over-fitting.** The model learns to fool the verifier (reward hacking) instead of solving the task.

### Application to MetaEngine — `real_recursive.py` + `amplify_distill.py`

**Weak spots in current implementation:**

1. **`real_recursive.py` has no reject-sampling filter.** Look at `run()` (lines 201–310): every generation's PBT result is fed to `distill()` regardless of quality. The distill step extracts "which trainers improved most" but never *rejects* runs that didn't actually improve. Compare STaR: only fine-tunes on CoTs that produce correct answers.
2. **`improvement_vs_prev = mean_fitness - prev_mean_fitness` is the only signal.** If L2 budget is exhausted and L0 surrogate drifts (the I5 correction band allows ±0.3), `mean_fitness` could *appear* to improve while the underlying L2 correctness is flat or falling. This is exactly the Huang et al. 2023 failure mode: "LLMs cannot self-correct reasoning yet" when there's no external check.
3. **No convergence criterion.** `run(num_generations=3)` just runs N times. STaR-style loops terminate when: (a) improvement drops below threshold for K consecutive generations, or (b) the held-out validation distribution stops shifting, or (c) the distill step finds no new insights.
4. **`amplify_distill.py` rule SET is fixed (7 rules in `AMPLIFY_RULE_NAMES`).** N5 only learns the *weights* of these rules, not the rules themselves. STaR+ and Self-Rewarding LM discover new reasoning patterns; MetaEngine cannot.
5. **N5's `_update_rule_weights` credits *all* fired rules with the same global improvement signal.** If 3 rules fired and improvement was +0.05, all 3 get credit. This is a credit-assignment problem — the rule that actually drove the improvement can't be distinguished. Multi-armed bandit / Thompson sampling would be more correct.
6. **Distillation insights are extracted but never *verified* against held-out tasks.** There's no train/test split for insights.

**Recommendations:**

- **R1.1 (real_recursive.py):** Add a **reject-sampling filter** to the distill step. Before extracting insights, drop runs where `l2_score < l2_score_threshold` (e.g., 0.5). Insights should come only from runs that genuinely solved L2 tasks. Publish a `distill.rejected` event when this happens. *(Medium effort. Constitution-compatible: doesn't promote anything to truth, just refuses to learn from low-quality runs.)*
- **R1.2 (real_recursive.py):** Add a **convergence criterion** based on the K-stage rolling improvement: stop if `|improvement_vs_prev| < improvement_threshold` for K=2 consecutive generations OR if `distillation_insights` is empty (no new insights to extract). Publish `recursive.converged` event. *(Low effort.)*
- **R1.3 (amplify_distill.py):** Replace the global-credit `_update_rule_weights` with a **per-rule credit-assignment via leave-one-out**. For each fired rule, compute what improvement *would have been* if that rule had not fired (re-run amplify with that rule's weight = 0, measure counterfactual fitness). Approximate this cheaply: maintain a per-rule EMA of `(improvement_when_rule_fired) - (improvement_when_rule_did_not_fire)`. *(Medium effort, no extra LLM calls — just bookkeeping.)*
- **R1.4 (real_recursive.py):** Add a **held-out validation task set** separate from the L2 task rotation. Every K generations, evaluate on the held-out set (counts against an `eval_budget`, not `l2_budget`). If held-out performance diverges from in-loop performance → publish `recursive.overfit_warning`. This is the STaR/rStar-Math anti-drift mechanism. *(High effort — requires a curated task bank. Constitution-compatible: held-out is observational, doesn't modify policy.)*
- **R1.5 (amplify_distill.py):** Add a **"discovered rule" mechanism**. When `distill()` extracts an insight like "high temperature helped on math but hurt on logic," propose a candidate new rule (e.g., `temperature_task_conditional`) and add it to `AMPLIFY_RULE_NAMES` with weight 1.0. After K observations, if the rule's weight is consistently below 0.5, prune it. This is the STaR+/Self-Discover pattern of expanding the rule set. *(High effort, must be carefully constitution-boundaried — explicitly observational, never promoted.)*

---

## 2. Reasoning quality metrics

### Key papers & core mechanisms

**Process Reward Models (PRMs) — Lightman et al., 2023, ICLR 2024 ("Let's Verify Step by Step"; arXiv:2305.20050).** Train a per-step reward model on human-annotated reasoning traces. At inference, the PRM scores each step and guides beam search. OpenAI's "verifiers" paper showed PRMs substantially outperform outcome reward models (ORMs) on math. The PRM catches *intermediate errors* before they propagate.

**Self-Consistency — Wang et al., 2022, ICLR 2023 (arXiv:2203.11171).** Sample N independent CoTs at high temperature, take majority vote on the final answer. Disagreement rate → uncertainty estimate. Cheap and surprisingly effective. Failure mode: if the model has a *systematic* bias, all N samples share it and majority vote confirms the bias.

**Chain-of-Thought faithfulness — Turpin et al., 2023, ACL ("Language Models Don't Always Say What They Think"; arXiv:2305.04388); Lyu et al., 2023 ("Faithful Chain-of-Thought Reasoning").** Test whether the CoT *causes* the answer or is post-hoc rationalization. Method: paraphrase the CoT preserving facts, perturb biased words, measure answer stability. If the answer changes a lot → unfaithful (CoT is decoration, not reasoning).

**Calibration — Kadavath et al., 2022, Anthropic ("Language Models (Mostly) Know What They Know"; arXiv:2207.05221).** P(True) probe: ask the model "is your previous answer true?" and compare to actual accuracy. Calibrated models have P(True) ≈ accuracy. ECE (Expected Calibration Error), Brier score. Key finding: larger models are better calibrated on multiple-choice but not on free-form generation — calibration is task-specific.

**Logical consistency — Betz 2022 ("Working Memory or Stack Memory?"; LLM-as-deduction-engine work); also "Can Language Models Follow Logical Rules?" (Sun et al., 2023).** Test whether the model obeys transitivity (if A>B and B>C then A>C), modus ponens, etc. Often they don't — especially when context introduces a conflicting prior.

**Reasoning step validity via natural-language verification — "Verify Step by Step" pattern from multiple 2024 papers (e.g., Skywork-Reasoning, Qwen-2.5-Math technical reports).** A separate verifier model checks each step of the CoT and labels it as valid / invalid / unsupported. The verifier can be the same model in a different role.

### Application to MetaEngine — `tiered_fitness.py`

**Weak spots in current implementation:**

1. **L2 score formula is bizarre (line 387–393 of `tiered_fitness.py`):**
   ```
   score = 0.5  # base
   if correct: score += 0.3
   if has_disclaimer: score += 0.2
   ```
   This means: **wrong answer + disclaimer = 0.7**, but **correct answer + no disclaimer = 0.8**. A model that refuses to answer ("I can't help with that — this is generative-only") would score 0.7, outranking a model that gets the math right but doesn't include the disclaimer. The disclaimer check is also a *substring match* on `"generative"` or `"verified"` — trivially gameable by adding "verified" to every output.

2. **L2 only checks outcome correctness, not reasoning quality.** The prompt asks for "only the number" or "one sentence." No CoT is captured, no step-level reward, no faithfulness probe. This means the flywheel is optimizing for "answer correctness on 3 specific tasks," not "general reasoning ability."

3. **Only 3 L2 tasks, rotated round-robin.** A model could memorize the 3 answers (17*23=391, Socrates is mortal, correlation ≠ causation) and game L2 without actually reasoning. **Rote-learning risk** is real.

4. **No calibration metric.** The model's confidence in its own answer is never measured. A correct answer with low confidence is *worse* than a correct answer with high confidence (because the system can't trust it).

5. **L1 score is purely a range check (lines 279–307 of `tiered_fitness.py`).** It checks `max_rounds in [1,8]`, `exploration_rate in [0, 0.30]`, `temperature in [0, 2.0]`. This is a *validator*, not a *reasoning-quality check*. There's no assessment of whether the configuration produces sound reasoning.

6. **No self-consistency across L2 calls.** Each L2 call is a single sample. If the temperature is high (the amplify rule increases temperature when RLAIF is low — line 222–231 of `amplify_distill.py`), the same theta will produce different answers on different L2 calls. Currently, only one is captured per generation.

**Recommendations:**

- **R2.1 (tiered_fitness.py):** Fix the L2 scoring formula to make correctness dominant. Proposed: `score = 0.1 (base) + 0.6 (correct) + 0.2 (disclaimer) + 0.1 (calibrated)`. Wrong answer should score ≤ 0.3, not 0.7. Also replace substring-match disclaimer with a more robust check (e.g., the response must explicitly acknowledge uncertainty, not just contain the word "generative"). *(Low effort, high impact.)*
- **R2.2 (tiered_fitness.py):** Add **process-level L2 evaluation**. When the L2 task is the math one (17*23), capture the full CoT, not just the answer. Have the LLM-as-judge (using the router) score each reasoning step on a 0-1 scale. Use the *minimum* step score as a "weakest-link" metric (PRM insight: a single bad step sinks the whole CoT). Publish `fitness.prm_score` event. *(Medium effort, +1 LLM call per L2 evaluation.)*
- **R2.3 (tiered_fitness.py):** Add **self-consistency** for L2 evaluations with high-temperature theta. If `temperature > 0.8`, do K=3 L2 calls and use majority vote on correctness + variance as an uncertainty signal. This is the Wang 2022 mechanism. Don't consume 3× budget — make it conditional on uncertainty. *(Medium effort.)*
- **R2.4 (tiered_fitness.py):** Expand L2 task set from 3 to ~20+ tasks (curated bank), sampled stochastically per generation. Publish task_id in events. This addresses the rote-learning risk and gives finer-grained signal. *(Low effort, high impact — the task bank is the work.)*
- **R2.5 (tiered_fitness.py + new module):** Add a **calibration probe**. Every K L2 evaluations, ask the model "On a scale of 0–1, how confident are you that your previous answer is correct?" Compute Brier score over time. Publish `fitness.calibration` event. A high-scoring model with poor calibration should *not* be promoted. *(Medium effort, +0 cost if appended to existing L2 prompt.)*
- **R2.6 (tiered_fitness.py):** Reframe **L1 as a *constitutional self-critique***, not a range check. Currently `_evaluate_l1` is a static validator. Replace with: prompt the model with its own theta + a 1-sentence description, ask "does this configuration respect the K0 constitution (no truth promotion, no code modification, bounded RSI)?" Use the model's yes/no + rationale as the L1 score. This matches Bai et al. 2022's actual innovation (model-driven constitutional critique), not the current validator-style implementation. *(High effort, +1 LLM call. Boundary: this is *evaluative*, not truth — the model's verdict is a score, not a binding decision.)*

---

## 3. Multi-step reasoning architectures

### Key papers & trade-offs

| Architecture | Cost (LLM calls) | Strength | Weakness |
|---|---|---|---|
| **Chain-of-Thought (CoT)** — Wei et al., 2022 | 1× | Cheap, baseline improvement | No search, no recovery |
| **Self-Consistency (SC)** — Wang et al., 2022 | N× (typically 5–40) | Reduces variance, uncertainty signal | Fails on systematic bias |
| **Tree of Thoughts (ToT)** — Yao et al., 2023, NeurIPS (arXiv:2305.10601) | O(B^D) | Search, backtracking, planning | Bad state-evaluator → bad pruning; expensive |
| **Graph of Thoughts (GoT)** — Besta et al., 2023, AAAI 2024 (arXiv:2308.09687) | O(B^D) with merges | Synthesis, refinement, non-tree DAG | Complex bookkeeping |
| **ReAct** — Yao et al., 2022, ICLR 2023 (arXiv:2210.03629) | 1× per step | External tool grounding | Tools must be reliable; loop control tricky |
| **Reflexion** — Shinn et al., 2023, NeurIPS (arXiv:2303.11366) | 1× + reflection per retry | Verbal reinforcement learning | Reflection can hallucinate causes |
| **Self-Discover** — Zhou et al., 2024 | 2-phase (compose + apply) | Task-adaptive reasoning structure | Stage 1 can mis-select modules |

**Key trade-offs:**
- **Cost vs quality**: ToT/GoT give the biggest quality lift but cost 10–100× a single CoT.
- **Recovery vs no-recovery**: Reflexion can recover from errors but only if the reflection is honest (Huang et al. 2023: intrinsic self-correction often degrades without external signal).
- **Search vs sampling**: ToT searches the state space; Self-Consistency samples it. ToT is better when the search tree is shallow + evaluator is good; SC is better when the tree is deep + evaluator is bad.
- **External grounding**: ReAct and AlphaCodium ground via tools/tests — most reliable, but tools must exist.

### Application to MetaEngine — `tiered_fitness.py`, `real_recursive.py`, `multi_model_router.py`

**Weak spots in current implementation:**

1. **`max_deep_engines` is parallel sampling, not Tree of Thoughts.** The L0 surrogate gives a bonus for more deep engines (line 245: `engine_score = min(0.2, max_deep * 0.02)`), but there's no mechanism for engines to *critique each other*, *merge*, or *backtrack*. This is a crude Self-Consistency without the vote.

2. **No Reflexion loop in the L2 evaluation.** If the L2 call gives a wrong answer, the system records it as a failure and moves on. There's no "retry with reflection" step that could turn a wrong answer into a right one.

3. **No ReAct-style tool grounding.** The math task (17*23) could be solved with a calculator tool; the logic task could be checked with a small Z3/prover. Currently all reasoning happens in-LLM, with no external verification beyond substring match.

4. **`multi_model_router` fails over but doesn't combine.** When the primary model fails, the router tries the next model. But it never tries *both* and votes, or asks one to critique the other. This is single-model failover, not ensemble reasoning.

5. **No state evaluation in the L2 loop.** ToT requires a state evaluator ("is this partial reasoning promising?"). MetaEngine's L2 only scores the final answer.

**Recommendations:**

- **R3.1 (multi_model_router.py):** Add an **ensemble mode** (in addition to failover). When `ensemble=True`, route the same prompt to all healthy backends, return all responses. Caller can then do majority vote or LLM-as-judge selection. *(Medium effort. Constitution: doesn't modify outputs, just observes multiple.)*
- **R3.2 (tiered_fitness.py):** Add an **optional Reflexion retry**. If the L2 call produces a wrong answer (correctness=False), and the budget allows, do a second L2 call with a reflection prompt: "Your previous answer was X. Critique your reasoning, then produce a new answer." Score is the *max* of original + retried. This is the Shinn 2023 mechanism. Cap retries at 1 to bound cost. *(Medium effort.)*
- **R3.3 (tiered_fitness.py):** Add **ReAct-style tool verification** for the math task. When the L2 task is "compute 17*23," additionally call `eval("17*23")` in Python and check whether the LLM's answer matches. This is the AlphaCodium/rStar-Math grounding mechanism. For logic tasks, a tiny Z3 / syllogism checker could serve. *(Medium effort. Adds a tool layer but very high quality signal — execution is ground truth.)*
- **R3.4 (new module or tiered_fitness.py extension):** Implement a **lightweight Tree of Thoughts** for the L2 evaluation specifically. Branching=2, depth=2 → 4 total LLM calls per L2 evaluation. Use the LLM-as-judge to score intermediate states. This is expensive (4× L2 cost) so make it opt-in via a `tot_mode=True` flag. *(High effort. Skip if L2 budget is the bottleneck.)*
- **R3.5 (real_recursive.py):** Use **Self-Discover** in the amplify step. Currently amplify applies 7 fixed rules. With Self-Discover, the model would (1) inspect the gen_metrics, (2) propose a *task-specific* reasoning structure ("for this generation, focus on exploration + temperature because metrics suggest stagnation"), (3) apply only the relevant rules. This is what Self-Discover does for individual questions — adapt it to the meta-level. *(High effort, +1 LLM call per generation.)*

---

## 4. Constitutional AI / self-correction

### Key papers & core mechanisms

**Constitutional AI (Bai et al., 2022, Anthropic; arXiv:2212.08073).** Two-phase recipe:
1. **Supervised (SL):** Model generates a response, critiques it against a list of *principles* ("is this helpful? is this harmless?"), revises. The revised response becomes the SL training target.
2. **RL (RLAIF):** Model generates pairs of responses, picks which is better *using the same principles as the critique prompt*, trains a preference model on these pairs, then RLs against it.

The principles are a fixed anchor — analogous to MetaEngine's K0 constitution. The innovation is that **the model itself generates the critique** based on the principles, not a human.

**Self-Refine (Madaan et al., 2023, NeurIPS; arXiv:2303.17651).** No training required. The same model: generates → critiques (with a feedback prompt) → refines (with the feedback as context). Iterate up to K times. Works best when feedback is actionable ("step 3 is wrong because..."). Fails when feedback is vague ("this could be better").

**Huang et al. 2023 — "Large Language Models Cannot Self-Correct Reasoning Yet" (arXiv:2310.01798, EMNLP findings).** Critical empirical finding: *intrinsic* self-correction (no external verifier, same model checks itself) **often degrades** performance on reasoning tasks. The model is over-confident in its own wrong answers, and self-critique amplifies the error. The fix: either (a) external verifier (CRITIC, rStar-Math), (b) ground-truth signal (AlphaCodium tests), or (c) test-time scaling with very strong models.

**CRITIC (Gou et al., 2024, ICLR; arXiv:2305.11738).** Self-correction loop augmented with *tools*: model generates → tools (search, code execution, fact-checker) critique → model revises. Tools act as the external ground truth. Crucially, this works for self-correction where intrinsic self-critique fails.

### Application to MetaEngine — `tiered_fitness.py`, `amplify_distill.py`, `event_publisher.py`

**Weak spots in current implementation:**

1. **L1 "constitution check" is a static range validator (lines 279–307 of `tiered_fitness.py`), not a model-driven constitutional critique.** The name `L1_CONSTITUTION` is misleading — Bai et al. would call this a *validator*. The actual Constitutional AI innovation (model generates the critique against principles) is not implemented.

2. **No self-refine loop.** When L2 returns a wrong answer, the system records the failure (and now, with the L2-fallback fix, falls back to L0). There's no retry with a self-critique prompt.

3. **Huang 2023 warning applies directly:** MetaEngine's L2 evaluation is intrinsic — same model checks itself. Without an external verifier (ReAct tools, test execution, separate judge model), self-correction will likely degrade. The L2 fallback count (`l2_fallback_count`) is a symptom: when L2 fails, the system gives up rather than retries with critique.

4. **The K0 constitution is a fixed anchor (good — matches Bai 2022 design), but it's never *invoked* in the L1 check.** The constitution's content (no truth promotion, no code modification, bounded RSI) isn't passed to a model for critique — it's encoded as range checks on theta. This loses the *principle-based reasoning* that's the actual innovation.

5. **No tool-augmented critique.** CRITIC's lesson: tools ground self-correction. MetaEngine has no tool layer for the L1/L2 evaluations.

**Recommendations:**

- **R4.1 (tiered_fitness.py):** Implement a **true L1 constitutional critique** as an optional alternative to the range-check L1. Prompt: "Here is a configuration theta. The K0 constitution requires: (1) no truth promotion, (2) no code modification, (3) bounded RSI. Does this theta respect all three principles? Reply with 'yes' or 'no' and a one-sentence reason." Score = 1.0 if yes, 0.5 if no with reason, 0.0 if no without reason. *(Medium effort, +1 LLM call when L1 fires. Boundary: the model's verdict is *scored*, not *binding* — truth_effect=NONE preserved.)*
- **R4.2 (tiered_fitness.py):** Add a **self-refine retry** for the L2 evaluation. If the L2 answer is incorrect AND the budget allows (this counts against L2 budget), do a second L2 call: "Your previous answer was X. The K0 constitution requires honest reasoning. Critique your previous reasoning, then produce a new answer." Score is the max of the two. Cap at 1 retry. This is the Madaan 2023 Self-Refine pattern, bounded by the Huang 2023 caveat (external check is still substring correctness). *(Medium effort.)*
- **R4.3 (tiered_fitness.py):** Add a **CRITIC-style external verifier** for at least the math task. The verifier is a deterministic function (`int(17*23) == 391`), not an LLM. This breaks the "intrinsic self-correction" failure mode by grounding. Publish `fitness.critic_verified` event. *(Low effort, very high impact.)*
- **R4.4 (event_publisher.py):** When the L1 constitutional critique (R4.1) returns "no" with a reason, publish a `constitution.critique_failed` event with the reason. This makes constitutional violations observable in real time, which is currently impossible (the L1 range check fails silently). *(Low effort.)*
- **R4.5 (amplify_distill.py):** Add a **constitutional audit** to the distill step. After extracting insights, prompt the model: "Here are the proposed insights. Which (if any) would constitute truth promotion, code modification, or unbounded RSI?" If any insight is flagged, it is logged but not promoted. This matches the Constitutional AI SL-phase pattern where principles act as a filter. *(Medium effort, +1 LLM call per distill.)*

---

## 5. Surrogate model accuracy

### Key papers & core mechanisms

**Surrogate-Assisted Optimization (Jin, 2011, IEEE EC survey; many follow-ups).** Three core techniques:
1. **Active learning for candidate selection** — don't evaluate the highest-scoring candidates, evaluate the *most uncertain* ones (the surrogate learns the most).
2. **Ensemble surrogates** — train K surrogates with different initializations / bootstraps; disagreement = uncertainty.
3. **Model management** — cheap surrogate pre-screens, expensive oracle verifies the survivors. (This is exactly MetaEngine's L0/L1/L2 architecture.)

**Bayesian Optimization (BO) with Gaussian Processes or ensembles** — e.g., BOHB (Falkner et al., 2018, ICML), Fabolas (Klein et al., 2017). Use posterior variance (GP) or ensemble disagreement as the *acquisition signal*. Standard acquisition functions:
- **UCB (Upper Confidence Bound):** `acq(x) = mean(x) + β · std(x)`. Trade-off via β.
- **EI (Expected Improvement):** `acq(x) = E[max(0, f(x) - f_best)]`.
- **PI (Probability of Improvement):** `P(f(x) > f_best)`.

**Online ensemble methods** — Mondrian forests (Lakshminarayanan et al., 2014), streaming gradient boosting (SGB). Handle non-stationary distributions. Critical for MetaEngine because the L0 surrogate must track the *changing* L2 distribution as amplify rules modify theta.

**Streaming linear models with uncertainty** — Bayesian linear regression: maintain a posterior over weights (μ, Σ). Prediction = μᵀx with variance xᵀΣx. Cheap, gives uncertainty. This is the natural upgrade to MetaEngine's current SGD-on-weights.

### Application to MetaEngine — `tiered_fitness.py` (specifically the I5 surrogate)

**Weak spots in current implementation:**

1. **Single linear model, no uncertainty.** `_surrogate_predict_correction` returns a point estimate (line 162–169). Without variance, can't do UCB / EI / active learning.

2. **L2 budget consumed top-down by L0 score (line 448):** `if l1_score >= self.l1_threshold and self._l2_calls_this_gen < self.l2_budget`. The first N candidates with L0 ≥ threshold get L2 evaluation. This is **pure exploitation** — the surrogate never gets to learn about regions of theta space it's uncertain about. Active learning would be: pick candidates with high uncertainty, not just high L0.

3. **Symmetric ±0.3 correction band.** Real residuals are often skewed — L0 might systematically over-estimate high-temperature policies (because the heuristic penalizes high temp) but under-estimate low-temp ones. A symmetric band can't capture this.

4. **Features are only the 4 hyperparameters.** No task descriptors, no historical L2 score, no generation number. The surrogate has no way to learn that "math tasks at temperature 0.8 are systematically mis-predicted."

5. **Rolling window of 100 obs (line 134).** For a 4-feature linear model, this is fine. But if features expand (recommendations below), need to handle non-stationarity more carefully — Mondrian forest or SGB with explicit forgetting.

6. **No validation of surrogate accuracy over time.** `mean_abs_error` is reported in `surrogate_state()` but not used to gate anything. A surrogate with MAE = 0.4 should not be trusted for L1/L2 gating; one with MAE = 0.05 can be.

**Recommendations:**

- **R5.1 (tiered_fitness.py):** Replace the linear surrogate with a **Bayesian linear regression** (BLR). Maintain (μ, Σ) over weights instead of point weights. Prediction: `μᵀx + bias`, variance: `xᵀΣx`. Updates via Kalman-filter rule (online, O(d²) per observation). This gives uncertainty essentially for free, no extra LLM calls. *(Medium effort. Backward-compatible — point estimate is just μ, same as current.)*
- **R5.2 (tiered_fitness.py):** Add an **acquisition-function-based L2 candidate selection**. Currently: top-N by L0 score. New: top-N by `acq(theta) = L0(theta) + β · sqrt(var(theta))` where β is a hyperparameter (start β=1.0). When L2 budget is exhausted, prefer high-uncertainty candidates (UCB). This is the active-learning insight from Jin 2011. *(Medium effort. Big quality lift per L2 call.)*
- **R5.3 (tiered_fitness.py):** Add **surrogate features for task type**. One-hot encode the L2 task (math / logic / reasoning). The surrogate can then learn "L0 overestimates math, underestimates logic." *(Low effort.)*
- **R5.4 (tiered_fitness.py):** **Asymmetric correction bands**. Replace `max(-0.3, min(0.3, correction))` with `max(-lower, min(upper, correction))` where `(lower, upper)` is learned from observation history (e.g., 5th and 95th percentile of observed residuals). *(Low effort.)*
- **R5.5 (tiered_fitness.py):** **Gate L1/L2 thresholds on surrogate MAE**. If `mean_abs_error > 0.2`, raise `l0_threshold` (be more conservative about who passes to L1) and lower `l2_budget` (don't waste L2 calls on a bad surrogate). If MAE < 0.05, lower thresholds (trust the surrogate more). Publish `surrogate.quality_changed` event when the gate changes. *(Low effort. Makes the surrogate's reliability observable.)*
- **R5.6 (tiered_fitness.py):** Maintain an **ensemble of K=3 BLR surrogates** with different priors or different feature subsets. Ensemble disagreement (std across members) is a more robust uncertainty estimate than single-model variance. *(Medium effort. ~3× memory, no extra LLM calls.)*

---

## 6. Memory and cross-run learning

### Key papers & core mechanisms

**Episodic memory + retrieval (RETRO, Borgeaud et al., 2022, DeepMind; arXiv:2112.04426).** Maintain a database of (context, continuation) pairs from past data. At inference, retrieve the K nearest neighbors to the current context, feed them into the model. Massive quality lift without retraining.

**Reflexion's verbal memory (Shinn et al., 2023).** After a failure, the model generates a natural-language "lesson learned" stored in a buffer. On retry, the lessons are prepended to the prompt. Key: the memory is *natural language*, not embeddings — human-readable, auditable.

**Voyager (Wang et al., 2023; arXiv:2305.16291).** Minecraft agent that builds a **skill library** as executable code. New skills are verified by execution (external ground truth), then stored with a natural-language description. On new tasks, retrieve relevant skills by description. Skills compose — enabling increasingly complex behavior.

**Generative Agents (Park et al., 2023, UIST; arXiv:2304.03442).** Memory stream with three operations: (1) **observe** (append events), (2) **retrieve** (recency + importance + relevance), (3) **reflect** (periodically summarize into higher-level insights). The reflection step turns raw episodes into generalizable knowledge.

**Meta-learning (MAML, Finn et al., 2017; Reptile, Nichol et al., 2018).** Learn an initialization that adapts fast to new tasks. Applicable to MetaEngine at the policy level: instead of `initial_policy()` for every PBT run, start from a meta-learned initialization that's good across past tasks.

**Prioritized Experience Replay (PER, Schaul et al., 2015, ICLR).** Weight replay samples by TD-error — surprising samples are replayed more often. Applicable to MetaEngine: weight historical L2 observations by their *surprise* (how wrong the surrogate's prediction was).

### Application to MetaEngine — `amplify_distill.py` (N4 persistence), `real_recursive.py`, `tiered_fitness.py`, `event_publisher.py`

**Weak spots in current implementation:**

1. **`DISTILLATION_HISTORY.json` (N4) is a flat list with no retrieval.** `get_persisted_insights()` returns all insights; there's no "given current theta + metrics, retrieve relevant past insights." The history accumulates but doesn't inform future runs except as raw inspection.

2. **`_load_accumulated_metrics()` only loads aggregate counts** (total_mechanisms, total_observations, evidence_graph_nodes, run_count, faithfulness_mean, transfer_rate). The *content* of past reasoning, past failures, past amplification decisions is not loaded. The system has no episodic memory of what it tried and what worked.

3. **PBT starts from `initial_policy()` every generation** (line 198, 233 of `real_recursive.py`). The champions from previous generations are not carried forward. This is the opposite of meta-learning — each generation is a cold start.

4. **No reflection step.** `distill()` extracts insights but never *summarizes them into higher-level principles*. The history grows linearly; there's no compression into generalizable knowledge (cf. Generative Agents' reflection step).

5. **No prioritized replay.** All surrogate observations are weighted equally (rolling window of 100). High-surprise observations (where the surrogate was very wrong) should be replayed more often.

6. **`event_publisher.py` events are append-only JSONL — no retrieval.** This is fine for the WebSocket push use case, but the events themselves could be a memory source (e.g., "find all `fitness.l2_fallback` events for theta near the current candidate"). Currently they're write-only.

7. **Memory is not separated by trust level.** Observations from successful L2 evaluations should be trusted more than fallback ones. Currently the L2-fallback fix correctly doesn't update the surrogate from fallbacks — but the *events* are still published with the same priority. A retrieval system would need to know which observations to trust.

**Recommendations:**

- **R6.1 (amplify_distill.py):** Add a **retrieval layer** over `DISTILLATION_HISTORY.json`. Index by (a) generation number, (b) amplified_config signature, (c) insights keywords. On `distill()`, before extracting new insights, retrieve the K=3 most similar past distillations (cosine similarity on config or simple key overlap) and surface them in the distill prompt: "Past similar runs produced these insights: ... What's new this run?" This is the Reflexion memory mechanism. *(Medium effort.)*
- **R6.2 (real_recursive.py):** **Carry forward PBT champions** as seeds for the next generation's PBT population. Currently `trainer.initialize(base_policy)` uses `initial_policy()` every generation. Instead, on generation N > 0, initialize 50% of the population from previous generation's champions (with small mutations) and 50% from `initial_policy()` for diversity. This is the meta-learning pattern (warm-start from prior knowledge). *(Low effort. Boundary: champions are *configurations*, not truths. truth_effect=NONE preserved.)*
- **R6.3 (amplify_distill.py):** Add a **reflection step** that runs every K=3 distillations. Prompt: "Here are the last 3 distillations. Summarize the recurring patterns into 1-3 high-level principles (e.g., 'increasing temperature helped on math but hurt on logic')." Store the principles in a separate `REFLECTED_PRINCIPLES.json` file. On subsequent amplify calls, retrieve the most relevant principle and add it to the rationale. This is the Generative Agents reflection pattern. *(Medium effort, +1 LLM call per K distillations. Boundary: principles are *descriptive*, not prescriptive — they're added to the rationale, not used to change config directly.)*
- **R6.4 (tiered_fitness.py):** Add **prioritized surrogate replay**. When `_surrogate_observations` exceeds the rolling window, instead of dropping the oldest, drop the *least surprising* (lowest |error|). Keep high-surprise observations longer — they're the most informative. This is PER. *(Low effort.)*
- **R6.5 (event_publisher.py + new module):** Add an **event index** that allows retrieval of past events by type + payload similarity. Currently `read_events_since(offset)` is the only accessor. Add `find_events(event_type, payload_query)` for retrieving similar past events. This unlocks "show me all past L2 fallbacks for theta near this candidate" — a Voyager-style skill library but for diagnostic events. *(Medium effort.)*
- **R6.6 (amplify_distill.py):** Add a **trust-tagged memory layer**. When persisting distillations, tag each entry with `trust = "high" | "medium" | "low"` based on: high = L2 real LLM succeeded; medium = L1 only; low = L2 fallback. Retrieval (R6.1) should prefer high-trust entries. This addresses the Huang 2023 warning — don't learn from unverified self-observations. *(Low effort.)*

---

## Consolidated recommendations per module

| Module | Rec ID | Recommendation | Effort | Priority | Constitution risk |
|---|---|---|---|---|---|
| `tiered_fitness.py` | R2.1 | Fix L2 scoring formula (wrong+disclaimer=0.7 → 0.3) | Low | P0 | None |
| `tiered_fitness.py` | R2.4 | Expand L2 task bank 3 → 20+ | Low | P0 | None |
| `tiered_fitness.py` | R5.5 | Gate L1/L2 thresholds on surrogate MAE | Low | P1 | None |
| `tiered_fitness.py` | R5.4 | Asymmetric correction bands | Low | P2 | None |
| `tiered_fitness.py` | R5.3 | Add task-type features to surrogate | Low | P2 | None |
| `tiered_fitness.py` | R2.3 | Self-consistency for high-temp L2 | Medium | P1 | None |
| `tiered_fitness.py` | R2.5 | Calibration probe (Brier score) | Medium | P1 | None |
| `tiered_fitness.py` | R2.2 | Process-level L2 (PRM-style step scoring) | Medium | P1 | None |
| `tiered_fitness.py` | R3.2 | Reflexion retry on wrong L2 | Medium | P1 | None |
| `tiered_fitness.py` | R3.3 | ReAct tool verification (math task) | Medium | P0 | Tool = ground truth, not LLM output |
| `tiered_fitness.py` | R4.1 | L1 as model-driven constitutional critique | Medium | P1 | Critique is scored, not binding |
| `tiered_fitness.py` | R4.2 | Self-refine retry | Medium | P2 | None |
| `tiered_fitness.py` | R4.3 | CRITIC-style external verifier | Low | P0 | None |
| `tiered_fitness.py` | R4.4 | Publish `constitution.critique_failed` event | Low | P1 | None |
| `tiered_fitness.py` | R5.1 | Bayesian linear regression surrogate | Medium | P1 | None |
| `tiered_fitness.py` | R5.2 | UCB acquisition for L2 candidate selection | Medium | P0 | None |
| `tiered_fitness.py` | R5.6 | Ensemble of K=3 BLR surrogates | Medium | P2 | None |
| `tiered_fitness.py` | R6.4 | Prioritized surrogate replay (PER) | Low | P2 | None |
| `tiered_fitness.py` | R3.4 | Tree of Thoughts (opt-in) | High | P3 | None |
| `real_recursive.py` | R1.1 | Reject-sampling filter in distill | Medium | P0 | None |
| `real_recursive.py` | R1.2 | Convergence criterion (early stop) | Low | P0 | None |
| `real_recursive.py` | R1.4 | Held-out validation task set | High | P1 | Held-out is observational |
| `real_recursive.py` | R3.5 | Self-Discover in amplify | High | P2 | None |
| `real_recursive.py` | R6.2 | Carry forward PBT champions (warm start) | Low | P1 | Champions are config, not truth |
| `amplify_distill.py` | R1.3 | Per-rule credit assignment | Medium | P1 | None |
| `amplify_distill.py` | R1.5 | Discovered-rule mechanism | High | P2 | New rules are observational only |
| `amplify_distill.py` | R4.5 | Constitutional audit in distill | Medium | P1 | Flagged insights logged not promoted |
| `amplify_distill.py` | R6.1 | Retrieval over distillation history | Medium | P1 | None |
| `amplify_distill.py` | R6.3 | Reflection step (every K=3 distills) | Medium | P2 | Principles are descriptive |
| `amplify_distill.py` | R6.6 | Trust-tagged memory layer | Low | P1 | None |
| `multi_model_router.py` | R3.1 | Ensemble mode (in addition to failover) | Medium | P2 | None |
| `event_publisher.py` | R6.5 | Event index for retrieval | Medium | P2 | None |

---

## Top 6 priority recommendations (highest-leverage first)

If you can only do 6 of the 30 recommendations, do these:

1. **R2.1 (P0, low effort)** — Fix the L2 scoring formula. The current `0.5 + 0.3*correct + 0.2*disclaimer` is structurally wrong: a model that refuses to answer scores higher than a model that gets it right without the disclaimer. This is the cheapest, highest-impact fix.

2. **R3.3 / R4.3 (P0, low effort)** — Add a deterministic external verifier for the math task. `int(17*23) == 391` is ground truth. Breaks the "intrinsic self-correction" failure mode (Huang 2023). Even just this one tool vastly improves signal quality.

3. **R5.2 (P0, medium effort)** — UCB acquisition for L2 candidate selection. The current top-N-by-L0 selection is pure exploitation. With L2 budget as the bottleneck (Phase 68 reported 100% utilization), this is the single biggest efficiency lever — typically 2–3× more signal per L2 call.

4. **R1.1 (P0, medium effort)** — Reject-sampling filter in distill. STaR's core insight: don't learn from low-quality runs. Currently every generation's PBT result is distilled, including failures.

5. **R1.2 (P0, low effort)** — Convergence criterion. `run(num_generations=3)` is unconditional. Should stop when improvement drops below threshold for K=2 consecutive generations. Saves L2 budget, prevents noise-driven "improvement."

6. **R6.2 (P1, low effort)** — Carry forward PBT champions. Each generation starts PBT from `initial_policy()` — a cold start. Warm-starting from previous champions (with mutation) is meta-learning without the LLM overhead, and it's the cheapest way to amplify the flywheel.

---

## Caveats and honest disclosures

1. **Source limitation.** As noted at the top, the `web_search` function returned HTTP 429 (rate-limited) for every query in this session. All citations are from the agent's training knowledge through approximately early 2025. Paper titles, authors, and arXiv IDs are recalled from memory and should be verified before external publication. The *mechanisms* described are robust; the *bibliographic details* may have small errors.

2. **2026 papers.** My knowledge may not include the latest 2025–2026 work. Specifically, post-DeepSeek-R1 (Jan 2025) and post-o3/o4 reasoning-model literature (mid-2025+) may have newer techniques I'm not fully aware of. Key things to verify externally:
   - Latest PRM training techniques (post-rStar-Math).
   - Reasoning model self-improvement loops (o1-style reasoning-trace bootstrapping).
   - Verifier-guided RL (RLVR / VRAG / process-supervised RLHF developments).
   - Memory architectures for reasoning models (post-RETRO and Reflexion).

3. **MetaEngine code references.** All line numbers and code references are based on the source files at `/home/z/my-project/METAENGINE_SLICE3_RESTORED/metaengine/`. I read `tiered_fitness.py` (564 lines), `real_recursive.py` (349 lines), `amplify_distill.py` (643 lines, partial — first ~500 lines and the rule-update block), `multi_model_router.py` (first 100 lines), `event_publisher.py` (188 lines). I did not exhaustively read every module; weak-spot claims are based on what I read and should be re-verified against the full source if implemented.

4. **Constitutional compatibility.** I tried to check every recommendation against the K0 constitution (truth_effect=NONE, no auto-promotion, no code modification, bounded RSI). The "Constitution risk" column in the table captures my best assessment. Two recommendations deserve particular scrutiny:
   - **R1.5 (discovered-rule mechanism)** — adding new rules to `AMPLIFY_RULE_NAMES` is the closest to "promotion." Mitigation: rules are observational, weights bounded [0.1, 3.0], and pruning is allowed but promoting requires external action. Should be reviewed by the constitution's amendment authority (currently NOT_IMPLEMENTED).
   - **R4.1 (L1 as model-driven critique)** — having the model evaluate against K0 principles sounds like it could become binding. Mitigation: the verdict is *scored*, not *binding*; the policy isn't modified by the critique.

5. **Effort estimates are approximate.** "Low / Medium / High" are relative to the existing codebase complexity. Each recommendation needs design + implementation + test, which historically (per worklog) ranges from ~100 LOC (low) to ~400 LOC (high) per fix.

6. **Recommendations are non-exhaustive.** Each section could be expanded into a full literature review. I prioritized the techniques most directly applicable to MetaEngine's existing architecture.

---

## Next actions for the orchestrator

The orchestrator may want to:
1. **Pick a P0 batch** (recommendations R2.1, R3.3/R4.3, R5.2, R1.1, R1.2) — these are the 5 cheapest, highest-impact changes. Estimated 1–2 days of work each.
2. **Verify the bibliographic claims** in the citations section before any external publication. Use web search when rate limit allows.
3. **Read the full source** of `amplify_distill.py` (643 lines) and `multi_model_router.py` (591 lines) before implementing recommendations targeting those modules — I only partially read them.
4. **Run an A/B comparison**: Phase 68 measured +0.0147 improvement over 2 generations. After implementing the P0 batch, re-run the same flywheel and measure delta. The expected impact is roughly 2–3× the improvement rate (driven primarily by R5.2 UCB selection and R1.1 reject-sampling).
5. **Treat R1.5 (discovered rules) and R3.4 (ToT) as research-stage only** — they're high effort and require careful constitution review. Defer until P0/P1 batches land.

---

*End of report.*
