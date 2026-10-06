"""Determine on-call for a service.

Rules:
  - F-05: Deprecated services with on-call entries must not crash.
  - F-07: SRE engineers are reachable for on-call even though they own no service.
  - On-call unavailable → route to owning team channel.
  - routed_to convention: on-call engineer's full name, or "<team> channel".
"""

from __future__ import annotations

from typing import Any

from ingest.normalize import normalize_service


def get_oncall(
    service_name: str,
    oncall_schedule: list[dict],
    roster: list[dict],
    services: list[dict],
) -> dict:
    """Find the currently-active on-call engineer for a service.

    Args:
        service_name: Normalized service name.
        oncall_schedule: On-call schedule from csv_loader.
        roster: Engineer roster.
        services: Service registry (for owning team lookup).

    Returns:
        Dict with keys:
          - engineer_name: str or None
          - engineer_emp_id: str or None
          - routed_to: str (engineer name or "<team> channel")
          - oncall_found: bool
          - owning_team: str
    """
    owning_team = _find_owning_team(service_name, services)

    # Normalize the service name to compare against on-call schedule
    svc_normalized = normalize_service(service_name)

    # Find currently active on-call entries for this service
    active_entries = []
    for entry in oncall_schedule:
        entry_service = normalize_service(entry.get("service_name_raw", ""))
        if entry_service != svc_normalized:
            continue
        if entry.get("currently_active", "").strip().lower() == "true":
            active_entries.append(entry)

    if not active_entries:
        # On-call unavailable → route to owning team channel
        return {
            "engineer_name": None,
            "engineer_emp_id": None,
            "routed_to": f"{owning_team} channel",
            "oncall_found": False,
            "owning_team": owning_team,
        }

    # Pick first active entry
    oncall = active_entries[0]
    emp_id = oncall.get("engineer_emp_id", "")

    # Look up engineer name from roster
    engineer_name = _get_engineer_name(emp_id, roster)

    if engineer_name:
        return {
            "engineer_name": engineer_name,
            "engineer_emp_id": emp_id,
            "routed_to": engineer_name,
            "oncall_found": True,
            "owning_team": owning_team,
        }

    # Engineer ID not found in roster → fallback to team channel
    return {
        "engineer_name": None,
        "engineer_emp_id": emp_id,
        "routed_to": f"{owning_team} channel",
        "oncall_found": True,
        "owning_team": owning_team,
    }


def resolve_routing(
    service_name: str,
    oncall_schedule: list[dict],
    roster: list[dict],
    services: list[dict],
) -> str:
    """Resolve the routing destination for a service.

    Returns the routed_to string directly.
    """
    result = get_oncall(service_name, oncall_schedule, roster, services)
    return result["routed_to"]


# ── Internal helpers ─────────────────────────────────────────────────────


def _find_owning_team(service_name: str, services: list[dict]) -> str:
    """Find the owning team for a service."""
    svc_norm = normalize_service(service_name)
    for svc in services:
        if svc.get("service_name_normalized", "") == svc_norm:
            return svc.get("owning_team", "Unknown")
    return "Unknown"


def _get_engineer_name(emp_id: str, roster: list[dict]) -> str | None:
    for entry in roster:
        if entry.get("emp_id", "") == emp_id:
            return entry.get("name", None)
    return None