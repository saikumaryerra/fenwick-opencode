# Discovery log

Append-only. Format and method: [PROTOCOL.md](PROTOCOL.md).

### D-01 · 2026-10-06 12:09 · What statements in the inputs could the data contradict?
- Why: Step 1 of the protocol — read scenario.txt and DATA_DICTIONARY.md, list every testable claim.
- Command: `scripts/discovery/C01_claims.sh` → `docs/discovery/output/C01.txt`
- Key output: "H1 | There are exactly 4 CSV files shipped alongside documents/" / "H4 | service_registry.service_name is the canonical service name" / "H9 | incident_log.date format is consistently ISO 8601"
- Observation: 20 hypotheses (H1–H20) recorded covering format claims, FK relationships, uniqueness, domain constraints, and document linking.
- Conclusion: H1 is immediately falsifiable (5 CSVs found, not 4). Several others (H4, H9, H5, H11) require cross-file verification. (confidence: high)
- Next: Inventory — are the 5 CSVs and 14 docx files as described?

### D-02 · 2026-10-06 12:09 · What are every file's size, line count, encoding and line endings?
- Why: Step 2 of the protocol — inventory all files in the data pack.
- Command: `scripts/discovery/C02_inventory.sh` → `docs/discovery/output/C02.txt`
- Key output: "2 CSV files found" / "Total docx: 14" / "5 .csv files found, scenario.txt says 'four CSVs'" / "All CSVs: CRLF (\\r\\n) line endings, CSV ASCII text"
- Observation: Files inventoried. incident_log.csv is the giant at 50K lines/5.9MB; all others <1KB. 14 docx files across 3 folders. All CSVs use CRLF line endings. All text is ASCII. H1 is confirmed false — the pack ships 5 CSVs, not 4.
- Conclusion: The scenario.txt claim of "four CSVs" is wrong. A system built on the dumps needs to handle 5 structured sources. (confidence: high)
- Next: Profile each structured file against 7 quality dimensions.

### D-03 · 2026-10-06 12:10 · Is engineer_roster.csv complete, valid, unique, and consistent?
- Why: Step 3 — profile the identity directory, which scenario.txt calls "Authoritative for who someone is."
- Command: `scripts/discovery/C03_profile_roster.py` → `docs/discovery/output/C03.txt`
- Key output: "Rows: 14" / "clearance_tier values: {'restricted': 7, 'general': 7}" / "Duplicate emp_id: 0" / "Any field empty: 0 rows"
- Observation: All 14 rows fully populated. No missing values, no duplicates. Clearance is exactly 50/50 restricted/general. Teams are Payments (3), Billing (3), Platform (3), Security (2), SRE (3). All emp_ids follow FEN-NNNN format. H3 holds (unique, authoritative).
- Conclusion: This file is clean — no data quality issues. A system can rely on emp_id as a stable FK. (confidence: high)
- Next: Does service_registry hold the same quality?

### D-04 · 2026-10-06 12:10 · Is service_registry.csv complete and authoritative for service identity?
- Why: Step 3 — profile the service catalog.
- Command: `scripts/discovery/C04_profile_service_registry.py` → `docs/discovery/output/C04.txt`
- Key output: "Rows: 10" / "service_name patterns: {'lowercase-hyphenated': 10}" / "owning_team values: {'Payments': 2, 'Billing': 2, 'Platform': 5, 'Security': 1}" / "Duplicate service_name: 0"
- Observation: All 10 rows complete, no duplicates. 9 active, 1 deprecated (notifications-worker). H4 holds (service_name is canonical). No SRE-owned service — SRE only exists as a team in the roster, not as owners.
- Conclusion: Clean file. The canonical lowercase-hyphenated naming convention is well-enforced. (confidence: high)
- Next: Does oncall_schedule actually join to this clean registry?

