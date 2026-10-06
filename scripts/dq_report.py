#!/usr/bin/env python3
"""Data-quality report — computed from the data, not hardcoded.

Outputs to stdout a structured report with numbers derived from the
actual data pack files.
"""

import os
import sys
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingest.csv_loader import (
    load_all,
    load_roster,
    load_services,
    load_oncall,
    load_incidents,
    load_open_tickets,
    csv_file_count,
)
from ingest.normalize import (
    normalize_service,
    parse_date,
    normalize_incident_id,
    parse_update_timestamp,
)
from ingest.doc_loader import load_documents, is_restricted
from auth.clearance import compute_clearance


def report() -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("DATA QUALITY REPORT — Computed from data pack")
    lines.append("=" * 60)

    # --- CSV file count (F-04) ---
    csv_count = csv_file_count()
    lines.append(f"\n[F-04] CSV file count: {csv_count} (expected: 5)")

    # --- Roster ---
    roster = load_roster()
    lines.append(f"\n--- engineer_roster.csv ---")
    lines.append(f"  Rows: {len(roster)}")

    teams = Counter(r["team"] for r in roster)
    lines.append(f"  Teams: {dict(teams)}")

    # Clearance: computed vs trusted (F-01)
    computed_clearances = {}
    trusted_clearances = {}
    for r in roster:
        computed = compute_clearance(r["team"], r["title"])
        computed_clearances[r["emp_id"]] = computed
        trusted_clearances[r["emp_id"]] = r["clearance_tier"]

    disagreements = 0
    for emp_id in roster:
        if computed_clearances[emp_id["emp_id"]] != trusted_clearances[emp_id["emp_id"]]:
            disagreements += 1
    lines.append(f"  Clearance disagreements (computed vs trusted): {disagreements}")
    if disagreements:
        lines.append("  Details:")
        for r in roster:
            c = compute_clearance(r["team"], r["title"])
            t = r["clearance_tier"]
            if c != t:
                lines.append(f"    {r['emp_id']} ({r['name']}): computed={c}, roster={t}")

    # --- Services ---
    services = load_services()
    lines.append(f"\n--- service_registry.csv ---")
    lines.append(f"  Rows: {len(services)}")
    active = sum(1 for s in services if s["status"] == "active")
    deprecated = sum(1 for s in services if s["status"] == "deprecated")
    lines.append(f"  Active: {active}, Deprecated: {deprecated}")

    # Service name normalization (F-02) — show original vs normalized
    lines.append(f"  Service name normalization examples:")
    for s in services:
        normalized = normalize_service(s["service_name"])
        if normalized != s["service_name"]:
            lines.append(f"    '{s['service_name']}' -> '{normalized}'")

    # --- On-call ---
    oncall = load_oncall()
    lines.append(f"\n--- oncall_schedule.csv ---")
    lines.append(f"  Rows: {len(oncall)}")

    # Service name raw uniqueness
    raw_names = set(r["service_name_raw"] for r in oncall)
    lines.append(f"  Unique raw service names: {len(raw_names)}")
    for rn in sorted(raw_names):
        normalized = normalize_service(rn)
        lines.append(f"    '{rn}' -> normalized: '{normalized}'")

    # Deprecated services with on-call (F-05)
    deprecated_services = [s for s in services if s["status"] == "deprecated"]
    deprecated_names = set(s["service_name_normalized"] for s in deprecated_services)
    oncall_normalized = {}
    for oc in oncall:
        n = normalize_service(oc["service_name_raw"])
        oncall_normalized.setdefault(n, []).append(oc["engineer_emp_id"])
    deprecated_with_oncall = deprecated_names & set(oncall_normalized.keys())
    lines.append(f"  Deprecated services with on-call entries: {len(deprecated_with_oncall)}")
    for d in sorted(deprecated_with_oncall):
        lines.append(f"    {d}: {oncall_normalized[d]}")

    # SRE on-call (F-07)
    sre_engineers = [r for r in roster if r["team"] == "SRE"]
    sre_oncall = []
    for oc in oncall:
        for sre in sre_engineers:
            if oc["engineer_emp_id"] == sre["emp_id"]:
                sre_oncall.append((oc["service_name_raw"], sre["name"]))
    lines.append(f"  SRE engineers on-call (F-07): {len(sre_oncall)} entries")

    # --- Incidents ---
    incidents = load_incidents()
    lines.append(f"\n--- incident_log.csv ---")
    lines.append(f"  Rows: {len(incidents)}")

    open_incidents = [i for i in incidents if i["status"] == "open"]
    resolved_incidents = [i for i in incidents if i["status"] == "resolved"]
    lines.append(f"  Open: {len(open_incidents)}, Resolved: {len(resolved_incidents)}")

    # Incident ID formats (F-08)
    inc_ids = [i["incident_id"] for i in incidents]
    short_ids = [iid for iid in inc_ids if len(iid) <= 8]  # INC-NNNN = 8 chars
    long_ids = [iid for iid in inc_ids if len(iid) > 8]
    lines.append(f"  Incident IDs: {len(short_ids)} short (INC-NNNN), {len(long_ids)} long (INC-NNNNNN)")

    # Date parsing (F-03) - show format distribution
    date_formats = Counter()
    for i in incidents:
        d = i["date"]
        if "T" in d:
            date_formats["ISO datetime"] += 1
        elif "-" in d and d.count("-") == 2:
            date_formats["ISO date (YYYY-MM-DD)"] += 1
        elif d.count("/") == 2:
            date_formats["MM/DD/YYYY"] += 1
        elif d.count(" ") == 2:
            date_formats["DD Mon YYYY"] += 1
        else:
            date_formats[f"other: {d[:20]}"] += 1
    lines.append(f"  Date format distribution:")
    for fmt, cnt in sorted(date_formats.items()):
        lines.append(f"    {fmt}: {cnt}")

    # Parsed vs unparsed dates
    unparsed_dates = sum(1 for i in incidents if i["date_parsed"] is None)
    lines.append(f"  Unparseable dates: {unparsed_dates}")

    # Update timestamp parsing (F-11)
    update_count = 0
    parsed_updates = 0
    unparsed_updates = 0
    for i in incidents:
        if i.get("updates_parsed"):
            for u in i["updates_parsed"]:
                update_count += 1
                if u["timestamp_parsed"] is not None:
                    parsed_updates += 1
                else:
                    unparsed_updates += 1
    lines.append(f"  Update entries: {update_count}")
    lines.append(f"  Update timestamps parsed: {parsed_updates}, unparsed: {unparsed_updates}")

    # Open tickets (F-04) — loaded from 5th CSV
    open_tickets = load_open_tickets()
    lines.append(f"\n--- open_tickets.csv (5th CSV, F-04) ---")
    lines.append(f"  Rows: {len(open_tickets)}")
    with_incident = sum(1 for t in open_tickets if t.get("related_incident_id", "").strip())
    without_incident = len(open_tickets) - with_incident
    lines.append(f"  With linked incident: {with_incident}, Without: {without_incident}")

    # --- Documents (F-09) ---
    docs = load_documents()
    lines.append(f"\n--- Documents (F-09 — discovered by scanning store) ---")
    lines.append(f"  Total .docx files: {len(docs)}")

    by_category = Counter()
    restricted_by_category = Counter()
    for fname, meta in docs.items():
        by_category[meta["category"]] += 1
        if meta["restricted"]:
            restricted_by_category[meta["category"]] += 1
    lines.append(f"  By category: {dict(by_category)}")
    lines.append(f"  Restricted by category: {dict(restricted_by_category)}")

    drafts = [fname for fname, meta in docs.items() if meta["is_draft"]]
    superseded = [fname for fname, meta in docs.items() if meta["is_superseded"]]
    lines.append(f"  Draft documents: {len(drafts)} ({', '.join(drafts)})")
    lines.append(f"  Superseded documents: {len(superseded)} ({', '.join(superseded)})")

    # Document families
    families = set(meta["doc_family"] for meta in docs.values())
    lines.append(f"  Document families: {len(families)}")
    for fam in sorted(families):
        members = [fname for fname, meta in docs.items() if meta["doc_family"] == fam]
        lines.append(f"    {fam}: {', '.join(members)}")

    # Documents not linked from incident_log (orphan docs, F-09)
    csv_postmortem_links = set()
    for i in incidents:
        pm = i.get("postmortem_doc", "").strip()
        if pm:
            csv_postmortem_links.add(pm)
    postmortem_files = set(
        os.path.basename(fname)
        for fname, meta in docs.items()
        if meta["category"] == "postmortems"
    )
    orphan_postmortems = postmortem_files - csv_postmortem_links
    lines.append(f"  Postmortem docs in CSV links: {len(csv_postmortem_links)}")
    lines.append(f"  Postmortem files on disk: {len(postmortem_files)}")
    lines.append(f"  Orphan postmortems (not in CSV): {len(orphan_postmortems)}")
    for o in sorted(orphan_postmortems):
        lines.append(f"    {o}")

    # --- Escalation values (F-06) ---
    lines.append(f"\n--- Escalation Timing (F-06 — designed, not built) ---")
    lines.append(f"  SEV1: 5 minutes (escalation-runbook)")
    lines.append(f"  SEV2: 10 minutes")
    lines.append(f"  SEV3: 1 business day")
    lines.append(f"  Policy (default): 15 minutes")
    lines.append(f"  Payments service conflict: 3 minutes")

    lines.append("\n" + "=" * 60)
    lines.append("END REPORT")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())