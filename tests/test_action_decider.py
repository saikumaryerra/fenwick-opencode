"""Tests for engine/action_decider.py — authorization rules."""

import pytest
from engine.action_decider import is_authorized_for_action, decide_action


def _make_filer(emp_id, name, team, title):
    return {"emp_id": emp_id, "name": name, "team": team, "title": title}


def _make_service(name, team, status="active"):
    return {
        "service_name": name,
        "service_name_normalized": name,
        "owning_team": team,
        "status": status,
    }


_SERVICES = [
    _make_service("payments-api", "Payments"),
    _make_service("checkout-service", "Payments"),
    _make_service("billing-worker", "Billing"),
    _make_service("notifications-worker", "Platform", status="deprecated"),
]

_ROSTER = [
    _make_filer("FEN-1001", "Priya Nathan", "Payments", "Senior Software Engineer"),
    _make_filer("FEN-1003", "Marisol Feng", "Payments", "Software Engineer"),
    _make_filer("FEN-1005", "Tomas Ilic", "Billing", "Software Engineer"),
    _make_filer("FEN-1008", "Grace Umeh", "Platform", "Software Engineer"),
    _make_filer("FEN-1010", "Layla Hassoun", "Security", "Security Engineer"),
]

_INCIDENTS = [
    {
        "incident_id": "INC-002115",
        "service_name_raw": "checkout-service",
        "service_normalized": "checkout-service",
        "status": "open",
        "updates_parsed": [
            {"note": "Investigating", "emp_id": "FEN-1001", "timestamp_raw": "2026-09-07T14:20:00"},
            {"note": "Correlated with downstream", "emp_id": "FEN-1003", "timestamp_raw": "2026-09-07T14:45:00"},
        ],
    },
]


class TestIsAuthorizedForAction:
    """Authorization checks for actions."""

    def test_authorized_page_oncall_owning_team(self):
        """Payments engineer can page on-call for payments-api."""
        filer = _make_filer("FEN-1003", "Marisol Feng", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is True

    def test_not_authorized_wrong_team(self):
        """Billing engineer cannot page on-call for payments-api."""
        filer = _make_filer("FEN-1005", "Tomas Ilic", "Billing", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "not authorised" in reason.lower()

    def test_not_authorized_filer_not_found(self):
        authorized, reason = is_authorized_for_action(
            None, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "not found" in reason.lower()

    def test_deprecated_service_not_authorized(self):
        """Deprecated services → tell owning team, don't page."""
        filer = _make_filer("FEN-1008", "Grace Umeh", "Platform", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", "notifications-worker", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "deprecated" in reason.lower()

    def test_security_team_authorized(self):
        """Security team can authorize actions."""
        filer = _make_filer("FEN-1010", "Layla Hassoun", "Security", "Security Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is True


class TestAuthorizedCloseIncident:
    """Close-incident authorization rules."""

    def test_owning_team_can_close(self):
        """Owning team member can close incident."""
        filer = _make_filer("FEN-1001", "Priya Nathan", "Payments", "Senior Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "close_incident", "checkout-service", _SERVICES, _ROSTER, _INCIDENTS
        )
        assert authorized is True

    def test_non_owning_team_without_post_cannot_close(self):
        """Non-owning team who hasn't posted cannot close."""
        filer = _make_filer("FEN-1005", "Tomas Ilic", "Billing", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "close_incident", "checkout-service", _SERVICES, _ROSTER, _INCIDENTS
        )
        assert authorized is False

    def test_poster_can_close(self):
        """Someone who posted on the incident can close it."""
        # FEN-1003 posted on checkout-service incident (see _INCIDENTS)
        filer = _make_filer("FEN-1003", "Marisol Feng", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "close_incident", "checkout-service", _SERVICES, _ROSTER, _INCIDENTS
        )
        assert authorized is True


class TestForbiddenActions:
    """Actions the system never performs."""

    def test_grant_access_forbidden(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "grant_access", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "not permitted" in reason.lower()

    def test_rollback_forbidden(self):
        filer = _make_filer("FEN-1001", "Priya", "Payments", "Senior Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "rollback", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False

    def test_deploy_forbidden(self):
        filer = _make_filer("FEN-1001", "Priya", "Payments", "Senior Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "deploy", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False

    def test_restart_forbidden(self):
        filer = _make_filer("FEN-1001", "Priya", "Payments", "Senior Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "restart", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False


class TestDecideAction:
    """Full decision record from decide_action."""

    def test_action_decided_disposition(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        decision = decide_action(
            filer, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert decision["disposition"] == "action_decided"
        assert decision["authorized"] is True

    def test_refused_disposition(self):
        filer = _make_filer("FEN-1005", "Tomas", "Billing", "Software Engineer")
        decision = decide_action(
            filer, "page_oncall", "payments-api", _SERVICES, _ROSTER
        )
        assert decision["disposition"] == "refused"
        assert decision["authorized"] is False


class TestEdgeCases:
    """Edge cases for action authorization."""

    def test_no_action(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, None, "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "no action" in reason.lower()

    def test_unknown_action(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "dance", "payments-api", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "unknown" in reason.lower()

    def test_no_service(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", None, _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "no service" in reason.lower()

    def test_service_not_found(self):
        filer = _make_filer("FEN-1003", "Marisol", "Payments", "Software Engineer")
        authorized, reason = is_authorized_for_action(
            filer, "page_oncall", "nonexistent-service", _SERVICES, _ROSTER
        )
        assert authorized is False
        assert "not found" in reason.lower()