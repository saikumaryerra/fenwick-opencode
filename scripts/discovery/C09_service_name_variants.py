#!/usr/bin/env python3
"""Deep-dive: cross-file service name consistency for oncall_schedule and incident_log vs service_registry."""
import csv, os
from collections import Counter, defaultdict

BASE = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack')

# 1. Load canonical names
reg_names = {}
with open(os.path.join(BASE, 'service_registry.csv'), newline='') as f:
    for r in csv.DictReader(f):
        reg_names[r['service_name']] = r['owning_team']

# 2. Build normalization maps (lowercase -> canonical)
canon_by_lower = {}
for n in reg_names:
    canon_by_lower[n.lower()] = n
    canon_by_lower[n.lower().replace('-', '_')] = n

# 3. oncall_schedule names
oncall_names = set()
with open(os.path.join(BASE, 'oncall_schedule.csv'), newline='') as f:
    for r in csv.DictReader(f):
        oncall_names.add(r['service_name_raw'])

print("=== Service name variant analysis ===")
print()

print("--- Canonical names (service_registry) ---")
for n in sorted(reg_names):
    print(f"  {n}  [{reg_names[n]}]")
print()

print("--- oncall_schedule names ---")
print(f"  Total distinct: {len(oncall_names)}")
for n in sorted(oncall_names):
    exact = 'EXACT' if n in reg_names else 'MISMATCH'
    lower = n.lower().replace('_', '-')
    normal_match = 'YES' if lower in canon_by_lower or n.lower() in canon_by_lower else 'NO'
    print(f"  '{n}' | exact={exact} | normalizes={'YES' if normal_match else 'NO'}")
print()

# 4. incident_log service names (full count)
print("--- incident_log service names ---")
inc_svc = Counter()
with open(os.path.join(BASE, 'incident_log.csv'), newline='') as f:
    for r in csv.DictReader(f):
        inc_svc[r['service_name_raw']] += 1

servant_variants = defaultdict(list)
for n, cnt in inc_svc.most_common():
    lower_norm = n.lower().replace('_', '-').replace(' ', '-')
    if n in reg_names:
        status = 'EXACT match'
    elif lower_norm in reg_names or n.lower() in reg_names:
        status = f'Normalizes to canonical (case/hyphen/underscore diff)'
    else:
        status = 'NO canonical match'
    print(f"  '{n}' ({cnt} rows) — {status}")

print()
print("--- Variant groups (by canonical) ---")
groups = defaultdict(list)
for n in inc_svc:
    lower = n.lower().replace('_', '-')
    if n in reg_names:
        groups[n].append(n)
    elif lower in reg_names:
        groups[lower].append(n)
    elif n.lower() in reg_names:
        groups[n.lower()].append(n)
    else:
        groups['NO_MATCH'].append(n)
for canon, variants in sorted(groups.items()):
    if len(variants) > 1:
        print(f"  Canonical '{canon}': {sorted(variants)}")
    else:
        print(f"  Canonical '{canon}': {variants}")
print()

print("=== Summary ===")
total_inc_svc = sum(inc_svc.values())
exact_inc = sum(cnt for n, cnt in inc_svc.items() if n in reg_names)
normalizable_inc = sum(cnt for n, cnt in inc_svc.items()
                       if n.lower().replace('_','-') in reg_names or n.lower() in reg_names or n in reg_names)
no_match_inc = total_inc_svc - normalizable_inc
print(f"  incident_log rows with exact match: {exact_inc}/{total_inc_svc} ({100*exact_inc//total_inc_svc}%)")
print(f"  incident_log rows normalizable: {normalizable_inc}/{total_inc_svc} ({100*normalizable_inc//total_inc_svc}%)")
print(f"  incident_log rows with NO match at all: {no_match_inc}/{total_inc_svc} (must be inspected)")

# Show unmatched
unmatched = [n for n in inc_svc if n not in reg_names and n.lower().replace('_','-') not in reg_names and n.lower() not in reg_names]
print(f"  Unmatched names: {unmatched}")

# oncall
oncall_exact = sum(1 for n in oncall_names if n in reg_names)
oncall_norm = sum(1 for n in oncall_names if n.lower().replace('_','-') in reg_names or n in reg_names or n.lower() in reg_names)
print(f"  oncall_schedule exact match: {oncall_exact}/{len(oncall_names)}")
print(f"  oncall_schedule normalizable: {oncall_norm}/{len(oncall_names)}")
unmatched_oncall = [n for n in oncall_names if n not in reg_names and n.lower().replace('_','-') not in reg_names and n.lower() not in reg_names]
print(f"  Unmatched oncall names: {unmatched_oncall}")