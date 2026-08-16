# Destruktion Studio 0.5 — Engine Integration Validation Report

## Integrated baseline

- Engine: `0.9.0-alpha.1`
- Studio: `0.5.0-engine-integration`
- Frozen required portable assets: **48**
- Frozen-asset fixity after merge: **PASS 48/48**
- Studio is external to the frozen asset set.

## Source archive audit

- 0.9 portable SHA-256: `62e521470bc3a56b2cebb18e4b7904ed297c147f1b5eca7d3ac24440e96ec713`
- 0.9 micro-local regression SHA-256: `bb73118301adfb9a53adc13de13670f4f79b29c78fc43bbe838aaab24a68c906`
- Previous Complete 0.4 SHA-256: `c1d0fe34c698d120530a6f35b1e60d99aeed9e0aa5263f752380a0c69652b3dc`
- Portable/regression overlap: **9/9 byte-identical**
- Regression-only file: `REPLAY.md`

## Automated validation

- Original 0.9 engine suite in offline mode: **PASS 77/77**
- Integrated engine + Studio suite after merge: **PASS 100/100**
- Portable check: **conformant, 0 ERROR / 0 REVIEW / 0 WARNING**
- Studio doctor: **CORE READY** with bundled AJV-compatible fallback
- Declarative gesture grammar: **PASS**
- Declarative GX7 real Geviert refinery run: **PASS**
- GX7 roles emitted: `SOURCE_RESISTANCE`, `REPRESENTATION_FAILURE`, `OPERATOR_DELTA`
- Method mutation emitted: **1**, state `EXPERIMENTAL_CANDIDATE_NOT_CORE`
- Cross-corpus operator-regression Studio alias: **PASS**
- Local operator-competition Studio alias: **PASS**
- Micro-local ecology Studio alias: **PASS**

## Regression discovered during integration

The first real declarative Geviert run exposed four incompatibilities not covered by the earlier unit suite:

1. missing `method_mutation_node_ids` in the declarative constellation schema;
2. missing `FORCES_MUTATION` edge relation;
3. stale declarative layer id (`0.1` vs `0.2`);
4. missing `source_resistance_handled_or_explicitly_absent` openness criterion.

All four were repaired outside the 48 frozen 0.9 assets, and the real refinery case was added as a permanent end-to-end test.

## Promotion firewall

The following remain non-promoting by contract:

- source resistance discovery;
- GX7 method mutation candidate generation;
- cross-corpus regression survival;
- local competition winner/composition;
- micro-local ecology routing.

No result above constitutes CORE promotion, philosophical truth, or external semantic validation.
