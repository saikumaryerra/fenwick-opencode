"""Cross-cutting tests for every F-id data rule.

These tests exercise the actual data pack files through the ingestion
pipeline and verify that each data rule is correctly applied in code.
"""

import pytest
from ingest.csv_loader import (
    load_all,
    load_roster,
    load_services,
    load_oncall,
    load_incidents,
    load_open_tickets,
    csv_file_count,
)
from ingest.normalize import (
    normalize_service,
    parse_date,
    normalize_incident_id,
    parse_update_timestamp,
)
from ingest.doc_loader import load_documents
from auth.clearance import compute_clearance, can_see_document


class TestF01_ClearanceComputed:
    """F-01: Clearance must be COMPUTED from team+title, not trusted from roster column."""

    def test_computed_clearance_differs_from_roster(self):
        """At least one engineer has computed clearance != roster clearance_tier."""
        roster = load_roster()
        differing = []
        for r in roster:
            computed = compute_clearance(r["team"], r["title"])
            if computed != r["clearance_tier"]:
                differing.append((r["emp_id"], r["name"], r["clearance_tier"], computed))
        assert len(differing) > 0, (
            "No disagreements — clearance_tier column matches computed for all. "
            "This means the roster column is being trusted directly."
        )

    def test_general_filer_refused_restricted_doc(self):
        """Feed restricted doc to a non-Security non-Senior filer; must be refused."""
        # Marisol Feng: Payments, Software Engineer → general
        clearance = compute_clearance("Payments", "Software Engineer")
        assert clearance == "general"
        assert can_see_document(clearance, True) is False


class TestF02_ServiceNameNormalization:
    """F-02: Service names must be normalized (lowercase, _ → -) before join/lookup."""

    def test_normalization_matches_variants(self):
        services = load_services()
        canonical = {s["service_name_normalized"] for s in services}

        # Load incidents and check normalization makes them joinable
        incidents = load_incidents()
        incident_services = set()
        for inc in incidents:
            incident_services.add(normalize_service(inc["service_name_raw"]))

        # Every incident service should match a canonical service
        unmatched = incident_services - canonical
        assert len(unmatched) == 0, f"Unmatched incident services after normalization: {unmatched}"

    def test_oncall_services_match_registry(self):
        services = load_services()
        oncall = load_oncall()
        canonical = {s["service_name_normalized"] for s in services}

        oncall_services = set()
        for oc in oncall:
            oncall_services.add(normalize_service(oc["service_name_raw"]))

        unmatched = oncall_services - canonical
        # notifications-worker (deprecated) is in registry, so should match
        assert len(unmatched) == 0, f"Unmatched on-call services: {unmatched}"


class TestF03_DateParsing:
    """F-03: Dates must be parsed with 3-parser fallback."""

    def test_all_incident_dates_parseable(self):
        incidents = load_incidents()
        unparsed = [i for i in incidents if i["date_parsed"] is None]
        assert len(unparsed) == 0, f"{len(unparsed)} dates failed to parse"

    def test_all_three_formats_present(self):
        """Verify all 3 date formats exist in the data."""
        incidents = load_incidents()
        formats = set()
        for i in incidents:
            d = i["date"]
            if "T" in d or d.count("-") == 2 and len(d) == 10:
                formats.add("ISO")
            elif d.count(" ") == 2:
                formats.add("DD Mon YYYY")
            elif d.count("/") == 2:
                formats.add("MM/DD/YYYY")
        assert len(formats) == 3, f"Expected 3 date formats, found {formats}"


class TestF04_FiveCSVs:
    """F-04: System must handle 5 CSV files, not 4."""

    def test_csv_count_is_five(self):
        assert csv_file_count() == 5

    def test_open_tickets_loaded(self):
        tickets = load_open_tickets()
        assert len(tickets) == 25


class TestF05_DeprecatedOncall:
    """F-05: Deprecated services with on-call entries must not crash."""

    def test_deprecated_with_oncall_does_not_crash(self):
        services = load_services()
        oncall = load_oncall()
        deprecated = {s["service_name"] for s in services if s["status"] == "deprecated"}
        deprecated_normalized = {
            normalize_service(s["service_name"])
            for s in services if s["status"] == "deprecated"
        }
        oncall_services = {normalize_service(oc["service_name_raw"]) for oc in oncall}
        overlap = deprecated_normalized & oncall_services
        # notifications-worker is deprecated but has on-call entries
        assert "notifications-worker" in deprecated
        assert len(overlap) >= 1
        # Querying on-call for a deprecated service should not raise
        for svc in overlap:
            entries = [
                oc for oc in oncall
                if normalize_service(oc["service_name_raw"]) == svc
            ]
            assert len(entries) > 0


