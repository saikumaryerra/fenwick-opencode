"""Tests for ingest/doc_loader.py — F-09."""

import pytest
from ingest.doc_loader import (
    load_documents,
    is_restricted,
    find_documents_by_family,
    get_current_doc_version,
)


class TestDocumentDiscovery:
    """F-09: Documents are discovered by scanning the store, not only by CSV links."""

    def test_all_14_docs_discovered(self):
        docs = load_documents()
        assert len(docs) == 14, f"Expected 14 .docx files, found {len(docs)}"

    def test_orphan_draft_postmortem_found(self):
        """CSV-only search would miss orphan DRAFT postmortems not linked from incident_log.csv."""
        docs = load_documents()
        # postmortem_payments_api_canary_2026-09-04_DRAFT.docx exists on disk
        # but may not be linked from incident_log.csv postmortem_doc column
        assert "postmortem_payments_api_canary_2026-09-04_DRAFT.docx" in docs, (
            "Orphan draft postmortem not found — CSV-only search would miss it"
        )

    def test_discovery_from_subdirectories(self):
        """Documents exist in runbooks, postmortems, and policies directories."""
        docs = load_documents()
        categories = set(m["category"] for m in docs.values())
        assert "runbooks" in categories
        assert "postmortems" in categories
        assert "policies" in categories


class TestRestrictedDetection:
    """Document sensitivity detection."""

    def test_policy_access_doc_not_restricted(self):
        """policy_access_and_clearance.docx is a GENERAL-access document
        despite mentioning 'restricted'. Its own body determines sensitivity."""
        docs = load_documents()
        policy_doc = docs.get("policy_access_and_clearance.docx")
        assert policy_doc is not None
        # The document's body determines sensitivity, not keyword presence.
        # Per BRIEFING.md §3: "The document's own body determines sensitivity,
        # not keyword presence."
        assert not policy_doc["restricted"], (
            "policy_access_and_clearance.docx should be GENERAL access despite mentioning 'restricted'"
        )

    def test_postmortem_restricted_status(self):
        """Postmortems with restricted content should be marked."""
        docs = load_documents()
        # The auth_gateway FINAL postmortem contains restricted content
        final = docs.get("postmortem_auth_gateway_outage_FINAL.docx")
        superseded = docs.get("postmortem_auth_gateway_outage_DRAFT_superseded.docx")
        # At least one should be restricted
        restricted_docs = [d for d in [final, superseded] if d and d["restricted"]]
        assert len(restricted_docs) >= 1


class TestDocumentFamilies:
    """Document family grouping and versioning."""

    def test_auth_gateway_family_has_two_members(self):
        docs = load_documents()
        members = find_documents_by_family(docs, "postmortem_auth_gateway_outage")
        assert len(members) == 2

    def test_current_version_is_final_not_superseded(self):
        docs = load_documents()
        current = get_current_doc_version(docs, "postmortem_auth_gateway_outage")
        assert current is not None
        # Current should be the FINAL version, not the DRAFT_superseded
        assert "FINAL" in current["path"]
        assert "superseded" not in current["path"].lower()

    def test_superseded_doc_skipped(self):
        docs = load_documents()
        current = get_current_doc_version(docs, "postmortem_auth_gateway_outage")
        superseded = docs.get("postmortem_auth_gateway_outage_DRAFT_superseded.docx")
        assert current is not None
        if superseded:
            assert current["path"] != superseded["path"]


class TestDocTypes:
    """Categories of documents."""

    def test_runbooks_count(self):
        docs = load_documents()
        runbooks = {n for n, m in docs.items() if m["category"] == "runbooks"}
        assert len(runbooks) == 6

    def test_postmortems_count(self):
        docs = load_documents()
        postmortems = {n for n, m in docs.items() if m["category"] == "postmortems"}
        assert len(postmortems) == 6

    def test_policies_count(self):
        docs = load_documents()
        policies = {n for n, m in docs.items() if m["category"] == "policies"}
        assert len(policies) == 2