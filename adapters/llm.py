"""LLM (Groq) adapter — wraps LLM inference behind LLMProtocol.

In this build, the LLM is wrapped for classification. When it fails or
times out, the system falls back to keyword-based rules.
The adapter can simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from classify.classify import classify as _rules_classify


class LLMAdapter:
    """Adapter for LLM inference (Groq).

    Wraps LLM calls for classification. Falls back to rules when the model
    fails or times out. Supports call-count tracking to enforce the 2-call
    per-ticket limit (§8).
    """

    def __init__(
        self,
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 8.0,
        max_calls_per_ticket: int = 2,
    ) -> None:
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds
        self._max_calls = max_calls_per_ticket
        self._calls_this_ticket = 0

    async def classify(self, text: str, services: list[dict]) -> dict:
        """Classify a ticket.

        Attempts model call first; falls back to rules on failure/timeout.
        Returns dict with kind, services, action_requested.
        """
        self._calls_this_ticket += 1

        # Check call cap
        if self._calls_this_ticket > self._max_calls:
            return self._rules_fallback(text, services)

        # Simulate model call
        try:
            await self._maybe_fail_or_timeout("LLM (Groq)")
            # In production: call Groq API here.
            # In this build: use rules classification (same as fallback)
            return self._rules_fallback(text, services)
        except (ConnectionError, TimeoutError):
            return self._rules_fallback(text, services)

    async def extract_services(self, text: str) -> list[str]:
        """Extract service names from text using the model."""
        self._calls_this_ticket += 1

        if self._calls_this_ticket > self._max_calls:
            return []

        try:
            await self._maybe_fail_or_timeout("LLM (Groq)")
            # In production: call Groq API
            return []
        except (ConnectionError, TimeoutError):
            return []

    def reset_call_count(self) -> None:
        """Reset the per-ticket call counter."""
        self._calls_this_ticket = 0

    def get_call_count(self) -> int:
        return self._calls_this_ticket

    # ── Failure simulation ─────────────────────────────────────────────

    def set_simulate_failure(self, value: bool) -> None:
        self._simulate_failure = value

    def set_simulate_timeout(self, value: bool) -> None:
        self._simulate_timeout = value

    def set_timeout_seconds(self, value: float) -> None:
        self._timeout_seconds = value

    def _rules_fallback(self, text: str, services: list[dict]) -> dict:
        """Fallback to keyword-based rules classification."""
        return _rules_classify(text, services)

    async def _maybe_fail_or_timeout(self, label: str) -> None:
        if self._simulate_failure:
            raise ConnectionError(f"{label} unavailable (simulated)")
        if self._simulate_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} timed out after {self._timeout_seconds}s (simulated)")