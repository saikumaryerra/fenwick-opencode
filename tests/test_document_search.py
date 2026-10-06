"""Tests for engine/document_search.py — F-01, F-09."""

import pytest
from engine.document_search import search, best_answer


def _make_doc(name, text, restricted=False, is_draft=False, is_superseded=False, category="runbooks"):
    return {
        "path": f"/docs/{name}",
        "text": text,
        "restricted": restricted,
        "is_draft": is_draft,
        "is_superseded": is_superseded,
        "category": category,
        "doc_family": name.replace(".docx", "").replace("_DRAFT", "").replace("_FINAL", ""),
    }


_DOCUMENTS = {
    "runbook_rollback_payments_api.docx": _make_doc(
        "runbook_rollback_payments_api.docx",
        "How to roll back payments-api. Step 1: Verify canary. Step 2: Run rollback script."
    ),
    "runbook_rollback_billing_worker.docx": _make_doc(
        "runbook_rollback_billing_worker.docx",
        "How to roll back billing-worker. Step 1: Drain queue. Step 2: Rollback."
    ),
    "postmortem_payments_api_5xx_2026-06-11.docx": _make_doc(
        "postmortem_payments_api_5xx_2026-06-11.docx",
        "Postmortem for payments-api 5xx errors on 2026-06-11. Root cause: dependency timeout.",
        category="postmortems",
    ),
    "postmortem_auth_gateway_outage_FINAL.docx": _make_doc(
        "postmortem_auth_gateway_outage_FINAL.docx",
        "FINAL postmortem for auth-gateway outage. Restricted content — security incident.",
        restricted=True,
        category="postmortems",
    ),
    "postmortem_auth_gateway_outage_DRAFT_superseded.docx": _make_doc(
        "postmortem_auth_gateway_outage_DRAFT_superseded.docx",
        "DRAFT superseded version of auth-gateway postmortem.",
        restricted=True,
        is_draft=True,
        is_superseded=True,
        category="postmortems",
    ),
    "postmortem_payments_api_canary_2026-09-04_DRAFT.docx": _make_doc(
        "postmortem_payments_api_canary_2026-09-04_DRAFT.docx",
        "DRAFT postmortem for payments-api canary failure on 2026-09-04. Not yet finalized.",
        is_draft=True,
        category="postmortems",
    ),
    "postmortem_search_index_reindex_lag_2026-08-02.docx": _make_doc(
        "postmortem_search_index_reindex_lag_2026-08-02.docx",
        "Postmortem for search-index reindex lag on 2026-08-02.",
        category="postmortems",
    ),
}


class TestSearchClearance:
    """F-01: Clearance-based document filtering."""

    def test_general_filer_cannot_see_restricted(self):
        """General-clearance filer does not get restricted docs in results."""
        results = search("auth-gateway outage", _DOCUMENTS, "general")
        # Should only find non-restricted results, or none
        for r in results:
            assert r["restricted"] is False, f"Restricted doc leaked: {r['filename']}"

    def test_general_filer_still_sees_general(self):
        """General filer still gets general-access docs."""
        results = search("payments-api rollback", _DOCUMENTS, "general")
        assert len(results) > 0
        # The filename uses underscores: runbook_rollback_payments_api.docx
        assert any("payments_api" in r["filename"] for r in results)

    def test_restricted_filer_sees_restricted(self):
        """Restricted-clearance filer can see restricted docs."""
        results = search("auth-gateway", _DOCUMENTS, "restricted")
        restricted_found = [r for r in results if r["restricted"]]
        assert len(restricted_found) > 0

    def test_restricted_filer_sees_both(self):
        """Restricted filer sees both restricted and general docs."""
        results = search("payments", _DOCUMENTS, "restricted")
        assert len(results) > 0


class TestSearchSuperseded:
    """Superseded docs should not appear."""

    def test_superseded_excluded(self):
        """DRAFT_superseded doc should not be in results."""
        results = search("auth-gateway", _DOCUMENTS, "restricted")
        filenames = [r["filename"] for r in results]
        assert "postmortem_auth_gateway_outage_DRAFT_superseded.docx" not in filenames

    def test_final_version_included(self):
        """FINAL version should be findable."""
        results = search("auth-gateway", _DOCUMENTS, "restricted")
        filenames = [r["filename"] for r in results]
        assert "postmortem_auth_gateway_outage_FINAL.docx" in filenames


class TestSearchDrafts:
    """Draft documents are included but labelled as draft."""

    def test_drafts_are_returned(self):
        """Draft postmortems should appear in results."""
        results = search("canary", _DOCUMENTS, "general")
        drafts = [r for r in results if r["is_draft"]]
        assert len(drafts) > 0

    def test_draft_label_present(self):
        results = search("payments-api canary", _DOCUMENTS, "general")
        for r in results:
            if r["is_draft"]:
                assert "DRAFT" in r["filename"]


class TestSearchEdgeCases:
    """F-09: Documents discovered by scanning store, not just CSV links."""

    def test_orphan_doc_discovered(self):
        """Orphan docs (no CSV link) are still searchable."""
        # postmortem_payments_api_canary_2026-09-04_DRAFT.docx is an orphan
        # (not linked in incident_log.csv postmortem_doc column)
        results = search("canary failure 2026-09-04", _DOCUMENTS, "general")
        filenames = [r["filename"] for r in results]
        assert "postmortem_payments_api_canary_2026-09-04_DRAFT.docx" in filenames

    def test_empty_query_returns_nothing(self):
        """Empty query should return no results."""
        results = search("", _DOCUMENTS, "general")
        assert len(results) == 0

    def test_no_documents_returns_empty(self):
        results = search("payments-api", {}, "general")
        assert len(results) == 0

    def test_top_k_respected(self):
        results = search("payments-api", _DOCUMENTS, "general", top_k=1)
        assert len(results) <= 1


class TestBestAnswer:
    """Single best answer selection."""

    def test_best_answer_found(self):
        answer = best_answer("roll back payments-api", _DOCUMENTS, "general")
        assert answer is not None
        assert "payments_api" in answer["filename"]

    def test_best_answer_none_for_restricted_doc_general_filer(self):
        answer = best_answer("auth-gateway outage restricted", _DOCUMENTS, "general")
        # May still find non-restricted results, but not the restricted one
        if answer is not None:
            assert answer["restricted"] is False

    def test_best_answer_returns_none_when_no_match(self):
        answer = best_answer("zxywv nonexisitent query", _DOCUMENTS, "general")
        assert answer is None