"""Tests for engine/routing.py — F-05, F-07."""

import pytest
from engine.routing import get_oncall, resolve_routing


# Simplified data for tests
_ROSTER = [
    {"emp_id": "FEN-1001", "name": "Priya Nathan", "team": "Payments", "title": "Senior Software Engineer"},
    {"emp_id": "FEN-1003", "name": "Marisol Feng", "team": "Payments", "title": "Software Engineer"},
    {"emp_id": "FEN-1005", "name": "Tomas Ilic", "team": "Billing", "title": "Software Engineer"},
    {"emp_id": "FEN-1007", "name": "Callum Osei", "team": "Platform", "title": "Staff Software Engineer"},
    {"emp_id": "FEN-1009", "name": "Femi Adaransi", "team": "Platform", "title": "Software Engineer"},
    {"emp_id": "FEN-1012", "name": "Beatrix Solano", "team": "SRE", "title": "Senior SRE"},
    {"emp_id": "FEN-1013", "name": "Ravi Deshpande", "team": "SRE", "title": "SRE"},
    {"emp_id": "FEN-1014", "name": "Wren Castellano", "team": "SRE", "title": "SRE"},
]

_SERVICES = [
    {"service_name": "payments-api", "service_name_normalized": "payments-api", "owning_team": "Payments", "status": "active"},
    {"service_name": "billing-worker", "service_name_normalized": "billing-worker", "owning_team": "Billing", "status": "active"},
    {"service_name": "checkout-service", "service_name_normalized": "checkout-service", "owning_team": "Payments", "status": "active"},
    {"service_name": "auth-gateway", "service_name_normalized": "auth-gateway", "owning_team": "Platform", "status": "active"},
    {"service_name": "edge-gateway", "service_name_normalized": "edge-gateway", "owning_team": "Platform", "status": "active"},
    {"service_name": "notifications-worker", "service_name_normalized": "notifications-worker", "owning_team": "Platform", "status": "deprecated"},
    {"service_name": "primary-db", "service_name_normalized": "primary-db", "owning_team": "Platform", "status": "active"},
]

_ONCALL = [
    {"service_name_raw": "payments-api", "engineer_emp_id": "FEN-1001", "currently_active": "true", "rotation_note": "Week 36 primary"},
    {"service_name_raw": "Payments-API", "engineer_emp_id": "FEN-1003", "currently_active": "false", "rotation_note": "Week 35 primary"},
    {"service_name_raw": "billing-worker", "engineer_emp_id": "FEN-1005", "currently_active": "true", "rotation_note": "Week 36 primary"},
    {"service_name_raw": "primary-db", "engineer_emp_id": "FEN-1012", "currently_active": "true", "rotation_note": "SRE primary, standing rotation"},
    {"service_name_raw": "auth_gateway", "engineer_emp_id": "FEN-1007", "currently_active": "true", "rotation_note": "Week 36 primary"},
    {"service_name_raw": "notifications-worker", "engineer_emp_id": "FEN-1014", "currently_active": "true", "rotation_note": "Legacy rotation, not yet wound down"},
    {"service_name_raw": "notifications-worker", "engineer_emp_id": "FEN-1013", "currently_active": "false", "rotation_note": "Week 35 primary"},
    {"service_name_raw": "checkout-service", "engineer_emp_id": "FEN-1003", "currently_active": "true", "rotation_note": "Week 36 primary"},
    {"service_name_raw": "checkout-service", "engineer_emp_id": "FEN-1001", "currently_active": "false", "rotation_note": "Week 35 primary"},
    {"service_name_raw": "edge-gateway", "engineer_emp_id": "FEN-1009", "currently_active": "false", "rotation_note": "Week 35 primary"},
]


