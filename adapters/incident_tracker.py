"""Incident tracker adapter — wraps engine/incident_matcher.py + engine/action_decider.py.

Read: find matching incidents, check live status.
Write: record decisions (dry-run in this build).
The adapter can simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from engine.incident_matcher import (
    find_matching_incidents as _find_matching,
    is_live as _is_live,
)
from engine.action_decider import record_decision as _record_decision


class IncidentTrackerAdapter:
    """Adapter for the incident tracker.

    Wraps existing incident matching and decision recording logic.
    Can simulate read failure and write failure for testing.
    """

    def __init__(
        self,
        incidents: list[dict],
        *,
        simulate_read_failure: bool = False,
        simulate_read_timeout: bool = False,
        simulate_write_failure: bool = False,
        simulate_write_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._incidents = incidents
        self._simulate_read_failure = simulate_read_failure
        self._simulate_read_timeout = simulate_read_timeout
        self._simulate_write_failure = simulate_write_failure
        self._simulate_write_timeout = simulate_write_timeout
        self._timeout_seconds = timeout_seconds

    # ── Read operations ────────────────────────────────────────────────

    async def find_matching_incidents(
        self, ticket_text: str, service_names: list[str]
    ) -> list[dict]:
        """Find open/live incidents matching a ticket."""
        await self._maybe_fail_read("Incident tracker (read)")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _find_matching, ticket_text, service_names, self._incidents
        )

    async def is_live(self, incident: dict) -> bool:
        """Check if an incident is live."""
        await self._maybe_fail_read("Incident tracker (read)")
        return _is_live(incident)

    # ── Write operations ───────────────────────────────────────────────

    async def record_decision(self, decision: dict) -> None:
        """Record an action decision (dry-run in this build)."""
        await self._maybe_fail_write("Incident tracker (write)")
        _record_decision(decision)

    # ── Failure simulation ─────────────────────────────────────────────

    def set_simulate_read_failure(self, value: bool) -> None:
        self._simulate_read_failure = value

    def set_simulate_read_timeout(self, value: bool) -> None:
        self._simulate_read_timeout = value

    def set_simulate_write_failure(self, value: bool) -> None:
        self._simulate_write_failure = value

    def set_simulate_write_timeout(self, value: bool) -> None:
        self._simulate_write_timeout = value

    def set_timeout_seconds(self, value: float) -> None:
        self._timeout_seconds = value

    async def _maybe_fail_read(self, label: str) -> None:
        if self._simulate_read_failure:
            raise ConnectionError(f"{label} unavailable (simulated)")
        if self._simulate_read_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} timed out after {self._timeout_seconds}s (simulated)")

    async def _maybe_fail_write(self, label: str) -> None:
        if self._simulate_write_failure:
            raise ConnectionError(f"{label} write failed (simulated)")
        if self._simulate_write_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} write timed out after {self._timeout_seconds}s (simulated)")