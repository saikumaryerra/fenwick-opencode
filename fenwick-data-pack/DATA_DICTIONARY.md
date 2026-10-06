# Data Dictionary — Fenwick Cloud Support-Queue Pack

## engineer_roster.csv
One row per Fenwick Cloud engineer.
- `emp_id` — employee id.
- `name` — full name.
- `team` — owning team (Payments, Billing, Platform, Security, SRE).
- `title` — job title.
- `clearance_tier` — `general` or `restricted`, as provisioned by IT.

## service_registry.csv
One row per operated service.
- `service_name` — canonical service name.
- `owning_team` — team accountable for the service.
- `status` — `active` or `deprecated`.
- `description` — one line on what the service does.

## oncall_schedule.csv
One row per (service, engineer) on-call assignment, as exported from the on-call
tool.
- `service_name_raw` — service name as written in the on-call tool export.
- `engineer_emp_id` — FK to `engineer_roster.emp_id`.
- `currently_active` — `true` if this is the current on-call shift for that service.
- `rotation_note` — free-text note from the on-call tool.

## incident_log.csv
One row per logged incident, past or current.
- `incident_id` — incident identifier.
- `service_name_raw` — service name as logged at incident time.
- `date` — incident date.
- `severity` — `SEV1` / `SEV2` / `SEV3`.
- `status` — `open` or `resolved`.
- `one_line_summary` — short human summary.
- `postmortem_doc` — filename of the postmortem document, blank if none exists yet
  (including a document that exists in `documents/postmortems/` but has not been
  linked back onto the incident row — this column reflects what has been linked,
  not necessarily everything that has been written).
- `updates` — a log of updates posted against the incident over time, as it
  accumulates them; blank if none have been posted yet. Where present, each entry
  is `ISO8601-timestamp|emp_id|note`, multiple entries separated by `;`.

## open_tickets.csv
One row per ticket currently open in the queue, as of hand-off.
- `ticket_id` — ticket identifier.
- `filed_by` — FK to `engineer_roster.emp_id`.
- `filed_at` — ISO8601 timestamp.
- `text` — the raw ticket text as filed.
- `related_incident_id` — FK to `incident_log.incident_id`, blank if this ticket
  was never linked to one.

## documents/runbooks/
Operational runbooks and team reference material (general access): rollback,
failover, and escalation procedures.

## documents/postmortems/
Incident postmortems, both general and restricted access (see
`policy_access_and_clearance.docx` for what "restricted" means). Not every
postmortem in this folder is linked from `incident_log.csv`'s `postmortem_doc`
column — a document can exist and be findable here before or without that link
being made.

## documents/policies/
`policy_access_and_clearance.docx` defines the two clearance tiers and who holds
each. `policy_oncall_rotation.docx` describes rotation cadence and acknowledgement
SLAs.

## Messaging and paging
Ships no dump. A channel per incident. Your system can post to it and can page a
person. Engineers reply in the channel. A page is delivered, or it is not. An
acknowledgement arrives whenever the person gets to it, and sometimes never.
