# Data discovery — how the data was investigated and what it showed

For reviewers. This explains how the investigation of `fenwick-data-pack/` was done, what it found, where each finding
is enforced in code, and what is still open. Everything under `docs/discovery/` is the primary record; this page is the
reading guide and cross-reference.

Two kinds of statement appear here. Claims marked **(record)** come from the sealed discovery files. Claims marked
**(checked for this page)** are things I re-ran while writing it; they are not in `LOG.md` (which is append-only and
closed), so treat them as a reviewer's re-check, not as discovery output.

## 1. Method

- **Protocol.** [PROTOCOL.md](discovery/PROTOCOL.md) fixed the rules before any data was read: inputs only
  (`scenario.txt`, the data pack, `AGENTS.md`), no application code, no web; every command is a saved script in
  `scripts/discovery/`, standard library only; every question gets an append-only log entry; errors are logged.
- **Six steps.** (1) list the claims the data could contradict; (2) inventory files; (3) profile each CSV on
  completeness, validity, uniqueness, consistency, integrity, timeliness, distribution; (4) extract and read the 14
  `.docx` files; (5) cross-check every document rule against the data and trace the scenario tickets A–E; (6) write a
  rule and a test for each finding.
- **The record.**
  - [LOG.md](discovery/LOG.md): 13 entries, D-01 … D-13. Each has the question, why it was asked, the command, key
    output, observation, conclusion and the next question.
  - [scripts/discovery/](../scripts/discovery/): C01 … C13, one script per command. Output of each is in
    [docs/discovery/output/](discovery/output/) (`C01.txt` … `C13.txt`, plus
    [C12_docx_extracts_summary.txt](discovery/output/C12_docx_extracts_summary.txt) and the per-document text in
    [C12_docx_extracts/](discovery/output/C12_docx_extracts/)).
  - [FINDINGS.md](discovery/FINDINGS.md): F-01 … F-11, each with evidence, rule, test, confidence, plus ten open
    questions for the data's owners.
  - [sessions/turn-1-2.json](discovery/sessions/turn-1-2.json): the raw agent session export. Turns 1 and 2 ran in one
    OpenCode session, so the transcript covers D-01 to the findings.
- **Hypotheses.** [C01.txt](discovery/output/C01.txt) lists H1–H20, taken from `scenario.txt` and
  `DATA_DICTIONARY.md`. Examples: H1 "exactly 4 CSV files", H9 "incident_log.date is consistently ISO 8601", H4
  "service_name is the canonical name".

### The sealing commit

Commit **`3a8afc4`** ("discovery: findings (turns 1-2 ran in one OpenCode session)") is the point where the findings
were written and the discovery record closed. It adds `FINDINGS.md`, D-12 and D-13, C12 and C13 with their outputs, the
document extracts and the session export. Earlier commits: `e7f229f` (inputs only, nothing investigated) and `dbf60f4`
(steps 1–3, D-01 … D-11, C01 … C11). Later commits do not change anything under `docs/discovery/` except adding
`C14.txt` and `C15.txt` in `25b1a4c` (see section 4).

To see exactly what the reviewer saw at sealing: `git show 3a8afc4 --stat` and `git checkout 3a8afc4 -- docs/discovery`.

### Replaying it

From the repository root:

```bash
bash scripts/discovery/run_all.sh
```

It re-runs C01 … C13 in the original order and **overwrites** `docs/discovery/output/` in place. The scripts need only
Python 3 and the shell. Run it in a throwaway clone if you want to keep the committed outputs untouched
(`git archive 3a8afc4 | tar -x -C /some/dir`).

**(checked for this page)** I replayed `run_all.sh` from a copy of `3a8afc4` in a scratch directory. It exited 0.
C08, C09, C10, C11 and all 14 document extracts were byte-identical to the committed output. The other outputs differ
only in a run timestamp, the printing order of a Python set (C05, C13), and an absolute path in the C12 summary. No
number changed.

