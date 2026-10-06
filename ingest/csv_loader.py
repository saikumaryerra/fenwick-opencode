"""Parse 5 CSVs, normalize, validate.

Uses csv module with newline='' for CRLF handling (F-10).
"""

import csv
import os
from collections.abc import Iterator

from ingest.normalize import normalize_service, parse_date, parse_update_timestamp


DATA_PACK = os.path.join(os.path.dirname(__file__), "..", "fenwick-data-pack")


def _csv_rows(path: str) -> Iterator[dict[str, str]]:
    """Yield rows from a CSV file, handling CRLF endings."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        yield from reader


def load_roster() -> list[dict]:
    """Load engineer_roster.csv. Returns list of dicts."""
    path = os.path.join(DATA_PACK, "engineer_roster.csv")
    return list(_csv_rows(path))


def load_services() -> list[dict]:
    """Load service_registry.csv. Returns list of dicts with normalized service_name."""
    path = os.path.join(DATA_PACK, "service_registry.csv")
    rows = list(_csv_rows(path))
    for r in rows:
        r["service_name_normalized"] = normalize_service(r["service_name"])
    return rows


def load_oncall() -> list[dict]:
    """Load oncall_schedule.csv. Returns list of dicts."""
    path = os.path.join(DATA_PACK, "oncall_schedule.csv")
    return list(_csv_rows(path))


def load_incidents() -> list[dict]:
    """Load incident_log.csv. Returns list of dicts with normalized service_name and parsed dates."""
    path = os.path.join(DATA_PACK, "incident_log.csv")
    rows = list(_csv_rows(path))
    for r in rows:
        r["service_normalized"] = normalize_service(r["service_name_raw"])
        r["date_parsed"] = parse_date(r["date"])
        r["updates_parsed"] = _parse_updates(r.get("updates", ""))
    return rows


def _parse_updates(updates_str: str) -> list[dict]:
    """Parse the updates field into a list of (timestamp, emp_id, note)."""
    if not updates_str or not updates_str.strip():
        return []
    entries = []
    for part in updates_str.split(";"):
        part = part.strip()
        if not part:
            continue
        segments = part.split("|", 2)
        if len(segments) == 3:
            ts_str, emp_id, note = segments
            entries.append({
                "timestamp_raw": ts_str,
                "timestamp_parsed": parse_update_timestamp(ts_str),
                "emp_id": emp_id,
                "note": note,
            })
    return entries


def load_open_tickets() -> list[dict]:
    """Load open_tickets.csv. Returns list of dicts."""
    path = os.path.join(DATA_PACK, "open_tickets.csv")
    return list(_csv_rows(path))


def load_all() -> dict:
    """Load all 5 CSV datasets. Returns a dict keyed by name."""
    return {
        "roster": load_roster(),
        "services": load_services(),
        "oncall": load_oncall(),
        "incidents": load_incidents(),
        "open_tickets": load_open_tickets(),
    }


def csv_file_count() -> int:
    """Return the number of CSV files in the data pack directory."""
    count = 0
    for f in os.listdir(DATA_PACK):
        if f.endswith(".csv"):
            count += 1
    return count