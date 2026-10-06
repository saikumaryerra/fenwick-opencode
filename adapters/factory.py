"""Factory — create all adapters with loaded data, ready for the orchestrator."""

from __future__ import annotations

from typing import Any

from adapters.doc_store import DocStoreAdapter
from adapters.identity import IdentityDirAdapter
from adapters.service_catalog import ServiceCatalogAdapter
from adapters.oncall import OncallSchedulerAdapter
from adapters.incident_tracker import IncidentTrackerAdapter
from adapters.messaging import MessagingAdapter
from adapters.llm import LLMAdapter
from adapters.orchestrator import Orchestrator


def create_orchestrator(
    roster: list[dict],
    services: list[dict],
    oncall_schedule: list[dict],
    incidents: list[dict],
    documents: dict[str, dict],
    open_tickets: list[dict] | None = None,
    *,
    httpx_client: Any | None = None,
) -> Orchestrator:
    """Create an orchestrator with all adapters wired up to loaded data.

    Args:
        roster: From csv_loader.load_roster()
        services: From csv_loader.load_services()
        oncall_schedule: From csv_loader.load_oncall()
        incidents: From csv_loader.load_incidents()
        documents: From doc_loader.load_documents()
        open_tickets: From csv_loader.load_open_tickets(), optional
        httpx_client: httpx.AsyncClient for LLM calls (created in main.py lifespan).

    Returns:
        A fully wired Orchestrator instance.
    """
    doc_store = DocStoreAdapter(documents)
    identity_dir = IdentityDirAdapter(roster)
    service_catalog = ServiceCatalogAdapter(services)
    oncall = OncallSchedulerAdapter(oncall_schedule, roster, services)
    incident_tracker = IncidentTrackerAdapter(incidents)
    messaging = MessagingAdapter()
    llm = LLMAdapter(client=httpx_client)

    orch = Orchestrator(
        doc_store=doc_store,
        identity_dir=identity_dir,
        service_catalog=service_catalog,
        oncall=oncall,
        incident_tracker=incident_tracker,
        messaging=messaging,
        llm=llm,
        open_tickets=open_tickets or [],
    )

    orch.set_data(
        services=services,
        roster=roster,
        documents=documents,
        incidents=incidents,
        oncall_schedule=oncall_schedule,
    )

    return orch