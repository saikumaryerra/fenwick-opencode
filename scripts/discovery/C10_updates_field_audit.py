#!/usr/bin/env python3
"""Audit the updates field in incident_log.csv — structure, timestamp format, and data quality."""
import csv, os
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/incident_log.csv')

total = 0
has_updates = 0
timestamp_fmts = Counter()
emp_id_issues = 0
note_empty = 0
entries_count = Counter()
sev_in_updates = 0

# Cross-check: does 'open' status always have updates?
open_no_updates = 0
resolved_with_updates = 0

with open(CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        total += 1
        status = r['status'].strip()
        updates = r.get('updates', '').strip()
        
        if status == 'open' and not updates:
            open_no_updates += 1
        if status == 'resolved' and updates:
            resolved_with_updates += 1
        
        if not updates:
            continue
        has_updates += 1
        
        # Parse entries separated by ;
        entries = updates.split(';')
        entries_count[len(entries)] += 1
        
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split('|')
            if len(parts) == 3:
                ts, eid, note = [p.strip() for p in parts]
                
                # Check emp_id format
                if not (eid.startswith('FEN-') and eid[4:].isdigit()):
                    emp_id_issues += 1
                
                # Check note empty
                if not note:
                    note_empty += 1
                
                # Timestamp format
                t = ts.strip()
                if len(t) == 19 and t[4] == '-' and t[10] == 'T':
                    try:
                        datetime.strptime(t, '%Y-%m-%dT%H:%M:%S')
                        timestamp_fmts['ISO8601'] += 1
                        continue
                    except:
                        pass
                if '/' in t and 'T' in t:
                    # e.g. MM/DD/YYYYTHH:MM:SS
                    timestamp_fmts['MM/DD/YYYYTHH:MM:SS (nonstandard)'] += 1
                else:
                    timestamp_fmts[f'OTHER: {t[:20]}'] += 1
            else:
                timestamp_fmts[f'MALFORMED ({len(parts)} parts): {entry[:50]}'] += 1

print("=== Updates field audit ===")
print(f"Total rows: {total}")
print(f"Rows with updates: {has_updates}")
print(f"Rows without updates: {total - has_updates}")
print()

# Consistency: open/expected vs actual
print("--- Consistency: status vs updates ---")
print(f"  'open' status rows with NO updates: {open_no_updates}")
print(f"  'resolved' status rows WITH updates: {resolved_with_updates}")
print()

print("--- Timestamp formats in updates ---")
for fmt, cnt in timestamp_fmts.most_common():
    print(f"  {fmt}: {cnt}")
print()

print("--- Entry counts per row ---")
for cnt, freq in sorted(entries_count.most_common()):
    print(f"  {cnt} entries: {freq} row(s)")
print()

print("--- Emp ID issues ---")
print(f"  FEN-NNNN format violations: {emp_id_issues}")
print(f"  Empty notes: {note_empty}")
print()

# Sample some updates from different formats
print("--- Sample updates ---")
shown = 0
with open(CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        updates = r.get('updates', '').strip()
        if not updates:
            continue
        if shown < 5:
            upd_trunc = updates[:300]
            print(f"  ID {r['incident_id']} ({r['status']}): [{upd_trunc}]")
            shown += 1
            if shown == 5:
                break
print()

print("=" * 60)
print("Postmortem doc linked vs available on disk")
doc_dir = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/documents/postmortems')
disk_docs = {f for f in os.listdir(doc_dir) if f.endswith('.docx')}
print(f"  Files ON DISK ({len(disk_docs)}):")
for d in sorted(disk_docs):
    print(f"    {d}")

linked_from_csv = set()
with open(CSV, newline='') as f:
    for r in csv.DictReader(f):
        pm = r.get('postmortem_doc', '').strip()
        if pm:
            linked_from_csv.add(pm)
print(f"  Files LINKED from CSV ({len(linked_from_csv)}):")
for d in sorted(linked_from_csv):
    print(f"    {d}")

orphans = disk_docs - linked_from_csv
missing = linked_from_csv - disk_docs
print(f"  ORPHAN docs (on disk, not linked): {sorted(orphans)}")
print(f"  MISSING docs (linked, not on disk): {sorted(missing)}")
print()

print("=== End updates + postmortem audit ===")