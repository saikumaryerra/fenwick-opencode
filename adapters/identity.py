"""Identity directory adapter — wraps auth/clearance.py behind IdentityDirProtocol.

In this build, the roster is loaded at startup and cached. The adapter can
simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from auth.clearance import get_filer as _get_filer


class IdentityDirAdapter:
    """Adapter for the identity directory.

    Wraps the existing roster lookup logic behind a clean interface that
    can fail or timeout under test.
    """

    def __init__(
        self,
        roster: list[dict],
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._roster = roster
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds

    async def get_filer(self, emp_id: str) -> dict | None:
        """Look up a filer by employee ID."""
        await self._maybe_fail_or_timeout("Identity directory")
        return _get_filer(self._roster, emp_id)

    async def get_roster(self) -> list[dict]:
        """Get the full engineer roster."""
        await self._maybe_fail_or_timeout("Identity directory")
        return list(self._roster)

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