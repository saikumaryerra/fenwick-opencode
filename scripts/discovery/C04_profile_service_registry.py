#!/usr/bin/env python3
"""Profile service_registry.csv across all 7 quality dimensions."""
import csv, sys, os
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/service_registry.csv')
rows = list(csv.DictReader(open(CSV, newline='')))

print("=== service_registry.csv profile ===")
print(f"Rows: {len(rows)}  |  Columns: 4 (service_name, owning_team, status, description)")
print()

# 1. COMPLETENESS
print("--- 1. Completeness ---")
for col in ['service_name','owning_team','status','description']:
    empty = sum(1 for r in rows if not r.get(col,'').strip())
    print(f"  {col}: {empty} empty")
print()

# 2. VALIDITY
print("--- 2. Validity ---")
# service_name format
names = [r['service_name'].strip() for r in rows]
name_formats = Counter('lowercase-hyphenated' if n.islower() and '-' in n else n for n in names)
print(f"  service_name patterns: {dict(name_formats)}")

# owning_team
teams = Counter(r['owning_team'] for r in rows)
print(f"  owning_team values: {dict(teams)}")

# status
statuses = Counter(r['status'] for r in rows)
print(f"  status values: {dict(statuses)}")
print()

# 3. UNIQUENESS
print("--- 3. Uniqueness ---")
n = [r['service_name'].strip() for r in rows]
dup_names = [x for x, c in Counter(n).items() if c > 1]
print(f"  Duplicate service_name: {len(dup_names)} {'('+str(dup_names)+')' if dup_names else ''}")
print()

# 4. CONSISTENCY
print("--- 4. Consistency ---")
# Check owning_team membership: only Payments, Billing, Platform, Security, SRE
valid_teams = {'Payments','Billing','Platform','Security','SRE'}
bad_teams = [r['owning_team'] for r in rows if r['owning_team'] not in valid_teams]
print(f"  Teams outside {{Payments,Billing,Platform,Security,SRE}}: {bad_teams}")
print()

# 5. INTEGRITY
print("--- 5. Integrity ---")
print("  service_name is the canonical name — referenced by other files via service_name_raw")
print()

# 6. TIMELINESS
print("--- 6. Timeliness ---")
print("  No timestamp. Data is a snapshot. scenario.txt: 'Authoritative for what exists'")
print()

# 7. DISTRIBUTION
print("--- 7. Distribution ---")
print(f"  Status distribution: {dict(statuses)}")
print(f"  Team distribution: {dict(teams)}")
# Check which services have 'deprecated' status
deprecated = [r['service_name'] for r in rows if r['status'] == 'deprecated']
print(f"  Deprecated services: {deprecated}")
print()

print("=== Profile complete ===")
print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}")