class TestGetOncall:
    """On-call resolution for active services."""

    def test_finds_active_oncall(self):
        """Active on-call entry for payments-api returns engineer name."""
        result = get_oncall("payments-api", _ONCALL, _ROSTER, _SERVICES)
        assert result["oncall_found"] is True
        assert result["engineer_name"] == "Priya Nathan"
        assert result["routed_to"] == "Priya Nathan"

    def test_service_name_normalization(self):
        """F-02: Service names are normalized (underscore → hyphen)."""
        result = get_oncall("auth-gateway", _ONCALL, _ROSTER, _SERVICES)
        assert result["oncall_found"] is True
        assert result["engineer_name"] == "Callum Osei"

    def test_no_active_oncall_falls_back_to_channel(self):
        """No active on-call → route to owning team channel."""
        # edge-gateway has no active entry
        result = get_oncall("edge-gateway", _ONCALL, _ROSTER, _SERVICES)
        assert result["oncall_found"] is False
        assert result["routed_to"] == "Platform channel"
        assert result["engineer_name"] is None


class TestF05_DeprecatedService:
    """F-05: Deprecated services with on-call entries don't crash."""

    def test_deprecated_service_with_oncall_no_crash(self):
        """Querying on-call for deprecated service must not raise."""
        result = get_oncall("notifications-worker", _ONCALL, _ROSTER, _SERVICES)
        # Should resolve without crashing
        assert result["oncall_found"] is True
        assert result["engineer_name"] == "Wren Castellano"
        assert result["owning_team"] == "Platform"

    def test_deprecated_inactive_entry(self):
        """Inactive on-call for deprecated service → channel fallback."""
        # If all entries were inactive, should fallback to channel
        active_only = [
            {"service_name_raw": "notifications-worker", "engineer_emp_id": "FEN-1013", "currently_active": "false"},
        ]
        result = get_oncall("notifications-worker", active_only, _ROSTER, _SERVICES)
        assert result["oncall_found"] is False


class TestF07_SREOncall:
    """F-07: SRE engineers reachable for on-call even though they own no service."""

    def test_sre_oncall_for_platform_service(self):
        """SRE engineer (Beatrix Solano) is on-call for primary-db."""
        result = get_oncall("primary-db", _ONCALL, _ROSTER, _SERVICES)
        assert result["oncall_found"] is True
        assert result["engineer_name"] == "Beatrix Solano"
        assert result["engineer_emp_id"] == "FEN-1012"

    def test_sre_not_owning_team(self):
        """SRE is not an owning team for any service."""
        teams = {s["owning_team"] for s in _SERVICES}
        assert "SRE" not in teams


class TestResolveRouting:
    """Routing resolution returns the correct routed_to string."""

    def test_routed_to_name(self):
        routed = resolve_routing("payments-api", _ONCALL, _ROSTER, _SERVICES)
        assert routed == "Priya Nathan"

    def test_routed_to_channel(self):
        routed = resolve_routing("edge-gateway", _ONCALL, _ROSTER, _SERVICES)
        assert routed == "Platform channel"

    def test_routed_to_channel_when_engineer_not_in_roster(self):
        oncall_no_roster = [
            {"service_name_raw": "payments-api", "engineer_emp_id": "FEN-9999", "currently_active": "true"},
        ]
        routed = resolve_routing("payments-api", oncall_no_roster, _ROSTER, _SERVICES)
        assert routed == "Payments channel"


class TestEdgeCases:
    """Edge cases for routing."""

    def test_no_oncall_schedule(self):
        result = get_oncall("payments-api", [], _ROSTER, _SERVICES)
        assert result["oncall_found"] is False
        assert result["routed_to"] == "Payments channel"

    def test_service_not_in_registry(self):
        result = get_oncall("unknown-service", _ONCALL, _ROSTER, _SERVICES)
        assert result["oncall_found"] is False
        assert result["routed_to"] == "Unknown channel"

    def test_empty_roster(self):
        result = get_oncall("payments-api", _ONCALL, [], _SERVICES)
        assert result["oncall_found"] is True
        assert result["routed_to"] == "Payments channel"  # engineer not in roster → channel