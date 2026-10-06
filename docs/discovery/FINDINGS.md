# Data discovery findings

Written per protocol Step 6. Each finding states a rule the system should apply and a test that would fail if the rule were wrong. Open questions at the end.

---

### F-01 · Clearance tier provisioning error
- **Evidence**: Owen Baptiste (FEN-1002) has `restricted` clearance in engineer_roster.csv but the policy `policy_access_and_clearance.docx` says he should have `general` — he is a Payments Software Engineer (not Security team, not Senior/Staff title). D-13.
- **Rule**: The system MUST NOT trust the `clearance_tier` column blindly. It SHOULD recompute clearance from team and title per the policy rule, OR reconcile the roster against the policy at startup and log/track discrepancies. A ticket filed_by a user whose computed and stored clearance disagree should at minimum be flagged.
- **Test**: Feed a query from a general-user employee who matches FEN-1002's profile (non-Security, non-Senior) to a restricted document. If the system serves the document, the rule is wrong.
- **Confidence**: high

### F-02 · Service name normalization required for cross-file joins
- **Evidence**: incident_log.csv uses 14 distinct `service_name_raw` values while service_registry.csv defines 10 canonical names. Only 86% of incident rows match exactly; 100% match after lowercasing and replacing underscores with hyphens. The 4 variant groups are: `auth-gateway`/`auth_gateway`/`Auth-Gateway`, `payments-api`/`Payments-API`/`payments_api`, plus 8 services with exact-only matches. D-09, D-05, D-07.
- **Rule**: The system MUST normalize service names with a standard function (lowercase, `_` → `-`) before any join or lookup across files. The normalization table should be explicit and logged.
- **Test**: Join incident_log to service_registry without normalization. Count unmatched rows. If >0, the test catches non-normalized joins; if 0 after fix, the rule is applied.
- **Confidence**: high

### F-03 · Date parsing must handle three coexisting formats
- **Evidence**: incident_log.csv's `date` column contains exactly three formats in equal proportion (~33% each): ISO `YYYY-MM-DD`, `DD Mon YYYY`, and `MM/DD/YYYY`. All three appear in every year (2024–2026) and every service. Within the `updates` field, timestamps mirror the same three-way split. 7,085 of 16,666 slash-format dates are ambiguous (both month and day ≤12). D-08, D-10.
- **Rule**: The system MUST attempt all three parsers and handle ambiguous MM/DD/YYYY dates deterministically (pick MM/DD/YYYY convention as default — the rosters date format `07/22/2026` confirms Fenwick uses MM/DD/YYYY). Parse failures for a format should fall through to the next parser. Unparseable rows should be logged and flagged.
- **Test**: Sort incidents by date using naive string sort. Compare to date-sorted using the three-parser approach. If differently ordered, the test catches the format gap.
- **Confidence**: high

### F-04 · The data pack contains 5 CSV files, not 4
- **Evidence**: scenario.txt states "documents/ plus four CSVs". The pack ships 5 CSV files: engineer_roster.csv, service_registry.csv, oncall_schedule.csv, incident_log.csv, and open_tickets.csv. D-02, D-01 (H1).
- **Rule**: The system design should not assume 4 sources. The fifth file (open_tickets.csv) is the active queue and is essential for the task.
- **Test**: Count CSV files in the data pack. If the design says "4 CSVs", it is incorrect.
- **Confidence**: high

### F-05 · Deprecated service notifications-worker still has active on-call assignments
- **Evidence**: notifications-worker is marked `deprecated` in service_registry.csv but has an active on-call entry (FEN-1014) in oncall_schedule.csv. The policy `policy_oncall_rotation.docx` says deprecated services "are wound down from the rotation once decommissioning begins." D-13, D-05.
- **Rule**: The system should handle on-call for deprecated services gracefully (i.e., not break when queried) but may note the inconsistency. The system must not assume service status and on-call presence are perfectly aligned.
- **Test**: Query on-call for a deprecated service. If the system crashes or returns no result when an entry exists, the rule is wrong.
- **Confidence**: medium

### F-06 · Escalation timing is documented inconsistently
- **Evidence**: `runbook_oncall_escalation.docx` says escalate after 10 minutes without acknowledgement. `payments_team_notes_rollback.docx` says the team "has been escalating after 3 minutes lately." The official policy `policy_oncall_rotation.docx` defines acknowledge SLAs (SEV1=5min, SEV2=15min, SEV3=1 business day). D-12, D-13.
- **Rule**: The system should prefer the official policy SLAs as defaults but should make escalation timing configurable per team or service, since documented practice differs from official procedure.
- **Test**: If the system hardcodes 10 minutes as the universal escalation threshold, it would be wrong for the Payments team that uses 3 minutes.
- **Confidence**: medium

### F-07 · SRE team exists in roster but owns no services
- **Evidence**: 3 SRE engineers in engineer_roster.csv (Beatrix Solano, Ravi Deshpande, Wren Castellano). No service in service_registry.csv is owned by SRE. SRE appears as on-call for primary-db and notifications-worker. All postmortems list "Incident commander: on-call SRE." D-11, D-13.
- **Rule**: The system should include SRE engineers in the on-call lookup for any service where they are assigned, even though they own no service. SRE's role is incident command, not service ownership.
- **Test**: If the system restricts on-call paging to owning-team members only, SRE would never be reached for primary-db incidents — contradicting the runbooks.
- **Confidence**: high

