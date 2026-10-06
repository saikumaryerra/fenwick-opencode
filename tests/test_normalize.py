"""Tests for ingest/normalize.py — F-02, F-03, F-08, F-11."""

import pytest
from ingest.normalize import (
    normalize_service,
    parse_date,
    normalize_incident_id,
    parse_update_timestamp,
)


class TestNormalizeService:
    """F-02: Service names must be normalized (lowercase, _ → -)."""

    def test_lowercase(self):
        assert normalize_service("Payments-API") == "payments-api"

    def test_underscore_to_hyphen(self):
        assert normalize_service("auth_gateway") == "auth-gateway"
        assert normalize_service("payments_api") == "payments-api"

    def test_mixed_case_and_underscore(self):
        assert normalize_service("Auth-Gateway") == "auth-gateway"
        assert normalize_service("Auth_Gateway") == "auth-gateway"

    def test_collision_resolution(self):
        """payments-api, Payments-API, payments_api all normalize to same."""
        a = normalize_service("payments-api")
        b = normalize_service("Payments-API")
        c = normalize_service("payments_api")
        assert a == b == c == "payments-api"

    def test_join_without_normalization_fails(self):
        """When joining incident_log to service_registry without normalization,
        unmatched rows appear due to name variants."""
        service_registry = {"payments-api", "auth-gateway"}
        incident_variants = {"payments-api", "payments_api", "Payments-API", "auth-gateway", "auth_gateway", "Auth-Gateway"}
        joined_via_raw = len(incident_variants & service_registry)
        normalized_incidents = {normalize_service(v) for v in incident_variants}
        joined_via_normalized = len(normalized_incidents & service_registry)
        assert joined_via_raw == 2  # exact matches only; 4 variants don't match
        assert joined_via_raw < len(incident_variants)  # without normalization, not all match
        assert joined_via_normalized == len(service_registry)  # all normalize to canonical names

    def test_whitespace_stripped(self):
        assert normalize_service("  payments-api  ") == "payments-api"


class TestParseDate:
    """F-03: Dates must be parsed with 3-parser fallback."""

    def test_iso_format(self):
        dt = parse_date("2025-04-26")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 4
        assert dt.day == 26

    def test_iso_datetime(self):
        dt = parse_date("2025-04-26T13:00:00")
        assert dt is not None
        assert dt.hour == 13
        assert dt.minute == 0

    def test_dd_mon_yyyy(self):
        dt = parse_date("28 May 2025")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 5
        assert dt.day == 28

    def test_mm_dd_yyyy(self):
        dt = parse_date("03/12/2024")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 3
        assert dt.day == 12  # MM/DD → March 12, not December 3

    def test_ambiguity_mm_dd_over_dd_mm(self):
        """MM/DD/YYYY format — 03/12/2024 is March 12, not December 3."""
        dt = parse_date("03/12/2024")
        assert dt.month == 3
        assert dt.day == 12

    def test_string_sort_vs_parsed_order(self):
        """String-sorting dates gives different order than parsed-date sorting.
        Without 3-parser, dates in DD Mon YYYY format sort incorrectly."""
        raw_dates = ["2024-01-05", "05 Feb 2024", "01/15/2024"]
        parsed = [parse_date(d) for d in raw_dates]
        parsed.sort()
        sorted_raw = sorted(raw_dates)
        # Raw sort: "01/15/2024" < "05 Feb 2024" (because '/' < 'F' < numeric)
        # Parsed sort: Jan 5 < Jan 15 < Feb 5
        assert sorted_raw != [d.strftime("%Y-%m-%d") for d in parsed if d]
        assert "".join(d.strftime("%Y-%m-%d") for d in parsed if d) == "2024-01-052024-01-152024-02-05"

    def test_empty_string(self):
        assert parse_date("") is None

    def test_none(self):
        assert parse_date(None) is None

    def test_whitespace(self):
        assert parse_date("   ") is None