`run_all.sh` does not include C14 and C15: those two outputs came from the build phase and no script for them is in
`scripts/discovery/` (section 4).

## 2. Findings

Read each block as: tip-off → evidence → rule → code → test → evaluation case. Confidence is the discovery's own,
from [FINDINGS.md](discovery/FINDINGS.md). Where code or tests fall short of the rule, the block says so; those
points are collected in section 5.

Paths to code are relative to the repository root. Tests are in [tests/](../tests/) and evaluation cases in
[eval/cases.py](../eval/cases.py).

### F-01 · Clearance must be computed, not read from the roster

- **Tip-off.** The identity directory is "authoritative for who someone is" (`scenario.txt`), but
  `policy_access_and_clearance.docx` says the roster's `clearance_tier` "is expected to match this rule; owning teams are
  responsible for flagging and correcting any roster entry that has drifted" ([extract](discovery/output/C12_docx_extracts/policy_access_and_clearance.txt)).
- **Entries.** D-03 (roster is clean on its face: 14 rows, no blanks or duplicates), D-12 (policy read), D-13
  (cross-check). Scripts [C03](../scripts/discovery/C03_profile_roster.py), [C12](../scripts/discovery/C12_extract_docx.py),
  [C13](../scripts/discovery/C13_cross_checks.py). Output [C13.txt](discovery/output/C13.txt), cross-check 1.
- **Evidence.** The policy gives restricted clearance to every Security member and anyone at Senior/Staff or above.
  FEN-1002 Owen Baptiste (Payments, "Software Engineer") is `restricted` in the roster and should be `general`. All
  other 13 rows agree with the policy.
- **Rule.** Compute clearance from team and title. The roster column is only compared against it. A refusal says a
  restricted document exists and does not quote it.
- **Code.** [auth/clearance.py](../auth/clearance.py) `compute_clearance`, `can_see_document`; used by
  [engine/document_search.py](../engine/document_search.py).
- **Test.** [tests/test_clearance.py](../tests/test_clearance.py), [tests/test_data_rules.py](../tests/test_data_rules.py)
  `TestF01_ClearanceComputed`.
- **Evaluation.** B01–B04 (general filers refused), B05–B06 (restricted filers answered from the FINAL postmortem).
  No case files as Owen himself; B01 uses FEN-1003, who has the same team and title.
- **Gap.** `compute_clearance` does not match the policy. See section 5, item 1.

### F-02 · Service names must be normalized before any join

- **Tip-off.** `DATA_DICTIONARY.md` says `oncall_schedule.service_name_raw` is "as written in the on-call tool export"
  and `incident_log.service_name_raw` is "as logged at incident time"; `service_registry.service_name` is "canonical".
  H4, H5, H12 in [C01](discovery/output/C01.txt).
- **Entries.** D-05, D-07, D-09. Scripts [C05](../scripts/discovery/C05_profile_oncall.py),
  [C07](../scripts/discovery/C07_profile_incident_log.py), [C09](../scripts/discovery/C09_service_name_variants.py).
- **Evidence.** [C09.txt](discovery/output/C09.txt): 43,332 of 50,000 incident rows (86%) match the registry exactly;
  50,000 of 50,000 after lowercasing and `_` → `-`. Variants are `Auth-Gateway`/`auth_gateway` and
  `Payments-API`/`payments_api`; on-call has `Payments-API` and `auth_gateway`.
- **Rule.** `normalize_service` at ingestion and at every lookup.
- **Code.** [ingest/normalize.py](../ingest/normalize.py) `normalize_service`; applied in
  [ingest/csv_loader.py](../ingest/csv_loader.py), [engine/routing.py](../engine/routing.py),
  [engine/incident_matcher.py](../engine/incident_matcher.py).
- **Test.** `TestF02_ServiceNameNormalization` in [tests/test_data_rules.py](../tests/test_data_rules.py);
  [tests/test_normalize.py](../tests/test_normalize.py); [tests/test_routing.py](../tests/test_routing.py).