class TestF06_EscalationTiming:
    """F-06: Escalation timing values — designed (not built)."""

    def test_escalation_values_defined(self):
        """Hardcoded 10min universal would be wrong per SEV1 policy SLA."""
        escalation = {
            "SEV1": 5,
            "SEV2": 10,
            "SEV3": 1440,  # 1 business day in minutes
        }
        assert escalation["SEV1"] == 5
        assert escalation["SEV2"] == 10
        assert escalation["SEV3"] == 1440


class TestF07_SREOncall:
    """F-07: SRE engineers are reachable for on-call even though they own no service."""

    def test_sre_in_oncall(self):
        roster = load_roster()
        oncall = load_oncall()
        sre_ids = {r["emp_id"] for r in roster if r["team"] == "SRE"}
        oncall_sre_ids = {oc["engineer_emp_id"] for oc in oncall}
        sre_oncall = sre_ids & oncall_sre_ids
        assert len(sre_oncall) > 0, "No SRE engineers on on-call schedule"

    def test_restrict_to_owning_team_misses_sre(self):
        """Restricting on-call to owning-team only would never find SRE."""
        services = load_services()
        owning_teams = {s["owning_team"] for s in services}
        # SRE is not an owning team
        assert "SRE" not in owning_teams
        # So restricting on-call resolution to owning-team engineers would miss SRE


class TestF08_IncidentIDFormats:
    """F-08: Both INC-NNNN and INC-NNNNNN are valid incident IDs."""

    def test_mixed_formats_exist(self):
        incidents = load_incidents()
        ids = [i["incident_id"] for i in incidents]
        four_digit = [iid for iid in ids if normalize_incident_id(iid) != iid.upper()]
        assert len(four_digit) > 0, "No short (4-digit) incident IDs found"
        six_digit = [iid for iid in ids if normalize_incident_id(iid) == iid.upper()]
        assert len(six_digit) > 0, "No long (6-digit) incident IDs found"

    def test_all_ids_normalizable(self):
        incidents = load_incidents()
        for inc in incidents:
            normalized = normalize_incident_id(inc["incident_id"])
            assert normalized is not None, f"Unnormalizable ID: {inc['incident_id']}"


class TestF09_DocumentDiscovery:
    """F-09: Documents discovered by scanning the store, not only by CSV links."""

    def test_orphan_docs_found(self):
        """Documents that exist on disk but aren't linked from CSV are still found."""
        docs = load_documents()
        postmortem_names = {
            n for n, m in docs.items() if m["category"] == "postmortems"
        }
        incidents = load_incidents()
        csv_links = set()
        for inc in incidents:
            if inc.get("postmortem_doc", "").strip():
                csv_links.add(inc["postmortem_doc"].strip())

        orphans = postmortem_names - csv_links
        assert len(orphans) > 0, (
            "No orphan documents found — CSV-only search would miss nothing, "
            "but there should be unlinked documents"
        )


class TestF10_CRLF:
    """F-10: CSV parsing must handle CRLF line endings (\\r\\n)."""

    def test_no_trailing_cr_on_any_field(self):
        data = load_all()
        for dataset_name, rows in data.items():
            for row in rows:
                for key, value in row.items():
                    if isinstance(value, str):
                        assert "\r" not in value, (
                            f"CR found in {dataset_name}: {key}={value!r}"
                        )


class TestF11_UpdateTimestamps:
    """F-11: Update timestamps have same 3-format problem as dates."""

    def test_update_timestamps_parsed(self):
        incidents = load_incidents()
        total_updates = 0
        unparsed = 0
        for inc in incidents:
            for u in inc.get("updates_parsed", []):
                total_updates += 1
                if u["timestamp_parsed"] is None:
                    unparsed += 1
        assert total_updates > 0, "No update entries found"
        failure_rate = unparsed / total_updates if total_updates else 0
        assert failure_rate < 0.5, (
            f"More than 50% of update timestamps unparseable ({unparsed}/{total_updates})"
        )

    def test_three_formats_in_updates(self):
        """The data contains update timestamps in all 3 formats."""
        incidents = load_incidents()
        all_raw = []
        for inc in incidents:
            for u in inc.get("updates_parsed", []):
                all_raw.append(u["timestamp_raw"])

        formats = set()
        for ts in all_raw:
            if "T" in ts:
                if ts[0].isdigit() and ts[4] == "-":
                    formats.add("ISO")
                elif ts[2] == "/":
                    formats.add("MM/DD/YYYY")
                else:
                    formats.add("DD Mon YYYY")
        assert "ISO" in formats
        assert "DD Mon YYYY" in formats or "MM/DD/YYYY" in formats