class TestNormalizeIncidentId:
    """F-08: Both INC-NNNN and INC-NNNNNN are valid."""

    def test_four_digit(self):
        assert normalize_incident_id("INC-9000") == "INC-009000"

    def test_six_digit(self):
        assert normalize_incident_id("INC-009000") == "INC-009000"

    def test_single_regex_fails_short(self):
        """A regex ^INC-\\d{6}$ would fail INC-9000 (4 digits)."""
        import re
        r = re.compile(r"^INC-\d{6}$")
        assert r.match("INC-009000") is not None
        assert r.match("INC-9000") is None  # fails!

    def test_lowercase_input(self):
        assert normalize_incident_id("inc-9000") == "INC-009000"

    def test_invalid_format(self):
        assert normalize_incident_id("foo") is None
        assert normalize_incident_id("") is None
        assert normalize_incident_id(None) is None

    def test_three_digit_rejected(self):
        assert normalize_incident_id("INC-900") is None

    def test_seven_digit_padded(self):
        assert normalize_incident_id("INC-9000000") is None


class TestParseUpdateTimestamp:
    """F-11: Update timestamps use same 3-parser strategy."""

    def test_iso_datetime(self):
        dt = parse_update_timestamp("2025-02-26T13:00:00")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 2
        assert dt.day == 26
        assert dt.hour == 13

    def test_dd_mon_yyyy_t_format(self):
        """DD Mon YYYYTHH:MM:SS format."""
        dt = parse_update_timestamp("09 Sep 2024T12:00:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 9
        assert dt.day == 9
        assert dt.hour == 12

    def test_mm_dd_yyyy_t_format(self):
        """MM/DD/YYYYTHH:MM:SS format."""
        dt = parse_update_timestamp("08/16/2024T13:00:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 8
        assert dt.day == 16
        assert dt.hour == 13

    def test_iso_only_parser_fails_majority(self):
        """An ISO-only parser would fail 60%+ of update timestamps."""
        timestamps = [
            "2025-02-26T13:00:00",  # ISO
            "09 Sep 2024T12:00:00",  # DD Mon
            "08/16/2024T13:00:00",  # MM/DD
            "01 Jan 2026T09:00:00",  # DD Mon
            "07/06/2026T14:00:00",  # MM/DD
        ]
        iso_only_success = 0
        for ts in timestamps:
            try:
                import datetime
                datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                iso_only_success += 1
            except ValueError:
                pass
        assert iso_only_success == 1  # only the first one

        three_parser_success = sum(
            1 for ts in timestamps if parse_update_timestamp(ts) is not None
        )
        assert three_parser_success == 5

    def test_empty_string(self):
        assert parse_update_timestamp("") is None

    def test_none(self):
        assert parse_update_timestamp(None) is None


class TestNormalizeIntegration:
    """Integration-level checks across rules."""

    def test_deprecated_service_oncall_does_not_crash(self):
        """F-05: Deprecated services with on-call entries must not crash."""
        from ingest.csv_loader import load_services, load_oncall
        from ingest.normalize import normalize_service

        services = load_services()
        oncall = load_oncall()

        deprecated = {s["service_name_normalized"] for s in services if s["status"] == "deprecated"}
        oncall_services = {normalize_service(oc["service_name_raw"]) for oc in oncall}

        overlap = deprecated & oncall_services
        # This should not crash — deprecated but still has on-call entries
        for svc in overlap:
            oc_for_svc = [oc for oc in oncall if normalize_service(oc["service_name_raw"]) == svc]
            assert len(oc_for_svc) > 0  # on-call entries exist

    def test_sre_reachable_for_oncall(self):
        """F-07: SRE engineers are reachable for on-call."""
        from ingest.csv_loader import load_roster, load_oncall
        from auth.clearance import compute_clearance

        roster = load_roster()
        oncall = load_oncall()

        sre_ids = {r["emp_id"] for r in roster if r["team"] == "SRE"}
        oncall_ids = {oc["engineer_emp_id"] for oc in oncall}

        # SRE engineers should appear in on-call entries
        assert sre_ids & oncall_ids, "No SRE engineers found on on-call"

        # Restrict on-call to owning-team only would miss SRE
        sre_not_found = sre_ids - oncall_ids
        assert len(sre_not_found) < len(sre_ids), "All SRE missing from on-call — wrong behavior"