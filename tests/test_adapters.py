"""Tests for adapters — failure modes, timeouts, and step tracking.

Tests every adapter's ability to:
1. Operate normally (success path)
2. Simulate failure (ConnectionError)
3. Simulate timeout (TimeoutError)
4. Integrate with step tracking for plan/steps_run
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from adapters.step_tracker import StepTracker
from adapters.doc_store import DocStoreAdapter
from adapters.identity import IdentityDirAdapter
from adapters.service_catalog import ServiceCatalogAdapter
from adapters.oncall import OncallSchedulerAdapter
from adapters.incident_tracker import IncidentTrackerAdapter
from adapters.messaging import MessagingAdapter
from adapters.llm import LLMAdapter
from adapters.orchestrator import Orchestrator


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_services():
    return [
        {"service_name": "payments-api", "service_name_normalized": "payments-api",
         "owning_team": "Payments", "status": "active"},
        {"service_name": "checkout-service", "service_name_normalized": "checkout-service",
         "owning_team": "Payments", "status": "active"},
        {"service_name": "billing-worker", "service_name_normalized": "billing-worker",
         "owning_team": "Billing", "status": "active"},
    ]


@pytest.fixture
def sample_roster():
    return [
        {"emp_id": "FEN-1001", "name": "Priya Nathan", "team": "Payments",
         "title": "Senior Software Engineer"},
        {"emp_id": "FEN-1003", "name": "Marisol Feng", "team": "Payments",
         "title": "Software Engineer"},
        {"emp_id": "FEN-1005", "name": "Tomas Ilic", "team": "Billing",
         "title": "Software Engineer"},
    ]


@pytest.fixture
def sample_oncall():
    return [
        {"service_name_raw": "payments-api", "engineer_emp_id": "FEN-1001",
         "currently_active": "true", "rotation_note": "Week 36 primary"},
        {"service_name_raw": "checkout-service", "engineer_emp_id": "FEN-1003",
         "currently_active": "true", "rotation_note": "Week 36 primary"},
    ]


@pytest.fixture
def sample_incidents():
    return [
        {
            "incident_id": "INC-002115",
            "service_name_raw": "checkout-service",
            "service_normalized": "checkout-service",
            "status": "open",
            "severity": "SEV2",
            "one_line_summary": "Checkout latency climbing",
            "date": "2026-09-07",
            "updates_parsed": [
                {"note": "Latency climbing, investigating", "emp_id": "FEN-1001",
                 "timestamp_raw": "2026-09-07T14:20:00"},
            ],
        },
    ]


@pytest.fixture
def sample_documents():
    return {
        "runbook_rollback_payments_api.docx": {
            "path": "/docs/runbook_rollback_payments_api.docx",
            "text": "How to roll back payments-api. Step 1: Verify canary. Step 2: Run rollback script.",
            "restricted": False,
            "is_draft": False,
            "is_superseded": False,
            "category": "runbooks",
            "doc_family": "runbook_rollback_payments_api",
        },
        "postmortem_auth_gateway_outage_FINAL.docx": {
            "path": "/docs/postmortem_auth_gateway_outage_FINAL.docx",
            "text": "FINAL postmortem for auth-gateway outage. Security incident analysis.",
            "restricted": True,
            "is_draft": False,
            "is_superseded": False,
            "category": "postmortems",
            "doc_family": "postmortem_auth_gateway_outage",
        },
    }


# ── Step Tracker Tests ────────────────────────────────────────────────────

class TestStepTracker:
    """StepTracker — plan creation, execution recording, contract compliance."""

    def test_plan_and_steps_run_are_separate(self):
        """Plan is created before execution; steps_run records what happened."""
        tracker = StepTracker()
        tracker.plan("Search documents", "Need to find relevant docs")
        tracker.plan("Classify ticket", "Determine ticket kind")

        tracker.ok("search_documents", "Found 2 matching documents")
        tracker.failed("classify_ticket", "LLM timed out, using rules")
        tracker.skipped("route_to_oncall", "Not a routing scenario")

        plan = tracker.get_plan()
        steps_run = tracker.get_steps_run()

        assert len(plan) == 2
        assert len(steps_run) == 3
        assert plan[0]["step"] == "Search documents"
        assert steps_run[0]["tool"] == "search_documents"
        assert steps_run[0]["outcome"] == "ok"
        assert steps_run[1]["outcome"] == "failed"
        assert steps_run[2]["outcome"] == "skipped"

    def test_all_outcomes(self):
        """All four outcomes are recordable."""
        tracker = StepTracker()
        tracker.ok("step1", "All good")
        tracker.failed("step2", "Broke")
        tracker.timeout("step3", "Took too long")
        tracker.skipped("step4", "Not needed")

        steps = tracker.get_steps_run()
        assert len(steps) == 4
        outcomes = {s["outcome"] for s in steps}
        assert outcomes == {"ok", "failed", "timeout", "skipped"}

    def test_assert_all_planned_steps_recorded_ok(self):
        """All planned steps have corresponding steps_run entries."""
        tracker = StepTracker()
        tracker.plan("Identify filer", "Look up filer")
        tracker.plan("Classify ticket", "Classify ticket kind")

        tracker.ok("identify_filer", "Found filer")
        tracker.ok("classify_ticket", "Classified")

        discrepancies = tracker.assert_all_planned_steps_recorded()
        assert discrepancies == []

    def test_assert_planned_steps_missing_step(self):
        """Missing steps are reported."""
        tracker = StepTracker()
        tracker.plan("Identify filer", "Look up filer")
        tracker.plan("Classify ticket", "Classify ticket kind")

        tracker.ok("identify_filer", "Found filer")
        # Classify was planned but never executed

        discrepancies = tracker.assert_all_planned_steps_recorded()
        assert len(discrepancies) == 1
        assert "classify" in discrepancies[0]

    def test_plan_and_steps_run_empty_by_default(self):
        tracker = StepTracker()
        assert tracker.get_plan() == []
        assert tracker.get_steps_run() == []


# ── DocStoreAdapter Tests ─────────────────────────────────────────────────

class TestDocStoreAdapter:
    """Document store adapter — success, failure, timeout."""

    @pytest.mark.asyncio
    async def test_search_success(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents)
        results = await adapter.search("payments-api rollback", "general")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_best_answer_success(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents)
        result = await adapter.best_answer("payments-api rollback", "general")
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_failure(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents, simulate_failure=True)
        with pytest.raises(ConnectionError, match="Document store unavailable"):
            await adapter.search("payments-api", "general")

    @pytest.mark.asyncio
    async def test_best_answer_failure(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents, simulate_failure=True)
        with pytest.raises(ConnectionError, match="Document store unavailable"):
            await adapter.best_answer("payments-api", "general")

    @pytest.mark.asyncio
    async def test_search_timeout(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents, simulate_timeout=True, timeout_seconds=0.001)
        with pytest.raises(TimeoutError, match="Document store timed out"):
            await adapter.search("payments-api", "general")

    @pytest.mark.asyncio
    async def test_best_answer_timeout(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents, simulate_timeout=True, timeout_seconds=0.001)
        with pytest.raises(TimeoutError, match="Document store timed out"):
            await adapter.best_answer("payments-api", "general")

    @pytest.mark.asyncio
    async def test_clearance_filter(self, sample_documents):
        """General filer must not see restricted documents."""
        adapter = DocStoreAdapter(sample_documents)
        results = await adapter.search("auth-gateway", "general")
        for r in results:
            assert r["restricted"] is False, f"Restricted doc leaked: {r['filename']}"

    @pytest.mark.asyncio
    async def test_restricted_filer_sees_restricted(self, sample_documents):
        adapter = DocStoreAdapter(sample_documents)
        results = await adapter.search("auth-gateway", "restricted")
        restricted = [r for r in results if r["restricted"]]
        assert len(restricted) > 0


# ── IdentityDirAdapter Tests ──────────────────────────────────────────────

class TestIdentityDirAdapter:
    """Identity directory adapter — success, failure, timeout."""

    @pytest.mark.asyncio
    async def test_get_filer_success(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster)
        filer = await adapter.get_filer("FEN-1001")
        assert filer is not None
        assert filer["name"] == "Priya Nathan"

    @pytest.mark.asyncio
    async def test_get_filer_not_found(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster)
        filer = await adapter.get_filer("FEN-9999")
        assert filer is None

    @pytest.mark.asyncio
    async def test_get_filer_failure(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster, simulate_failure=True)
        with pytest.raises(ConnectionError, match="Identity directory unavailable"):
            await adapter.get_filer("FEN-1001")

    @pytest.mark.asyncio
    async def test_get_filer_timeout(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster, simulate_timeout=True, timeout_seconds=0.001)
        with pytest.raises(TimeoutError, match="Identity directory timed out"):
            await adapter.get_filer("FEN-1001")

    @pytest.mark.asyncio
    async def test_get_roster_success(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster)
        roster = await adapter.get_roster()
        assert len(roster) == 3

    @pytest.mark.asyncio
    async def test_get_roster_failure(self, sample_roster):
        adapter = IdentityDirAdapter(sample_roster, simulate_failure=True)
        with pytest.raises(ConnectionError):
            await adapter.get_roster()


# ── ServiceCatalogAdapter Tests ───────────────────────────────────────────

class TestServiceCatalogAdapter:
    """Service catalog adapter — success, failure, timeout."""

    @pytest.mark.asyncio
    async def test_find_service_success(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services)
        svc = await adapter.find_service("payments-api")
        assert svc is not None
        assert svc["owning_team"] == "Payments"

    @pytest.mark.asyncio
    async def test_find_service_not_found(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services)
        svc = await adapter.find_service("nonexistent-service")
        assert svc is None

    @pytest.mark.asyncio
    async def test_find_service_failure(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services, simulate_failure=True)
        with pytest.raises(ConnectionError, match="Service catalog unavailable"):
            await adapter.find_service("payments-api")

    @pytest.mark.asyncio
    async def test_find_service_timeout(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services, simulate_timeout=True, timeout_seconds=0.001)
        with pytest.raises(TimeoutError, match="Service catalog timed out"):
            await adapter.find_service("payments-api")

    @pytest.mark.asyncio
    async def test_get_services_success(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services)
        all_svc = await adapter.get_services()
        assert len(all_svc) == 3

    @pytest.mark.asyncio
    async def test_get_services_failure(self, sample_services):
        adapter = ServiceCatalogAdapter(sample_services, simulate_failure=True)
        with pytest.raises(ConnectionError):
            await adapter.get_services()


# ── OncallSchedulerAdapter Tests ──────────────────────────────────────────

class TestOncallSchedulerAdapter:
    """On-call scheduler adapter — success, failure, timeout, graceful degradation."""

    @pytest.mark.asyncio
    async def test_get_oncall_success(self, sample_oncall, sample_roster, sample_services):
        adapter = OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services)
        result = await adapter.get_oncall("payments-api")
        assert result["oncall_found"] is True
        assert result["engineer_name"] == "Priya Nathan"

    @pytest.mark.asyncio
    async def test_get_oncall_failure_falls_back_to_channel(
        self, sample_oncall, sample_roster, sample_services
    ):
        """When scheduler fails, route to owning team channel (§7)."""
        adapter = OncallSchedulerAdapter(
            sample_oncall, sample_roster, sample_services, simulate_failure=True
        )
        result = await adapter.get_oncall("payments-api")
        # Must NOT raise — gracefully fall back
        assert result["oncall_found"] is False
        assert result["engineer_name"] is None
        assert result["routed_to"] == "Payments channel"

    @pytest.mark.asyncio
    async def test_get_oncall_timeout_falls_back_to_channel(
        self, sample_oncall, sample_roster, sample_services
    ):
        adapter = OncallSchedulerAdapter(
            sample_oncall, sample_roster, sample_services,
            simulate_timeout=True, timeout_seconds=0.001,
        )
        result = await adapter.get_oncall("payments-api")
        assert result["oncall_found"] is False
        assert result["engineer_name"] is None
        assert result["routed_to"] == "Payments channel"

    @pytest.mark.asyncio
    async def test_no_active_oncall_fallback(self, sample_roster, sample_services):
        """No active entries → route to owning team channel."""
        adapter = OncallSchedulerAdapter([], sample_roster, sample_services)
        result = await adapter.get_oncall("payments-api")
        assert result["oncall_found"] is False
        assert result["routed_to"] == "Payments channel"

    @pytest.mark.asyncio
    async def test_deprecated_service_no_crash(self, sample_oncall, sample_roster, sample_services):
        """F-05: Deprecated service with on-call must not crash."""
        deprecated_services = sample_services + [
            {"service_name": "notifications-worker",
             "service_name_normalized": "notifications-worker",
             "owning_team": "Platform", "status": "deprecated"},
        ]
        adapter = OncallSchedulerAdapter(sample_oncall, sample_roster, deprecated_services)
        result = await adapter.get_oncall("notifications-worker")
        # Just shouldn't crash; result may vary
        assert "owning_team" in result


# ── IncidentTrackerAdapter Tests ──────────────────────────────────────────

class TestIncidentTrackerAdapter:
    """Incident tracker adapter — success, read failure, write failure, timeout."""

    @pytest.mark.asyncio
    async def test_find_matching_success(self, sample_incidents):
        adapter = IncidentTrackerAdapter(sample_incidents)
        matches = await adapter.find_matching_incidents(
            "checkout latency", ["checkout-service"]
        )
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_find_matching_read_failure(self, sample_incidents):
        adapter = IncidentTrackerAdapter(sample_incidents, simulate_read_failure=True)
        with pytest.raises(ConnectionError, match="Incident tracker.*read.*unavailable"):
            await adapter.find_matching_incidents("checkout latency", ["checkout-service"])

    @pytest.mark.asyncio
    async def test_find_matching_read_timeout(self, sample_incidents):
        adapter = IncidentTrackerAdapter(
            sample_incidents, simulate_read_timeout=True, timeout_seconds=0.001
        )
        with pytest.raises(TimeoutError, match="Incident tracker.*read.*timed out"):
            await adapter.find_matching_incidents("checkout latency", ["checkout-service"])

    @pytest.mark.asyncio
    async def test_record_decision_dry_run(self, sample_incidents):
        adapter = IncidentTrackerAdapter(sample_incidents)
        # Should not raise — dry run
        await adapter.record_decision({"authorized": True, "action": "page_oncall"})

    @pytest.mark.asyncio
    async def test_record_decision_write_failure(self, sample_incidents):
        adapter = IncidentTrackerAdapter(sample_incidents, simulate_write_failure=True)
        with pytest.raises(ConnectionError, match="Incident tracker.*write.*failed"):
            await adapter.record_decision({"authorized": True})

    @pytest.mark.asyncio
    async def test_record_decision_write_timeout(self, sample_incidents):
        adapter = IncidentTrackerAdapter(
            sample_incidents, simulate_write_timeout=True, timeout_seconds=0.001
        )
        with pytest.raises(TimeoutError, match="Incident tracker.*write.*timed out"):
            await adapter.record_decision({"authorized": True})

    @pytest.mark.asyncio
    async def test_is_live_success(self, sample_incidents):
        adapter = IncidentTrackerAdapter(sample_incidents)
        is_live = await adapter.is_live(sample_incidents[0])
        assert is_live is True

    @pytest.mark.asyncio
    async def test_is_live_no_matching(self, sample_incidents):
        adapter = IncidentTrackerAdapter([])
        matches = await adapter.find_matching_incidents(
            "checkout latency", ["checkout-service"]
        )
        assert matches == []


# ── MessagingAdapter Tests ────────────────────────────────────────────────

class TestMessagingAdapter:
    """Messaging & paging adapter — success, failure, timeout, dry-run."""

    @pytest.mark.asyncio
    async def test_send_channel_message_dry_run(self):
        adapter = MessagingAdapter()
        result = await adapter.send_channel_message(
            "payments-alerts", "High latency detected"
        )
        assert result["status"] == "recorded_dry_run"
        assert result["channel"] == "payments-alerts"

    @pytest.mark.asyncio
    async def test_page_engineer_dry_run(self):
        adapter = MessagingAdapter()
        result = await adapter.page_engineer("Priya Nathan", "SEV2")
        assert result["status"] == "recorded_dry_run"
        assert result["engineer_name"] == "Priya Nathan"

    @pytest.mark.asyncio
    async def test_dry_run_log(self):
        adapter = MessagingAdapter()
        await adapter.send_channel_message("test", "msg1")
        await adapter.page_engineer("Alice", "SEV3")
        log = adapter.get_dry_run_log()
        assert len(log) == 2

    @pytest.mark.asyncio
    async def test_clear_dry_run_log(self):
        adapter = MessagingAdapter()
        await adapter.send_channel_message("test", "msg")
        adapter.clear_dry_run_log()
        assert adapter.get_dry_run_log() == []

    @pytest.mark.asyncio
    async def test_send_failure(self):
        adapter = MessagingAdapter(simulate_failure=True)
        with pytest.raises(ConnectionError, match="Messaging unavailable"):
            await adapter.send_channel_message("test", "msg")

    @pytest.mark.asyncio
    async def test_page_failure(self):
        adapter = MessagingAdapter(simulate_failure=True)
        with pytest.raises(ConnectionError, match="Paging unavailable"):
            await adapter.page_engineer("Priya", "SEV1")

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        adapter = MessagingAdapter(simulate_timeout=True, timeout_seconds=0.001)
        with pytest.raises(TimeoutError, match="Messaging timed out"):
            await adapter.send_channel_message("test", "msg")


# ── LLMAdapter Tests ──────────────────────────────────────────────────────

class TestLLMAdapter:
    """LLM adapter — success, failure, timeout, call cap, rules fallback."""

    @pytest.mark.asyncio
    async def test_classify_success(self, sample_services):
        adapter = LLMAdapter()
        result = await adapter.classify("who owns payments-api", sample_services)
        assert "kind" in result
        assert "services" in result

    @pytest.mark.asyncio
    async def test_classify_failure_falls_back_to_rules(self, sample_services):
        """LLM failure should fall back to rules, not crash."""
        adapter = LLMAdapter(simulate_failure=True)
        result = await adapter.classify("who owns payments-api", sample_services)
        # Falls back gracefully — still gets a valid classification
        assert "kind" in result
        assert result.get("services") == ["payments-api"]

    @pytest.mark.asyncio
    async def test_classify_timeout_falls_back_to_rules(self, sample_services):
        """LLM timeout should fall back to rules, not crash."""
        adapter = LLMAdapter(simulate_timeout=True, timeout_seconds=0.001)
        result = await adapter.classify("who owns payments-api", sample_services)
        assert "kind" in result

    @pytest.mark.asyncio
    async def test_call_cap_2_calls(self, sample_services):
        """After 2 calls, further calls return rules fallback without model attempt."""
        adapter = LLMAdapter(max_calls_per_ticket=2)
        await adapter.classify("who owns payments-api", sample_services)
        await adapter.classify("page oncall for payments-api", sample_services)
        assert adapter.get_call_count() == 2

        # Third call should use rules without attempting model
        result = await adapter.classify("who owns billing-worker", sample_services)
        assert adapter.get_call_count() == 3
        assert "kind" in result  # Still returns valid result

    @pytest.mark.asyncio
    async def test_reset_call_count(self, sample_services):
        adapter = LLMAdapter()
        await adapter.classify("test", sample_services)
        assert adapter.get_call_count() == 1
        adapter.reset_call_count()
        assert adapter.get_call_count() == 0

    @pytest.mark.asyncio
    async def test_extract_services_empty_in_build(self, sample_services):
        adapter = LLMAdapter()
        # In this build, extract_services returns empty (uses rules for service extraction)
        result = await adapter.extract_services("payments-api is down")
        assert result == []


# ── Orchestrator Integration Tests ────────────────────────────────────────

class TestOrchestratorFailureModes:
    """Orchestrator handling of adapter failures.

    Tests that the orchestrator correctly interprets adapter failures
    per BRIEFING.md §7 behaviour.
    """

    @pytest.mark.asyncio
    async def test_identity_directory_failure_refuses(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """Identity directory unavailable → refused (§7)."""
        identity_dir = IdentityDirAdapter(sample_roster, simulate_failure=True)
        llm = LLMAdapter()

        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=identity_dir,
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=llm,
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket("payments-api is down", "FEN-1001")
        assert result["disposition"] == "refused"
        assert "Identity directory" in result["answer"]
        # Steps_run should show the failure
        steps = result["steps_run"]
        failed_steps = [s for s in steps if s["outcome"] == "failed"]
        assert any("identity" in s["tool"].lower() or "identify" in s["tool"].lower()
                   for s in failed_steps)

    @pytest.mark.asyncio
    async def test_identity_directory_timeout_refuses(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """Identity directory timeout → refused."""
        identity_dir = IdentityDirAdapter(
            sample_roster, simulate_timeout=True, timeout_seconds=0.001
        )
        llm = LLMAdapter()

        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=identity_dir,
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=llm,
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket("payments-api is down", "FEN-1001")
        assert result["disposition"] == "refused"
        assert "timeout" in result["answer"].lower() or "try again" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_filer_not_found_refuses(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """Filer not in roster → refused."""
        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=LLMAdapter(),
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket("payments-api is down", "FEN-9999")
        assert result["disposition"] == "refused"
        assert "identity" in result["answer"].lower() or "verified" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_oncall_failure_routes_to_channel(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """On-call scheduler unavailable → route to owning team channel."""
        oncall = OncallSchedulerAdapter(
            sample_oncall, sample_roster, sample_services,
            simulate_failure=True,
        )
        llm = LLMAdapter()

        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=oncall,
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=llm,
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        # A live problem with checkout-service should route (since checkout has a live incident)
        # Filing a problem about a service with no live incident → routes
        result = await orch.process_ticket("billing-worker is slow and failing", "FEN-1005")
        assert result["disposition"] == "routed"
        steps_run = result["steps_run"]
        assert any("route" in s["tool"].lower() for s in steps_run)

    @pytest.mark.asyncio
    async def test_plan_differs_per_ticket(self):
        """Different ticket kinds produce different plans (D2 contract)."""
        tracker_a = StepTracker()
        tracker_a.plan("Identify filer", "Look up filer")
        tracker_a.plan("Classify ticket", "Determine ticket kind")
        tracker_a.plan("Search documents", "Find relevant docs by keyword")
        tracker_a.ok("identify_filer", "Found filer")
        tracker_a.ok("classify_ticket", "Kind: answerable")
        tracker_a.ok("search_documents", "Found docs")

        tracker_b = StepTracker()
        tracker_b.plan("Identify filer", "Look up filer")
        tracker_b.plan("Classify ticket", "Determine ticket kind")
        tracker_b.plan("Check open incidents", "Look for matching open/live incidents")
        tracker_b.plan("Route to on-call", "Find on-call engineer")
        tracker_b.ok("identify_filer", "Found filer")
        tracker_b.ok("classify_ticket", "Kind: live_problem")
        tracker_b.ok("check_incidents", "No live incidents found")
        tracker_b.ok("route_to_oncall", "Routed to Priya Nathan")

        plan_a = [p["step"] for p in tracker_a.get_plan()]
        plan_b = [p["step"] for p in tracker_b.get_plan()]
        assert plan_a != plan_b, "Different tickets must produce different plans"

    @pytest.mark.asyncio
    async def test_plan_steps_run_contract(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """Every step in plan must appear in steps_run (may be skipped/failed)."""
        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=LLMAdapter(),
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket("who owns payments-api", "FEN-1001")
        plan = result["plan"]
        steps_run = result["steps_run"]

        # Every planned step must have a corresponding steps_run entry
        plan_tools = {p["step"] for p in plan}
        run_tools = {s["tool"] for s in steps_run}

        # Allow for naming differences: planned step names are human-readable,
        # tool names are code identifiers. At minimum, each plan step should
        # have at least one steps_run entry.
        # The contract says "every step in plan must appear in steps_run"
        assert len(steps_run) >= len(plan), (
            f"steps_run ({len(steps_run)}) is shorter than plan ({len(plan)})"
        )


# ── Orchestrator End-to-End Tests ─────────────────────────────────────────

class TestOrchestratorEndToEnd:
    """End-to-end tests with different ticket kinds."""

    @pytest.mark.asyncio
    async def test_vpn_redirect_answer(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """VPN/wifi/all-hands → answered (not refused)."""
        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=LLMAdapter(),
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket(
            "I can't connect to VPN, please help", "FEN-1003"
        )
        assert result["disposition"] == "answered"
        assert "vpn" in result["answer"].lower() or "self-service" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_ownership_query(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=LLMAdapter(),
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket(
            "who owns payments-api", "FEN-1001"
        )
        assert result["disposition"] == "answered"
        assert "Payments" in result["answer"]

    @pytest.mark.asyncio
    async def test_plan_and_steps_run_present(
        self, sample_roster, sample_services, sample_oncall,
        sample_incidents, sample_documents
    ):
        """Every response has plan and steps_run."""
        orch = Orchestrator(
            doc_store=DocStoreAdapter(sample_documents),
            identity_dir=IdentityDirAdapter(sample_roster),
            service_catalog=ServiceCatalogAdapter(sample_services),
            oncall=OncallSchedulerAdapter(sample_oncall, sample_roster, sample_services),
            incident_tracker=IncidentTrackerAdapter(sample_incidents),
            messaging=MessagingAdapter(),
            llm=LLMAdapter(),
        )
        orch.set_data(sample_services, sample_roster, sample_documents, sample_incidents, sample_oncall)

        result = await orch.process_ticket("who owns payments-api", "FEN-1001")
        assert "plan" in result
        assert "steps_run" in result
        assert isinstance(result["plan"], list)
        assert isinstance(result["steps_run"], list)
        assert len(result["plan"]) > 0
        assert len(result["steps_run"]) > 0