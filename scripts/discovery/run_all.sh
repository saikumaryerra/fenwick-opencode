#!/usr/bin/env bash
# Re-runs every discovery command in the order it was first run.
set -euo pipefail

bash scripts/discovery/C01_claims.sh > docs/discovery/output/C01.txt 2>&1
bash scripts/discovery/C02_inventory.sh > docs/discovery/output/C02.txt 2>&1
python3 scripts/discovery/C03_profile_roster.py > docs/discovery/output/C03.txt 2>&1
python3 scripts/discovery/C04_profile_service_registry.py > docs/discovery/output/C04.txt 2>&1
python3 scripts/discovery/C05_profile_oncall.py > docs/discovery/output/C05.txt 2>&1
python3 scripts/discovery/C06_profile_open_tickets.py > docs/discovery/output/C06.txt 2>&1
python3 scripts/discovery/C07_profile_incident_log.py > docs/discovery/output/C07.txt 2>&1
python3 scripts/discovery/C08_date_format_crisis.py > docs/discovery/output/C08.txt 2>&1
python3 scripts/discovery/C09_service_name_variants.py > docs/discovery/output/C09.txt 2>&1
python3 scripts/discovery/C10_updates_field_audit.py > docs/discovery/output/C10.txt 2>&1
python3 scripts/discovery/C11_scenario_mapping.py > docs/discovery/output/C11.txt 2>&1
python3 scripts/discovery/C12_extract_docx.py > docs/discovery/output/C12_docx_extracts_summary.txt 2>&1
python3 scripts/discovery/C13_cross_checks.py > docs/discovery/output/C13.txt 2>&1
