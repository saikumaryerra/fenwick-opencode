#!/usr/bin/env bash
# Step 1 — Claims: list every statement in scenario.txt and DATA_DICTIONARY.md
# that the data could contradict.
# Run: bash scripts/discovery/C01_claims.sh > docs/discovery/output/C01.txt 2>&1
set -euo pipefail

echo "=== D-01 hypotheses ==="
echo "Date: $(date '+%Y-%m-%d %H:%M')"
echo "Source: scenario.txt, DATA_DICTIONARY.md"
echo ""

echo "H1  | There are exactly 4 CSV files shipped alongside documents/"
echo "    | (scenario.txt: 'The dumps ship as documents/ plus four CSVs')"
echo ""

echo "H2  | open_tickets.csv is a snapshot of open tickets at hand-off"
echo "    | (DATA_DICTIONARY: 'One row per ticket currently open in the queue, as of hand-off')"
echo ""

echo "H3  | engineer_roster.emp_id is unique and authoritative for employee identity"
echo "    | (DATA_DICTIONARY: 'FK reference', scenario: 'Authoritative for who someone is')"
echo ""

echo "H4  | service_registry.service_name is the canonical service name"
echo "    | (DATA_DICTIONARY: 'canonical service name')"
echo ""

echo "H5  | oncall_schedule.service_name_raw can be joined to service_registry.service_name"
echo "    | (DATA_DICTIONARY: 'service name as written in the on-call tool export')"
echo ""

echo "H6  | incident_log.incident_id is unique: one row per logged incident"
echo "    | (DATA_DICTIONARY: 'One row per logged incident')"
echo ""

echo "H7  | incident_log.postmortem_doc references a filename in documents/postmortems/"
echo "    | (DATA_DICTIONARY: 'filename of the postmortem document')"
echo ""

echo "H8  | incident_log.updates uses the format ISO8601-timestamp|emp_id|note, ;-separated"
echo "    | (DATA_DICTIONARY: 'each entry is ISO8601-timestamp|emp_id|note, ;-separated')"
echo ""

echo "H9  | incident_log.date format is consistently ISO 8601 (YYYY-MM-DD)"
echo "    | (implied by ISO8601 use elsewhere, though DATA_DICTIONARY just says 'incident date')"
echo ""

echo "H10 | open_tickets.related_incident_id FK resolves to incident_log.incident_id when non-blank"
echo "    | (DATA_DICTIONARY: 'FK to incident_log.incident_id')"
echo ""

echo "H11 | Every service that appears in oncall_schedule also exists in service_registry"
echo "    | (implied: on-call assignments are for operated services)"
echo ""

echo "H12 | Every service in incident_log also appears in service_registry"
echo "    | (implied: incidents are for operated services)"
echo ""

echo "H13 | clearance_tier in engineer_roster has exactly the values 'general' and 'restricted'"
echo "    | (DATA_DICTIONARY: 'general or restricted, as provisioned by IT')"
echo ""

echo "H14 | Documents in documents/postmortems/ that are linked via postmortem_doc exist on disk"
echo "    | (implied by DATA_DICTIONARY description)"
echo ""

echo "H15 | A postmortem doc that exists on disk but is not linked via postmortem_doc is expected"
echo "    | (DATA_DICTIONARY: 'a document can exist before or without that link being made')"
echo ""

echo "H16 | 'Messaging and paging ships no dump' (DATA_DICTIONARY)"
echo "    | (confirmed by absence)"
echo ""

echo "H17 | oncall_schedule.currently_active has only 'true'/'false' values"
echo "    | (DATA_DICTIONARY: 'true if this is the current on-call shift')"
echo ""

echo "H18 | Each ticket type (A-E scenario examples) maps to a disposition"
echo "    | (scenario: each scenario needs different handling)"
echo ""

echo "H19 | The document store files are readable .docx format"
echo "    | (implied by 'hundreds to thousands of documents, growing')"
echo ""

echo "H20 | open_tickets.ticket_id is unique"
echo "    | (DATA_DICTIONARY: 'ticket identifier', implies PK)"
echo ""