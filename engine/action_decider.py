"""Decide if a filer may request an action; record dry-run decision.

Authorisation rules:
  - Filer is authorised for an action if they are an engineer in the roster
    for an active service.
  - Exception: close-incident requires owning team or someone who has posted
    on that incident (DECISIONS Q4).
  - Deprecated services → tell owning team, don't page.
  - Never grants clearance, never rolls back, deploys or restarts.
"""

from __future__ import annotations

from typing import Any

from ingest.normalize import normalize_service


# Actions the system will never perform.
_FORBIDDEN_ACTIONS = {"grant_access", "clearance", "rollback", "deploy", "restart"}

# Actions that are performable (dry-run).
_PERFORMABLE_ACTIONS = {"page_oncall", "open_incident", "close_incident", "change_production"}


def is_authorized_for_action(
    filer: dict | None,
    action: str | None,
    service_name: str | None,
    services: list[dict],
    roster: list[dict],
    incidents: list[dict] | None = None,
) -> tuple[bool, str]:
    """Check if a filer is authorised for a requested action.

    Args:
        filer: Roster entry for the filer, or None if not found.
        action: The action requested (from classify).
        service_name: Normalized service name (or None).
        services: Full service registry.
        roster: Full engineer roster.
        incidents: Incident list (needed for close_incident).

    Returns:
        (authorized: bool, reason: str)
    """
    if filer is None:
        return False, "Filer not found in roster"

    if action is None:
        return False, "No action requested"

    # Forbidden actions
    if action in _FORBIDDEN_ACTIONS:
        return False, f"Action '{action}' is not permitted by policy"

    if action not in _PERFORMABLE_ACTIONS:
        return False, f"Unknown action '{action}'"

    # If no service identified, check if filer is an engineer at all
    if not service_name:
        # General action request without specific service
        return False, "No service identified for action"

    # Look up service
    svc = _find_service(service_name, services)
    if svc is None:
        return False, f"Service '{service_name}' not found in registry"

    # Check if service is deprecated
    if svc.get("status", "").strip().lower() == "deprecated":
        return False, f"Service '{service_name}' is deprecated; notify owning team instead"

    # Filer must be an engineer (have emp_id in roster)
    filer_id = filer.get("emp_id", "")
    if not filer_id:
        return False, "Filer identity not resolvable"

    # For close_incident: special rules
    if action == "close_incident":
        return _authorized_close_incident(filer, service_name, services, incidents)

    # For all other actions: filer must be on the owning team or an SRE
    owning_team = svc.get("owning_team", "").strip()
    filer_team = filer.get("team", "").strip()

    if filer_team == owning_team or filer_team == "SRE":
        return True, f"Filer is on {filer_team}, authorised for {action} on {service_name}"

    # Security team can authorise actions
    if filer_team == "Security":
        return True, f"Security team member authorised for {action} on {service_name}"

    return False, f"Filer on {filer_team} is not authorised for {action} on {service_name} (requires {owning_team})"


def decide_action(
    filer: dict | None,
    action: str | None,
    service_name: str | None,
    services: list[dict],
    roster: list[dict],
    incidents: list[dict] | None = None,
) -> dict:
    """Decide whether to record an action decision (dry run).

    Returns a decision dict:
      - authorized: bool
      - disposition: 'action_decided' or 'refused'
      - reason: str
      - action: str or None
    """
    authorized, reason = is_authorized_for_action(
        filer, action, service_name, services, roster, incidents
    )

    if authorized:
        return {
            "authorized": True,
            "disposition": "action_decided",
            "reason": reason,
            "action": action,
        }
    else:
        return {
            "authorized": False,
            "disposition": "refused",
            "reason": reason,
            "action": action,
        }


def record_decision(decision: dict) -> None:
    """Record a decision (dry run — no side effect in this build).

    In production: write to SQLite with idempotency key.
    """
    # This build records the decision only (dry run).
    pass


def _find_service(normalized_name: str, services: list[dict]) -> dict | None:
    for svc in services:
        if svc.get("service_name_normalized", "") == normalized_name:
            return svc
    return None


def _authorized_close_incident(
    filer: dict,
    service_name: str,
    services: list[dict],
    incidents: list[dict] | None,
) -> tuple[bool, str]:
    """Close-incident requires owning team or someone who posted on that incident."""
    svc = _find_service(service_name, services)
    if svc is None:
        return False, f"Service '{service_name}' not found"

    owning_team = svc.get("owning_team", "").strip()
    filer_team = filer.get("team", "").strip()
    filer_id = filer.get("emp_id", "")

    # Owning team can always close
    if filer_team == owning_team:
        return True, f"Filer on owning team {owning_team}, authorised to close"

    # Check if filer has posted on any open incident for this service
    if incidents:
        for inc in incidents:
            inc_service = normalize_service(inc.get("service_name_raw", ""))
            if inc_service != service_name:
                continue
            for upd in inc.get("updates_parsed", []):
                if upd.get("emp_id", "") == filer_id:
                    return True, f"Filer has posted updates on an incident for {service_name}"
    return False, f"Filer not on owning team ({owning_team}) and has not posted on any incident for {service_name}"