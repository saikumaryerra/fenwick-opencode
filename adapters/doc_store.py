"""Document store adapter — wraps engine/document_search.py behind DocStoreProtocol.

In this build, documents are loaded at startup and searched in-memory.
The adapter can simulate failures and timeouts for testing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from engine.document_search import search as _search, best_answer as _best_answer


class DocStoreAdapter:
    """Adapter for the document store.

    Wraps the existing in-memory document search logic behind a clean interface
    that can fail or timeout under test.
    """

    def __init__(
        self,
        documents: dict[str, dict],
        *,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._documents = documents
        self._simulate_failure = simulate_failure
        self._simulate_timeout = simulate_timeout
        self._timeout_seconds = timeout_seconds

    async def search(
        self, query: str, filer_clearance: str, *, top_k: int = 3
    ) -> list[dict]:
        """Search documents by keyword, filtered by clearance."""
        await self._maybe_fail_or_timeout("Document store")
        return _search(query, self._documents, filer_clearance, top_k=top_k)

    async def best_answer(
        self, query: str, filer_clearance: str
    ) -> dict | None:
        """Get the single best answer from documents, or None."""
        await self._maybe_fail_or_timeout("Document store")
        return _best_answer(query, self._documents, filer_clearance)

    # ── Failure simulation ─────────────────────────────────────────────

    def set_simulate_failure(self, value: bool) -> None:
        self._simulate_failure = value

    def set_simulate_timeout(self, value: bool) -> None:
        self._simulate_timeout = value

    def set_timeout_seconds(self, value: float) -> None:
        self._timeout_seconds = value

    async def _maybe_fail_or_timeout(self, label: str) -> None:
        """Raise an exception if failure or timeout is simulated."""
        if self._simulate_failure:
            raise ConnectionError(f"{label} unavailable (simulated)")
        if self._simulate_timeout:
            await asyncio.sleep(self._timeout_seconds)
            raise TimeoutError(f"{label} timed out after {self._timeout_seconds}s (simulated)")