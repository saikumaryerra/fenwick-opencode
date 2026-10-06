"""Label ticket: kind, services, actions requested.

Uses keyword rules for classification. An LLM-based classifier wraps this
fallback (see rules.py for the rule-based implementation).
"""

from __future__ import annotations

import re

# Kind labels returned by classify().
KIND_ANSWERABLE = "answerable"          # Document has the answer
KIND_ASK_ACTION = "requests_action"     # Filer is requesting an action (page, open/close incident, etc.)
KIND_ASK_WHAT_TO_DO = "asks_what_to_do" # Wants guidance, document may answer + incident match
KIND_LIVE_PROBLEM = "live_problem"      # Describes a live/latent problem
KIND_VPN_REDIRECT = "vpn_redirect"      # VPN/wifi/all-hands redirect
KIND_OWNERSHIP = "ownership_query"      # "Who owns X?"
KIND_GENERAL_QUERY = "general_query"    # Catch-all


def classify(text: str, services: list[dict]) -> dict:
    """Classify a ticket.

    Returns dict with keys:
      - kind: one of the KIND_* constants
      - services: list of normalized service names mentioned
      - action_requested: str or None — what action was asked for
    """
    text_lower = text.lower().strip()

    # 1. VPN / wifi / all-hands → redirect (highest priority match)
    if _is_vpn_redirect(text_lower):
        return {"kind": KIND_VPN_REDIRECT, "services": [], "action_requested": None}

    # 2. Extract services mentioned (needed by multiple checks below)
    svcs = _extract_services(text_lower, services)

    # 3. Ownership queries (checked BEFORE action requests so
    #    "who's on call" → ownership, not action request)
    if _is_ownership_query(text_lower):
        return {"kind": KIND_OWNERSHIP, "services": svcs, "action_requested": None}

    # 4. Asks what to do — wants guidance (checked BEFORE action requests so
    #    "…after today's deploy, what should I do" → asks_what_to_do, not an
    #    action request. Q8: ticket A is answered from the runbook. A plain
    #    action request ("page the on-call") never matches these patterns.)
    if _is_ask_what_to_do(text_lower):
        return {"kind": KIND_ASK_WHAT_TO_DO, "services": svcs, "action_requested": None}

    # 5. Detect action requests
    action = _detect_action_request(text_lower)
    if action:
        return {"kind": KIND_ASK_ACTION, "services": svcs, "action_requested": action}

    # 6. Live problem keywords
    if _is_live_problem(text_lower):
        return {"kind": KIND_LIVE_PROBLEM, "services": svcs, "action_requested": None}

    # 7. Has a known service mentioned → likely answerable from docs
    if svcs:
        return {"kind": KIND_ANSWERABLE, "services": svcs, "action_requested": None}

    return {"kind": KIND_GENERAL_QUERY, "services": [], "action_requested": None}


# ── Keyword helpers ──────────────────────────────────────────────────────

_VPN_KEYWORDS = [
    "vpn", "wifi", "all-hands", "all hands",
    "redirect", "can't connect", "cannot connect",
    "laptop won't connect", "network access",
]


def _is_vpn_redirect(text: str) -> bool:
    for kw in _VPN_KEYWORDS:
        if kw in text:
            return True
    return False


_ACTION_PATTERNS: list[tuple[str, str]] = [
    (r"\broll\s*back\b", "rollback"),
    (r"\bdeploy\b", "deploy"),
    (r"\brestart\b", "restart"),
    (r"\bpage\b\s+\S*\s*\bon.?call\b", "page_oncall"),
    (r"\bopen\s+(an?\s+)?incident\b", "open_incident"),
    (r"\bclose\s+(an?\s+)?incident\b", "close_incident"),
    (r"((i|we)\s+)?\bgrant\s+(access|clearance|permission)\b", "grant_access"),
    (r"\breset\s+(my\s+)?(password|token|vpn|access|credential)\b", None),  # reset vpn is a redirect
    (r"\bchange\s+(prod|production|access)\b", "change_production"),
    (r"\bon.?call\s+(for|is|page)\b", "page_oncall"),
]


def _detect_action_request(text: str) -> str | None:
    # If the text is asking about documentation (runbook, how-to, what's a…),
    # skip action detection — this is a documentation query, not an action request.
    # Matches question/procedure indicators before an action verb, including
    # spaced forms ("what is …", "how to …") so information requests about a
    # procedure are never misread as directives to perform it.
    if re.search(
        r"\b(what[\s']*is|what.s|how[\s']*(do|to|does)|where.is|"
        r"procedure|steps?|runbook|document|guide|question|way)\b.*"
        r"\b(roll\s*back|deploy|restart|page|on.call|incident)\b",
        text,
    ):
        return None
    for pattern, action_label in _ACTION_PATTERNS:
        if re.search(pattern, text):
            if action_label is not None:
                return action_label
            # pattern has action_label=None → it's a non-action match (e.g. vpn reset)
            return None
    return None


def _is_ownership_query(text: str) -> bool:
    patterns = [
        r"who\s+owns?\b",
        r"who\s+is\s+(the\s+)?on.?call\b",
        r"who.s\s+on.?call\b",
        r"who\s+(manages?|handles?)\b",
        r"who\s+(do|can|should)\b.*\bon.?call\b",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _is_live_problem(text: str) -> bool:
    patterns = [
        r"(is|looks?\s+|seems?\s+)?(down|slow|spiking|failing|error)",
        r"(healthcheck|latency|timeout|degrad)",
        r"can\s+(anyone|some(?:one|body))\s+(check|look|see)\b",
        r"is\s+(anyone|this|there)\s+(already\s+)?(on|working)\b",
        r"is\s+this\s+(known|being\s+(looked|worked))\b",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _is_ask_what_to_do(text: str) -> bool:
    patterns = [
        r"what\s+(should|do|shall|can)\s+(i|we)\b",
        r"how\s+(should|do|shall|can)\s+(i|we)\b",
        r"what\s+(did|was)\s+(we|the)\b.*conclud",
        r"what\s+is\s+the\s+(plan|next.step)\b",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _extract_services(text: str, services: list[dict]) -> list[str]:
    """Find known service names mentioned in the text.

    Matches on:
    1. Full service name substring (e.g. "checkout-service" in text).
    2. Hyphen-separated prefix, only when no exact matches exist.
       This handles shorthand references like "checkout" → "checkout-service"
       without creating false matches when the full name is also present
       (e.g. "billing-sync" should not also match "billing-worker").
    """
    from ingest.normalize import normalize_service

    exact_matches: list[str] = []
    prefix_matches: list[str] = []
    text_lower = text.lower()

    for svc in services:
        name = svc.get("service_name", "")
        name_lower = name.lower()
        if name_lower in text_lower:
            exact_matches.append(normalize_service(name))
            continue
        # Prefix match (shorthand): only if no exact match for this service
        parts = name_lower.split("-")
        if len(parts) > 1 and parts[0] in text_lower:
            prefix_matches.append(normalize_service(name))

    # Prefer exact matches; fall back to prefix matches
    results = exact_matches if exact_matches else prefix_matches

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for s in results:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def extract_services(text: str, services: list[dict]) -> list[str]:
    """Public wrapper: extract normalized service names from ticket text."""
    return _extract_services(text, services)


def extract_action_request(text: str) -> str | None:
    """Public wrapper: detect an action request in the text."""
    return _detect_action_request(text.lower().strip())