- **Evaluation.** A01, A03 (INC-2101 is logged as `Payments-API`), DL02, DL03.

### F-03 · Three date formats in one column

- **Tip-off.** H9: the data dictionary says only "incident date", while updates are said to be ISO 8601; the column was
  assumed consistent until profiled.
- **Entries.** D-07, D-08. Script [C08](../scripts/discovery/C08_date_format_crisis.py).
- **Evidence.** [C08.txt](discovery/output/C08.txt): ISO 16,668, `DD Mon YYYY` 16,666, `MM/DD/YYYY` 16,666, in
  roughly equal shares in each of 2024, 2025, 2026 (and in every service, C13 cross-check 11). 7,085 of the 16,666
  slash dates have both parts ≤ 12 and are ambiguous on their face.
- **Rule.** Try all three parsers; treat slash dates as month-first.
- **Code.** [ingest/normalize.py](../ingest/normalize.py) `parse_date`; `date_parsed` set in
  [ingest/csv_loader.py](../ingest/csv_loader.py).
- **Test.** `TestF03_DateParsing` in [tests/test_data_rules.py](../tests/test_data_rules.py);
  [tests/test_normalize.py](../tests/test_normalize.py).
- **Evaluation.** None directly. The only consumer of `date_parsed` is the recency sort in
  [engine/incident_matcher.py](../engine/incident_matcher.py).
- **Correction to the record.** FINDINGS says month-first is confirmed by "the rosters date format `07/22/2026`". The
  roster has no dates. **(checked for this page)** The real evidence is in the incident log: of the 16,666 slash dates,
  0 have a first part above 12, 9,581 have a second part above 12, and 7,085 are ambiguous. Month-first is the only
  reading that is consistent with the unambiguous rows. The decision stands; the stated reason in `FINDINGS.md` was wrong.

### F-04 · Five CSVs, not four

- **Tip-off.** "The dumps ship as documents/ plus four CSVs" (`scenario.txt`). H1.
- **Entries.** D-01, D-02 (H1 false), D-06. Scripts [C02](../scripts/discovery/C02_inventory.sh),
  [C06](../scripts/discovery/C06_profile_open_tickets.py).
- **Evidence.** [C02.txt](discovery/output/C02.txt): five `.csv` files. The fifth, `open_tickets.csv`, is the live
  hand-off queue: 25 rows, all `filed_by` and the one `related_incident_id` (TCK-0101 → INC-2115) resolve
  ([C06.txt](discovery/output/C06.txt)).
- **Rule.** Load all five; the queue's ticket ids accept follow-ups.
- **Code.** [ingest/csv_loader.py](../ingest/csv_loader.py) `load_all`, `csv_file_count`; queue used by
  [engine/duplicate_check.py](../engine/duplicate_check.py) and [adapters/orchestrator.py](../adapters/orchestrator.py).
- **Test.** [tests/test_csv_loader.py](../tests/test_csv_loader.py), `TestF04_FiveCSVs`.
- **Evaluation.** The briefing assigns F-04 to FU01/FU02 and DL01, but FU01/FU02 use freshly filed tickets and DL01 is a
  duplicate-of-INC-2115 case; none of them files against a `TCK-` id. **(checked for this page)** Posting a follow-up
  with `ticket_id: "TCK-0101"` returns 200 and the same id.
