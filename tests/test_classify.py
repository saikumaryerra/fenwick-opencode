"""Tests for classify/classify.py — ticket classification."""

import pytest
from classify.classify import (
    classify,
    extract_services,
    extract_action_request,
    KIND_ANSWERABLE,
    KIND_ASK_ACTION,
    KIND_LIVE_PROBLEM,
    KIND_VPN_REDIRECT,
    KIND_OWNERSHIP,
    KIND_ASK_WHAT_TO_DO,
    KIND_GENERAL_QUERY,
)


_SERVICES = [
    {"service_name": "payments-api", "service_name_normalized": "payments-api"},
    {"service_name": "billing-worker", "service_name_normalized": "billing-worker"},
    {"service_name": "checkout-service", "service_name_normalized": "checkout-service"},
    {"service_name": "auth-gateway", "service_name_normalized": "auth-gateway"},
    {"service_name": "edge-gateway", "service_name_normalized": "edge-gateway"},
    {"service_name": "notifications-worker", "service_name_normalized": "notifications-worker"},
    {"service_name": "billing-sync", "service_name_normalized": "billing-sync"},
]


class TestClassifyKinds:
    """Telling kinds of tickets apart."""

    def test_vpn_redirect(self):
        """VPN/wifi/all-hands tickets are redirected, not refused."""
        result = classify("can someone reset my VPN access", _SERVICES)
        assert result["kind"] == KIND_VPN_REDIRECT

    def test_wifi_redirect(self):
        result = classify("laptop won't connect to the office wifi again", _SERVICES)
        assert result["kind"] == KIND_VPN_REDIRECT

    def test_all_hands_redirect(self):
        result = classify("when is the next all-hands", _SERVICES)
        assert result["kind"] == KIND_VPN_REDIRECT

    def test_action_request_page_oncall(self):
        """'page on-call' is an action request."""
        result = classify("page on-call for payments-api", _SERVICES)
        assert result["kind"] == KIND_ASK_ACTION
        assert result["action_requested"] == "page_oncall"
        assert "payments-api" in result["services"]

    def test_action_request_open_incident(self):
        """'open an incident' is an action request."""
        result = classify("please open an incident for checkout-service", _SERVICES)
        assert result["kind"] == KIND_ASK_ACTION
        assert result["action_requested"] == "open_incident"

    def test_action_request_close_incident(self):
        result = classify("close incident INC-2101 please", _SERVICES)
        assert result["kind"] == KIND_ASK_ACTION
        assert result["action_requested"] == "close_incident"

    def test_live_problem_latency(self):
        """'X is slow/latency' tags as live problem."""
        result = classify("checkout-service latency spiking again since about 14:20", _SERVICES)
        assert result["kind"] == KIND_LIVE_PROBLEM
        assert "checkout-service" in result["services"]

    def test_live_problem_healthcheck(self):
        result = classify("edge-gateway healthcheck failing intermittently", _SERVICES)
        assert result["kind"] == KIND_LIVE_PROBLEM
        assert "edge-gateway" in result["services"]

    def test_live_problem_is_this_known(self):
        result = classify("fraud-detection-worker healthcheck failing, is this known", _SERVICES)
        # Matches both failure keywords and "is this known"
        assert result["kind"] == KIND_LIVE_PROBLEM

    def test_ownership_query(self):
        """'who owns X' is an ownership query."""
        result = classify("who owns billing-sync these days", _SERVICES)
        assert result["kind"] == KIND_OWNERSHIP
        assert "billing-sync" in result["services"]

    def test_ownership_oncall(self):
        result = classify("who's on call for billing-worker right now", _SERVICES)
        assert result["kind"] == KIND_OWNERSHIP
        assert "billing-worker" in result["services"]

    def test_ask_what_to_do(self):
        """'what should we do' is asks_what_to_do."""
        result = classify("what should we do about the billing-sync errors", _SERVICES)
        assert result["kind"] == KIND_ASK_WHAT_TO_DO

    def test_ask_what_concluded(self):
        result = classify("what did we conclude about the last billing-sync incident", _SERVICES)
        assert result["kind"] == KIND_ASK_WHAT_TO_DO

    def test_answerable_service_mention(self):
        """Ticket mentioning a service with no other signal → answerable."""
        result = classify("what's the rollback runbook for payments-api", _SERVICES)
        assert result["kind"] == KIND_ANSWERABLE
        assert "payments-api" in result["services"]

    def test_general_query_no_service(self):
        """No service mentioned + no specific pattern → general."""
        result = classify("hello how does this work", _SERVICES)
        assert result["kind"] == KIND_GENERAL_QUERY
        assert result["services"] == []


class TestExtractServices:
    """Service name extraction from ticket text."""

    def test_single_service(self):
        svcs = extract_services("checkout-service is slow", _SERVICES)
        assert svcs == ["checkout-service"]

    def test_multiple_services(self):
        svcs = extract_services("payments-api and billing-worker both have errors", _SERVICES)
        assert "payments-api" in svcs
        assert "billing-worker" in svcs

    def test_no_service(self):
        svcs = extract_services("hello world", _SERVICES)
        assert svcs == []


class TestExtractActionRequest:
    """Action request detection."""

    def test_page_oncall_detected(self):
        assert extract_action_request("page on-call for auth-gateway") == "page_oncall"

    def test_open_incident_detected(self):
        assert extract_action_request("open an incident") == "open_incident"

    def test_close_incident_detected(self):
        assert extract_action_request("close incident") == "close_incident"

    def test_rollback_detected(self):
        assert extract_action_request("roll back payments-api") == "rollback"

    def test_deploy_detected(self):
        assert extract_action_request("deploy new version") == "deploy"

    def test_no_action(self):
        assert extract_action_request("what time is it") is None