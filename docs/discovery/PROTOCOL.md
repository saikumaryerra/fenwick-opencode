# Data discovery protocol

This phase investigates the data for the task in `scenario.txt` before any design or code exists. Assume nothing about
the data and verify everything. The record of the investigation is a deliverable: a reviewer must be able to follow every
question, command, output and conclusion, in order.

## Rules

- Inputs: `scenario.txt`, the data pack folder, `AGENTS.md` if present. No web, nothing outside this folder. No
  application code in this phase.
- Never open a large file whole with a read tool or `cat`; inspect it with scripts that print counts, format classes or
  a handful of rows.
- **Every command is a saved file**: `scripts/discovery/Cnn_<slug>.py` or `.sh` (standard library only, run from the repo
  root). Run it as `python3 scripts/discovery/Cnn_<slug>.py > docs/discovery/output/Cnn.txt 2>&1` and append the same
  line to `scripts/discovery/run_all.sh`. Keep each output under ~60 lines; summarise inside the script.
- **Every question gets a log entry** in `docs/discovery/LOG.md`. The log is append-only: never edit an earlier entry;
  corrections are new entries that reference the old one. Get the time with `date '+%Y-%m-%d %H:%M'`.
- Errors, crashes and dead ends are logged too.
- Do not ask the user about the data; investigate and log. Keep replies to at most 10 lines. At the end of every turn
  append one line to `PROGRESS.md`: `Turn <n> | discovery | <done / partial: …> | next: <…>`. Never commit.

## Log entry format

```markdown
### D-<nn> · <YYYY-MM-DD HH:MM> · <the question, as a question>
- Why: <what prompted it: a quoted phrase from the inputs, or an earlier entry (cite D-nn)>
- Command: `scripts/discovery/Cnn_<slug>.py` → `docs/discovery/output/Cnn.txt`
- Key output: <at most 6 quoted lines>
- Observation: <what the output shows, with numbers>
- Conclusion: <what it means for a system built on this data> (confidence: high | medium | low)
- Next: <the question this raises>
```

## Method, in order

1. **Claims.** Read `scenario.txt` and every README or data dictionary in the data pack. List every statement the data
   could contradict (formats, meanings, ownership, what each source is authoritative for, the example scenarios the task
   describes) as hypotheses H1…Hn in entry D-01.
2. **Inventory.** Every file with size, line count, encoding and line endings. Read small files whole.
3. **Profile each structured file** against the standard data-quality dimensions:
   - *Completeness*: missing or empty values, per column.
   - *Validity*: parse every field with a strict parser; count the format classes in each column.
   - *Uniqueness*: duplicate keys and duplicate rows.
   - *Consistency*: fields in the same row that should agree with each other.
   - *Integrity*: every reference resolves; the same entity is named the same way in every file.
   - *Timeliness*: the as-of time of each source, and what "now" means for each.
   - *Distribution*: value counts and outliers; rows that do not fit the bulk pattern.
4. **Unstructured documents.** Extract each one separately (standard library), scan for hidden or tracked content, then
   read each one fully. Record its metadata (title, status, version, owner, dates), how it relates to other documents and
   to the structured data, any markings, and every concrete rule or number it states.
5. **Cross-checks.** Test every rule stated in a document against the data. Compare every pair of sources that describe
   the same thing. For each example scenario in `scenario.txt`, trace the data it depends on and whether that data
   supports a correct outcome.
6. **Rules.** For each finding, state the rule a system should apply and a test that would fail if the rule were wrong.

## Findings file

`docs/discovery/FINDINGS.md`, written at the end of step 6:

```markdown
### F-<nn> · <short title>
- Evidence: <numbers, with the D-entries that produced them>
- Rule: <what the system should do>
- Test: <what would fail if the rule were wrong>
- Confidence: high | medium | low
```

End the file with **Open questions**: what you would ask the data's owners before relying on it.
