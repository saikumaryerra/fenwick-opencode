"""Protocols (interfaces) for each external system.

Every adapter implements its system's protocol, and the rest of the code
depends only on these protocols. In this build the implementations wrap
the loaded in-memory data; in production they would make real API calls.
"""

from __future__ import annotations

import abc
from typing import Any, Protocol


class DocStoreProtocol(Protocol):
    """Read documents — runbooks, postmortems, policies."""

    async def search(
        self, query: str, filer_clearance: str, *, top_k: int = 3
    ) -> list[dict]:
        """Search documents by keyword, filtered by clearance."""
        ...

    async def best_answer(
        self, query: str, filer_clearance: str
    ) -> dict | None:
        """Get the single best answer from documents, or None."""
        ...


class IdentityDirProtocol(Protocol):
    """Read identity directory — staff, team, title, clearance."""

    async def get_filer(self, emp_id: str) -> dict | None:
        """Look up a filer by employee ID. Returns roster entry or None."""
        ...

    async def get_roster(self) -> list[dict]:
        """Get the full engineer roster."""
        ...


class ServiceCatalogProtocol(Protocol):
    """Read service catalog — services, owners, status."""

    async def find_service(self, name: str) -> dict | None:
        """Look up a service by normalized name."""
        ...

    async def get_services(self) -> list[dict]:
        """Get all services."""
        ...


class OncallSchedulerProtocol(Protocol):
    """Read on-call schedule — who's on call right now."""

    async def get_oncall(
        self, service_name: str
    ) -> dict:
        """Find the currently-active on-call engineer for a service.

        Returns dict with engineer_name, routed_to, oncall_found, owning_team.
        When unavailable, routed_to falls back to "<team> channel".
        """
        ...


class IncidentTrackerProtocol(Protocol):
    """Read + write incident tracker — past and current incidents."""

    async def find_matching_incidents(
        self, ticket_text: str, service_names: list[str]
    ) -> list[dict]:
        """Find open/live incidents matching a ticket."""
        ...

    async def record_decision(self, decision: dict) -> None:
        """Record an action decision (dry-run in this build)."""
        ...

    async def is_live(self, incident: dict) -> bool:
        """Check if an incident is live (open + non-boilerplate update)."""
        ...


class MessagingProtocol(Protocol):
    """Write messaging & paging — channels and pages."""

    async def send_channel_message(self, channel: str, message: str) -> dict:
        """Post a message to a channel. Returns delivery status."""
        ...

    async def page_engineer(
        self, engineer_name: str, escalation_sev: str
    ) -> dict:
        """Page an engineer. Returns delivery status (dry-run)."""
        ...


class LLMProtocol(Protocol):
    """Inference — classify tickets, extract info."""

    async def classify(self, text: str, services: list[dict]) -> dict:
        """Classify a ticket: kind, services, action_requested.

        Returns dict with keys: kind, services, action_requested.
        """
        ...

    async def extract_services(self, text: str) -> list[str]:
        """Extract service names from text."""
        ...