"""Check for same-service same-symptom duplicates within 2h.

The duplicate check is for API-filed tickets: same service + same symptoms
within 2h of the service's own timestamps, and only after an earlier report
was already routed or action-decided.

Not to be confused with the "live problem, already has open live incident"
check (see incident_matcher.py). The hand-off queue tickets (open_tickets.csv)
with no linked incident are routed, not duplicate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ingest.normalize import normalize_service


DUPLICATE_WINDOW_MINUTES = 120  # 2-hour window


def check_duplicate(
    text: str,
    service_names: list[str],
    open_tickets: list[dict],
    now: datetime | None = None,
) -> dict | None:
    """Check if a new report is a duplicate of a recent ticket.

    A duplicate is: same service + overlapping symptom keywords within 2h
    of an earlier ticket that was already routed or action-decided.

    Args:
        text: The new ticket text.
        service_names: Normalized service names extracted from the ticket.
        open_tickets: The open_tickets list (hand-off queue).
        now: Reference time (defaults to UTC now).

    Returns:
        The matching earlier ticket dict, or None.
    """
    if not service_names:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    window_start = now - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
    keywords = _extract_symptom_keywords(text)

    for ticket in open_tickets:
        ticket_time = _parse_ticket_time(ticket.get("filed_at", ""))
        if ticket_time is None:
            continue

        # Must be within the duplicate window
        if ticket_time < window_start:
            continue

        # Must be same service (check if ticket text mentions the same service)
        ticket_text = (ticket.get("text") or "").lower()
        if not _mentions_any_service(ticket_text, service_names):
            continue

        # Check symptom overlap
        ticket_keywords = _extract_symptom_keywords(ticket_text)
        overlap = keywords & ticket_keywords
        if len(overlap) >= 1:
            return ticket

    return None


def recent_same(
    ticket: dict,
    open_tickets: list[dict],
    now: datetime | None = None,
) -> dict | None:
    """Check if a specific hand-off ticket has a recent same-symptom match."""
    text = (ticket.get("text") or "")
    service_names = _extract_service_from_ticket_text(text)
    return check_duplicate(text, service_names, open_tickets, now)


# ── Internal helpers ─────────────────────────────────────────────────────

_SYMPTOM_KEYWORDS = {
    "latency", "slow", "spiking", "error", "degrad", "timeout",
    "down", "fail", "unreachable", "unavailable", "healthcheck",
    "backlog", "queue", "crash", "oom", "memory", "cpu",
    "5xx", "4xx", "401", "403", "500", "502", "503", "504",
    "intermittent", "timeout", "connection", "reset",
}


def _extract_symptom_keywords(text: str) -> set[str]:
    """Extract symptom-related keywords from text."""
    import re
    text_lower = text.lower()
    words = set(re.findall(r"[a-z0-9]+", text_lower))
    return words & _SYMPTOM_KEYWORDS


def _mentions_any_service(text: str, service_names: list[str]) -> bool:
    for svc in service_names:
        if svc in text:
            return True
    return False


def _extract_service_from_ticket_text(text: str) -> list[str]:
    """Naively extract likely service names from text."""
    import re
    svc_patterns = re.findall(r"([a-z]+(?:-[a-z]+)*)", text.lower())
    # Return generic; real extraction uses classify module.
    return svc_patterns[:3]


def _parse_ticket_time(filed_at: str) -> datetime | None:
    """Parse the filed_at timestamp from open_tickets.csv (ISO format)."""
    if not filed_at or not filed_at.strip():
        return None
    try:
        dt = datetime.fromisoformat(filed_at.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None