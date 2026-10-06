"""Tests for auth/clearance.py — F-01."""

import pytest
from auth.clearance import compute_clearance, can_see_document, get_filer
from ingest.csv_loader import load_roster


class TestComputeClearance:
    """F-01: Clearance must be computed from team+title, not from roster column."""

    def test_security_team_restricted(self):
        """Security team members get restricted."""
        assert compute_clearance("Security", "Security Engineer") == "restricted"

    def test_sre_team_restricted(self):
        """SRE team members get restricted."""
        assert compute_clearance("SRE", "SRE") == "restricted"
        assert compute_clearance("SRE", "Senior SRE") == "restricted"

    def test_senior_title_restricted(self):
        """Senior title → restricted, even in general team."""
        assert compute_clearance("Payments", "Senior Software Engineer") == "restricted"
        assert compute_clearance("Billing", "Senior Software Engineer") == "restricted"

    def test_staff_title_restricted(self):
        """Staff title → restricted."""
        assert compute_clearance("Platform", "Staff Software Engineer") == "restricted"

    def test_general_engineer_general_clearance(self):
        """Non-senior, non-Security, non-SRE → general."""
        assert compute_clearance("Payments", "Software Engineer") == "general"
        assert compute_clearance("Billing", "Software Engineer") == "general"
        assert compute_clearance("Platform", "Software Engineer") == "general"

    def test_restricted_doc_refused_for_general(self):
        """F-01 test: Feed restricted doc to a non-Security non-Senior filer; must be refused."""
        clearance = compute_clearance("Payments", "Software Engineer")  # general
        assert clearance == "general"
        assert can_see_document(clearance, document_restricted=True) is False

    def test_restricted_doc_allowed_for_restricted(self):
        clearance = compute_clearance("Security", "Security Engineer")  # restricted
        assert can_see_document(clearance, document_restricted=True) is True

    def test_general_doc_visible_to_all(self):
        assert can_see_document("general", document_restricted=False) is True
        assert can_see_document("restricted", document_restricted=False) is True

    def test_roster_clearance_tier_not_trusted(self):
        """Verify that computed clearance differs from roster column for some entries."""
        roster = load_roster()
        disagreements = 0
        for r in roster:
            computed = compute_clearance(r["team"], r["title"])
            if computed != r["clearance_tier"]:
                disagreements += 1
        # At least one engineer should have computed != roster
        assert disagreements > 0, "No disagreements — could mean clearance_tier is trusted, not computed"


class TestCanSeeDocument:
    """Clearance checks for document access."""

    def test_general_cannot_see_restricted(self):
        assert can_see_document("general", True) is False

    def test_restricted_can_see_restricted(self):
        assert can_see_document("restricted", True) is True

    def test_anyone_can_see_general(self):
        assert can_see_document("general", False) is True
        assert can_see_document("restricted", False) is True


class TestGetFiler:
    """Filer lookup from roster."""

    def test_finder_found(self):
        roster = load_roster()
        filer = get_filer(roster, "FEN-1001")
        assert filer is not None
        assert filer["name"] == "Priya Nathan"

    def test_filer_not_found(self):
        roster = load_roster()
        filer = get_filer(roster, "FEN-9999")
        assert filer is None