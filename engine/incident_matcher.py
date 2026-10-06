"""Match ticket to open/live incidents (F-08).

A "live" incident is an open incident with at least one non-boilerplate update.
"Boilerplate" means any update matching the pattern "Investigating, no update yet".
No age cutoff.

Both INC-NNNN and INC-NNNNNN are valid incident IDs (F-08).
"""

from __future__ import annotations

import re
from typing import Any

from ingest.normalize import normalize_incident_id


# The sole boilerplate variant observed in the data.
_BOILERPLATE_NOTE = "investigating, no update yet"


def find_matching_incidents(
    ticket_text: str,
    service_names: list[str],
    incidents: list[dict],
) -> list[dict]:
    """Find open/live incidents matching a ticket's service + symptoms.

    Args:
        ticket_text: The ticket text (lowercased for matching).
        service_names: Normalized service names extracted from the ticket.
        incidents: Full incident list from csv_loader.load_incidents().

    Returns:
        List of matching incident dicts. Each returned incident is either
        'live' (open + non-boilerplate update) or 'open' (open, any update).
        Incidents are sorted by match quality: live > open, then by date recency.
    """
    matches: list[dict] = []

    for inc in incidents:
        # Must be open
        if inc.get("status", "").strip().lower() != "open":
            continue

        # Check service match (normalized comparison)
        inc_service = inc.get("service_normalized", "")
        if not inc_service or inc_service not in service_names:
            # Try matching against raw service name too
            raw = inc.get("service_name_raw", "")
            if not raw or normalize_service_simple(raw) not in service_names:
                continue

        # Determine if live
        is_live = _is_live_incident(inc)

        # Build a clean result
        result = {
            "incident_id": inc.get("incident_id", ""),
            "incident_id_normalized": normalize_incident_id(inc.get("incident_id", "")),
            "service_name": inc_service,
            "severity": inc.get("severity", ""),
            "summary": inc.get("one_line_summary", ""),
            "date": inc.get("date", ""),
            "is_live": is_live,
            "update_count": len(inc.get("updates_parsed", [])),
        }
        matches.append(result)

    # Sort: live first, then by date (most recent first)
    def _date_sort_key(m: dict) -> tuple:
        inc = next(
            (i for i in incidents
             if normalize_incident_id(i.get("incident_id", ""))
                == m.get("incident_id_normalized", "")),
            None,
        )
        parsed = inc.get("date_parsed") if inc else None
        # Reverse-chronological: more recent = lower sort value
        live_sort = 0 if m["is_live"] else 1
        if parsed:
            return (live_sort, -parsed.timestamp())
        return (live_sort, 0)

    matches.sort(key=_date_sort_key)

    return matches


def is_live(incident: dict) -> bool:
    """Check if an incident dict represents a live incident."""
    return _is_live_incident(incident)


def has_non_boilerplate_updates(updates_parsed: list[dict]) -> bool:
    """Check if any update is non-boilerplate."""
    for upd in updates_parsed:
        note = (upd.get("note") or "").strip().lower()
        if note and note != _BOILERPLATE_NOTE:
            return True
    return False


# ── Internal helpers ─────────────────────────────────────────────────────


def _is_live_incident(incident: dict) -> bool:
    """An incident is live if open + has >=1 non-boilerplate update."""
    if incident.get("status", "").strip().lower() != "open":
        return False
    updates_parsed = incident.get("updates_parsed", [])
    return has_non_boilerplate_updates(updates_parsed)


def normalize_service_simple(name: str) -> str:
    """Simple normalization for incident matching."""
    return name.strip().lower().replace("_", "-")