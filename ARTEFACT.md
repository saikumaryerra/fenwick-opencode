# ARTEFACT — what calling the endpoint cannot show

Design entry point: [APPROACH.md](APPROACH.md). This file does not re-describe endpoint responses.

**Where the numbers come from.** Each number below is from a committed file, named next to it:
[docs/dq_report.txt](docs/dq_report.txt) (output of [scripts/dq_report.py](scripts/dq_report.py), generated from the data
pack), the [discovery outputs](docs/discovery/output/), the [evaluation results](eval/results/), [PROGRESS.md](PROGRESS.md)
and `git log`. Where a figure is an estimate or comes from nowhere committed, it says so. The evaluation results were
produced by the code at commit `25b1a4c`; the code has changed since (section 3).

## 1 · Data quality

Where the systems disagreed with each other, with the data dictionary, or with a policy, and the rule applied.
Evidence is in [FINDINGS.md](docs/discovery/FINDINGS.md) and [DATA_DISCOVERY.md](docs/DATA_DISCOVERY.md); the rules are
enforced in [ingest/](ingest/) and [auth/](auth/).

| # | Disagreement | Numbers | Rule applied | Source |
| --- | --- | --- | --- | --- |
| 1 | Brief says four CSVs | 5 CSVs in the pack | Load all five; the fifth (`open_tickets.csv`, 25 rows) is the live queue | [dq_report](docs/dq_report.txt), [C02](docs/discovery/output/C02.txt) |
| 2 | Service names differ by case and separator across files | Incident log: 14 distinct raw names against 10 canonical, 43,332 of 50,000 rows (86%) match exactly, 50,000 after lowercasing and `_` → `-`. On-call: 11 raw names, 9 exact | Normalize before every join or lookup | [C09](docs/discovery/output/C09.txt) |
| 3 | Dictionary says only "incident date"; the column holds three formats | ISO 16,668; `DD Mon YYYY` 16,666; `MM/DD/YYYY` 16,666; 7,085 of the slash dates are ambiguous on their face; 0 unparseable | Three-parser fallback; slash dates read month-first (no slash date has a first part above 12) | [dq_report](docs/dq_report.txt), [C08](docs/discovery/output/C08.txt), [DATA_DISCOVERY F-03](docs/DATA_DISCOVERY.md) |
| 4 | Dictionary says update timestamps are ISO 8601 | Three formats across the 494 open incidents: `MM/DD/YYYYT…` 187, ISO 159, `DD Mon YYYYT…` 148. 496 update entries, 0 unparsed | Same three parsers | [C10](docs/discovery/output/C10.txt), [dq_report](docs/dq_report.txt) |
| 5 | Roster clearance against the access policy | Policy rule gives 1 mismatch (FEN-1002, Owen Baptiste: roster `restricted`, policy `general`) | Compute clearance from team and title; the roster column is only compared | [C13](docs/discovery/output/C13.txt) |
| 6 | The code's computed clearance against the roster | 3 disagreements: FEN-1002 as above, plus FEN-1013 and FEN-1014 (SRE, title "SRE"), which the **code** makes `restricted` and the roster and policy make `general` | **Not a data problem; a code departure from the policy, open.** See limitation 1 | [dq_report](docs/dq_report.txt), [DATA_DISCOVERY §5.1](docs/DATA_DISCOVERY.md) |
| 7 | Deprecated service still has on-call rows | `notifications-worker`: 2 rows (FEN-1014, FEN-1013) | Do not page it; tell the owning team. Routing still returns the old rotation (limitation 3) | [dq_report](docs/dq_report.txt), [C13](docs/discovery/output/C13.txt) |
| 8 | SRE is on call but owns no service | 4 SRE on-call rows; 0 services owned | On-call lookup is not limited to the owning team | [dq_report](docs/dq_report.txt), [C13](docs/discovery/output/C13.txt) |
| 9 | Postmortem files against the incident log's links | 6 files on disk, 4 linked, 2 orphans (superseded auth-gateway draft; canary draft for INC-2101), 0 linked files missing | Discover documents by scanning the store; skip the superseded draft; label a current draft | [dq_report](docs/dq_report.txt), [C10](docs/discovery/output/C10.txt) |
| 10 | Two incident-id widths | 6 short (`INC-NNNN`), 49,994 long (`INC-NNNNNN`) | Accept both; ids are opaque | [dq_report](docs/dq_report.txt) |
| 11 | Three escalation times | Policy 5 / 15 min / one business day; runbook 10 min; Payments notes 3 min | 5 / 10 / one business day (tighter of policy and runbook); the 3 minutes is mentioned, not followed. Designed, not built | [DECISIONS Q6](docs/design/DECISIONS.md), [C13](docs/discovery/output/C13.txt) |
| 12 | The access policy contains the word "restricted" but is a general document | 2 of 14 documents are restricted (the two auth-gateway postmortems), by their own marking line | Sensitivity comes from the document's own marking, not keyword presence | [dq_report](docs/dq_report.txt), [DECISIONS Q4](docs/design/DECISIONS.md) |
| 13 | Placeholder updates on open incidents | 494 open incidents; 492 of 496 update entries are "Investigating, no update yet" | "Live" = open with a non-boilerplate update; two incidents qualify (INC-2101, INC-2115) | [C07](docs/discovery/output/C07.txt), [DATA_DISCOVERY §2](docs/DATA_DISCOVERY.md) |
| 14 | CSV line endings | All five CRLF | `csv` module with `newline=""` | [C02](docs/discovery/output/C02.txt) |