- **Note.** The C06 script prints a hard-coded "Latest is 2026-09-07T17:13:00" line (the script, line 94); the
  actual latest `filed_at` is 2026-09-07T14:31 (the same output's range line, and D-06). Harmless to the rule.

### F-05 · A deprecated service still has an on-call rotation

- **Tip-off.** `policy_oncall_rotation.docx`: "owning teams are responsible for removing a deprecated service's entries
  from the on-call tool." Registry marks `notifications-worker` deprecated.
- **Entries.** D-04, D-05, D-13. Output [C13.txt](discovery/output/C13.txt), cross-checks 2 and 10.
- **Evidence.** `notifications-worker` has two on-call rows (FEN-1014 active, FEN-1013 inactive).
- **Rule (findings).** Do not crash. **Rule (decisions).** Do not page the leftover rotation; tell the owning team
  ([DECISIONS Q3, Q4](design/DECISIONS.md)).
- **Code.** Action path refuses: [engine/action_decider.py](../engine/action_decider.py) `is_authorized_for_action`.
  Routing path still returns the old rotation: [engine/routing.py](../engine/routing.py) `get_oncall`.
- **Test.** `TestF05_DeprecatedOncall` in [tests/test_data_rules.py](../tests/test_data_rules.py); `TestF05` cases in
  [tests/test_routing.py](../tests/test_routing.py).
- **Evaluation.** REF01 (page on a deprecated service → refused).
- **Gap.** See section 5, item 2.

### F-06 · Three escalation times

- **Tip-off.** Three documents disagree: policy acknowledgement SLA SEV1 5 min / SEV2 15 min / SEV3 one business day
  ([policy](discovery/output/C12_docx_extracts/policy_oncall_rotation.txt)); escalation runbook, 10 minutes for
  SEV1/SEV2 ([runbook](discovery/output/C12_docx_extracts/runbook_oncall_escalation.txt)); Payments team notes, "we've
  been escalating after 3 minutes lately, not 10" ([notes](discovery/output/C12_docx_extracts/payments_team_notes_rollback.txt)).
- **Entries.** D-12, D-13 (cross-check 3 and 9).
- **Evidence.** The dumps hold no acknowledgement timestamps, so the real practice cannot be measured (C13).
- **Rule.** Findings: prefer the policy and make it configurable. Decisions (Q6) chose the tighter of policy and
  runbook per severity (5 / 10 / one business day), mention the conflict, and not follow the 3-minute note.
- **Code.** Not built. Designed only ([DECISIONS Q9](design/DECISIONS.md); BRIEFING §5, §8).
  [scripts/dq_report.py](../scripts/dq_report.py) prints the values.
- **Test.** `TestF06_EscalationTiming` in [tests/test_data_rules.py](../tests/test_data_rules.py) asserts a literal
  dict against itself. It checks no behaviour.
- **Evaluation.** None, on purpose (BRIEFING §9).

### F-07 · SRE is on call but owns nothing

- **Tip-off.** Roster teams include SRE; the registry's owning teams do not. Every postmortem names "on-call SRE" as
  incident commander.
- **Entries.** D-04, D-11, D-13 (cross-check 10).
- **Evidence.** `primary-db` and `notifications-worker` have SRE engineers on call.
- **Rule.** Do not restrict on-call lookup to the owning team.
- **Code.** [engine/routing.py](../engine/routing.py) `get_oncall` takes the active row regardless of team.
  **(checked for this page)** `primary-db` resolves to Beatrix Solano (SRE).
- **Test.** `TestF07` in [tests/test_routing.py](../tests/test_routing.py). The `TestF07_SREOncall` tests in
  `test_data_rules.py` only check the data.
- **Evaluation.** None for routing to SRE.

### F-08 · Two incident-id widths

- **Tip-off.** H6 (id format). The six incidents that the scenario and postmortems refer to are `INC-1994`,
  `INC-2031`, `INC-2058`, `INC-2077`, `INC-2101`, `INC-2115`; the other 49,994 are `INC-009000` and up.
- **Entries.** D-07, D-13. Output [C13.txt](discovery/output/C13.txt), cross-check 12.
- **Rule.** Accept both; treat ids as opaque. (FINDINGS also said new ids should use the short form;
  [DECISIONS Q2](design/DECISIONS.md) rejected that as guessing.)
- **Code.** [ingest/normalize.py](../ingest/normalize.py) `normalize_incident_id`;
  [engine/incident_matcher.py](../engine/incident_matcher.py).
- **Test.** `TestF08_IncidentIDFormats` in [tests/test_data_rules.py](../tests/test_data_rules.py);
  [tests/test_incident_matcher.py](../tests/test_incident_matcher.py).
- **Evaluation.** A01 (INC-2101 in `related`), DL01–DL03.

### F-09 · Documents the CSV does not link

- **Tip-off.** `DATA_DICTIONARY.md`: "a document can exist and be findable here before or without that link being
  made."
- **Entries.** D-10, D-12. Script [C10](../scripts/discovery/C10_updates_field_audit.py).
- **Evidence.** [C10.txt](discovery/output/C10.txt): four of six postmortems are linked; the two orphans are
  `postmortem_auth_gateway_outage_DRAFT_superseded.docx` and `postmortem_payments_api_canary_2026-09-04_DRAFT.docx`
  (about open INC-2101). No linked file is missing.
- **Rule.** Discover documents by scanning the store; skip the superseded draft; use the current draft but call it a draft.
- **Code.** [ingest/doc_loader.py](../ingest/doc_loader.py) `load_documents`;
  [engine/document_search.py](../engine/document_search.py); draft label in
  [adapters/orchestrator.py](../adapters/orchestrator.py).
- **Test.** `TestF09_DocumentDiscovery` in [tests/test_data_rules.py](../tests/test_data_rules.py);
  [tests/test_doc_loader.py](../tests/test_doc_loader.py); [tests/test_document_search.py](../tests/test_document_search.py).
- **Evaluation.** A01–A03 (cite the runbook and the canary draft), B05–B06 (FINAL, never the superseded draft).
- **Gap.** The draft label depends on which document ranks first. See section 5, item 4.

### F-10 · CRLF line endings

- **Tip-off.** [C02.txt](discovery/output/C02.txt): all five CSVs use CRLF.
- **Entries.** D-02.
- **Rule.** Parse with the `csv` module and `newline=""`.
- **Code.** [ingest/csv_loader.py](../ingest/csv_loader.py) `_csv_rows`.
- **Test.** `TestF10_CRLF` in [tests/test_data_rules.py](../tests/test_data_rules.py) (no `\r` in any loaded field);
  [tests/test_csv_loader.py](../tests/test_csv_loader.py).
- **Evaluation.** None; a startup property.

### F-11 · Update timestamps use the same three formats

- **Tip-off.** `DATA_DICTIONARY.md` says each update is `ISO8601-timestamp|emp_id|note`.
- **Entries.** D-10.
- **Evidence.** [C10.txt](discovery/output/C10.txt): timestamp formats `MM/DD/YYYYTHH:MM:SS` 187, ISO 159,
  `DD Mon YYYYTHH:MM:SS` 148 across the 494 open incidents. No malformed entry (all have three `|` parts).
- **Rule.** Same three-parser strategy.
- **Code.** [ingest/normalize.py](../ingest/normalize.py) `parse_update_timestamp`;
  [ingest/csv_loader.py](../ingest/csv_loader.py) `_parse_updates`. **(checked for this page)** 496 update entries,
  0 unparsed.
- **Test.** `TestF11_UpdateTimestamps` in [tests/test_data_rules.py](../tests/test_data_rules.py) (its bar is "fewer than
  50% fail", which is loose); [tests/test_normalize.py](../tests/test_normalize.py).
- **Evaluation.** DL02 is labelled F-11, but see section 5, item 5.

### The live-incident rule is a gap, not a finding

[DECISIONS](design/DECISIONS.md) says plainly that "live" (open with at least one update that is not the boilerplate
"Investigating, no update yet") is not a numbered finding, because no discovery entry counted placeholders by age. What
the record does hold: 492 of the 496 update entries are that boilerplate (samples in [C07.txt](discovery/output/C07.txt)
and [C10.txt](discovery/output/C10.txt)), and 494 incidents are open. **(checked for this page)** Under the rule, only
INC-2101 (`Payments-API`) and INC-2115 (`checkout-service`) are live; both belong to scenario tickets A/C and D. Code:
[engine/incident_matcher.py](../engine/incident_matcher.py) `is_live`.

## 3. Findings not handled

| Item | Why it is not handled |
| --- | --- |
| F-06, acknowledgement and escalation timers | Designed only. The build records the decision and does not run timers ([DECISIONS Q6, Q9](design/DECISIONS.md)). |
| F-06 per-team configurability (the Payments 3-minute figure) | Rejected in Q6: the notes are unofficial; the conflict is mentioned, not followed. |
| F-08 "generate new ids in the short form" | Rejected in Q2: ids are opaque; no new incident ids are generated. |
| F-09 hiding or deleting the superseded draft | Not done. Search skips it; the file stays. Whether it should be removed is an owner question. |
| F-03 "log and flag unparseable rows" | Nothing is flagged because nothing fails: all 50,000 dates parse. |
| D-12 / D-13 notes with no rule: DRAFT canary postmortem references an open incident; docs have no tracked changes | Informational. The first is used by F-09; the second needs no handling. |
| Open questions 1, 2, 3, 7, 8 in [FINDINGS.md](discovery/FINDINGS.md) (who set Owen's tier and whether other tiers drifted; why three date formats; why two id schemes; whether the queue is filtered; who pages SRE for `primary-db`) | Only the data's owners can answer. The build does not depend on the answers. |
| Open questions 4, 5, 6, 9, 10 | Settled as assumptions in [DECISIONS](design/DECISIONS.md) (orphan drafts, escalation values, deprecated services, `filed_by` trusted per the brief, no search index at 14 documents). |

## 4. Findings that surfaced only while building or evaluating

Sources: [PROGRESS.md](../PROGRESS.md), `git log`, the two committed evaluation runs in
[eval/results/](../eval/results/), and the two build-phase traces
[C14.txt](discovery/output/C14.txt) (plan and steps for sample tickets C01, D01, E01, FA02, B01) and
[C15.txt](discovery/output/C15.txt) (plan-versus-steps_run check of the same tickets). No script for C14/C15 is in
`scripts/discovery/`.

1. **Sensitivity is a marking in the document, not a word.** D-12 flagged `policy_access_and_clearance.docx` as
   RESTRICTED because the word appears in it (see "MARKING" at the top of its section in
   [C12 summary](discovery/output/C12_docx_extracts_summary.txt)). The policy itself is general. The marking that matters
   is a standalone line `RESTRICTED — see policy_access_and_clearance.docx` in the two auth-gateway postmortems.
   Corrected in [DECISIONS Q4](design/DECISIONS.md) (commit `226f166`), implemented in
   [ingest/doc_loader.py](../ingest/doc_loader.py).
2. **The hand-off queue gives "already being worked on" a definition.** DECISIONS Q5 rests on the 25 queue tickets in
   [C13.txt](discovery/output/C13.txt) (cross-check 14): TCK-0101 is linked to INC-2115; TCK-0102 is a different
   problem (errors, not latency) that D-13 called a "potential duplicate". Decided in `226f166`.
3. **Escalation values changed in review.** The first briefing took the policy's 15 minutes for SEV2; the review pass
   (`a50236d`) switched to the runbook's 10 and recorded the policy value as a conflict.
4. **Evaluation cases were rewritten between the two committed runs (18:50 and 19:00).** The first run expected D04 and
   D05 (checkout errors, TCK-0102's shape) to be `routed`, DL01 `routed`, and DL02/DL03 to cite `INC-009012`. The second
   run expects `duplicate` for D04, D05, DL01 and `INC-2101` for DL02/DL03. Both D04/D05 expectations after the change
   contradict DECISIONS Q5/Q8 (TCK-0102 is routed). See section 5, item 3.
5. **Evaluation bars as committed** ([latest_summary.md](../eval/results/latest_summary.md)): restricted leaks 0,
   wrongful refusals 0, disposition and routing 100% (30/30), p95 1.51 s, but "planned steps executed" 37.5% (12/32),
   which fails the 100% bar, and 13 of 33 cases pass all their checks. Every failing check in the 19:00 run is
   `plans_executed`: plan labels such as "check open incidents" are compared with tool names such as `check_incidents`
   (C15 shows the same mismatch). I did not determine whether the plan or the check is the faulty side.
6. **Test suite** (**checked for this page**, `GROQ_API_KEY` unset): 296 passed, 2 failed. The two failures are the
   `TestLLMAdapter` mock-transport tests that the Groq commit `df752ea` already marks as work in progress.
7. **Rules-fallback classification can wrongly refuse.** **(checked for this page)** Without a model, "auth-gateway is
   returning 500s" from a general filer is classified as a document question and refused because a restricted
   document exists; it is a live problem and should route to on-call. This is a wrongful refusal, and it also tells a
   general filer that a restricted document exists.
8. **Hand-off follow-ups work.** A follow-up on `TCK-0101` is accepted (F-04 above).

## 5. Where the build falls short of the findings

These are open, not fixed by this page.

1. **Clearance code is not the policy.** `compute_clearance` also treats the whole SRE team as restricted and treats
   "lead" and "principal" as senior. The policy lists only Security and Senior/Staff-or-above. Effect: FEN-1013 and
   FEN-1014 (SRE, title "SRE"; `general` in the roster and in `FILER_INFO` in `eval/cases.py`) are computed `restricted`.
   **(checked for this page)** FEN-1013 asked about the auth-gateway outage and was answered from the restricted FINAL
   postmortem. Under the policy and DECISIONS Q4 that ticket is a refusal. `tests/test_clearance.py` asserts the SRE
   behaviour, so the tests agree with the code and not with the policy. Owen (FEN-1002) is correctly `general` and is
   refused.
2. **Deprecated service still routes.** **(checked for this page)** A live-problem ticket about `notifications-worker`
   is routed to Wren Castellano (the leftover rotation). DECISIONS Q3 says not to route to that rotation.
3. **TCK-0102-shaped reports are duplicates in code, routed in the design.** **(checked for this page)** "customers
   reporting checkout-service errors intermittently today, seems unrelated to latency" returns `duplicate` of INC-2115.
   DECISIONS Q5/Q8 and BRIEFING §9 say `routed`. Evaluation cases D04, D05 and DL01 were changed to match the code
   (item 4 in section 4); the design documents were not.
4. **Draft label is conditional.** The `[DRAFT — not yet finalized]` label is added only when the draft is the top-ranked
   document. In A01 the runbook ranks first, the canary draft is cited, and **(checked for this page)** the answer text
   does not say "draft". DECISIONS Q8 requires the label whenever the draft is cited.
5. **F-11 is not load-bearing.** The live rule reads the update notes, not the timestamps, and
   `timestamp_parsed` is not read by anything in `engine/`. DL02/DL03 pass whether or not the timestamps parse.
6. **Who may ask for an action is stricter in code than in the design.** DECISIONS Q4 rejects the "owning team, or
   on-call, or SRE" rule and lets any engineer ask for a page or an incident on an active service. **(checked for this
   page)** [engine/action_decider.py](../engine/action_decider.py) `is_authorized_for_action` requires the owning team,
   SRE or Security. A Platform engineer paging `payments-api` is refused (eval C03, REF03), whereas DECISIONS Q8 says
   case C is `action_decided` for a filer who is not on the Payments team. The evaluation cases encode the code's rule.
7. **Refusal text.** The refusal says "contact your team lead or the document owner". DECISIONS Q4 and the policy say to
   name the owning team.