### D-05 · 2026-10-06 12:10 · Can oncall_schedule be reliably joined to service_registry and engineer_roster?
- Why: Step 3 — profile on-call data; test H5 (joinability), H11 (service existence), H17 (currently_active domain).
- Command: `scripts/discovery/C05_profile_oncall.py` → `docs/discovery/output/C05.txt`
- Key output: "service_name_raw with no exact match in service_registry: ['Payments-API', 'auth_gateway']" / "engineer_emp_id not in engineer_roster: []" / "currently_active values: {'true': 10, 'false': 5}" / "Number of distinct name variants: 11"
- Observation: 15 rows, all populated. All engineer_emp_ids resolve. However, 2 of 11 service_name_raw values ('Payments-API', 'auth_gateway') have NO exact match in service_registry because of case/separator differences. H5 is partially false — joining requires normalization. H17 holds (true/false only). 10 active, 5 inactive assignments.
- Conclusion: All FKs resolve with normalization (lowercase, underscore→hyphen). A system MUST normalize service names to join reliably. The normalization is simple and lossless. (confidence: high)
- Next: Do the 25 open tickets also join cleanly? And what about the 50K-incident log?

### D-06 · 2026-10-06 12:10 · Are open_tickets.csv's FKs resolvable and its data timely?
- Why: Step 3 — profile open_tickets; test H2 (snapshot), H10 (incident FK), H18 (ticket content), H20 (ticket_id uniqueness).
- Command: `scripts/discovery/C06_profile_open_tickets.py` → `docs/discovery/output/C06.txt`
- Key output: "Rows: 25" / "Duplicate ticket_id: 0" / "filed_by not in engineer_roster: [] (all OK)" / "related_incident_id not in incident_log: [] (all OK)" / "Filed date range: [2026-09-02] — [2026-09-07]"
- Observation: All 25 tickets clean. All filers exist in roster. Only 1 of 25 tickets has a related_incident_id (TCK-0101 → INC-2115), and it resolves. Latest ticket is 2026-09-07T14:31 — matches "as of hand-off." H2, H10, H20 all hold.
- Conclusion: Open tickets are a clean, small snapshot. The 24 tickets without incident links are "self-serve" inquiries or non-incident requests. (confidence: high)
- Next: Profile the 50K-row incident_log — this is where surprises live.

### D-07 · 2026-10-06 12:10 · What quality issues hide in the 50,000-row incident_log.csv?
- Why: Step 3 — profile the largest file across all 7 dimensions.
- Command: `scripts/discovery/C07_profile_incident_log.py` → `docs/discovery/output/C07.txt`
- Key output: "postmortem_doc blank: 49996/50000" / "updates blank: 49506/50000" / "Date formats: {'ISO (YYYY-MM-DD)': 16668, 'DD Mon YYYY': 16666, …many MM/DD/YYYY variants…}" / "service_name_raw values exactly matching service_registry: 10/14" / "Inc ident format: 6 with INC-0000, 49994 with INC-000000" / "Severity: SEV1=2492, SEV2=12562, SEV3=34946" / "Open: 494, Resolved: 49506"
- Observation: Massive but sparse — 99.99% lack postmortem_doc links, 99% lack updates. **THREE date formats** coexist in the same column (~⅓ each). Service naming has 14 distinct values vs 10 canonical names. 2 separate incident_id numbering styles (6 old short IDs, 49994 long IDs). 4 postmortem filenames are linked; only 494 incidents are open.
- Conclusion: This file has major date-format integrity issues and service-name joinability problems. A consuming system must handle both. (confidence: high)
- Next: How deeply are the dates broken? Can they be parsed safely? Are the service-name variants fully mappable?

