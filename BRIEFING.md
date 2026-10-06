# BRIEFING — Fenwick Cloud Engineering Support Queue

## 0 · Session rules for later turns

1. Keep command output short; summarise inside the script.
2. Never read large data files whole with `read` or `cat`.
3. Run tests showing only the summary (e.g. `pytest -q --tb=short`).
4. Never read `.env` files.
5. Never commit.
6. Append one line to `PROGRESS.md` per turn: `Turn <n> | <phase> | <status> | next: <…>`.
7. Reply in at most 10 lines.
8. Use `scripts/discovery/Cnn_*.py` or `.sh` for investigations (stdlib only); output to `docs/discovery/output/Cnn.txt`.
9. Log every question in `docs/discovery/LOG.md` (append-only). Never edit earlier entries.
10. Refer to BRIEFING.md for all design decisions; do not re-open settled choices.

---

## 1 · Deliverables (from scenario.txt)

| # | Deliverable | Location | Status |
|---|---|---|---|
| D1 | `POST /tickets` endpoint, deployed at public HTTPS URL | Deployed service | built |
| D2 | Plan that differs per ticket (B ≠ D must show different sequences) | API response `plan` field | built |
| D3 | At least one answer that lives only in a document, not in any CSV | API response `citations` | built |
| D4 | Decision on a ticket that asks for a real effect | `action_decided` / `refused` disposition | built |
| D5 | Evaluation set, executed, results committed | Committed alongside code | built |
| D6 | APPROACH.md — written design, all areas covered | `APPROACH.md` | designed |
| D7 | ARTEFACT.md — data quality, access/auth, eval results, cost, limits | `ARTEFACT.md` | designed |
| D8 | README — clean clone to running system | `README.md` | built |
| D9 | Repository with source code | This repo | built |

---

## 2 · API contract (verbatim from scenario.txt)

```
POST /tickets — JSON body:
{"text": string, "filed_by": string, "ticket_id": string | null}
filed_by is an employee id from the identity directory dump.
ticket_id: null files a new ticket; passing one returned earlier adds to that ticket.
We send this body and nothing else.

Returns 200:
{ "ticket_id":   string,
  "disposition": "answered" | "routed" | "duplicate" | "action_decided" | "refused",
  "answer":      string,
  "plan":        [{"step": string, "why": string}],
  "steps_run":   [{"tool": string, "outcome": "ok"|"failed"|"timeout"|"skipped", "detail": string}],
  "routed_to":   string | null,
  "citations":   [{"source": string, "reference": string}],
  "related":     [string] }
```

**Added (not in contract, designed internally):** None. The response is exactly as specified. Internal state (`filer clearance`, `service canonical name`, `matched incident id`) is kept in SQLite and visible in `steps_run` detail but not in dedicated fields.

**Contract invariants:**
- `plan` is what the system *decided* to do; `steps_run` is what *actually happened*. Both are compared by graders.
- `disposition` and `citations` must be populated correctly, not just formatted.
- `refused` covers: filer not cleared for the answer, or not authorized for the requested action.
- `action_decided` means the system determined an action was warranted and recorded that decision. No side effect is expected or graded.

---

## 3 · Architecture

```
┌──────────────┐     POST /tickets
│  Client/Harness│ ──────────────────► ┌──────────────────────────────────┐
└──────────────┘                       │  FastAPI process (single worker) │
                                       │                                  │
                                       │  1. Identify filer & clearance   │
                                       │  2. Classify ticket (model│rules)│
                                       │  3. Choose path per kind         │
                                       │  4. Execute steps, record events │
                                       │  5. Return response              │
                                       └──────────┬───────────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │        In-memory (startup)  │      SQLite (disk)          │
                    │                             │                             │
                    │  Engineer roster (14 rows)  │  Ticket state (follow-ups)  │
                    │  Service registry (10 rows) │  Recorded decisions (audit) │
                    │  On-call schedule (15 rows) │  Hand-off queue loaded at   │
                    │  Incident log (50K rows)    │    startup from open_tickets │
                    │  Document texts (14 docx)   │                             │
                    │  Open tickets (25 rows)     │                             │
                    └─────────────────────────────┴─────────────────────────────┘
```

