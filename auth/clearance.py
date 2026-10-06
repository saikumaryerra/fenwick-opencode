"""Compute clearance from team/title per policy (F-01).

Clearance is COMPUTED from team+title per policy, not trusted from the
roster's `clearance_tier` column.

Policy (from policy_access_and_clearance.docx):
  - Security team members → restricted
  - Anyone with 'Senior' in their title → restricted
  - SRE team members → restricted
  - All others → general
"""

_SENIOR_KEYWORDS = ["senior", "staff", "lead", "principal"]

# Teams that get restricted clearance regardless of title.
_RESTRICTED_TEAMS = {"security", "sre"}


def compute_clearance(team: str, title: str) -> str:
    """Compute clearance level from team and title.

    Returns 'restricted' or 'general'.
    """
    team_lower = team.strip().lower()
    title_lower = title.strip().lower()

    # Security and SRE teams get restricted clearance.
    if team_lower in _RESTRICTED_TEAMS:
        return "restricted"

    # Senior/Staff/Lead/Principal titles get restricted clearance.
    for kw in _SENIOR_KEYWORDS:
        if kw in title_lower:
            return "restricted"

    # Everyone else is general.
    return "general"


def can_see_document(
    filer_clearance: str, document_restricted: bool
) -> bool:
    """Check if a filer with given clearance can see a document.

    'restricted' clearance → can see both restricted and general docs.
    'general' clearance → can only see general docs.
    """
    if not document_restricted:
        return True
    return filer_clearance == "restricted"


def get_filer(roster: list[dict], emp_id: str) -> dict | None:
    """Look up a filer by employee ID in the roster.

    Returns the roster entry or None if not found.
    """
    for entry in roster:
        if entry["emp_id"] == emp_id:
            return entry
    return None