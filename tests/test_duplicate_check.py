"""Tests for engine/duplicate_check.py — duplicate detection within 2h."""

import pytest
from datetime import datetime, timezone, timedelta
from engine.duplicate_check import check_duplicate, recent_same


def _make_ticket(ticket_id, text, filed_at, related_incident=""):
    return {
        "ticket_id": ticket_id,
        "text": text,
        "filed_at": filed_at,
        "related_incident_id": related_incident,
    }


_NOW = datetime(2026, 9, 7, 15, 0, 0, tzinfo=timezone.utc)


class TestDuplicateCheck:
    """Duplicate detection: same service + same symptoms within 2h."""

    def test_duplicate_detected_within_window(self):
        """Same service + same symptoms within 2h → duplicate."""
        existing = [
            _make_ticket("TCK-0101", "checkout-service latency spiking again since about 14:20", "2026-09-07T14:31:00"),
        ]
        result = check_duplicate(
            "checkout-service latency is slow and spiking right now",
            ["checkout-service"],
            existing,
            now=_NOW,
        )
        assert result is not None
        assert result["ticket_id"] == "TCK-0101"

    def test_no_duplicate_outside_window(self):
        """Same service + same symptoms but > 2h ago → no duplicate."""
        old_time = _NOW - timedelta(hours=3)
        existing = [
            _make_ticket("TCK-0101", "checkout latency spiking", old_time.isoformat()),
        ]
        result = check_duplicate(
            "checkout-service is slow",
            ["checkout-service"],
            existing,
            now=_NOW,
        )
        assert result is None

    def test_no_duplicate_different_service(self):
        """Different service → no duplicate."""
        existing = [
            _make_ticket("TCK-0101", "payments-api error", "2026-09-07T14:00:00"),
        ]
        result = check_duplicate(
            "checkout-service is slow",
            ["checkout-service"],
            existing,
            now=_NOW,
        )
        assert result is None

    def test_no_duplicate_different_symptoms(self):
        """Same service but different symptoms → no duplicate."""
        existing = [
            _make_ticket("TCK-0102", "customers reporting checkout-service errors", "2026-09-07T10:05:00"),
        ]
        result = check_duplicate(
            "checkout latency spiking since 14:20",
            ["checkout-service"],
            existing,
            now=_NOW,
        )
        # TCK-0102 mentions "errors" not "latency" — different symptom cluster
        assert result is None

    def test_no_duplicate_when_no_service(self):
        """No service names → no duplicate."""
        result = check_duplicate("what time is it", [], [], now=_NOW)
        assert result is None

    def test_tck_0102_not_duplicate_of_latency(self):
        """TCK-0102 (errors/checkout) is routed, not duplicate of latency incident.
        
        This tests the hand-off queue rule: tickets with no linked incident 
        are routed, not duplicate. TCK-0102 has different symptoms from 
        the latency ticket TCK-0101.
        """
        existing = [
            _make_ticket("TCK-0101", "checkout latency spiking again since about 14:20", "2026-09-07T14:31:00"),
        ]
        result = check_duplicate(
            "customers reporting checkout-service errors intermittently today, seems unrelated to the general slowness people mentioned",
            ["checkout-service"],
            existing,
            now=_NOW,
        )
        # Different symptom cluster (errors vs latency) → not duplicate
        assert result is None


class TestDuplicateCheckEmptyData:
    """Edge cases with empty inputs."""

    def test_empty_open_tickets(self):
        result = check_duplicate("checkout slow", ["checkout-service"], [], now=_NOW)
        assert result is None

    def test_empty_text(self):
        existing = [_make_ticket("TCK-0101", "latency", "2026-09-07T14:00:00")]
        result = check_duplicate("", ["checkout-service"], existing, now=_NOW)
        assert result is None