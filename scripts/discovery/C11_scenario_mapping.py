#!/usr/bin/env python3
"""Map the 5 scenario example tickets (A-E) against the actual data."""
import csv, os
from datetime import datetime

BASE = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack')
print("=== Scenario ticket mapping (A-E) ===")
print()

# --- Load tickets ---
tickets = []
with open(os.path.join(BASE, 'open_tickets.csv'), newline='') as f:
    for r in csv.DictReader(f):
        tickets.append(r)

# Ticket D: "checkout latency spiking again since about 14:20"
print("--- Ticket D: checkout latency (scenario example) ---")
d_tickets = [t for t in tickets if 'checkout' in t['text'].lower() and 'latency' in t['text'].lower()]
print(f"  Matching tickets: {len(d_tickets)}")
for t in d_tickets:
    print(f"    {t['ticket_id']} | {t['filed_by']} | {t['filed_at']} | related_inc={t['related_incident_id']}")
# Check related incident
if d_tickets:
    tkt = d_tickets[0]
    inc_id = tkt['related_incident_id'].strip()
    if inc_id:
        with open(os.path.join(BASE, 'incident_log.csv'), newline='') as f:
            for r in csv.DictReader(f):
                if r['incident_id'] == inc_id:
                    print(f"    -> Related incident: {r['incident_id']} ({r['status']}, {r['severity']}): {r['one_line_summary']}")
                    print(f"       Updates: {r['updates'][:200] if r.get('updates','') else '(none)'}")
                    break
print()

# --- Check ticket B: "what did we conclude about the March auth-gateway outage" ---
print("--- Ticket B: March auth-gateway outage ---")
# Look for relevant tickets about auth-gateway
b_tickets = [t for t in tickets if 'auth-gateway' in t['text'].lower() or 'auth_gateway' in t['text'].lower() or 'auth gateway' in t['text'].lower()]
print(f"  Tickets about auth-gateway: {len(b_tickets)}")
for t in b_tickets:
    print(f"    {t['ticket_id']} | {t['text'][:80]}")
# Look for auth-gateway postmortems mentioning March
print("  Postmortems about auth-gateway:")
pm_dir = os.path.join(BASE, 'documents/postmortems')
for fn in sorted(os.listdir(pm_dir)):
    if 'auth' in fn.lower():
        print(f"    {fn}")
print()

# --- Ticket A: payments-api canary ---
print("--- Ticket A: payments-api canary 5xx ---")
a_tickets = [t for t in tickets if 'payments-api' in t['text'].lower() or 'payments api' in t['text'].lower()]
print(f"  Tickets about payments-api: {len(a_tickets)}")
for t in a_tickets:
    print(f"    {t['ticket_id']} | {t['text'][:80]}")
print(f"  Postmortems about payments-api:")
for fn in sorted(os.listdir(pm_dir)):
    if 'payments' in fn.lower():
        print(f"    {fn}")
print()

# --- Ticket C: "page whoever's on call for payments-api" ---
print("--- Ticket C: on-call for payments-api ---")
# Check oncall schedule
with open(os.path.join(BASE, 'oncall_schedule.csv'), newline='') as f:
    oncall_rows = list(csv.DictReader(f))
for r in oncall_rows:
    if 'payments' in r['service_name_raw'].lower() and r['currently_active'] == 'true':
        print(f"  Current on-call for payments-api: {r['engineer_emp_id']} ({r['rotation_note']})")
# Check engineer name
with open(os.path.join(BASE, 'engineer_roster.csv'), newline='') as f:
    for r in csv.DictReader(f):
        if r['emp_id'] == 'FEN-1001':
            print(f"  Engineer FEN-1001: {r['name']}, {r['team']}, {r['title']}")
print()

# --- Ticket E: "who owns billing-sync now" ---
print("--- Ticket E: who owns billing-sync ---")
with open(os.path.join(BASE, 'service_registry.csv'), newline='') as f:
    for r in csv.DictReader(f):
        if 'billing-sync' in r['service_name'].lower():
            print(f"  Service: {r['service_name']} | Owner: {r['owning_team']} | Status: {r['status']}")
print()

# --- Cross-file consistency checks ---
print("=== Cross-file consistency ===")
print()

# Check: do all on-call engineers exist in roster?
print("--- On-call engineers in roster ---")
roster_eids = set()
with open(os.path.join(BASE, 'engineer_roster.csv'), newline='') as f:
    for r in csv.DictReader(f):
        roster_eids.add(r['emp_id'])
oncall_eids = set()
with open(os.path.join(BASE, 'oncall_schedule.csv'), newline='') as f:
    for r in csv.DictReader(f):
        oncall_eids.add(r['engineer_emp_id'])
missing_from_roster = oncall_eids - roster_eids
print(f"  On-call engineers not in roster: {missing_from_roster} {'(none)' if not missing_from_roster else ''}")
print()

# Check: do all ticket filers exist in roster?
print("--- Ticket filers in roster ---")
ticket_eids = set()
with open(os.path.join(BASE, 'open_tickets.csv'), newline='') as f:
    for r in csv.DictReader(f):
        ticket_eids.add(r['filed_by'])
missing_filers = ticket_eids - roster_eids
print(f"  Ticket filers not in roster: {missing_filers} {'(none)' if not missing_filers else ''}")
print()

# Check: service ownership teams — do owning_team names match roster teams?
print("--- Team names match between roster and registry ---")
roster_teams = set()
with open(os.path.join(BASE, 'engineer_roster.csv'), newline='') as f:
    for r in csv.DictReader(f):
        roster_teams.add(r['team'])
registry_teams = set()
with open(os.path.join(BASE, 'service_registry.csv'), newline='') as f:
    for r in csv.DictReader(f):
        registry_teams.add(r['owning_team'])
print(f"  Roster teams: {sorted(roster_teams)}")
print(f"  Registry teams: {sorted(registry_teams)}")
diff = roster_teams ^ registry_teams
print(f"  Symmetric difference: {diff} {'(none — perfect match)' if not diff else ''}")
print()

# Check: incident_log severity/status distributions 
print("--- Incident severity by status ---")
sev_status = {}
with open(os.path.join(BASE, 'incident_log.csv'), newline='') as f:
    for r in csv.DictReader(f):
        key = (r['severity'], r['status'])
        sev_status[key] = sev_status.get(key, 0) + 1
for (sev, sts), cnt in sorted(sev_status.items()):
    print(f"  {sev}/{sts}: {cnt}")
print()

print("=== End scenario mapping ===")