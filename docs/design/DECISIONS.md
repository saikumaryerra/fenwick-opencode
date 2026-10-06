# Design decisions

Choices for the Turn 3 options. A rejection rests on the API contract in `scenario.txt`, a finding in `docs/discovery/FINDINGS.md`, or a gap named in the last section. The live-incident rule is a gap, not a finding.

## Q1 · Stack, hosting and what runs where
- Choice: A for the request path, plus the persistence half of B. Not B's job queue, not C.
- Why: `POST /tickets` must return the decision in that same response. Option B's "return pending, client polls" does not fit the contract. Option C reloads the roster and documents on every call and makes follow-ups hard. A single Python/FastAPI process does the work inside the request. In-memory caches are only for the read-only extracts.
- Host: a Hugging Face Docker Space, and no other. It gives the public HTTPS URL with no login on the route. The Groq key is a Space secret.
- Sleep: a free Space sleeps after 48 hours without traffic, and the next request waits for a cold start. Graders call the URL whenever they choose. Before submission, wake it and confirm `POST /tickets` answers. In `ARTEFACT.md`, state the sleep and the cold start as a limit. Do not add a second host to avoid it.
- Model: Groq, using the `GROQ_API_KEY` already configured for this project. The briefing names the model ids after checking Groq's current model list; models get retired.
- State: ticket state goes in SQLite on the Space's disk. That disk does not survive a restart, so a restart forgets API-filed tickets and recorded decisions. The hand-off queue is re-seeded from the extract on startup. A persistent disk is the production fix and is designed, not built.
- Findings it relies on: F-04 (five sources, including the live queue), F-10 (CSV parsing).

## Q2 · How a ticket's steps are decided and bounded
- Choice: C, hybrid. Not B.
- Why: The model may label the ticket (kind, services, actions). Code chooses the steps from that label. Ticket B and ticket D then differ because they take different code paths, which is what the brief requires, and the sequence stays the same if the model is down. A pure LLM planner (B) can invent steps, has no hard cost bound, and cannot be tested without the model. A pure rules tree (A) is the fallback when the model fails, not the only planner.
- Bounds, enforced in code: at most 2 model calls per ticket, a token cap on the answer, and the timeouts in Q7. A failed step is recorded; it does not invent a success.
- Findings it relies on: F-02 (normalize names before any lookup), F-03 and F-11 (parse dates before matching), F-08 (treat both id widths as opaque strings; do not generate new ids by guessing the "newer" width).

## Q3 · How each external system is reached, cached and handled when slow or down
- Choice: the risk-based split in option A, with two corrections.
- Why:
  - Documents, directory and catalog: load from the extract at startup. They change slowly. If the directory cannot be read, the disposition is `refused`: clearance cannot be computed, and someone whose clearance is unknown is not cleared. `steps_run` shows the directory failed, which is how this differs from a policy denial. Do not guess who the filer is.
  - On-call: in production, read live, cache at most about a minute. A stale answer pages the wrong person. This prototype only has the shipped extract, so use it and say which rotation it is. Do not pretend a startup snapshot is live. If the scheduler does not answer, route to the owning team and record the failure. Never fill in a name from an old copy.
  - Incident tracker: read open incidents for the service, then keep only live ones (Q5). Writes are decided and recorded, not sent, in this build. If the tracker does not answer, do not claim a duplicate; route the report and say the check failed.
  - Messaging and paging: decide who would be paged and record it. This build does not place the call.
- Findings it relies on: F-01 (cache the recomputed clearance, not the roster column), F-05 (a deprecated service can still have an on-call row; do not page that leftover rotation), F-07 (SRE can be the on-call even when they own no service).

## Q4 · What "sensitive" and "authorized" mean, and where each is enforced
- Choice: option A for seeing documents. For actions, reject the agent's "owning team, or on-call, or SRE" rule.
- Why:
  - Sensitive means a document marked restricted in its own body, checked per document before any of its text is given to the model or put in an answer. The access policy mentions the word "restricted" and is itself general; a substring search would hide it (the discovery log over-marked that policy). Unknown or unreadable sensitivity is treated as not viewable.
  - Clearance is computed from team and title using the policy (Security, or Senior/Staff and above). The roster column is only compared. F-01's own test says serving a restricted document to that profile is a failure, so Owen (FEN-1002) is general and is refused restricted content. He is not "allowed because the roster says restricted".
  - A refusal states that a restricted document exists and who owns it. It does not quote or paraphrase it.
  - Who may request an action is not in the brief or the findings. F-07 says who can be on call (SRE, even though they own no service). It does not say who may ask for the page. Assumption: any engineer in the directory may ask to page on-call or open an incident for an active service. A deprecated service is not paged; the owning team is told instead (F-05). Closing an incident needs the owning team or someone who has posted on it. The system never grants clearance and never rolls back, deploys or restarts.
  - `filed_by` is the identity, as the brief says. Claims inside the ticket text are not.