**Checked and found clean** ([LOG.md](docs/discovery/LOG.md) D-03, D-04, D-06): roster 14 rows with no blanks or duplicate
ids; registry 10 rows (9 active, 1 deprecated), no duplicates; 25 queue tickets, no duplicate ids, every `filed_by`
resolves, the one `related_incident_id` resolves; every on-call `engineer_emp_id` is in the roster.

**Two corrections to the discovery record** (the log is append-only, so they live in [DATA_DISCOVERY.md](docs/DATA_DISCOVERY.md)):
the month-first reason cited the roster, which has no dates; and D-12 marked the access policy restricted by keyword.

## 2 · Access and authorization, in plain words

**Sensitive.** A document is sensitive if it marks itself restricted in its own text. Today that is two documents: both
versions of the auth-gateway postmortem. The word appearing in a document does not make it sensitive; the access policy
is general. If the system cannot tell, it treats the document as not viewable.

**Cleared.** The person who filed the ticket (`filed_by`, trusted as the caller's identity) is cleared for restricted
documents if they are on the Security team, or hold a Senior, Staff or higher title on any team. Everyone else is
general. This is worked out from team and title, not read from the roster's `clearance_tier`, because that column is
wrong for at least one person (Owen Baptiste). What the ticket says about who the filer is, or what they are allowed, is
ignored.

**How it is checked.** Per document, before the text is given to the model or put in an answer. A person who is not
cleared is told that a restricted document exists and that they lack clearance to see it; nothing from it is quoted or
summarised. If the identity directory cannot say who the filer is, the ticket is refused, because someone with unknown
clearance is not cleared. Follow-ups are handled afresh for whoever sends them, and earlier answers are not replayed.
([DECISIONS Q4, Q6](docs/design/DECISIONS.md), [auth/clearance.py](auth/clearance.py).)

**Authorized (a ticket asking for something to be done).** **Design:** any engineer in the directory may ask the system to
page on-call or open an incident for an active service; the decision is recorded and nothing is sent. **Code:** only the
owning team, SRE or Security may (limitation 2). A deprecated service is not paged (the owning team is told). Closing an incident needs the owning team or someone who has posted on it. The system
never grants clearance and never rolls back, deploys or restarts, for anyone. Who may ask is an assumption: neither the brief nor
the findings say ([DECISIONS Q4](docs/design/DECISIONS.md)). The design's choice and the code's differ, and the evaluation
cases follow the code ([action_decider.py](engine/action_decider.py), eval C03 and REF03).

**Where this does not yet hold.** The code treats the whole SRE team as cleared, which the policy does not. Of the 14
engineers it changes two (FEN-1013, FEN-1014). It also limits who may request an action more tightly than the design.
Details: limitations 1 and 2.

## 3 · Evaluation

The set is [eval/cases.py](eval/cases.py): 33 cases in 10 categories (A 3, B 6, C 3, D 5, E 2, VPN 2, Refused 4,
FollowUp 2, Failure 3, DataLoading 3). The runner is [eval/runner.py](eval/runner.py), in-process or against a URL. The
bars were fixed before the first run ([DECISIONS Q8](docs/design/DECISIONS.md), [BRIEFING §9](BRIEFING.md)).

### Committed runs against the bars

| Bar | Target | Run 1 — [18:50:35](eval/results/2026-10-06_18-50-35_summary.md) | Run 2 (= latest) — [19:00:09](eval/results/latest_summary.md) |
| --- | --- | --- | --- |
| Restricted content leaks | 0 | 0 — pass | 0 — pass |
| Wrongful refusals | 0 | 0 — pass | 0 — pass |
| Disposition and routing accuracy | ≥ 90% | 83.3% (25/30) — **fail** | 100% (30/30) — pass |
| Planned steps executed | 100% | 43.8% (14/32) — **fail** | 37.5% (12/32) — **fail** |
| p95 latency | ≤ 8 s | 0.73 s — pass | 1.51 s — pass |
| Cases with every check passing | — | 8 of 33 (24.2%) | 13 of 33 (39.4%) |

**Headline: four bars of five pass in the latest committed run; the planned-steps bar fails.** Raw data:
[2026-10-06_18-50-35_results.json](eval/results/2026-10-06_18-50-35_results.json), [latest_results.json](eval/results/latest_results.json).

### What changed between the two failed runs

Both runs were committed together in `25b1a4c` ("added complete code, tests and evals - turn 6-11"), so the history does not
separate code changes from case changes. What the two result files show:

- **B01–B04** failed run 1 on `answer_not(RESTRICTED)` ("forbidden 'RESTRICTED' found in answer"). They pass in run 2, and
  the current cases forbid the words "credential" and "postmortem" instead ([eval/cases.py](eval/cases.py)). The
  forbidden-word check was changed, not only the answer.
- **D04, D05** expected `routed` in run 1 (the TCK-0102 reading in [DECISIONS Q5, Q8](docs/design/DECISIONS.md)) and got
  `duplicate`. In run 2 they expect `duplicate`. **The expectation was changed to match the code**; the design says
  `routed`.
- **DL01** changed from expecting `routed` to `duplicate`. **DL02, DL03** changed from expecting `duplicate` citing
  `INC-009012` (and getting `answered`) to citing `INC-2101` (and getting `duplicate`).
- **FA01** failed run 1 on `answer_contains("not verified")`; it now requires "identity" and "verified".
- Code fixes recorded in [PROGRESS.md](PROGRESS.md): turn 9, three bugs found during a scenario test; turn 10, two code bugs
  (classifier guard, orchestrator timeout outcomes).
- Run 1's plan-step check compared `check_open_incidents`-style names; run 2 compares `check open incidents`-style plan
  labels with tool names. Both fail on the same mismatch.

### What the failing bar is

All 20 failing checks in the latest run are the plan-versus-`steps_run` comparison ([latest_summary.md](eval/results/latest_summary.md)).
The planned label (for example "check open incidents") is not found in the tool names that ran (`check_incidents`). The
brief says the plan and steps_run are compared by the reader, so this is real, not cosmetic. Whether the plan labels or
the matcher are at fault has not been determined; every other check in those cases passed.

### What the bars do not cover

- **Restricted leaks** is computed over the 4 category-B cases filed by a general filer. No case files as Owen, and none
  as an SRE engineer asking for a restricted document, which is the one place the code departs from policy
  (limitation 1). The bar says 0 and that is true for what it covers; it is not evidence that the SRE case is safe.
- **Wrongful refusals** counts a refusal only where the case did not expect one, and excludes B-general and Failure cases.
- **Disposition accuracy** compares against expectations that, for the five cases above, were revised after run 1.
- **F-06** (escalation) has no case, on purpose ([BRIEFING §9](BRIEFING.md)). F-03 has none directly.
- FU01/FU02 do not file against a queue id (`TCK-…`), although the briefing says they would.

### The committed results are older than the code

The latest run (19:00) predates commit `df752ea` (20:14), which rewrote [adapters/llm.py](adapters/llm.py) and changed
[adapters/orchestrator.py](adapters/orchestrator.py), [classify/rules.py](classify/rules.py) and [eval/runner.py](eval/runner.py).
The results file does not record whether a model key was set. The unit tests at the current commit: 296 pass, 2 fail
(`TestLLMAdapter` mock-transport tests, which that commit's message calls work in progress).
**The evaluation must be re-run at the submitted commit and its results committed.**

## 4 · Cost and latency

**Measured** (committed, [latest_results.json](eval/results/latest_results.json), 33 cases): p95 1.51 s; median 0.50 s;
slowest 1.93 s (A01). 16 of the 33 cases show 0.0 s because they never reach a lookup or a model (refusals and
fixed-path answers), so the p95 is set by the other 17 (median 0.63 s). Run 1: p95 0.73 s. Whether the model was called
in these runs is not recorded. **Not measured:** tokens per ticket, dollars per ticket, latency over a Groq call at
load.

**Bounds in code** ([BRIEFING §8](BRIEFING.md), [adapters/llm.py](adapters/llm.py), [orchestrator.py](adapters/orchestrator.py)):
2 model calls per ticket; 200 tokens to classify, 512 to compose; 8 s per model call; 2 s per local lookup; 20 s per
ticket. Breaching a bound falls back to rules and an extractive answer and is recorded in `steps_run`.

**Estimate, not a result** ([BRIEFING §8](BRIEFING.md)): about $0.0005–0.002 per ticket on a paid tier; $0.02–0.08 a day at
the brief's 40 tickets a day. [DECISIONS Q7](docs/design/DECISIONS.md) rejects dollar figures that are not in the inputs;
these are planning numbers until a paid tier is measured. Free-tier Groq limits are 30 requests/minute, 8K tokens/minute,
1K requests/day ([BRIEFING §8](BRIEFING.md)).

**What would be measured and where the bound sits.** Per ticket: latency, tokens, model calls, fallback or failed steps,
without ticket text. Bound: p95 ≤ 8 s (the evaluation bar), fallback rate drift, per-ticket cost ceiling from the two-call
cap, and a daily spend cap that switches to the no-model path (designed, not built; [Q7, Q9](docs/design/DECISIONS.md)).

## 5 · How you would know it is working

**What good looks like.** No restricted text reaches anyone not cleared; no cleared person is refused; a duplicate
names a live incident that exists; a routed ticket names the person on call; every planned step appears in `steps_run`;
latency is under the bar.

**How to check** (proposal; the first two exist in the repository):
1. Run the [evaluation](eval/runner.py) at the deployed URL on every deploy and before submission
   (`python -m eval.runner --url …`, [README](README.md)).
2. Run [tests/](tests/), including the F-rule tests in [test_data_rules.py](tests/test_data_rules.py).
3. Daily, replay a fixed probe set against production: restricted-document questions from each clearance level (including
   Owen and each SRE engineer), reworded and adversarial; any leak is an incident.
4. Weekly, sample tickets for human review of duplicate and routing decisions, and compare against the person who ended up
   handling them.
5. Re-run [scripts/dq_report.py](scripts/dq_report.py) on each new data extract and compare against
   [docs/dq_report.txt](docs/dq_report.txt): roster disagreements, unparseable dates, unmatched service names, orphan documents.

**What tells you it has degraded, before a complaint.** Fallback-rate rise (model failing); `steps_run` failed or timeout
rate by system (a dependency is down); share of `refused` rising (over-refusal) or falling (possible leak); share of
`duplicate` pointing at an incident that has since closed; roster-versus-computed clearance disagreements changing
(directory drift); the plan-versus-`steps_run` mismatch rate, which is already 20 of 32 checks.

## 6 · Known limitations

Numbered as referenced above. Full detail in [DATA_DISCOVERY §5](docs/DATA_DISCOVERY.md).

1. **Clearance code is broader than the policy.** SRE as a team, and "lead" and "principal" titles, count as restricted;
   the policy lists Security and Senior/Staff or above. FEN-1013 asking about the auth-gateway outage was answered from the
   restricted postmortem; under the policy that is a refusal. The tests assert the code's behaviour, so they do not catch it.
2. **Who may request an action is stricter in code than in the design.** The code allows only the owning team, SRE or
   Security; [DECISIONS Q4](docs/design/DECISIONS.md) rejects that rule and lets any engineer ask. A Platform engineer paging
   `payments-api` is refused (eval C03, REF03); DECISIONS Q8 expects `action_decided`. Cases follow the code.
3. **Deprecated service still routes.** A live-problem ticket on `notifications-worker` goes to the leftover on-call
   person, against [Q3](docs/design/DECISIONS.md).
4. **TCK-0102-shaped reports are marked duplicate** of INC-2115; the design says `routed`. Evaluation cases were revised to
   match the code.
5. **The draft label is conditional.** It is added only when the draft ranks first; a cited draft may go unlabelled (A01).
6. **The timestamps parser is not load-bearing.** "Live" reads the update text, and nothing in `engine/` uses the parsed
   update times, so the F-11 evaluation cases pass whether or not they parse.
7. **Rules-only classification can refuse a live problem.** Without a model, "auth-gateway is returning 500s" from a
   general filer is read as a document question and refused. That is a wrongful refusal and discloses that a restricted
   document exists.
8. **No persistent ticket state.** `ticket_id` is echoed and a follow-up is handled as a new ticket; all state is lost on
   restart, and the free plan sleeps after 15 minutes ([README](README.md)).
9. **The planned-steps bar fails** at 37.5% (12/32).
10. **Refusal text** says to contact "your team lead or the document owner", not the owning team, as the policy asks.
11. **Nothing is sent.** Pages, incident writes and channel posts are decisions recorded as dry runs; escalation timers,
    spend caps and a search index are designed only ([Q9](docs/design/DECISIONS.md)).
12. **Data limits.** The extracts have different as-of times; the dumps hold no acknowledgement timestamps, so real
    escalation behaviour is unmeasured ([C13](docs/discovery/output/C13.txt)); five of the ten questions for the data's owners
    are still open ([DATA_DISCOVERY §3](docs/DATA_DISCOVERY.md)).

**With more token budget and time, the focus would be tests, evaluation and data cleanup** (plan in
[APPROACH §7](APPROACH.md#7--decisions-assumptions-open-questions)), ahead of new features.

**What more time would have caught first:** a case for each clearance profile (all 14 engineers against a restricted
document); a plan-label check agreed with the tool names; re-running the evaluation after the model adapter changed;
replacing the cases that were edited to fit the code with cases that fit the design and letting them fail.
