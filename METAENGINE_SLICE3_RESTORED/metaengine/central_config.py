"""Fix 9: Central configuration for MetaEngine magic constants.

Previously: ~80 magic constants scattered across 20+ modules.
Now: all tunable parameters in one place. Modules import from here.

This file does NOT contain secrets, keys, or constitution data.
It contains ONLY tunable hyperparameters and thresholds.

Constitution: truth_effect=NONE. These are configuration values, not truth.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# LLM Bridge defaults
# ---------------------------------------------------------------------------

LLM_BRIDGE_ENDPOINT = "http://localhost:3031"
LLM_BRIDGE_MODEL = "metaengine-glm-1"
LLM_BRIDGE_MAX_TOKENS = 512
LLM_BRIDGE_TEMPERATURE = 0.4
LLM_BRIDGE_TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# Tiered Fitness defaults (tiered_fitness.py)
# ---------------------------------------------------------------------------

TIERED_L2_BUDGET = 3
TIERED_L0_THRESHOLD = 0.3
TIERED_L1_THRESHOLD = 0.5
TIERED_CACHE_SIZE = 50
TIERED_SURROGATE_LEARNING_RATE = 0.1
TIERED_SURROGATE_MAX_OBSERVATIONS = 100
TIERED_UCB_EXPLORATION = 0.3
TIERED_L2_BLEND_WEIGHT = 0.7  # L2 weight in blend (was 0.5, now 0.7)


# ---------------------------------------------------------------------------
# Amplify/Distill defaults (amplify_distill.py)
# ---------------------------------------------------------------------------

AMPLIFY_IMPROVEMENT_THRESHOLD = 0.01
AMPLIFY_MAX_CONFIG_CHANGE = 0.3
AMPLIFY_RULE_LEARNING_RATE = 0.1
AMPLIFY_RLAIF_LOW_THRESHOLD = 0.4
AMPLIFY_PBT_FITNESS_PLATEAU = 0.7
AMPLIFY_FAITHFULNESS_LOW = 0.5
AMPLIFY_MARL_FOE_LOW = 0.05
AMPLIFY_TRANSFER_LOW = 0.3


# ---------------------------------------------------------------------------
# PBT defaults (pbt_trainer.py)
# ---------------------------------------------------------------------------

PBT_POPULATION_SIZE = 8
PBT_EXPLOIT_FRACTION = 0.25
PBT_PERTURBATION_FACTOR_LOW = 0.8
PBT_PERTURBATION_FACTOR_HIGH = 1.2


# ---------------------------------------------------------------------------
# ES defaults (es_optimizer.py)
# ---------------------------------------------------------------------------

ES_POPULATION_SIZE = 8
ES_INITIAL_SIGMA = 0.3
ES_INITIAL_ALPHA = 0.1
ES_SIGMA_DECAY = 0.95
ES_ALPHA_DECAY = 0.97
ES_MIN_SIGMA = 0.01
ES_MIN_ALPHA = 0.001


# ---------------------------------------------------------------------------
# RLAIF defaults (rlaif_trainer.py)
# ---------------------------------------------------------------------------

RLAIF_TEMPERATURE = 0.2
RLAIF_WEIGHT_PROVENANCE = 0.15
RLAIF_WEIGHT_NO_TRUTH = 0.15
RLAIF_WEIGHT_COHERENCE = 0.15
RLAIF_WEIGHT_NOVELTY = 0.15
RLAIF_WEIGHT_GROUNDING = 0.15
RLAIF_WEIGHT_SAFETY = 0.25


# ---------------------------------------------------------------------------
# RedTeam defaults (redteam_adversary.py)
# ---------------------------------------------------------------------------

REDTEAM_TEMPERATURE = 0.8
REDTEAM_MAX_TOKENS = 256
REDTEAM_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# LLM Judge defaults (llm_judge.py)
# ---------------------------------------------------------------------------

LLM_JUDGE_TEMPERATURE = 0.2
LLM_JUDGE_MAX_TOKENS = 512


# ---------------------------------------------------------------------------
# Faithfulness defaults (faithfulness_tester.py)
# ---------------------------------------------------------------------------

FAITHFULNESS_HIGH_THRESHOLD = 0.75
FAITHFULNESS_LOW_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Real Recursive defaults (real_recursive.py)
# ---------------------------------------------------------------------------

RECURSIVE_CONVERGENCE_THRESHOLD = 0.005
RECURSIVE_CONVERGENCE_PATIENCE = 2
RECURSIVE_REGRESSION_THRESHOLD = 0.005
RECURSIVE_L2_BUDGET = 3
RECURSIVE_NUM_PBT_GENERATIONS = 2
RECURSIVE_PBT_POPULATION_SIZE = 4


# ---------------------------------------------------------------------------
# API Server defaults (api_server.py)
# ---------------------------------------------------------------------------

API_RATE_LIMIT_WINDOW_SECONDS = 60.0
API_RATE_LIMIT_BURST = 1
API_DEFAULT_PORT = 8080


# ---------------------------------------------------------------------------
# Multi-Model Router defaults (multi_model_router.py)
# ---------------------------------------------------------------------------

ROUTER_COOLDOWN_SECONDS = 60.0
ROUTER_MAX_FAILURES = 3
ROUTER_HEALTH_CHECK_INTERVAL = 30.0
ROUTER_SIMPLE_PROMPT_MAX_CHARS = 200
ROUTER_SIMPLE_MAX_TOKENS = 128


# ---------------------------------------------------------------------------
# Epistemic Gain defaults (epistemic_gain.py)
# ---------------------------------------------------------------------------

EPISTEMIC_ENGINE_COSTS = {
    "engine_01": 1.0, "engine_02": 1.0, "engine_03": 1.0, "engine_04": 1.0,
    "engine_05": 0.5, "engine_06": 0.5, "engine_07": 0.5, "engine_08": 0.5,
    "engine_09": 0.8, "engine_10": 0.8, "engine_11": 0.6, "engine_12": 0.6,
    "engine_13": 0.7, "engine_14": 0.7, "engine_15": 0.9, "engine_16": 0.9,
}

EPISTEMIC_WEIGHTS = {
    "provenance": 0.15,
    "no_truth": 0.15,
    "coherence": 0.20,
    "novelty": 0.20,
    "grounding": 0.15,
    "safety": 0.15,
}