### D-08 · 2026-10-06 12:11 · What are the exact date format proportions by year?
- Why: D-07 revealed 3 date formats. Need to understand if they cluster by year or are mixed evenly (which would mean deeper corruption).
- Command: `scripts/discovery/C08_date_format_crisis.py` → `docs/discovery/output/C08.txt`
- Key output: "ISO (YYYY-MM-DD): 16668 (33.3%)" / "DD Mon YYYY: 16666 (33.3%)" / "MM/DD/YYYY: 16666 (33.3%)" / "Distribution by year — each year has all 3 formats, roughly equal" / "Ambiguous (both parts <=12, could be DD/MM or MM/DD): 7085"
- Observation: All 3 formats appear in every year (2024, 2025, 2026) in roughly equal proportions (~⅓ each). They are NOT segregated by source or time period. 7085 of 16666 MM/DD/YYYY entries are ambiguous (both month and day ≤12). The three-way split is consistent across the entire 50K dataset, suggesting it is systematic (e.g., from 3 different system exports merged without normalization).
- Conclusion: Any system parsing incident_log dates MUST try all 3 parsers and accept that 42% of slash-format dates are ambiguous by string alone. Resolving ambiguous dates may require external evidence or a documented convention. (confidence: high)
- Next: Are all service names at least normalizable, even if not exact matches?

### D-09 · 2026-10-06 12:11 · Are all service-name variants in incident_log and oncall_schedule normalizable to canonical names?
- Why: D-07 found 14 distinct service_name_raw values vs 10 canonical names. Need to know if any are irrecoverable.
- Command: `scripts/discovery/C09_service_name_variants.py` → `docs/discovery/output/C09.txt`
- Key output: "incident_log rows with exact match: 43332/50000 (86%)" / "incident_log rows normalizable: 50000/50000 (100%)" / "Variant groups — auth-gateway: ['Auth-Gateway', 'auth-gateway', 'auth_gateway']" / "payments-api: ['Payments-API', 'payments-api', 'payments_api']"
- Observation: Every single one of the 50K incident rows maps to a canonical name after lowercasing and replacing underscores with hyphens. No unmappable names exist. The 4 variant groups are: auth-gateway (3 variants), payments-api (3 variants), and 8 services with exact-only matches. oncall_schedule's 2 mismatches also normalize cleanly.
- Conclusion: A simple normalization function (lowercase, _→-) resolves 100% of service name references. H4 holds with normalization. A system should apply this normalization at ingestion. (confidence: high)
- Next: Audit the updates field — is its structure reliable? And do postmortem doc links match disk?

### D-10 · 2026-10-06 12:12 · Is the updates field structured correctly and do postmortem doc links resolve?
- Why: D-07 found sparse updates and postmortem links. Need to validate the format DATA_DICTIONARY describes and check disk/filesystem integrity.
- Command: `scripts/discovery/C10_updates_field_audit.py` → `docs/discovery/output/C10.txt`
- Key output: "Rows with updates: 494 (all 'open' status)" / "Timestamp formats: MM/DD/YYYYTHH:MM:SS (nonstandard): 187, ISO8601: 159, 'DD Mon YYYYTHH:MM:SS': 148" / "ORPHAN docs on disk not linked: ['postmortem_auth_gateway_outage_DRAFT_superseded.docx', 'postmortem_payments_api_canary_2026-09-04_DRAFT.docx']" / "MISSING docs: []"
- Observation: The updates field has its own three-way date format crisis matching the main date column's pattern. All 494 open incidents have exactly updates matching their status (0 open with no updates, 0 resolved with updates). All 4 linked postmortem docs exist on disk. 2 additional docs are on disk but unlinked (the superseded DRAFT and a new DRAFT). No malformed update entries found (all 3-pipe parts).
- Conclusion: H8 partially holds (structure is correct) but the timestamp format within updates is inconsistent — same three-way split as the date column. The orphan docs represent content the CSV hasn't caught up with yet. (confidence: high)
- Next: Do the 5 scenario tickets (A–E) from scenario.txt actually appear in the data? How do the systems line up?

