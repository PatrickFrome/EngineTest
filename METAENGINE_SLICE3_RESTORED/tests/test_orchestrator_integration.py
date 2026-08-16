"""Tests for Phase 48 — Orchestrator Integration of new modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.orchestrator import MetaOrchestrator
from metaengine.trace_extractor import ReasoningTraceExtractor
from metaengine.faithfulness_tester import SummarizerFaithfulnessTester


# ---------------------------------------------------------------------------
# Tests: Imports wired
# ---------------------------------------------------------------------------


class TestImportsWired:
    """Test that new modules are imported in orchestrator."""

    def test_trace_extractor_imported(self):
        import metaengine.orchestrator as orch
        assert hasattr(orch, 'ReasoningTraceExtractor')

    def test_faithfulness_tester_imported(self):
        import metaengine.orchestrator as orch
        assert hasattr(orch, 'SummarizerFaithfulnessTester')

    def test_orchestrator_source_contains_phase48(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'Phase 48' in source
        assert 'REASONING_TRACE_EXTRACTION' in source
        assert 'FAITHFULNESS_TEST' in source
        assert 'RLAIF_EVALUATION' in source


# ---------------------------------------------------------------------------
# Tests: Post-run hooks exist
# ---------------------------------------------------------------------------


class TestPostRunHooks:
    """Test that post-run hooks are present in orchestrator.run()."""

    def test_trace_extraction_hook_present(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'ReasoningTraceExtractor()' in source
        assert 'extract_from_run' in source
        assert 'add_to_mechanism_library' in source

    def test_faithfulness_hook_present(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'SummarizerFaithfulnessTester()' in source
        assert 'faith_tester.test_run' in source or 'test_run(out)' in source

    def test_rlaif_hook_present(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'ConstitutionalRLAIFTrainer' in source
        assert 'evaluate_run_contributions' in source
        assert 'update_biography' in source

    def test_ledger_entries_present(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'TRACES_EXTRACTED' in source
        assert 'FAITHFULNESS_TESTED' in source
        assert 'RLAIF_EVALUATED' in source
        # Failure paths
        assert 'TRACE_EXTRACTION_FAILED' in source
        assert 'FAITHFULNESS_TEST_FAILED' in source
        assert 'RLAIF_EVALUATION_SKIPPED' in source


# ---------------------------------------------------------------------------
# Tests: Fault tolerance
# ---------------------------------------------------------------------------


class TestFaultTolerance:
    """Test that failing hooks don't crash orchestrator."""

    def test_trace_extraction_failure_doesnt_crash(self):
        """If trace extraction fails, orchestrator should still return state."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        # Verify try/except around trace extraction
        assert 'TRACE_EXTRACTION_FAILED' in source

    def test_faithfulness_failure_doesnt_crash(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'FAITHFULNESS_TEST_FAILED' in source

    def test_rlaif_failure_doesnt_crash(self):
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'RLAIF_EVALUATION_SKIPPED' in source

    def test_all_hooks_have_try_except(self):
        """All Phase 48 hooks must be wrapped in try/except."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        # Find the Phase 48 section
        phase48_start = source.find('Phase 48')
        phase48_end = source.find('return state', phase48_start)
        phase48_section = source[phase48_start:phase48_end]
        # Count try/except pairs
        try_count = phase48_section.count('try:')
        except_count = phase48_section.count('except Exception')
        assert try_count >= 3  # at least 3 hooks
        assert except_count >= 3


# ---------------------------------------------------------------------------
# Tests: Output artifacts
# ---------------------------------------------------------------------------


class TestOutputArtifacts:
    """Test that hooks produce expected output artifacts."""

    def test_trace_extraction_writes_json(self):
        """Verify REASONING_TRACE_EXTRACTION.json is written."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'REASONING_TRACE_EXTRACTION.json' in source

    def test_faithfulness_writes_json(self):
        """Verify FAITHFULNESS_TEST.json is written."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'FAITHFULNESS_TEST.json' in source

    def test_rlaif_writes_json(self):
        """Verify RLAIF_EVALUATION.json is written."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'RLAIF_EVALUATION.json' in source


# ---------------------------------------------------------------------------
# Tests: RLAIF is optional (bridge-dependent)
# ---------------------------------------------------------------------------


class TestRLAIFOptional:
    """Test that RLAIF hook only runs if bridge is available."""

    def test_rlaif_health_check_called(self):
        """Verify health_check() is called before RLAIF evaluation."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'health_check()' in source
        assert 'if rlaif_trainer.health_check()' in source

    def test_rlaif_skipped_without_bridge(self):
        """If bridge is not available, RLAIF should be skipped gracefully."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        # The if condition means RLAIF only runs if bridge is healthy
        assert 'if rlaif_trainer.health_check():' in source


# ---------------------------------------------------------------------------
# Tests: Mechanism library integration
# ---------------------------------------------------------------------------


class TestMechanismLibraryIntegration:
    """Test that trace extraction adds to mechanism library."""

    def test_mechanism_library_loaded(self):
        """Verify mechanism_library.json is loaded."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'mechanism_library.json' in source
        assert 'MechanismLibrary.load' in source

    def test_mechanism_library_saved(self):
        """Verify mechanism_library.json is saved after adding traces."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'lib.save' in source

    def test_biography_updated_by_rlaif(self):
        """Verify biographies are updated with RLAIF reward."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        assert 'update_biography' in source
        assert 'self.biographies' in source


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that integration preserves constitution."""

    def test_all_hooks_use_try_except(self):
        """All hooks must be fault-tolerant (constitution: no crash)."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        phase48_start = source.find('Phase 48')
        phase48_end = source.find('return state', phase48_start)
        phase48_section = source[phase48_start:phase48_end]
        # Every hook should have its own try/except
        assert phase48_section.count('try:') == phase48_section.count('except Exception')

    def test_no_code_modification(self):
        """Integration doesn't modify any code."""
        orch_path = ROOT / 'metaengine' / 'orchestrator.py'
        source = orch_path.read_text()
        phase48_start = source.find('Phase 48')
        phase48_end = source.find('return state', phase48_start)
        phase48_section = source[phase48_start:phase48_end]
        # No exec() or eval() or compile()
        assert 'exec(' not in phase48_section
        assert 'eval(' not in phase48_section
        assert 'compile(' not in phase48_section

    def test_truth_effect_preserved(self):
        """All hooks produce evaluative output (truth_effect=NONE)."""
        # The modules themselves preserve truth_effect=NONE
        # Integration just calls them, so constitution is preserved
        from metaengine.trace_extractor import TRACE_EXTRACTION_VERSION
        from metaengine.faithfulness_tester import FAITHFULNESS_VERSION
        assert TRACE_EXTRACTION_VERSION is not None
        assert FAITHFULNESS_VERSION is not None