**Stack (DECISIONS Q1):** Python/FastAPI single process. Hugging Face Docker Space (free tier, sleeps after 48h idle). Groq for LLM inference (model: agent's choice — llama3-70b-8192 or equivalent free-tier model when deployed). SQLite for state. No job queue, no background workers (designed but not built).

**Key architectural rules:**
- All read-only extracts load at startup from CSVs + document files.
- Clearance is *computed* from team/title per policy, not trusted from the roster column (F-01).
- `policy_access_and_clearance.docx` is a GENERAL-access document despite mentioning the word "restricted" — the discovery log's substring search over-marked it (DECISIONS Q4). The document's own body determines sensitivity, not keyword presence.
- Follow-ups re-process the ticket; stored answers are audit-only, never replayed (Q6).
- No authentication on the route; `filed_by` is trusted as the caller's identity (scenario.txt §Deployment).
- State does not survive Space restart (SQLite on ephemeral disk). Production fix: persistent volume (designed, not built).

---

## 4 · Module layout

| File | Responsibility | Main functions |
|---|---|---|
| `main.py` | FastAPI app, route handler, startup loading | `POST /tickets()`, `load_all()`, `lifespan()` |
| `ingest/csv_loader.py` | Parse 5 CSVs, normalize, validate | `load_roster()`, `load_services()`, `load_oncall()`, `load_incidents()`, `load_open_tickets()` |
| `ingest/doc_loader.py` | Parse 14 .docx files, extract text, detect restricted flag | `load_documents()`, `is_restricted()`, `extract_text()` |
| `ingest/normalize.py` | Service name normalization, date parsing, ID normalization | `normalize_service()`, `parse_date()`, `normalize_incident_id()` |
| `auth/clearance.py` | Compute clearance from team/title per policy | `compute_clearance()`, `can_see_document()`, `get_filer()` |
| `classify/classify.py` | Label ticket: kind, services, actions requested | `classify()`, `extract_services()`, `extract_action_request()` |
| `classify/rules.py` | Rule-based fallback when model fails | `rules_classify()`, `match_keywords()` |
| `engine/orchestrator.py` | Choose & run steps per kind; build plan then execute | `run()`, `plan_for_kind()`, `execute_plan()` |
| `engine/document_search.py` | Search loaded documents by keyword, respect clearance | `search()`, `best_answer()`, `get_current_doc_version()` |
| `engine/incident_matcher.py` | Match ticket to open/live incidents | `find_matching_incidents()`, `is_live()` |
| `engine/duplicate_check.py` | Check for same-service same-symptom within 2h | `check_duplicate()`, `recent_same()` |
| `engine/action_decider.py` | Decide if filer may request action; record dry-run decision | `decide_action()`, `record_decision()`, `is_authorized_for_action()` |
| `engine/routing.py` | Determine on-call for a service | `get_oncall()`, `resolve_routing()` |
| `state/store.py` | SQLite read/write for ticket state, follow-ups | `get_ticket()`, `save_ticket()`, `load_handoff_queue()` |
| `eval/runner.py` | Execute evaluation cases, assert bars, produce report | `run_cases()`, `check_bars()`, `report()` |
| `eval/cases.py` | Evaluation case definitions (30+ cases) | `all_cases()` (case tuple list) |

---

## 5 · Data rules

| F-id | Rule | Enforced where | Test |
|---|---|---|---|
| F-01 | Clearance must be **computed** from team+title per policy, not trusted from roster column | `auth/clearance.py` — `compute_clearance()` | Feed restricted doc to a non-Security non-Senior filer; must be refused |
| F-02 | Service names must be normalized (lowercase, `_` → `-`) before any join/lookup | `ingest/normalize.py` — `normalize_service()` | Join incident_log to service_registry without normalization → unmatched rows |
| F-03 | Dates must be parsed with 3-parser fallback (ISO, DD Mon YYYY, MM/DD/YYYY); ambiguities resolve MM/DD/YYYY | `ingest/normalize.py` — `parse_date()` | String-sort dates vs parsed dates → different order without 3-parser |
| F-04 | System must handle 5 CSV files, not 4 (open_tickets.csv is the 5th) | `ingest/csv_loader.py` — `load_all()` | Count CSVs; if design says "4" it's wrong |
| F-05 | Deprecated services with on-call entries must not crash, but rotation is stale | `engine/routing.py` — `get_oncall()` | Query on-call for deprecated service; crash = wrong |
| F-06 | Escalation timing: use escalation-runbook times (SEV1=5min, SEV2=10min, SEV3=1bd); mention policy (15min) and Payments 3min conflict | `engine/action_decider.py` — `record_decision()` (designed, not built) | Hardcoded 10min universal = wrong per SEV1 policy SLA; test checks design doc, not live enforcement |
| F-07 | SRE engineers are reachable for on-call even though they own no service | `engine/routing.py` — `get_oncall()` | Restrict on-call to owning-team only → SRE never found |
| F-08 | Both INC-NNNN and INC-NNNNNN are valid incident IDs; treat uniformly | `ingest/normalize.py` — `normalize_incident_id()` | Single regex `^INC-\d{6}$` fails 6 short IDs |
| F-09 | Documents are discovered by scanning the store, not only by CSV links | `engine/document_search.py` — `search()` | CSV-only search misses orphan DRAFT postmortems |
| F-10 | CSV parsing must handle CRLF line endings (`\r\n`) | `ingest/csv_loader.py` — use `newline=''` | `split('\n')` leaves trailing `\r` on last field |
| F-11 | Update timestamps have same 3-format problem as dates; apply same 3-parser strategy | `ingest/normalize.py` — `parse_date()` | ISO-only timestamp parser fails 60%+ of update timestamps |

---

## 6 · Behaviour per kind of ticket

Steps in order for every ticket:

1. **Identify filer & compute clearance** (auth/clearance.py). If filer not in roster → `refused` (cannot compute clearance). If identity directory unavailable → `refused` with failed step.
2. **Classify** (classify/classify.py). Model labels: kind, services, action requests. Fallback to keyword rules if model fails/times out.
3. **Execute per kind** (engine/orchestrator.py):

| Kind | Disposition | Steps | What decides outcome |
|---|---|---|---|
| **Answerable from document** (filer may see it) | `answered` | Search documents → filter by clearance → cite best match | Document exists + filer clearance allows it. Superseded docs skipped. Drafts allowed, labelled as draft. Superseded status detected by filename suffix `_DRAFT_superseded` or doc body `Status: DRAFT / SUPERSEDED`. Current version is the one with `FINAL` status or the highest version number for that doc family. |
| **Live problem, already has open live incident** | `duplicate` | Check open incidents for service + symptoms → link as related | Open incident exists with ≥1 non-boilerplate update. No age cutoff. Also `related` the earlier ticket. |
| **Live problem, no live incident** | `routed` | Find on-call for service → name in `routed_to` | On-call resolved from schedule. If on-call unavailable → route to owning team channel. |
| **Asks what to do, document answers** | `answered` + `related` | Document search + incident match in `related` | Same as answerable, but still name any open incident in `related`. |
| **Requests action** (page, open/close incident, grant/change production) | `action_decided` or `refused` | Check authorization → record decision (dry run) | Authorized if filer is engineer in roster for active service. Exception: close-incident requires owning team or someone who has posted on that incident (DECISIONS Q4). The system never grants clearance and never rolls back, deploys or restarts. Deprecated services → tell owning team, don't page. |
| **VPN/wifi/all-hands/redirect** | `answered` | No search needed; redirect in `answer` | Matched by classifier keywords. Not `refused`. |
| **Filer not cleared for document** | `refused` | State document exists + owner; do not quote/paraphrase | Clearance check per doc before any text reaches model or answer. |
| **Filer not authorized for action** | `refused` | State action not authorized | Filer is not engineer, or service is not active. |

**Live incident rule (DECISIONS Q5):** Open incident with ≥1 non-boilerplate update. "Boilerplate" means any update matching the pattern `"Investigating, no update yet"` (the sole boilerplate variant observed in the 494 open incidents with updates; all others are substantive). No age cutoff. The day counts from C07 are not used (discovery gap not promoted to finding).

**Duplicate check for API-filed tickets:** Same service + same symptoms within 2h of the service's own timestamps, and only after an earlier report was already routed or action-decided.

**Hand-off queue tickets (open_tickets.csv):** 24 tickets with no linked incident are `routed` (not `duplicate`). TCK-0102 (errors/checkout) is `routed`, not duplicate of the latency incident.

**`routed_to` convention:** Contains the on-call engineer's full name (from engineer_roster) when on-call resolves. Contains `"<owning_team> channel"` (e.g. `"Platform channel"`) when on-call is unavailable. Null for all non-routed dispositions.

---

## 7 · Failure behaviour per external system

| System | When unavailable | Behaviour |
|---|---|---|
| **Document store** | Files can't be read at startup | Service fails to start (documents loaded at startup per Q3). In production with live API: return `answered` with no citations, log failure. |
| **Identity directory** | Can't read roster at startup | Service fails to start (clearance cannot be computed). In production with live API: `refused` — unknown clearance = not cleared. `steps_run` shows directory failed. Do not guess who the filer is. |
| **Service catalog** | Can't read at startup | Service fails to start (can't resolve service names). |
| **On-call scheduler** | Doesn't answer | Route to owning team's channel. Record the failure in `steps_run`. Never fill in a name from a stale copy. |
| **Incident tracker** | Doesn't answer (read) | Cannot check for duplicates. Route the report and say the check failed in `steps_run`. Do not claim a duplicate. |
| **Incident tracker** | Write fails | In designed production: decision recorded first, then write with idempotency key. If write fails, leave visible for retry. This build records decision only (dry run). |
| **Messaging & paging** | Page undelivered / no ack | This build: decide who would be paged, record decision, do not send. Designed: idempotency key, no double-page for same service within window. SEV1: 5min ack → secondary. SEV2: 10min → team queue. SEV3: 1bd → team queue. If no secondary exists → owning team channel. |
| **LLM (Groq)** | Times out / returns error | Fallback to keyword-based rules classification. No model call = no invented steps. Document search still runs. |
| **LLM (Groq)** | Over budget | Per-ticket cap enforced (2 calls max). If daily spend cap hit → no-model path for rest of day. |