- Findings it relies on: F-01, F-05. F-07 applies to who is paged, not to who may ask.

## Q5 · How each kind of ticket is told apart, and what happens to it
- Choice: the five dispositions in the contract, with a different order and two different outcomes from the recommendation.
- Why:
  - Order: identify the filer, compute clearance, classify, then run that kind's steps. A duplicate check does not run before access. Content is filtered before it is used.
  - Answerable from a document the filer may see: `answered`, with citations. Search the document files, not only the tracker's link column (F-09). A superseded version is never the answer; point at the current one. A current draft may be used and must be called a draft.
  - Live problem already covered by a live open incident: `duplicate`, and do not pull in a new person. Live means an open incident with at least one update that is not the boilerplate "Investigating, no update yet". No age cutoff is used. The day counts that show a cutoff cannot separate the example incidents from placeholders are not in `docs/discovery/` yet. They get cited here only after a discovery entry records them.
  - An earlier report counts as "already being worked on" only when a person or a live incident is already on it. For the hand-off queue, that is a ticket linked to a live incident: TCK-0101 is linked to INC-2115, so a new report of the same symptoms is a duplicate of both. TCK-0102, TCK-0105, TCK-0106, TCK-0110, TCK-0115, TCK-0116 and TCK-0120 are problem reports with no linked incident, and nothing in the extract shows anyone working them. A new report that matches one of those is `routed` to a person. The earlier ticket goes in `related`. It is not a duplicate, and it does not suppress the route. No age window is involved.
  - Reports filed through the API during a run: same service and same symptoms, within 2 hours on the timestamps the service itself writes, and only after this service has already routed that earlier report or decided an action for it. That is the clock. The September dates in the extract are not compared with today.
  - TCK-0102 is not that case. The discovery log called it a duplicate of the checkout-latency report. The text is about errors and says the slowness is unrelated. Route it.
  - Live problem with no live match: `routed` to current on-call. Not a page; paging is an action.
  - The filer asks what to do and a document answers it: `answered`, and still name the open incident in `related`. Do not drop the procedure just because an incident exists.
  - Asks the system to page, open, close, grant or change production: `action_decided` if allowed, `refused` if not. Record the decision. Do not perform the side effect.
  - VPN, wifi, all-hands: `answered` with a redirect and `routed_to` null. Not `refused`. Refused means not cleared or not allowed to have an action done.
- Findings it relies on: F-02, F-08, F-09, F-03, F-11. Also the open-ticket texts in C13, which the findings file did not turn into a rule.

## Q6 · Follow-ups and state between requests
- Choice: the state record in Q6, stored in SQLite (Q1), not an in-memory dict and not a 24-hour delete.
- Why: a follow-up passes `ticket_id` and is handled again for whoever sent it. Stored answers are audit only and are never replayed, so a less-cleared person cannot read a restricted answer by following up. The service remembers services, linked incident, disposition and the events. Hand-off tickets in `open_tickets.csv` are loaded so those ids accept follow-ups (F-04).
- If nobody acknowledges a page: the decision names the deadline and where it escalates. This build does not run a background timer. The runbook's 10 minutes covers SEV1 and SEV2 only, so it is not applied to SEV3.
  - SEV1: 5 minutes, the policy acknowledgement time, which is tighter than the runbook. Escalation pages the secondary on-call, as the runbook says. The extract has no active secondary, so the decision says that and names the owning team's channel instead.
  - SEV2: 10 minutes, the runbook, which is tighter than the policy's 15 minutes. Escalation goes to the team's normal queue.
  - SEV3: one business day, the policy acknowledgement time. Escalation goes to the team's normal queue.
  - The Payments notes' 3 minutes are unofficial (F-06). Mention the conflict. Do not follow it.
- A partial write, once real writes exist: record the decision first, then each external write with an idempotency key, and leave a failed write visible for retry. People get paged even if the incident record is still pending.

