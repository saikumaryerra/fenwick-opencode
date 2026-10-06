#!/usr/bin/env python3
"""Profile engineer_roster.csv across all 7 quality dimensions."""
import csv, sys, os
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/engineer_roster.csv')
rows = list(csv.DictReader(open(CSV, newline='')))

print("=== engineer_roster.csv profile ===")
print(f"Rows: {len(rows)}  |  Columns: 5 (emp_id, name, team, title, clearance_tier)")
print(f"As-of: shipped with pack, no timestamp column")
print()

# 1. COMPLETENESS
print("--- 1. Completeness (missing/empty values) ---")
miss = {}
for col in ['emp_id','name','team','title','clearance_tier']:
    empty = sum(1 for r in rows if not r.get(col,'').strip())
    miss[col] = empty
    print(f"  {col}: {empty} empty")
print(f"  Any field empty: {sum(1 for r in rows if any(not r.get(c,'').strip() for c in rows[0]))} rows")
print()

# 2. VALIDITY
print("--- 2. Validity (format classes per column) ---")
# emp_id
ids = [r['emp_id'] for r in rows]
emp_formats = Counter('FEN-NNNN' if e.startswith('FEN-') and e[4:].isdigit() else e for e in ids)
print(f"  emp_id formats: {dict(emp_formats)}")

# team
teams = Counter(r['team'] for r in rows)
print(f"  team values: {dict(teams)}")

# title
titles = Counter(r['title'] for r in rows)
print(f"  title values: {dict(titles)}")

# clearance_tier
tiers = Counter(r['clearance_tier'] for r in rows)
print(f"  clearance_tier values: {dict(tiers)}")
print()

# 3. UNIQUENESS
print("--- 3. Uniqueness ---")
emp_ids = [r['emp_id'] for r in rows]
dup_ids = [e for e, c in Counter(emp_ids).items() if c > 1]
print(f"  Duplicate emp_id: {len(dup_ids)}")
dup_rows = len(rows) - len(set(tuple(r.items()) for r in rows))
print(f"  Duplicate rows: {dup_rows}")
print()

# 4. CONSISTENCY (same-row field agreement)
print("--- 4. Consistency ---")
# No obvious cross-field constraints in a single row for this table.
# Team/title: e.g. 'SRE' team with 'SRE' / 'Senior SRE' titles — expected.
print("  No cross-field consistency rules for this table")
print()

# 5. INTEGRITY (no FK column references another table)
print("--- 5. Integrity ---")
print("  emp_id is the PK — no FK columns in this table")
print()

# 6. TIMELINESS
print("--- 6. Timeliness ---")
print("  No timestamp column. Data is a snapshot.")
print(f"  As-of: shipped with pack. Changes slowly per scenario.txt.")
print()

# 7. DISTRIBUTION
print("--- 7. Distribution ---")
print(f"  Teams: {dict(Counter(r['team'] for r in rows))}")
print(f"  Clearance: {tiers}")
print(f"  Titles: {dict(titles)}")
restricted = sum(1 for r in rows if r['clearance_tier'] == 'restricted')
print(f"  Restricted: {restricted}/{len(rows)} ({100*restricted//len(rows)}%)")
print(f"  General: {len(rows)-restricted}/{len(rows)}")
print()

print("=== Profile complete ===")
print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}")