### F-08 · Two incident numbering conventions coexist
- **Evidence**: 6 incidents use short IDs (`INC-1994`, `INC-2031`, `INC-2058`, `INC-2077`, `INC-2101`, `INC-2115`) while 49,994 use long IDs (`INC-009000` through `INC-058XXX`). The short IDs are more recent (June–September 2026) than long IDs (January 2024–), suggesting a numbering reset or two merged systems. D-07, D-13.
- **Rule**: The system should accept both INC-NNNN and INC-NNNNNN formats as incident IDs and treat them uniformly. ID generation for new incidents should follow the newer short format.
- **Test**: If the system validates incident IDs with a single regex (e.g., `^INC-\d{6}$`), the 6 short-ID incidents will fail to match.
- **Confidence**: high

### F-09 · Only 4 of 6 postmortems on disk are linked from incident_log
- **Evidence**: 6 postmortem .docx files exist on disk. Only 4 are referenced in incident_log.csv's `postmortem_doc` column. Orphans: `postmortem_auth_gateway_outage_DRAFT_superseded.docx` (known superseded version), `postmortem_payments_api_canary_2026-09-04_DRAFT.docx` (new DRAFT for INC-2101, not yet linked). D-10, D-06.
- **Rule**: The system should discover documents by scanning the document store, not only by following CSV links. A DRAFT document that exists on disk but is not in the CSV is still findable by someone who searches for it.
- **Test**: Search for "payments-api canary" using only CSV-linked postmortem paths. The result will miss the DRAFT document that answers the question.
- **Confidence**: high

### F-10 · CRLF line endings on all CSVs require correct parser handling
- **Evidence**: All 5 CSV files use CRLF (`\r\n`) line endings. Python's `csv` module handles this transparently with `newline=''` but naive line splitting would leave trailing `\r` on every field. D-02.
- **Rule**: All CSV parsing code must handle CRLF line endings correctly. The `newline=''` parameter in Python's CSV reader handles this; naive `split('\n')` or similar would break.
- **Test**: Parse a CSV line with split('\n') and check the last field for trailing \r.
- **Confidence**: high

### F-11 · Updates field structure is reliable but timestamps have the same three-format problem
- **Evidence**: The updates field in incident_log.csv uses the `ISO8601-timestamp|emp_id|note;` structure described in DATA_DICTIONARY.md. 494 rows have updates (all open incidents). Timestamp format splits exactly like the date column: ISO8601, MM/DD/YYYYTHH:MM:SS, and DD Mon YYYYTHH:MM:SS. D-10.
- **Rule**: The same three-parser date strategy must be applied to update timestamps. The `|` delimiter is reliable (no malformed entries found across all 494 update rows).
- **Test**: Parse an update timestamp assuming only ISO8601 format. Over 60% of timestamps will fail. If the three-parser fallback is applied, all pass.
- **Confidence**: high

---

## Open questions

Questions I would ask the data's owners before relying on this data in production:

1. **Why is Owen Baptiste (FEN-1002) marked `restricted` in the roster when the clearance policy says he should be `general`?** Is this a provisioning error in the roster, or is there an exception to the policy that is not documented? If it's an error, how many other entries have drifted?

2. **Why are there three date formats in incident_log.csv and its updates field?** Are these from three different systems (e.g., merged exports from different regions, different tracker tools) that were concatenated without normalization? Which format should NEW records use?

3. **Why do the 6 most recent incidents use a different ID numbering scheme (INC-1994–2115) from the 49,994 preceding ones (INC-009000+)?** Was there a tracker migration, a reset, or are these from a second tracker instance?

4. **Do the 2 orphan postmortems (DRAFT superseded and canary DRAFT) represent deliberate omissions or just lag?** Specifically: should the canary DRAFT be findable by an engineer searching for the current payments-api incident? Should the superseded DRAFT be hidden or deleted?

5. **Is the escalation timing in the Payments team notes (3 minutes) an approved exception or a team-local shortcut?** Should the system use 3 minutes for Payments services and 10 for others, or is the official 10 minutes the correct universal value?

6. **Should deprecated services like notifications-worker still have active on-call entries?** Is decommissioning in progress, or was this an oversight in the on-call tool?

7. **Does the open_tickets.csv represent ALL open tickets, or was it filtered (e.g., excludes tickets that are already linked to an incident)?** 24 of 25 tickets have no `related_incident_id` — is this typical?

8. **Who pages the on-call SRE for primary-db incidents if SRE owns no service?** The runbooks and postmortems all say "Incident commander: on-call SRE" — how is this routed today?

9. **Is the `filed_by` field in POST /tickets truly trusted for authorization, or should the system re-verify the caller's identity against the identity directory?**

10. **What is the expected latency/cost profile for document searches?** With "hundreds to thousands of documents, growing" per scenario.txt, naive full-text search across 14 files works in the prototype but would need a search index at scale.