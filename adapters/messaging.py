"""Messaging & paging adapter — wraps messaging/paging behind MessagingProtocol.

In this build, messaging and paging is dry-run only: we decide who would
be paged and what message would be sent, but nothing is actually delivered.
The adapter can simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any


class MessagingAdapter:
    """Adapter for messaging & paging.

    This build: dry-run only — records what would be sent.
    Designed: sends via channels/paging API with idempotency keys.
    """

    def __init__(
        self,
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._dry_run: list[dict] = []
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds

    async def send_channel_message(self, channel: str, message: str) -> dict:
        """Post a message to a channel.

        Returns delivery status. In this build, messages are recorded
        but not sent (dry-run).
        """
        await self._maybe_fail_or_timeout("Messaging")
        entry = {"channel": channel, "message": message, "status": "recorded_dry_run"}
        self._dry_run.append(entry)
        return entry

    async def page_engineer(
        self, engineer_name: str, escalation_sev: str
    ) -> dict:
        """Page an engineer.

        Returns delivery status. In this build, pages are recorded
        but not sent (dry-run).
        """
        await self._maybe_fail_or_timeout("Paging")
        entry = {
            "engineer_name": engineer_name,
            "escalation_sev": escalation_sev,
            "status": "recorded_dry_run",
        }
        self._dry_run.append(entry)
        return entry

    def get_dry_run_log(self) -> list[dict]:
        """Get the log of dry-run actions (for test assertions)."""
        return list(self._dry_run)

    def clear_dry_run_log(self) -> None:
        self._dry_run.clear()

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