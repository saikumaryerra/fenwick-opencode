"""FastAPI app — POST /tickets endpoint (BRIEFING.md §2, §3).

Loads all read-only extracts into memory at startup, wires the adapters
into an orchestrator, and serves the single POST /tickets route.

Defines the request flow per BRIEFING.md §6:
  1. Identify filer & compute clearance (handled inside orchestrator)
  2. Classify the ticket
  3. Execute per kind (answered | routed | duplicate | action_decided | refused)
  4. Return plan + steps_run

ticket_id handling: a null ticket_id files a new ticket and gets a fresh
id; passing an earlier id adds a follow-up to that ticket. Follow-ups
re-process the ticket (audit-only answers are never replayed, Q6). This
build tracks tickets in memory; durable SQLite persistence is the
state/store.py module.
"""

from __future__ import annotations

import itertools
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from ingest.csv_loader import (
    load_roster,
    load_services,
    load_oncall,
    load_incidents,
    load_open_tickets,
)
from ingest.doc_loader import load_documents
from adapters.factory import create_orchestrator


# ── Request/response models ─────────────────────────────────────────────

class TicketRequest(BaseModel):
    """POST /tickets request body (verbatim from scenario.txt)."""
    text: str = Field(..., description="Ticket text")
    filed_by: str = Field(..., description="Employee id from the identity directory")
    ticket_id: str | None = Field(None, description="null files a new ticket; an id adds a follow-up")


class PlannedStep(BaseModel):
    step: str
    why: str


class ExecutedStep(BaseModel):
    tool: str
    outcome: str
    detail: str


class Citation(BaseModel):
    source: str
    reference: str


class TicketResponse(BaseModel):
    """POST /tickets response body (verbatim from scenario.txt)."""
    ticket_id: str
    disposition: str
    answer: str
    plan: list[PlannedStep]
    steps_run: list[ExecutedStep]
    routed_to: str | None = None
    citations: list[Citation]
    related: list[str]


# ── Startup / global state ──────────────────────────────────────────────

_orchestrator = None  # type: ignore
_ticket_counter = itertools.count(2000)  # avoid colliding with TCK-0101..0125
_httpx_client: httpx.AsyncClient | None = None


def _next_ticket_id() -> str:
    return f"TCK-{next(_ticket_counter)}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data at startup, wire adapters, create the orchestrator."""
    global _orchestrator, _httpx_client

    roster = load_roster()
    services = load_services()
    oncall = load_oncall()
    incidents = load_incidents()
    documents = load_documents()
    open_tickets = load_open_tickets()

    # Create the shared httpx client for LLM calls.
    _httpx_client = httpx.AsyncClient(timeout=15.0)

    _orchestrator = create_orchestrator(
        roster=roster,
        services=services,
        oncall_schedule=oncall,
        incidents=incidents,
        documents=documents,
        open_tickets=open_tickets,
        httpx_client=_httpx_client,
    )
    yield
    if _httpx_client is not None:
        await _httpx_client.aclose()
    _orchestrator = None
    _httpx_client = None


app = FastAPI(title="Fenwick Cloud Engineering Support Queue", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/tickets", response_model=TicketResponse)
async def post_tickets(req: TicketRequest) -> dict:
    """Process one ticket and return what the system decided to do.

    Flow (BRIEFING.md §6):
      1. Identify filer & compute clearance
      2. Classify
      3. Execute per kind
      4. Return plan + steps_run
    """
    if _orchestrator is None:
        raise RuntimeError("Service not ready: data not loaded")

    # ticket_id: null files a new ticket; an id adds a follow-up.
    ticket_id = req.ticket_id or _next_ticket_id()

    result = await _orchestrator.process_ticket(req.text, req.filed_by)
    result["ticket_id"] = ticket_id

    return result