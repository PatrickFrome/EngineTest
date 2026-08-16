import json, pathlib
from metaengine.orchestrator import MetaOrchestrator

def test_config_has_16_engines():
    root=pathlib.Path(__file__).resolve().parents[1]; c=json.loads((root/'config/meta_engine.json').read_text()); assert len(c['engines'])==16; assert [e['ordinal'] for e in c['engines']]==list(range(1,17))

def test_every_engine_has_source_hash():
    root=pathlib.Path(__file__).resolve().parents[1]; c=json.loads((root/'config/meta_engine.json').read_text()); assert all(len(e['source_archive_sha256'])==64 for e in c['engines'])

def test_no_majority_truth_invariant():
    root=pathlib.Path(__file__).resolve().parents[1]; c=json.loads((root/'config/meta_engine.json').read_text()); assert c['invariants']['majority_is_not_truth'] is True