## Q7 · Cost and latency limits, and how they are enforced
- Choice: hard per-ticket limits, plus a designed org cap. Reject the $0.05 / 30s / ~$20k-a-month figures; they are not in the inputs, and 10,000 engineers times 40 tickets a day is not what the brief says.
- Why: the brief's volume is about 40 tickets a day for one team, later the whole engineering org, with no surprise bill. Enforce 2 model calls and a token cap on the answer. A local lookup step times out at 2 seconds, a model call at 8 seconds, and the whole ticket at 20 seconds. The evaluation bar is p95 latency at or under 8 seconds (Q8). If the model is down, over budget, or would pass the 20-second deadline, the rules and an extractive answer still return a response. Log tokens, latency and failures per ticket, without logging ticket text. Alert if p95 passes 8 seconds, or if the fallback rate or cost per ticket drifts. A search index is a later change if documents grow past what a scan can do; 14 documents do not need one.

## Q8 · Evaluation set and the bars it must meet
- Choice: the shapes in the agent's table, with the corrections below, plus the hand-off queue and failure cases. Bars fixed before the first run.
- Corrections:
  - A is answered from the runbook and related to the open canary incident. The draft postmortem may be cited and must be labeled a draft (F-09). Citing the draft alone is not enough.
  - B for a general filer, including Owen, is `refused` with no restricted content. B for a restricted filer is `answered` from the FINAL postmortem, never the superseded draft. The agent's bar ("Owen is general, so allowed") contradicts F-01.
  - C is `action_decided` for a filer who is not on the Payments team. The agent's "Billing engineer is refused" contradicts Q4. C does not describe the canary symptoms, so it does not match INC-2101, which C13 found open. The decision opens a new incident, puts INC-2101 in `related` for a person to merge, and pages the payments-api on-call. It does not attach to INC-2101 and it does not refuse.
  - D is `duplicate` of the open latency incident and of the earlier matching ticket. TCK-0102 is `routed`, not a duplicate.
  - E is `answered` with the owning team.
  - VPN is `answered`, not `refused`.
- Bars: restricted leaks = 0, wrongful refusals = 0, disposition and routing at least 90%, every planned step appears in `steps_run`, p95 latency at or under 8 seconds (Q7).
- Findings it relies on: F-01, F-09, F-02, F-08.

## Q9 · Built versus only designed
- Choice: the agent's split, with escalation timers and real writes moved to designed-only.
- Built: `POST /tickets`, ingestion and the data-quality report, clearance and document filtering, classification with a rules fallback, lookups, duplicate matching, follow-ups in SQLite, action decisions recorded as dry runs, tests, the evaluation set and its committed results, a deployable service.
- Designed only: live APIs for the six systems, real pages and incident writes, the retry worker, acknowledgement timers, per-filer and org spend caps, search at a large document count, metrics dashboards.
- Why: the brief asks for a narrow build and a complete design. A timer service and a search cluster are not what the endpoint has to prove.

## The agent's open questions (1–4)
1. On-call down for a long time: do not fall back to a stale roster. Route to the owning team and say the scheduler did not answer. A wrong page is worse than a delayed name.
2. How live on-call arrives: designed as an API read. This build uses the extract and reports its as-of.
3. Double page if the ack is lost: send with an idempotency key, and do not page the same person again for the same service within a short window even if the first result was unclear.
4. Budget envelope: no number was given. Cap each ticket (Q7), alert on daily spend, and switch to the no-model path when the cap is hit. Ask the head of engineering for the monthly number before production.

## Left to the agent
- None of Q1–Q9. The briefing should follow this file. If a detail here is silent, choose the smaller option and mark it "(agent's choice)" in `BRIEFING.md`.

## Discovery gaps this file is not pretending were findings
`FINDINGS.md` did not give these a rule. They still bind the build:
- Open incidents are not split by age. Q5's live-incident rule is this gap, not a finding. C07 has a date range and an open count, and C10 has sample timestamps. Neither output is the count of placeholder incidents inside an age window, so those counts are not cited above. A discovery turn has to log that command before the briefing may quote the numbers.
- The extracts were not taken at the same moment. The on-call week label is in C05, the queue's latest `filed_at` in C06, and the incident date range in C07. Each source keeps its own as-of. Q5 does not use those clocks to decide that a hand-off ticket is recent. It uses the link to a live incident, and for API-filed tickets the service's own timestamps.
- "Restricted" is a marking on a document, not the word appearing anywhere in it. The discovery log's document pass marked the access policy restricted for that reason. It is general.
