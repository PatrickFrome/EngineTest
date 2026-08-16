# MetaEngine Benchmark Analysis — 2026-08-16T05:53:11Z

**Total results aggregated**: 30

## Per-category summary

| Category | Total | Pass | Fail | Crash | Pass% | Avg Fit | Det | Depth | Rivals | Subl | RT(s) |
|----------|------:|----:|----:|------:|------:|--------:|----:|------:|-------:|-----:|------:|
| ARITHMETIC | 15 | 3 | 12 | 0 | 20.0% | 0.545 | 0.191 | 1.000 | 105 | 30 | 51.1 |
| LOGIC | 12 | 5 | 7 | 0 | 41.7% | 0.564 | 0.228 | 1.000 | 80 | 24 | 52.9 |
| REASONING | 3 | 0 | 3 | 0 | 0.0% | 0.525 | 0.150 | 1.000 | 21 | 6 | 52.6 |

## Improvement patches generated: 3

### 1. [ROUTING_HINT] Route numeric tasks to dedicated solver
**Target**: `metaengine/learned_router.py`  
**Confidence**: 70%  
**Rationale**: ARITHMETIC tasks have pass_rate=20.00% (3/15). MetaEngine is dialectical, not arithmetic — routing numeric tasks to a dedicated solver should improve pass_rate.  
**Patch content**:
```json
{
  "rule_name": "ROUTE_NUMERIC_TASKS_TO_DEDICATED_SOLVER",
  "trigger_keywords": [
    "multiplied by",
    "factorial",
    "square root",
    "GCD",
    "LCM",
    "remainder"
  ],
  "action": "route_to_engine_05_or_external_calculator",
  "applies_to_categories": [
    "ARITHMETIC"
  ],
  "expected_improvement": "ARITHMETIC pass_rate from 20.00% to 0.7"
}
```

### 2. [AMPLIFY_RULE] Increase deep engines for LOGIC tasks
**Target**: `metaengine/dspy_amplify.py`  
**Confidence**: 50%  
**Rationale**: LOGIC pass_rate=41.67%. Increasing deep engine count may surface more relevant perspectives.  
**Patch content**:
```json
{
  "rule_name": "INCREASE_DEEP_ENGINES_FOR_LOGIC",
  "action": "max_deep_engines += 1",
  "applies_to_categories": [
    "LOGIC"
  ],
  "expected_improvement": "LOGIC pass_rate from 41.67% to 0.6"
}
```

### 3. [AMPLIFY_RULE] Increase deep engines for REASONING tasks
**Target**: `metaengine/dspy_amplify.py`  
**Confidence**: 50%  
**Rationale**: REASONING pass_rate=0.00%. Increasing deep engine count may surface more relevant perspectives.  
**Patch content**:
```json
{
  "rule_name": "INCREASE_DEEP_ENGINES_FOR_REASONING",
  "action": "max_deep_engines += 1",
  "applies_to_categories": [
    "REASONING"
  ],
  "expected_improvement": "REASONING pass_rate from 0.00% to 0.6"
}
```
