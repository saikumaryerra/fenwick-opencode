Turn 1 | discovery | done (steps 1–3) | next: step 4 — extract unstructured documents (14 .docx files)
Turn 2 | discovery | done (steps 4–6) | next: design phase — see scenario.txt and PROTOCOL.md
Turn 3 | design | done (options Q1–Q9 in chat, Plan mode, no files) | next: I write docs/design/DECISIONS.md myself; Turn 4 drafts BRIEFING.md
Turn 4 | design | done (BRIEFING.md drafted) | next: review BRIEFING.md before coding
Turn 5 | review | done | next: code — implement modules per BRIEFING.md
Turn 6 | scaffold + data ingestion | done | next: auth/clearance + engine modules + eval
Turn 7 | domain layer | done (classify, document_search, incident_matcher, duplicate_check, action_decider, routing + 180 tests pass) | next: orchestrator + state/store + eval cases
Turn 8 | adapters | done (6 adapters + orchestrator + step tracker + 60 failure-mode tests, 240 total pass) | next: state/store + eval cases
Turn 9 | request flow + POST /tickets | done (main.py, 3 bug fixes during scenario test, 240 tests pass) | next: state/store + eval cases
Turn 10 | API-level tests | done (50 new tests: contract shape, per-kind §6, external failures/timeouts, adversarial access, follow-ups, invalid input; fixed 2 code bugs in classifier guard + orchestrator timeout outcomes; 290 total pass) | next: state/store + eval cases
Turn 11 | eval framework | done (eval/cases.py: 33 cases; eval/runner.py: in-process or URL, per-case checks, §9 bars, JSON+MD output) | next: state/store + eval results in ARTEFACT.md