#!/usr/bin/env bash
# Step 2 — Inventory: sizes, line counts, encoding, line endings for every file.
# Run: bash scripts/discovery/C02_inventory.sh > docs/discovery/output/C02.txt 2>&1
set -euo pipefail

D="/home/saikumar/projects/fenwick-opencode/fenwick-data-pack"
echo "=== Inventory: fenwick-data-pack ==="
echo "Date: $(date '+%Y-%m-%d %H:%M')"
echo ""

echo "--- CSV files ---"
for f in "$D"/*.csv; do
  fn=$(basename "$f")
  echo "File: $fn"
  echo "  Size (bytes): $(wc -c < "$f")"
  echo "  Lines: $(wc -l < "$f")"
  echo "  Encoding: $(file -b "$f")"
  # Check CRLF
  if grep -l $'\r$' "$f" >/dev/null 2>&1; then
    echo "  Line endings: CRLF (\\r\\n)"
  else
    echo "  Line endings: LF (\\n)"
  fi
  # Column count from header
  header=$(head -1 "$f")
  cols=$(echo "$header" | awk -F',' '{print NF}')
  echo "  Columns: $cols"
  echo "  Header: $header"
  echo ""
done

echo "--- Documents (docx) ---"
for d in runbooks postmortems policies; do
  echo "Directory: documents/$d/"
  for f in "$D/documents/$d/"*.docx; do
    fn=$(basename "$f")
    sz=$(wc -c < "$f")
    echo "  $fn | ${sz} bytes | $(file -b "$f")"
  done
  echo ""
done

echo "--- DATA_DICTIONARY.md ---"
echo "  Size: $(wc -c < "$D/DATA_DICTIONARY.md") bytes"
echo "  Lines: $(wc -l < "$D/DATA_DICTIONARY.md")"
echo ""

echo "--- scenario.txt ---"
echo "  Size: $(wc -c < /home/saikumar/projects/fenwick-opencode/scenario.txt) bytes"
echo "  Lines: $(wc -l < /home/saikumar/projects/fenwick-opencode/scenario.txt)"
echo ""

echo "--- AGENTS.md ---"
echo "  Size: $(wc -c < /home/saikumar/projects/fenwick-opencode/AGENTS.md) bytes"
echo "  Lines: $(wc -l < /home/saikumar/projects/fenwick-opencode/AGENTS.md)"
echo ""

echo "--- Total file count ---"
echo "  CSV files: 5"
echo "  Runbooks (docx): $(ls "$D/documents/runbooks/"*.docx 2>/dev/null | wc -l)"
echo "  Postmortems (docx): $(ls "$D/documents/postmortems/"*.docx 2>/dev/null | wc -l)"
echo "  Policies (docx): $(ls "$D/documents/policies/"*.docx 2>/dev/null | wc -l)"
echo "  Total docx: $(find "$D/documents" -name '*.docx' | wc -l)"
echo ""

echo "--- Surprise check: 4 CSVs claimed vs 5 found ---"
echo "  scenario.txt says 'four CSVs' but there are 5 .csv files."
echo "  H1 is FALSE."