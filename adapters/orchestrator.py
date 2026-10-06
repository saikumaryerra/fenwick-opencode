"""Orchestrator — uses all adapters to process a ticket and produce plan + steps_run.

The orchestrator:
  1. Creates a plan (what to do) before any execution.
  2. Executes steps via adapters, recording outcomes.
  3. Handles failures per BRIEFING.md §7 behaviour.
  4. Returns the full response with plan and steps_run.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from auth.clearance import compute_clearance, can_see_document
from classify.classify import (
    KIND_ANSWERABLE,
    KIND_ASK_ACTION,
    KIND_ASK_WHAT_TO_DO,
    KIND_LIVE_PROBLEM,
    KIND_VPN_REDIRECT,
    KIND_OWNERSHIP,
    KIND_GENERAL_QUERY,
)
from engine.document_search import search as _search, best_answer as _best_answer
from engine.incident_matcher import find_matching_incidents as _match_incidents
from engine.duplicate_check import check_duplicate as _check_duplicate
from engine.action_decider import decide_action as _decide_action
from engine.routing import get_oncall as _get_oncall

from adapters.step_tracker import StepTracker
from adapters.doc_store import DocStoreAdapter
from adapters.identity import IdentityDirAdapter
from adapters.service_catalog import ServiceCatalogAdapter
from adapters.oncall import OncallSchedulerAdapter
from adapters.incident_tracker import IncidentTrackerAdapter
from adapters.messaging import MessagingAdapter
from adapters.llm import LLMAdapter, PerTicketBudget


# Total per-ticket timeout (§8).
_PER_TICKET_TIMEOUT: float = 20.0


class Orchestrator:
    """Processes one ticket through the full pipeline.

    Produces 'plan' (decided before execution) and 'steps_run'
    (what actually happened) per the API contract.
    """

    def __init__(
        self,
        doc_store: DocStoreAdapter,
        identity_dir: IdentityDirAdapter,
        service_catalog: ServiceCatalogAdapter,
        oncall: OncallSchedulerAdapter,
        incident_tracker: IncidentTrackerAdapter,
        messaging: MessagingAdapter,
        llm: LLMAdapter,
        *,
        open_tickets: list[dict] | None = None,
    ) -> None:
        self._doc_store = doc_store
        self._identity_dir = identity_dir
        self._service_catalog = service_catalog
        self._oncall = oncall
        self._incident_tracker = incident_tracker
        self._messaging = messaging
        self._llm = llm
        self._open_tickets = open_tickets or []

        # Internal copies for domain logic that accesses data directly.
        self._services_cache: list[dict] = []
        self._roster_cache: list[dict] = []
        self._documents_cache: dict[str, dict] = {}
        self._incidents_cache: list[dict] = []
        self._oncall_cache: list[dict] = []

    def set_data(
        self,
        services: list[dict],
        roster: list[dict],
        documents: dict[str, dict],
        incidents: list[dict],
        oncall_schedule: list[dict],
    ) -> None:
        """Set cached data for domain logic that accesses data directly."""
        self._services_cache = services
        self._roster_cache = roster
        self._documents_cache = documents
        self._incidents_cache = incidents
        self._oncall_cache = oncall_schedule

    async def process_ticket(
        self, text: str, filed_by: str
    ) -> dict:
        """Process a single ticket.

        Returns the full API response dict including plan and steps_run.
        """
        tracker = StepTracker()

        try:
            return await asyncio.wait_for(
                self._process(text, filed_by, tracker),
                timeout=_PER_TICKET_TIMEOUT,
            )
        except asyncio.TimeoutError:
            tracker.timeout("process_ticket", "Total per-ticket timeout exceeded")
            return self._build_response(
                disposition="refused",
                answer="Processing timed out. Please try again or contact support.",
                tracker=tracker,
                routed_to=None,
                citations=[],
                related=[],
            )

    async def _process(
        self, text: str, filed_by: str, tracker: StepTracker
    ) -> dict:
        """Internal pipeline — plan, then execute, then respond."""

        # Create per-ticket budget for model calls.
        deadline = time.monotonic() + _PER_TICKET_TIMEOUT
        budget = PerTicketBudget(deadline=deadline)
        self._llm.set_budget(budget)

        # ── Phase 1: Identify filer ─────────────────────────────────────
        tracker.plan("Identify filer", "Look up who filed the ticket in the identity directory")

        filer = None
        try:
            filer = await self._identity_dir.get_filer(filed_by)
            if filer is None:
                tracker.failed("identify_filer", f"Employee ID '{filed_by}' not found in roster")
                return self._build_response(
                    disposition="refused",
                    answer="Your identity could not be verified. Please contact support.",
                    tracker=tracker,
                    routed_to=None,
                    citations=[],
                    related=[],
                )
            tracker.ok("identify_filer", f"Found {filer.get('name', filed_by)} ({filed_by})")
        except ConnectionError:
            tracker.failed("identify_filer", "Identity directory unavailable — cannot verify filer")
            return self._build_response(
                disposition="refused",
                answer="Identity directory is unavailable. Cannot verify your clearance. Please try again later.",
                tracker=tracker,
                routed_to=None,
                citations=[],
                related=[],
            )
        except TimeoutError:
            tracker.timeout("identify_filer", "Identity directory timed out")
            return self._build_response(
                disposition="refused",
                answer="Identity directory timed out. Cannot verify your clearance. Please try again.",
                tracker=tracker,
                routed_to=None,
                citations=[],
                related=[],
            )

        # ── Phase 2: Compute clearance ──────────────────────────────────
        tracker.plan("Compute clearance", "Determine filer's clearance level from team and title")

        clearance = compute_clearance(filer.get("team", ""), filer.get("title", ""))
        tracker.ok("compute_clearance", f"Clearance: {clearance}")

        # ── Phase 3: Classify ───────────────────────────────────────────
        tracker.plan("Classify ticket", "Determine ticket kind, services, and action requests")

        # The LLM adapter uses its per-ticket budget internally.  It attempts
        # a model call when the budget allows and falls back to rules on any
        # failure.  The orchestrator records the outcome step.
        classification = await self._llm.classify(
            text, self._services_cache, catalog=self._services_cache
        )

        # Record the classify step based on what the adapter did.
        budget = self._llm._budget  # type: ignore[union-attr]
        if budget is not None and budget.calls > 0:
            tracker.ok("model_classify",
                       f"Model: {self._llm._model_id}, kind={classification.get('kind', 'unknown')}")
        else:
            tracker.ok("rules_classify",
                       f"Rules fallback (no model call), kind={classification.get('kind', 'unkonwn')}")

        kind = classification.get("kind", KIND_GENERAL_QUERY)
        services = classification.get("services", [])
        action = classification.get("action_requested")

        # ── Phase 4: Execute per kind ───────────────────────────────────
        disposition = "answered"
        answer = ""
        routed_to: str | None = None
        citations: list[dict] = []
        related: list[str] = []

        if kind == KIND_VPN_REDIRECT:
            result = await self._handle_vpn_redirect(text, tracker)
            disposition = result["disposition"]
            answer = result["answer"]

        elif kind == KIND_OWNERSHIP:
            result = await self._handle_ownership(text, services, clearance, tracker)
            disposition = result["disposition"]
            answer = result["answer"]
            citations = result["citations"]

        elif kind == KIND_ANSWERABLE:
            result = await self._handle_answerable(text, services, clearance, tracker)
            disposition = result["disposition"]
            answer = result["answer"]
            citations = result["citations"]
            related = result["related"]

        elif kind == KIND_ASK_WHAT_TO_DO:
            result = await self._handle_ask_what_to_do(text, services, clearance, tracker)
            disposition = result["disposition"]
            answer = result["answer"]
            citations = result["citations"]
            related = result["related"]

        elif kind == KIND_LIVE_PROBLEM:
            result = await self._handle_live_problem(text, services, tracker, clearance)
            disposition = result["disposition"]
            answer = result["answer"]
            routed_to = result.get("routed_to")
            citations = result["citations"]
            related = result["related"]

        elif kind == KIND_ASK_ACTION:
            result = await self._handle_action_request(
                text, services, action, filer, tracker
            )
            disposition = result["disposition"]
            answer = result["answer"]
            related = result["related"]

        else:
            result = await self._handle_answerable(text, services, clearance, tracker)
            disposition = result["disposition"]
            answer = result["answer"]
            citations = result["citations"]
            related = result["related"]

        return self._build_response(
            disposition=disposition,
            answer=answer,
            tracker=tracker,
            routed_to=routed_to,
            citations=citations,
            related=related,
        )

    # ── Kind handlers ───────────────────────────────────────────────────

    async def _handle_vpn_redirect(
        self, text: str, tracker: StepTracker
    ) -> dict:
        """VPN/wifi/all-hands: redirect, never refused."""
        tracker.plan("Redirect to self-service", "Matched VPN/wifi/all-hands redirect pattern")

        answer = (
            "This sounds like a VPN, wifi, or all-hands access request. "
            "Please visit https://fenwick.cloud/self-service/access for "
            "self-service options to resolve this."
        )
        tracker.ok("redirect", "Provided self-service redirect")

        return {"disposition": "answered", "answer": answer}

    async def _handle_ownership(
        self, text: str, services: list[str], clearance: str, tracker: StepTracker
    ) -> dict:
        """Who owns X: answered from service catalog."""
        tracker.plan("Look up service ownership", "Find owning team from service registry")

        if not services:
            tracker.failed("lookup_ownership", "No services identified in ticket")
            return {
                "disposition": "answered",
                "answer": "I couldn't identify which service you're asking about. Please specify a service name.",
                "citations": [],
            }

        svc = services[0]
        svc_info = await self._service_catalog.find_service(svc)
        if svc_info:
            tracker.ok("lookup_ownership", f"{svc} owned by {svc_info.get('owning_team', 'Unknown')}")
            return {
                "disposition": "answered",
                "answer": f"The service '{svc}' is owned by the **{svc_info.get('owning_team')}** team and is currently **{svc_info.get('status')}**.",
                "citations": [{"source": "service_registry.csv", "reference": svc}],
            }
        else:
            tracker.failed("lookup_ownership", f"Service '{svc}' not found in registry")
            return {
                "disposition": "answered",
                "answer": f"Could not find service '{svc}' in the service registry.",
                "citations": [],
            }

    async def _handle_answerable(
        self, text: str, services: list[str], clearance: str, tracker: StepTracker
    ) -> dict:
        """Answerable from documents: search, filter by clearance, cite best match.

        Per §6: If matching restricted documents exist and the filer is not
        cleared, refuse. A weak tangential match (e.g. a runbook that mentions
        a service in passing) does not override this — the real answer is
        behind the clearance wall.
        """
        tracker.plan("Search documents", "Find relevant documents by keyword matching")

        # If the filer has general clearance, check whether restricted documents
        # are the best match BEFORE the filtered search (a weak tangential hit
        # like a runbook that merely mentions a service should not bypass the
        # clearance wall per §6).
        if clearance == "general":
            restricted_names = self._check_restricted_docs_match(text)
            if restricted_names:
                tracker.failed("search_documents",
                               f"Restricted document(s) exist but require higher clearance: "
                               f"{', '.join(restricted_names)}")
                return {
                    "disposition": "refused",
                    "answer": (
                        f"A document matching your query exists but requires restricted clearance "
                        f"to view. Please contact your team lead or the document owner "
                        f"if you need access."
                    ),
                    "citations": [],
                    "related": [],
                }

        try:
            docs_result = await self._doc_store.search(text, clearance)
        except TimeoutError as e:
            # §8: local lookup timeout → step recorded as `timeout`.
            tracker.timeout("search_documents", f"Document store timed out: {e}")
            return {
                "disposition": "answered",
                "answer": "",
                "citations": [],
                "related": [],
            }
        except ConnectionError as e:
            tracker.failed("search_documents", f"Document store unavailable: {e}")
            return {
                "disposition": "answered",
                "answer": "",
                "citations": [],
                "related": [],
            }

        citations = []
        for doc in docs_result[:2]:
            ref_text = doc.get("text", "")[:200]
            citations.append({
                "source": doc.get("filename", ""),
                "reference": ref_text,
            })

        if docs_result:
            best = docs_result[0]
            answer_text = best.get("text", "")
            tracker.ok("search_documents", f"Found {len(docs_result)} matching documents")

            # Draft label is always added by code, never by the model.
            if best.get("is_draft"):
                answer_text = f"[DRAFT — not yet finalized]\n\n{answer_text}"

            # Also check for related open incidents
            related = await self._find_related_incidents(services, tracker)

            # Call 2: attempt model compose for a better answer.
            # Send at most the top 2 docs that passed clearance, 8 000 chars total.
            model_answer = await self._llm.compose_answer(
                text, docs_result[:2], clearance
            )
            if model_answer:
                tracker.ok("model_compose_answer",
                           f"Model composed answer ({len(model_answer)} chars)")
                # Draft label stays applied by code even if model composed.
                if best.get("is_draft"):
                    model_answer = f"[DRAFT — not yet finalized]\n\n{model_answer}"
                answer_text = model_answer
            else:
                # Keep the extractive answer on failure — no step recorded;
                # the adapter already logged the reason.
                pass

            return {
                "disposition": "answered",
                "answer": answer_text,
                "citations": citations,
                "related": related,
            }
        else:
            tracker.ok("search_documents", "No matching documents found")
            return {
                "disposition": "answered",
                "answer": "I couldn't find a document that answers this question. Please contact your team lead.",
                "citations": [],
                "related": [],
            }

    async def _handle_ask_what_to_do(
        self, text: str, services: list[str], clearance: str, tracker: StepTracker
    ) -> dict:
        """Asks what to do: document search + incident match in related."""
        result = await self._handle_answerable(text, services, clearance, tracker)
        # Also match incidents even if no document found
        if not result["related"]:
            related = await self._find_related_incidents(services, tracker)
            result["related"] = related
        return result

    async def _handle_live_problem(
        self, text: str, services: list[str], tracker: StepTracker,
        clearance: str
    ) -> dict:
        """Live problem: check open incidents, then route or duplicate."""
        tracker.plan("Check open incidents", "Look for matching open/live incidents")

        try:
            matches = await self._incident_tracker.find_matching_incidents(text, services)
        except TimeoutError as e:
            # §8: local lookup timeout → step recorded as `timeout`.
            tracker.timeout("check_incidents", f"Incident lookup timed out: {e}")
            # Cannot check for duplicates — route the report
            return await self._route_to_oncall(services[0] if services else "", tracker,
                                                citations=[], related=[],
                                                note="Incident tracker timed out — could not check for duplicates")
        except ConnectionError as e:
            tracker.failed("check_incidents", f"Cannot check live incidents: {e}")
            # Cannot check for duplicates — route the report
            return await self._route_to_oncall(services[0] if services else "", tracker,
                                                citations=[], related=[],
                                                note="Incident tracker unavailable — could not check for duplicates")

        if matches:
            live = [m for m in matches if m.get("is_live")]
            if live:
                tracker.ok("check_incidents", f"Found {len(live)} live matching incident(s)")
                # Duplicate: link as related
                related = [m["incident_id"] for m in live[:3]]
                inc = live[0]
                return {
                    "disposition": "duplicate",
                    "answer": f"This appears to be related to an existing open incident {inc['incident_id']} ({inc.get('summary', '')}). The incident is being actively worked on.",
                    "citations": [{"source": "incident_log.csv", "reference": inc["incident_id"]}],
                    "related": related,
                    "routed_to": None,
                }
            else:
                tracker.ok("check_incidents", "Found open incidents but none are live")
                # Check duplicates with hand-off queue
                dup = await self._check_duplicate(text, services, tracker)
                if dup:
                    return {
                        "disposition": "duplicate",
                        "answer": f"This appears to be a duplicate of ticket {dup['ticket_id']} filed earlier. The issue is already being tracked.",
                        "citations": [{"source": "open_tickets.csv", "reference": dup.get("ticket_id", "")}],
                        "related": [dup.get("ticket_id", "")],
                        "routed_to": None,
                    }
        else:
            tracker.ok("check_incidents", "No matching open incidents found")

        # No live incident → route to on-call
        # First check duplicate with hand-off queue
        if not services:
            tracker.failed("route_problem", "No services identified for routing")
            return {
                "disposition": "refused",
                "answer": "Could not identify a service from your ticket. Please specify which service you're reporting an issue with.",
                "citations": [],
                "related": [],
                "routed_to": None,
            }

        return await self._route_to_oncall(services[0], tracker,
                                            citations=[], related=[])

    async def _handle_action_request(
        self,
        text: str,
        services: list[str],
        action: str | None,
        filer: dict | None,
        tracker: StepTracker,
    ) -> dict:
        """Action request: check authorization, record decision."""
        tracker.plan("Check action authorization", "Verify filer is authorized for the requested action")

        svc = services[0] if services else None
        decision = _decide_action(
            filer, action, svc,
            self._services_cache, self._roster_cache, self._incidents_cache
        )

        disposition = decision["disposition"]
        reason = decision["reason"]

        # Record the decision (dry-run)
        try:
            await self._incident_tracker.record_decision(decision)
            tracker.ok("record_decision", f"Action '{action}' recorded (dry-run)")
        except TimeoutError as e:
            tracker.timeout("record_decision", f"Decision write timed out: {e}")
        except ConnectionError as e:
            tracker.failed("record_decision", f"Failed to record decision: {e}")

        if disposition == "action_decided":
            tracker.ok("check_authorization", reason)

            # Find related open incidents
            related = []
            if svc:
                try:
                    matches = await self._incident_tracker.find_matching_incidents(text, [svc])
                    if matches:
                        related = [m["incident_id"] for m in matches[:3]]
                except (ConnectionError, TimeoutError):
                    pass

            return {
                "disposition": "action_decided",
                "answer": f"Action authorised: {action} on {svc}. {reason}",
                "related": related,
            }
        else:
            tracker.failed("check_authorization", reason)
            return {
                "disposition": "refused",
                "answer": f"Action not authorised: {reason}",
                "related": [],
            }

    # ── Shared helpers ──────────────────────────────────────────────────

    async def _route_to_oncall(
        self, service_name: str, tracker: StepTracker,
        citations: list[dict] | None = None,
        related: list[str] | None = None,
        note: str = "",
    ) -> dict:
        """Route a problem to the on-call engineer."""
        tracker.plan("Route to on-call", f"Find on-call engineer for {service_name}")

        try:
            oncall_result = await self._oncall.get_oncall(service_name)
        except (ConnectionError, TimeoutError):
            # This shouldn't happen since the adapter handles this internally,
            # but just in case.
            owning_team = self._find_owning_team(service_name)
            tracker.failed("route_to_oncall", f"On-call scheduler unavailable, routing to {owning_team} channel")
            return {
                "disposition": "routed",
                "answer": f"On-call scheduler is unavailable. Your issue has been routed to the {owning_team} team channel.",
                "routed_to": f"{owning_team} channel",
                "citations": citations or [],
                "related": related or [],
            }

        routed_to = oncall_result.get("routed_to", "")
        if oncall_result.get("oncall_found"):
            tracker.ok("route_to_oncall", f"Routed to {routed_to}")
        else:
            tracker.ok("route_to_oncall", f"On-call not found, routed to {routed_to}")

        answer = f"Your issue has been routed to {routed_to} for investigation."
        if note:
            answer = f"{note}\n\n{answer}"

        return {
            "disposition": "routed",
            "answer": answer,
            "routed_to": routed_to,
            "citations": citations or [],
            "related": related or [],
        }

    async def _check_duplicate(
        self, text: str, services: list[str], tracker: StepTracker
    ) -> dict | None:
        """Check for duplicates in the hand-off queue."""
        tracker.plan("Check duplicate tickets", "Look for same-service same-symptom tickets within 2h")
        from engine.duplicate_check import check_duplicate
        dup = _check_duplicate(text, services, self._open_tickets)
        if dup:
            tracker.ok("check_duplicate", f"Duplicate of {dup.get('ticket_id', 'unknown')}")
        else:
            tracker.ok("check_duplicate", "No duplicates found")
        return dup

    async def _find_related_incidents(
        self, services: list[str], tracker: StepTracker
    ) -> list[str]:
        """Find open incidents related to identified services."""
        if not services:
            return []
        try:
            matches = await self._incident_tracker.find_matching_incidents(
                " ".join(services), services
            )
            if matches:
                tracker.ok("find_related_incidents",
                           f"Found {len(matches)} related incident(s)")
                return [m["incident_id"] for m in matches[:3]]
        except (ConnectionError, TimeoutError):
            tracker.skipped("find_related_incidents",
                            "Incident tracker unavailable, skipping")
        return []

    def _find_owning_team(self, service_name: str) -> str:
        from ingest.normalize import normalize_service as _norm
        svc_norm = _norm(service_name)
        for svc in self._services_cache:
            if svc.get("service_name_normalized", "") == svc_norm:
                return svc.get("owning_team", "Unknown")
        return "Unknown"

    def _check_restricted_docs_match(self, text: str) -> list[str]:
        """Check if restricted documents match more strongly than general docs.

        Does an unfiltered document search and compares top scores. If the
        highest-scoring restricted document has a significantly higher score
        than the highest-scoring general document, the real answer is behind
        the clearance wall → return the restricted doc names.

        Per §6: Filer not cleared for document → refused.
        Per Q8: a general filer asking about the auth-gateway postmortem
        must be refused (the runbook that merely mentions "auth-gateway"
        is not a real answer).
        """
        if not self._documents_cache or not text:
            return []
        from engine.document_search import search as _search_unfiltered

        # Score the best general doc
        general_results = _search_unfiltered(text, self._documents_cache, "general", top_k=1)
        general_best_score = general_results[0]["relevance_score"] if general_results else 0

        # Score the best restricted doc (search as "restricted" to allow restricted docs through)
        restricted_results = _search_unfiltered(text, self._documents_cache, "restricted", top_k=3)
        restricted_best = [
            r for r in restricted_results if r["restricted"]
        ]
        if not restricted_best:
            return []
        restricted_best_score = restricted_best[0]["relevance_score"]

        # Refuse only if a restricted document is a substantially better match
        # (score ratio >= 2x or restricted score >= 4 higher than general).
        if restricted_best_score >= 4 or (general_best_score > 0
                                          and restricted_best_score >= general_best_score * 2):
            return [r["filename"] for r in restricted_best[:2]]

        return []

    # ── Response builder ───────────────────────────────────────────────

    def _build_response(
        self,
        *,
        disposition: str,
        answer: str,
        tracker: StepTracker,
        routed_to: str | None = None,
        citations: list[dict] | None = None,
        related: list[str] | None = None,
    ) -> dict:
        """Build the full API response dict."""
        return {
            "ticket_id": None,
            "disposition": disposition,
            "answer": answer,
            "plan": tracker.get_plan(),
            "steps_run": tracker.get_steps_run(),
            "routed_to": routed_to,
            "citations": citations or [],
            "related": related or [],
        }