### D-11 · 2026-10-06 12:13 · Do the scenario example tickets (A–E) exist in the data, and do cross-file references hold?
- Why: The protocol requires tracing example scenarios against data. Also need cross-file FK checks.
- Command: `scripts/discovery/C11_scenario_mapping.py` → `docs/discovery/output/C11.txt`
- Key output: "TCK-0101 → INC-2115 (open, SEV2): Checkout latency climbing..." / "No ticket matches scenario A (payments-api canary 5xx) exactly" / "On-call engineers not in roster: none" / "Team diff: SRE exists in roster but owns no service in registry"
- Observation: Only Ticket D (checkout latency) maps to a real ticket in open_tickets.csv. The other 4 scenario examples are illustrative — they DO NOT appear in the dump. The on-call data resolves correctly (Priya Nathan, FEN-1001, is on-call for payments-api). FKs all resolve across files. Notable: SRE team exists in roster but owns no service in registry — SRE only handles primary-db on-call. Also: 2 different incident_id numbering styles (6 short IDs, 49994 long ones like INC-009000+).
- Conclusion: The scenario examples are realistic but not all present in the dump. The system must handle examples not in the training set. Cross-file integrity is solid after name normalization. The SRE mismatch needs design attention — who pages SRE if they own nothing? (confidence: high)
- Next: Step 4 — extract unstructured documents (14 .docx files).

### D-12 · 2026-10-06 13:10 · What do the 14 unstructured documents contain, and what rules do they state?
- Why: Step 4 of the protocol — extract every .docx, scan for tracked/hidden content, record metadata, read fully.
- Command: `scripts/discovery/C12_extract_docx.py` → `docs/discovery/output/C12_docx_extracts_summary.txt` (full extracts in `docs/discovery/output/C12_docx_extracts/`)
- Key output: "Total documents: 14, Total rules extracted: 78" / "No tracked changes detected" / "RESTRICTED docs: policy_access_and_clearance, both auth-gateway postmortems" / "payments_team_notes_rollback says escalation is 3 min, not 10 min"
- Observation: All 14 documents extracted cleanly — zero tracked changes/revisions. Two key policies (access & clearance, on-call rotation) define the system rules. 6 postmortems document past incidents; 2 are RESTRICTED (both auth-gateway versions). 6 runbooks describe procedures. The payments team notes contain an unofficial escalation window (3 min) that contradicts the official runbook (10 min). The DRAFT canary postmortem references INC-2101 which IS an open incident. Critical clearance rule codified: restricted = Security team (any title) OR Senior/Staff+ (any team).
- Conclusion: Document store is well-structured but contains contradictions (escalation timing) and unlinked content (orphan DRAFTs). The clearance policy is the most important rule for system design. (confidence: high)
- Next: Cross-check every documented rule against the data — do the CSVs follow what the documents say?

### D-13 · 2026-10-06 13:15 · Does the data follow the rules stated in the policies and postmortems?
- Why: Step 5 — test every document rule against the structured data; compare every pair of sources that describe the same thing; trace every scenario.
- Command: `scripts/discovery/C13_cross_checks.py` → `docs/discovery/output/C13.txt`
- Key output: "MISMATCH: FEN-1002 (Owen Baptiste) — team=Payments, title=Software Engineer, actual=restricted, expected=general" / "Deprecated services still with on-call entries: [notifications-worker]" / "INC-2101 found — matches scenario A exactly" / "SRE in roster but no service ownership"
- Observation: 14 cross-checks performed. **Clearance policy violation found**: Owen Baptiste (FEN-1002) is a Payments Software Engineer (not Senior/Staff, not Security) but has `restricted` clearance in the roster — the policy says he should be `general`. notifications-worker is still on the on-call rotation despite being deprecated. **Every other cross-check passed**: clearance assignment for all other 13 engineers is correct; all incident FKs resolve; INC-2101 exists (open, matches scenario A's "payments-api canary 5xx" exactly); the checkout latency scenario (D) has a potential duplicate (TCK-0102 filed 4 hours earlier). The escalation timing contradiction (3 min vs 10 min) is a documentation quality issue, not a data issue. Date formats are evenly split per service (every service has 33% of each format), confirming the format mix is system-wide, not per-service.
- Conclusion: The clearance_tier column has at least 1 provisioning error (Owen Baptiste should be general, not restricted). A system relying on the roster for authorization could over-authorize Owen. The deprecated-service-on-call issue is a gap but won't break a system. Everything else cross-checks correctly. (confidence: high)
- Next: Write FINDINGS.md with all rules and tests.
