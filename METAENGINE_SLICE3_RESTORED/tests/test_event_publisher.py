"""Fix 2: Tests for event_publisher.py — previously had NO tests."""
from __future__ import annotations
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.event_publisher import (
    publish_event, read_events_since, get_event_count,
    reset_event_log, publisher_state, EVENT_PUBLISHER_VERSION,
)


class TestEventPublisher:
    def setup_method(self):
        reset_event_log()

    def teardown_method(self):
        reset_event_log()

    def test_publish_returns_hash(self):
        h = publish_event("test.event", {"key": "value"})
        assert h is not None
        assert len(h) == 64

    def test_event_has_truth_effect_none(self):
        publish_event("test.event", {"x": 1})
        events, _ = read_events_since(0)
        assert events[0]["truth_effect"] == "NONE"

    def test_read_events_since_offset(self):
        for i in range(5):
            publish_event("test.event", {"index": i})
        events, offset = read_events_since(0)
        assert len(events) == 5

    def test_get_event_count(self):
        assert get_event_count() == 0
        publish_event("a", {})
        publish_event("b", {})
        assert get_event_count() == 2

    def test_reset_event_log(self):
        publish_event("test", {})
        assert get_event_count() == 1
        reset_event_log()
        assert get_event_count() == 0

    def test_publisher_state(self):
        publish_event("test", {"x": 1})
        state = publisher_state()
        assert state["event_count"] == 1
        assert state["truth_effect"] == "NONE"

    def test_publish_failure_non_fatal(self):
        h = publish_event("test.event", {"unserializable": object()})
        assert h is None or isinstance(h, str)
