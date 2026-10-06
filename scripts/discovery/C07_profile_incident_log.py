#!/usr/bin/env python3
"""Profile incident_log.csv (50K rows) across all 7 quality dimensions. Sampling for large columns."""
import csv, os, sys
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/incident_log.csv')
all_rows = []
with open(CSV, newline='') as f:
    for r in csv.DictReader(f):
        all_rows.append(r)
rows = all_rows  # 50,000 data rows

print("=== incident_log.csv profile ===")
print(f"Rows: {len(rows)}  |  Columns: 8", flush=True)
print()

# 1. COMPLETENESS
print("--- 1. Completeness ---", flush=True)
for col in ['incident_id','service_name_raw','date','severity','status','one_line_summary','postmortem_doc','updates']:
    empty = sum(1 for r in rows if not r.get(col,'').strip())
    print(f"  {col}: {empty} empty")
# postmortem_doc blank (expected for many)
pm_blank = sum(1 for r in rows if not r.get('postmortem_doc','').strip())
updates_blank = sum(1 for r in rows if not r.get('updates','').strip())
print(f"  postmortem_doc blank (no linked doc): {pm_blank}/{len(rows)}")
print(f"  updates blank (no updates): {updates_blank}/{len(rows)}")
print()

# 2. VALIDITY — parse every field with strict parsers
print("--- 2. Validity ---", flush=True)

# incident_id format
ids = [r['incident_id'].strip() for r in rows]
id_fmts = Counter()
for iid in ids:
    if iid.startswith('INC-') and len(iid) >= 5 and iid[4:].isdigit():
        ndigits = len(iid) - 4
        key = f'INC-{"0"*ndigits} ({"digits" if ndigits < 10 else "many"})'
        id_fmts[key] += 1
    else:
        id_fmts[iid] += 1
print(f"  incident_id format classes:")
for fmt, cnt in sorted(id_fmts.items()):
    print(f"    {fmt}: {cnt}")
print()

# service_name_raw — sample format classes
svc_names = [r['service_name_raw'].strip() for r in rows]
svc_fmts = Counter(svc_names)
print(f"  service_name_raw distinct values: {len(svc_fmts)}")
print(f"  Top 10: {dict(svc_fmts.most_common(10))}")
print()

# date — check format
date_fmts = Counter()
bad_date_count = 0
for r in rows:
    d = r['date'].strip()
    # ISO: YYYY-MM-DD
    if len(d) == 10 and d[4] == '-' and d[7] == '-':
        try:
            datetime.strptime(d, '%Y-%m-%d')
            date_fmts['ISO (YYYY-MM-DD)'] += 1
            continue
        except:
            pass
    # DD Mon YYYY
    try:
        datetime.strptime(d, '%d %b %Y')
        date_fmts['DD Mon YYYY'] += 1
        continue
    except:
        pass
    try:
        datetime.strptime(d, '%d %B %Y')
        date_fmts['DD Month YYYY'] += 1
        continue
    except:
        pass
    # other
    date_fmts[d[:20] if d else 'EMPTY'] += 1
    bad_date_count += 1
print(f"  Date formats: {dict(date_fmts)}")
print()

# severity
sev = Counter(r['severity'].strip() for r in rows)
print(f"  Severity values: {dict(sev)}")
unexp_sev = [s for s in sev if s not in ('SEV1','SEV2','SEV3')]
if unexp_sev:
    print(f"  Unexpected: {unexp_sev}")
print()

# status
sts = Counter(r['status'].strip() for r in rows)
print(f"  Status values: {dict(sts)}")
unexp_sts = [s for s in sts if s not in ('open','resolved')]
if unexp_sts:
    print(f"  Unexpected: {unexp_sts}")
print()

# 3. UNIQUENESS
print("--- 3. Uniqueness ---", flush=True)
dup_ids_count = sum(1 for iid, c in Counter(ids).items() if c > 1)
print(f"  Duplicate incident_ids: {dup_ids_count}")
dup_rows = len(rows) - len(set(tuple(r.items()) for r in rows))
print(f"  Duplicate rows: {dup_rows}")
print()

# 4. CONSISTENCY (same row)
print("--- 4. Consistency (same-row conflicts) ---", flush=True)
# SEV1/SEV2/SEV3 vs status — open/resolved — no obvious contradiction rule
# Check 'resolved' + 'open' status
open_resolved = sum(1 for r in rows if r['status'].strip() == 'open')
resolved = sum(1 for r in rows if r['status'].strip() == 'resolved')
print(f"  Open: {open_resolved}  |  Resolved: {resolved}")
print()

# 5. INTEGRITY (cross-file)
print("--- 5. Integrity ---", flush=True)
# service_name_raw -> service_registry.service_name (exact match check via sample)
reg_path = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/service_registry.csv')
reg_names = set()
with open(reg_path, newline='') as f:
    for r in csv.DictReader(f):
        reg_names.add(r['service_name'].strip())
# Unique service_names in incident_log
inc_svc_names = set(svc_names)
exact_match = inc_svc_names & reg_names
no_match = sorted(inc_svc_names - reg_names)
print(f"  service_name_raw values exactly matching service_registry: {len(exact_match)}/{len(inc_svc_names)}")
print(f"  Raw names NOT in service_registry (first 10): {no_match[:10]}")
print()

# 6. TIMELINESS
print("--- 6. Timeliness ---", flush=True)
# Parse dates for range
iso_dates = []
for r in rows:
    d = r['date'].strip()
    try:
        dt = datetime.strptime(d, '%Y-%m-%d')
        iso_dates.append(dt)
        continue
    except:
        pass
    try:
        dt = datetime.strptime(d, '%d %b %Y')
        iso_dates.append(dt)
    except:
        pass
if iso_dates:
    print(f"  Date range: {min(iso_dates).date()} — {max(iso_dates).date()}")
    print(f"  Latest incident: row(s) with date {max(iso_dates).date()}")
print()

# 7. DISTRIBUTION
print("--- 7. Distribution ---", flush=True)
print(f"  Severity: {dict(sev)}")
print(f"  Status: {dict(sts)}")
print(f"  Top 10 service_name_raw: {dict(svc_fmts.most_common(10))}")
# Check updates format
upd_present = [r['updates'].strip() for r in rows if r.get('updates','').strip()]
print(f"  Rows with non-empty updates: {len(upd_present)}")
if upd_present:
    # sample a few update entries
    print(f"  Sample update entries (first 3 rows with updates):")
    sample = 0
    for r in rows:
        if r.get('updates','').strip():
            print(f"    {r['updates'][:200]}...")
            sample += 1
            if sample >= 3:
                break
print()

# postmortem_doc links
pm_docs = [r['postmortem_doc'].strip() for r in rows if r.get('postmortem_doc','').strip()]
pm_doc_names = Counter(pm_docs)
print(f"  Distinct postmortem_doc filenames linked: {len(pm_doc_names)}")
print(f"  List: {sorted(pm_doc_names.keys())}")
print()

print("=== Profile complete ===")
print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}", flush=True)