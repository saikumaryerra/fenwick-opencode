"""On-call scheduler adapter — wraps engine/routing.py behind OncallSchedulerProtocol.

In this build, the on-call schedule is loaded at startup and cached.
When unavailable, falls back to "<team> channel". Never fills in a name
from a stale copy (§7). The adapter can simulate failures and timeouts.
"""

from __future__ import annotations

import asyncio
from typing import Any

from engine.routing import get_oncall as _get_oncall


class OncallSchedulerAdapter:
    """Adapter for the on-call scheduler.

    Wraps the existing on-call resolution logic. When the scheduler is
    unavailable, routes to owning team channel. Never returns a stale name.
    """

    def __init__(
        self,
        oncall_schedule: list[dict],
        roster: list[dict],
        services: list[dict],
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._oncall = oncall_schedule
        self._roster = roster
        self._services = services
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds

    async def get_oncall(self, service_name: str) -> dict:
        """Find the currently-active on-call engineer for a service.

        When the scheduler is unavailable, returns team-channel fallback
        without filling in a stale engineer name (§7).
        """
        try:
            await self._maybe_fail_or_timeout("On-call scheduler")
            # Wraps the synchronous routing function
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                _get_oncall,
                service_name,
                self._oncall,
                self._roster,
                self._services,
            )
        except (ConnectionError, TimeoutError):
            # Scheduler unavailable → route to owning team channel
            owning_team = self._resolve_owning_team(service_name)
            return {
                "engineer_name": None,
                "engineer_emp_id": None,
                "routed_to": f"{owning_team} channel",
                "oncall_found": False,
                "owning_team": owning_team,
            }

    # ── Failure simulation ─────────────────────────────────────────────

    def set_simulate_failure(self, value: bool) -> None:
        self._simulate_failure = value

    def set_simulate_timeout(self, value: bool) -> None:
        self._simulate_timeout = value

    def set_timeout_seconds(self, value: float) -> None:
        self._timeout_seconds = value

    def _resolve_owning_team(self, service_name: str) -> str:
        from ingest.normalize import normalize_service as _norm
        svc_norm = _norm(service_name)
        for svc in self._services:
            if svc.get("service_name_normalized", "") == svc_norm:
                return svc.get("owning_team", "Unknown")
        return "Unknown"

    async def _maybe_fail_or_timeout(self, label: str) -> None:
        if self._simulate_failure:
            raise ConnectionError(f"{label} unavailable (simulated)")
        if self._simulate_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} timed out after {self._timeout_seconds}s (simulated)")