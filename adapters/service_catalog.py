"""Service catalog adapter — wraps service registry lookup behind ServiceCatalogProtocol.

In this build, the service registry is loaded at startup and cached.
The adapter can simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ingest.normalize import normalize_service as _normalize_service


class ServiceCatalogAdapter:
    """Adapter for the service catalog.

    Wraps the existing service registry lookup logic behind a clean interface
    that can fail or timeout under test.
    """

    def __init__(
        self,
        services: list[dict],
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._services = services
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds

    async def find_service(self, name: str) -> dict | None:
        """Look up a service by normalized name."""
        await self._maybe_fail_or_timeout("Service catalog")
        normalized = _normalize_service(name)
        for svc in self._services:
            if svc.get("service_name_normalized", "") == normalized:
                return dict(svc)
        return None

    async def get_services(self) -> list[dict]:
        """Get all services."""
        await self._maybe_fail_or_timeout("Service catalog")
        return [dict(svc) for svc in self._services]

    # ── Failure simulation ─────────────────────────────────────────────

    def set_simulate_failure(self, value: bool) -> None:
        self._simulate_failure = value

    def set_simulate_timeout(self, value: bool) -> None:
        self._simulate_timeout = value

    def set_timeout_seconds(self, value: float) -> None:
        self._timeout_seconds = value

    async def _maybe_fail_or_timeout(self, label: str) -> None:
        if self._simulate_failure:
            raise ConnectionError(f"{label} unavailable (simulated)")
        if self._simulate_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} timed out after {self._timeout_seconds}s (simulated)")