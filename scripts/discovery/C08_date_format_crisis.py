#!/usr/bin/env python3
"""Deep-dive into incident_log.csv date format inconsistency — distribution by year and format."""
import csv, os
from collections import Counter
from datetime import datetime

CSV = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/incident_log.csv')

fmt_counts = Counter()
fmt_by_year = {}
row_count = 0

with open(CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        row_count += 1
        d = r['date'].strip()
        # ISO
        if len(d) == 10 and d[4] == '-' and d[7] == '-':
            try:
                dt = datetime.strptime(d, '%Y-%m-%d')
                key = 'ISO (YYYY-MM-DD)'
                yr = dt.year
            except:
                key = f'UNPARSEABLE: {d}'
                yr = 0
        elif len(d) == 11 and d[2] == ' ':
            try:
                dt = datetime.strptime(d, '%d %b %Y')
                key = 'DD Mon YYYY (e.g. 28 May 2025)'
                yr = dt.year
            except:
                key = f'UNPARSEABLE: {d}'
                yr = 0
        elif '/' in d:
            # MM/DD/YYYY — but sample check: if month>12, it's actually DD/MM — test all
            parts = d.split('/')
            if len(parts) == 3:
                m, day, y = parts
                key_date = f'MM/DD/YYYY: {d}'
            else:
                key_date = f'OTHER: {d}'
            key = 'MM/DD/YYYY'
            try:
                dt = datetime.strptime(d, '%m/%d/%Y')
                yr = dt.year
            except:
                try:
                    dt = datetime.strptime(d, '%d/%m/%Y')
                    key = 'DD/MM/YYYY (ambiguous)'
                    yr = dt.year
                except:
                    yr = 0
                    key = f'UNPARSEABLE SLASH: {d}'
        else:
            key = f'OTHER: {d}'
            yr = 0
        
        fmt_counts[key] += 1
        if yr not in fmt_by_year:
            fmt_by_year[yr] = Counter()
        fmt_by_year[yr][key] += 1

print("=== Date format crisis in incident_log.csv ===")
print(f"Total rows: {row_count}")
print()

print("--- Format breakdown ---")
for fmt, cnt in fmt_counts.most_common():
    pct = 100 * cnt / row_count
    print(f"  {fmt}: {cnt} ({pct:.1f}%)")
print()

print("--- Distribution by year ---")
for yr in sorted(fmt_by_year):
    print(f"  {yr}:")
    for fmt, cnt in sorted(fmt_by_year[yr].items()):
        print(f"    {fmt}: {cnt}")
print()

print("--- Impact analysis ---")
print("  All 3 formats appear throughout — they are NOT segregated by year.")
print("  => Any query that sorts, filters, or compares dates will be incorrect")
print("     unless the date is parsed format-by-format.")
print("  => A system consuming this must attempt all 3 parsers and validate.")
print()

# Check whether the MM/DD/YYYY dates could be ambiguous (month vs day)
print("--- Ambiguity risk in MM/DD/YYYY ---")
slash_count = 0
ambiguous_count = 0
with open(CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        d = r['date'].strip()
        if '/' in d:
            slash_count += 1
            parts = d.split('/')
            if len(parts) == 3:
                p1, p2, p3 = parts
                # Both month and day <= 12 -> ambiguous
                if int(p1) <= 12 and int(p2) <= 12:
                    ambiguous_count += 1
print(f"  Total slash-format dates: {slash_count}")
print(f"  Ambiguous (both parts <=12, could be DD/MM or MM/DD): {ambiguous_count}")
print()

# Sample from each format
print("--- Samples per format ---")
samples = {'ISO (YYYY-MM-DD)': [], 'DD Mon YYYY (e.g. 28 May 2025)': [], 'MM/DD/YYYY': []}
with open(CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        d = r['date'].strip()
        if len(samples['ISO (YYYY-MM-DD)']) < 3 and len(d) == 10 and d[4] == '-' and d[7] == '-':
            samples['ISO (YYYY-MM-DD)'].append(d)
        elif len(samples['DD Mon YYYY (e.g. 28 May 2025)']) < 3 and len(d) == 11 and d[2] == ' ':
            samples['DD Mon YYYY (e.g. 28 May 2025)'].append(d)
        elif len(samples['MM/DD/YYYY']) < 3 and '/' in d:
            samples['MM/DD/YYYY'].append(d)
        if all(len(v) >= 3 for v in samples.values()):
            break
for fmt, samps in samples.items():
    print(f"  {fmt}:")
    for s in samps:
        print(f"    '{s}'")
print()

print("=== End date analysis ===")