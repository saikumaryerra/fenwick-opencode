"""Tests for engine/incident_matcher.py — F-08, live incident detection."""

import pytest
from engine.incident_matcher import (
    find_matching_incidents,
    is_live,
    has_non_boilerplate_updates,
    normalize_service_simple,
)


def _make_incident(
    inc_id,
    service_raw,
    status="open",
    updates=None,
    severity="SEV2",
    summary="Test incident",
):
    if updates is None:
        updates = []
    return {
        "incident_id": inc_id,
        "service_name_raw": service_raw,
        "service_normalized": normalize_service_simple(service_raw),
        "status": status,
        "severity": severity,
        "one_line_summary": summary,
        "date": "2026-09-07",
        "updates_parsed": updates,
    }


def _make_update(note, emp_id="FEN-1001"):
    return {"note": note, "emp_id": emp_id, "timestamp_raw": "2026-09-07T14:00:00"}


class TestIsLive:
    """Live incident detection — open + ≥1 non-boilerplate update."""

    def test_open_with_non_boilerplate_is_live(self):
        inc = _make_incident(
            "INC-002115", "checkout-service",
            updates=[_make_update("Checkout latency climbing, investigating")],
        )
        assert is_live(inc) is True

    def test_open_with_only_boilerplate_not_live(self):
        inc = _make_incident(
            "INC-009012", "primary-db",
            updates=[_make_update("Investigating, no update yet")],
        )
        assert is_live(inc) is False

    def test_open_with_no_updates_not_live(self):
        inc = _make_incident("INC-009012", "primary-db", updates=[])
        assert is_live(inc) is False

    def test_resolved_not_live(self):
        inc = _make_incident("INC-009000", "payments-api", status="resolved")
        assert is_live(inc) is False


class TestHasNonBoilerplateUpdates:
    """Edge cases for boilerplate detection."""

    def test_boilerplate_only(self):
        updates = [
            _make_update("Investigating, no update yet"),
            _make_update("Investigating, no update yet"),
        ]
        assert has_non_boilerplate_updates(updates) is False

    def test_mixed_updates(self):
        updates = [
            _make_update("Investigating, no update yet"),
            _make_update("Found the root cause, working on fix"),
        ]
        assert has_non_boilerplate_updates(updates) is True

    def test_all_substantive(self):
        updates = [
            _make_update("Checkout latency climbing since ~14:20, investigating"),
            _make_update("Correlated with downstream dependency slowdown"),
        ]
        assert has_non_boilerplate_updates(updates) is True

    def test_empty_updates(self):
        assert has_non_boilerplate_updates([]) is False

    def test_case_insensitive_boilerplate(self):
        updates = [_make_update("INVESTIGATING, NO UPDATE YET")]
        assert has_non_boilerplate_updates(updates) is False


class TestFindMatchingIncidents:
    """Matching tickets to open/live incidents."""

    def test_match_live_incident_by_service(self):
        incidents = [
            _make_incident(
                "INC-002115", "checkout-service",
                updates=[_make_update("Latency climbing, investigating")],
            ),
        ]
        matches = find_matching_incidents(
            "checkout latency spiking", ["checkout-service"], incidents
        )
        assert len(matches) == 1
        assert matches[0]["incident_id"] == "INC-002115"
        assert matches[0]["is_live"] is True

    def test_no_match_for_unrelated_service(self):
        incidents = [
            _make_incident(
                "INC-002115", "checkout-service",
                updates=[_make_update("Latency climbing")],
            ),
        ]
        matches = find_matching_incidents(
            "billing-worker is slow", ["billing-worker"], incidents
        )
        assert len(matches) == 0

    def test_resolved_incidents_not_matched(self):
        incidents = [
            _make_incident("INC-009000", "payments-api", status="resolved"),
        ]
        matches = find_matching_incidents(
            "payments-api error", ["payments-api"], incidents
        )
        assert len(matches) == 0

    def test_no_incidents_returns_empty(self):
        matches = find_matching_incidents("checkout slow", ["checkout-service"], [])
        assert matches == []


class TestIncidentIDFormats:
    """F-08: Both INC-NNNN and INC-NNNNNN are valid."""

    def test_four_digit_id(self):
        inc = _make_incident(
            "INC-2115", "checkout-service",
            updates=[_make_update("Non-boilerplate update")],
        )
        assert is_live(inc) is True
        assert inc["incident_id"] == "INC-2115"

    def test_six_digit_id(self):
        inc = _make_incident(
            "INC-002115", "checkout-service",
            updates=[_make_update("Non-boilerplate update")],
        )
        assert is_live(inc) is True

    def test_service_name_variants_normalized(self):
        """F-02: Service name variants are normalized."""
        inc1 = _make_incident("INC-001", "auth_gateway",
                              updates=[_make_update("Real update")])
        inc2 = _make_incident("INC-002", "auth-gateway",
                              updates=[_make_update("Real update")])
        assert inc1["service_normalized"] == "auth-gateway"
        assert inc2["service_normalized"] == "auth-gateway"