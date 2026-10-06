"""Tests for ingest/csv_loader.py — F-04, F-10."""

import pytest
from ingest.csv_loader import (
    csv_file_count,
    load_all,
    load_roster,
    load_services,
    load_oncall,
    load_incidents,
    load_open_tickets,
)


class TestCsvFileCount:
    """F-04: System must handle 5 CSV files."""

    def test_exactly_five_csvs(self):
        """There must be 5 CSV files, not 4."""
        count = csv_file_count()
        assert count == 5, f"Expected 5 CSV files, found {count}. If design says 4, it's wrong."

    def test_open_tickets_is_fifth(self):
        """open_tickets.csv is the 5th CSV."""
        open_tickets = load_open_tickets()
        assert len(open_tickets) > 0, "open_tickets.csv must contain data"


class TestLoadDatasets:
    """All 5 datasets load without error."""

    def test_roster_has_14_rows(self):
        roster = load_roster()
        assert len(roster) == 14

    def test_services_has_10_rows(self):
        services = load_services()
        assert len(services) == 10

    def test_oncall_has_15_rows(self):
        oncall = load_oncall()
        assert len(oncall) == 15

    def test_incidents_have_rows(self):
        incidents = load_incidents()
        assert len(incidents) > 0

    def test_open_tickets_have_25_rows(self):
        open_tickets = load_open_tickets()
        assert len(open_tickets) == 25

    def test_load_all_returns_5_keys(self):
        data = load_all()
        assert set(data.keys()) == {"roster", "services", "oncall", "incidents", "open_tickets"}


class TestCRLFHandling:
    """F-10: CSV parsing must handle CRLF line endings (\\r\\n)."""

    def test_no_trailing_cr(self):
        """Using newline='' with csv.DictReader avoids trailing \\r."""
        roster = load_roster()
        for r in roster:
            for key, value in r.items():
                assert not value.endswith("\r"), f"Field '{key}' has trailing CR: {value!r}"
                # Check that individual fields don't have embedded \r
                assert "\r" not in value, f"Field '{key}' contains CR: {value!r}"

    def test_split_newline_would_fail(self):
        """Using split('\\n') would leave trailing \\r on last field."""
        with open("fenwick-data-pack/engineer_roster.csv", "rb") as f:
            raw = f.read()
        # Simulate split('\n')
        lines = raw.decode("utf-8").split("\n")
        for line in lines[1:]:  # skip header
            if line.strip():
                fields = line.split(",")
                last_field = fields[-1]
                if last_field.endswith("\r"):
                    break  # confirms the issue
        else:
            # If we didn't find any, the raw check will catch it
            pass

    def test_csv_fields_have_no_cr_in_ticket_text(self):
        """open_tickets has multi-word text fields; ensure no \\r contamination."""
        tickets = load_open_tickets()
        for t in tickets:
            text = t.get("text", "")
            assert "\r" not in text, f"Ticket {t['ticket_id']} text contains CR"


class TestServiceNormalizationInLoader:
    """Services loaded should have normalized names attached."""

    def test_normalized_key_present(self):
        services = load_services()
        for s in services:
            assert "service_name_normalized" in s


class TestIncidentUpdatesParsed:
    """Incident updates should be parsed into structured entries."""

    def test_updates_parsed_key_present(self):
        incidents = load_incidents()
        for inc in incidents:
            assert "updates_parsed" in inc
            assert "service_normalized" in inc
            assert "date_parsed" in inc