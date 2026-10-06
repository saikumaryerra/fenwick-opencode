#!/usr/bin/env python3
"""Profile oncall_schedule.csv across all 7 quality dimensions."""
import csv, os
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/oncall_schedule.csv')
rows = list(csv.DictReader(open(CSV, newline='')))

print("=== oncall_schedule.csv profile ===")
print(f"Rows: {len(rows)}  |  Columns: 4 (service_name_raw, engineer_emp_id, currently_active, rotation_note)")
print()

# 1. COMPLETENESS
print("--- 1. Completeness ---")
for col in ['service_name_raw','engineer_emp_id','currently_active','rotation_note']:
    empty = sum(1 for r in rows if not r.get(col,'').strip())
    print(f"  {col}: {empty} empty")
print()

# 2. VALIDITY
print("--- 2. Validity ---")
# service_name_raw format classes
names = [r['service_name_raw'].strip() for r in rows]
print(f"  service_name_raw values: {Counter(names)}")
print(f"  Number of distinct name variants: {len(set(names))}")

# currently_active
actives = Counter(r['currently_active'] for r in rows)
print(f"  currently_active values: {dict(actives)}")

# engineer_emp_id format
eids = [r['engineer_emp_id'] for r in rows]
eid_formats = Counter('FEN-NNNN' if e.startswith('FEN-') and e[4:].isdigit() else e for e in eids)
print(f"  engineer_emp_id formats: {dict(eid_formats)}")
print()

# 3. UNIQUENESS
print("--- 3. Uniqueness ---")
# service_name_raw + engineer_emp_id should be unique (one assignment per person per service)
keys = [(r['service_name_raw'].strip(), r['engineer_emp_id']) for r in rows]
dup_keys = [k for k, c in Counter(keys).items() if c > 1]
print(f"  Duplicate (service, engineer) pairs: {len(dup_keys)} {'('+str(dup_keys)+')' if dup_keys else ''}")
dup_rows = len(rows) - len(set(tuple(r.items()) for r in rows))
print(f"  Duplicate rows: {dup_rows}")
print()

# 4. CONSISTENCY
print("--- 4. Consistency ---")
# Check that services referenced here exist in service_registry
# (handled in cross-file integrity test, but note variations here)
name_variants = set(names)
print(f"  Distinct name_raw values: {name_variants}")
# The naming variations visible:
print(f"  Variants:")
for n in sorted(name_variants):
    print(f"    '{n}'")
print()

# 5. INTEGRITY
print("--- 5. Integrity ---")
# FK: engineer_emp_id -> engineer_roster.emp_id (cursory check)
roster_eids = set()
import csv as csv2
roster_path = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/engineer_roster.csv')
with open(roster_path, newline='') as f:
    for r in csv2.DictReader(f):
        roster_eids.add(r['emp_id'])
bad_eids = [e for e in eids if e not in roster_eids]
print(f"  engineer_emp_id not in engineer_roster: {bad_eids}")

# FK: service_name_raw -> service_registry.service_name (need to normalize)
reg_path = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/service_registry.csv')
reg_names = set()
with open(reg_path, newline='') as f:
    for r in csv2.DictReader(f):
        reg_names.add(r['service_name'])
reg_names_lower = {n.lower().replace('-','_').replace('-','') for n in reg_names}  # noqa
# Check exact matches
exact_missing = [n for n in names if n not in reg_names]
print(f"  service_name_raw with no exact match in service_registry: {exact_missing}")
print()

# 6. TIMELINESS
print("--- 6. Timeliness ---")
print("  currently_active column is the as-of marker.")
print("  No explicit timestamp but rotation notes mention 'Week 36' and 'Week 35'.")
print("  Week 36 assignments are current. Data is time-sensitive.")
print()

# 7. DISTRIBUTION
print("--- 7. Distribution ---")
print(f"  Active assignments: {actives.get('true',0)}  |  Inactive: {actives.get('false',0)}")
# Count assignments per service
svc_counts = Counter(n for n in names)
print(f"  Assignments per service:")
for svc, cnt in sorted(svc_counts.items()):
    print(f"    {svc}: {cnt}")
print()

print("=== Profile complete ===")
print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}")