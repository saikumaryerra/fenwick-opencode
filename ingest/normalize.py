"""Service name normalization, date parsing, ID normalization."""

import re
from datetime import datetime, timezone


def normalize_service(name: str) -> str:
    """Normalize a service name: lowercase, underscores to hyphens, strip whitespace."""
    result = name.strip().lower().replace("_", "-")
    return result


def parse_date(value: str) -> datetime | None:
    """Parse a date string using 3-parser fallback.

    Formats attempted (in order):
      1. ISO 8601 (e.g. 2025-04-26, 2025-04-26T13:00:00)
      2. DD Mon YYYY (e.g. 28 May 2025)
      3. MM/DD/YYYY (e.g. 03/12/2024)

    Returns a timezone-aware datetime (UTC), or None if all fail.
    """
    if not value or not value.strip():
        return None
    val = value.strip()

    # Parser 1: ISO 8601 (date or datetime)
    try:
        if "T" in val:
            dt = datetime.strptime(val.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        dt = datetime.strptime(val, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Parser 2: DD Mon YYYY (e.g. 28 May 2025)
    try:
        dt = datetime.strptime(val, "%d %b %Y")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Parser 3: MM/DD/YYYY (e.g. 03/12/2024)
    try:
        dt = datetime.strptime(val, "%m/%d/%Y")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    return None


def normalize_incident_id(incident_id: str) -> str | None:
    """Normalize an incident ID to a standard form.

    Accepts INC-NNNN or INC-NNNNNN (4 to 6 digits).
    Returns zero-padded 6-digit form (INC-NNNNNN), or None if invalid.
    """
    if not incident_id or not incident_id.strip():
        return None
    val = incident_id.strip().upper()
    m = re.match(r"^INC-(\d{4,6})$", val)
    if not m:
        return None
    digits = m.group(1)
    return f"INC-{digits.zfill(6)}"


def parse_update_timestamp(val: str) -> datetime | None:
    """Parse an update-timestamp field using the same 3-parser strategy.

    Update timestamps in incident_log.csv use the same three formats
    as dates, but always include a time component (T-separated).

    Formats:
      1. ISO 8601 datetime: 2025-02-26T13:00:00
      2. DD Mon YYYY + T + time: "09 Sep 2024T12:00:00"
      3. MM/DD/YYYY + T + time: "08/16/2024T13:00:00"
    """
    if not val or not val.strip():
        return None
    v = val.strip()

    # Parser 1: ISO with T (e.g. 2025-02-26T13:00:00)
    try:
        dt = datetime.strptime(v.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Parser 2: DD Mon YYYYTHH:MM:SS (e.g. 09 Sep 2024T12:00:00)
    try:
        dt = datetime.strptime(v, "%d %b %YT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Parser 3: MM/DD/YYYYTHH:MM:SS (e.g. 08/16/2024T13:00:00)
    try:
        dt = datetime.strptime(v, "%m/%d/%YT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    return None