---

## 8 · Limits and enforcement

| Limit | Value | Enforced by | When breached |
|---|---|---|---|
| Model calls per ticket | 2 max | `engine/orchestrator.py` — counter before each call | Use keyword fallback; record `skipped` for uncalled steps |
| Answer token cap | 2048 tokens (agent's choice) | Response builder truncation | Answer is truncated; `steps_run` notes truncation |
| Local lookup timeout | 2 seconds | `asyncio.wait_for()` on document search and DB queries | Step recorded as `timeout`; skip to model or fallback |
| Model call timeout | 8 seconds | `asyncio.wait_for()` on LLM call | Fallback to rules; step recorded as `timeout` |
| Total per-ticket timeout | 20 seconds | `asyncio.wait_for()` on the whole handler | Return whatever is ready; `steps_run` shows partial execution |
| Duplicate check window | 2 hours | `engine/duplicate_check.py` — compare timestamps | Outside window → treats as new report (still checks open incidents) |
| Escalation times | SEV1=5min, SEV2=10min, SEV3=1bd | Designed (not built in this build) | Decision records the deadline and escalation path |
| Daily spend (designed) | Alert on drift; cap → no-model path | Designed: metrics on token count per ticket | Alert if p95 > 8s or fallback rate > 10% |
| Org-scale cap (designed) | Per-ticket limits scale; search index needed at 100K+ docs | Designed: search index when scan time degrades | Log scan times per document; alert if >500ms average |

**Cost-per-ticket (designed):** ~1–2 model calls × Groq free-tier tokens ≈ $0.0005–0.002 per ticket. At 40 tickets/day for one team → ~$0.02–0.08/day. Full org (estimate ~400 tickets/day) → ~$0.20–0.80/day on free-tier Groq. Production would need a paid tier; per-ticket limits prevent runaway.

---

## 9 · Evaluation plan

### Case categories

| Category | Count | Description |
|---|---|---|
| A (canary 5xx) | 3+ variants | Answered from runbook + draft postmortem; related to open incident. Variants: different filer clearances, different wordings. Also tests F-02 (service name), F-03 (date match), F-08 (incident ID), F-09 (doc discovery of orphan draft). |
| B (auth-gateway postmortem) — general filer | 2+ | `refused` — Owen/any general filer cannot see restricted postmortem |
| B (auth-gateway postmortem) — restricted filer | 2+ | `answered` from FINAL postmortem; never superseded draft |
| C (page on-call, open incident) | 3+ | `action_decided` for non-Payments filer; opens new incident, INC-2101 in `related` |
| D (checkout latency duplicate) | 3+ | `duplicate` of open latency incident + earlier matching ticket |
| D (TCK-0102 — errors, different symptoms) | 2+ | `routed` (not duplicate) |
| E (who owns billing-sync) | 2+ | `answered` with owning team |
| VPN/wifi/all-hands (redirect) | 2+ | `answered` with redirect; not `refused` |
| Refused — unauthorized action | 2+ | Non-engineer or deprecated service |
| Follow-up | 2+ | Same ticket_id re-contacted; re-processed. Also tests F-04 (hand-off queue ids loaded from 5th CSV accept follow-ups). |
| Failure / edge cases | 3+ | Identity lookup fails, on-call unavailable, LLM timeout |
| Data loading (F-04, F-10, F-11) | 3+ | Startup loads all 5 CSVs (open_tickets included, F-04) with CRLF handled (F-10); follow-up on a TCK-id proves the 5th source loaded. Live-incident detection uses the 3-parser on update timestamps (F-11). |
| **Total** | **~35+** | |

F-06 has no runtime eval case: escalation timers are design-only in this build (Q9). Its rule and test live in §5, and the §8 limits row records the chosen values.

### Bars (fixed, DECISIONS Q8)

| Bar | Target | How checked |
|---|---|---|
| Restricted content leaks | **0** | Every restricted-content case where filer is general → disposition must be `refused` |
| Wrongful refusals | **0** | Every authorized-general case → must not be `refused`; VPN/redirect → `answered` |
| Disposition & routing accuracy | **≥90%** | Assert all non-failure cases have correct `disposition` + `routed_to` |
| Planned steps executed | **100%** | Every step in `plan` must appear in `steps_run` (may be `skipped`/`failed`/`timeout`) |
| p95 latency | **≤8 seconds** | From measurement over all eval cases |

---

## 10 · Documents to write (from scenario.txt)

| Document | Required content |
|---|---|
| `APPROACH.md` | Entry point to written design. Cover: (1) the six systems and their surfaces — live vs cached, cost of wrong cache, behaviour when down; (2) how a ticket moves — arrival to close, what decides sequence, state between steps, failure mid-step; (3) parts that touch people and records — what gets posted/paged/written, in what order, in-flight state, unacknowledged record shape, half-succeeded writes, postmortem on existing incident record, follow-ups; (4) stack, cost, scale — cloud, what runs vs buys, cost per ticket, latency, what stops runaway at 10K engineers, what changes needed at scale, what to measure; (5) decisions, assumptions, open questions — major choices with rejected alternatives, assumptions where brief/data was silent, deliberately not built, mapping built artifacts to decisions. Must be linkable from artifacts. Include walkthrough: workflow, hardest-defended decision, deliberately not built, first thing to break under real usage. |
| `ARTEFACT.md` | What calling the endpoint cannot show. Sections: (1) data quality — system disagreements and rules applied; (2) access & authorization — what "sensitive" and "authorized" mean, how each checked; (3) evaluation — executed set results against bars with real numbers; (4) cost & latency — what measured, bounds, where bounds sit; (5) how you know it's working — good result definition, check method, degradation indicators; (6) known limitations — what doesn't handle well, what more time would catch. |
| `README.md` | Clean clone to running system. Deployed URL. |

---

## 11 · Deployment

- **Host:** Hugging Face Docker Space (free tier).
- **URL:** Public HTTPS (no auth on `/tickets` route).
- **Wake:** Free Space sleeps after 48h idle. Cold start on first request. Before submission: wake and confirm `POST /tickets` answers.
- **Credential:** Groq API key stored as Space secret (`GROQ_API_KEY`). The service needs its own inference credential.
- **Port:** 7860 (agent's choice — Hugging Face default).
- **State persistence:** SQLite on ephemeral disk. Does not survive restart. Production fix: persistent volume (designed, not built). Hand-off queue re-seeded from extract on startup.
- **URL to submit:** Alongside repository. Do not put auth on the route.
- **No second host:** Not adding a second host to avoid cold start. Stated as limit in ARTEFACT.md.