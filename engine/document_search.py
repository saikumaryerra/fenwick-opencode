"""Search loaded documents by keyword, respect clearance (F-01, F-09).

Documents are discovered by scanning the store (F-09), not only by CSV links.
Search respects filer clearance: restricted documents are only returned for
restricted-clearance filers. Superseded docs are skipped. Drafts are included
but labelled as draft.
"""

from __future__ import annotations

import re


def search(
    query: str,
    documents: dict[str, dict],
    filer_clearance: str,
    *,
    top_k: int = 3,
) -> list[dict]:
    """Search documents by keyword, filtered by clearance.

    Args:
        query: The ticket text or search query.
        documents: Dict of {filename: meta} from doc_loader.load_documents().
        filer_clearance: 'general' or 'restricted'.
        top_k: Max results to return.

    Returns:
        List of dicts with keys: filename, text, restricted, is_draft,
        doc_family, category, relevance_score.
        Only documents the filer is cleared to see are returned.
    """
    from auth.clearance import can_see_document

    query_lower = query.lower().strip()
    if not query_lower:
        return []

    # Break query into significant keywords (words 3+ chars, skip stopwords)
    keywords = _extract_keywords(query_lower)

    scored: list[dict] = []

    for fname, meta in documents.items():
        # Skip superseded documents
        if meta.get("is_superseded"):
            continue

        # Clearance check: skip docs the filer cannot see
        doc_restricted = meta.get("restricted", False)
        if not can_see_document(filer_clearance, doc_restricted):
            continue

        text = meta.get("text", "")
        score = _score_document(text, query_lower, keywords)
        if score > 0:
            scored.append({
                "filename": fname,
                "text": text,
                "restricted": doc_restricted,
                "is_draft": meta.get("is_draft", False),
                "doc_family": meta.get("doc_family", fname),
                "category": meta.get("category", ""),
                "relevance_score": score,
            })

    scored.sort(key=lambda d: d["relevance_score"], reverse=True)
    return scored[:top_k]


def best_answer(
    query: str,
    documents: dict[str, dict],
    filer_clearance: str,
) -> dict | None:
    """Get the single best answer from documents, or None.

    Returns the top-scoring document (already clearance-filtered).
    """
    results = search(query, documents, filer_clearance, top_k=1)
    if results:
        return results[0]
    return None


def get_current_doc_version(
    documents: dict[str, dict], family: str, filer_clearance: str
) -> dict | None:
    """Get the current version of a document family, respecting clearance.

    The current version is the one with FINAL status, or the highest
    non-superseded version. Drafts are fallback if no FINAL exists.
    """
    from auth.clearance import can_see_document
    from ingest.doc_loader import get_current_doc_version as _get_version

    # First use the existing doc_loader logic
    result = _get_version(documents, family)
    if result is None:
        return None

    # Then check clearance
    doc_restricted = result.get("restricted", False)
    if not can_see_document(filer_clearance, doc_restricted):
        return None

    return result


# ── Internal helpers ─────────────────────────────────────────────────────

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "shall", "should", "may", "might", "must", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "they", "them", "this", "that", "these", "those", "what",
    "which", "who", "whose", "whom", "about", "up", "if", "or", "and",
    "but", "because", "while", "since", "until", "if",
}


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text (3+ chars, not stopwords)."""
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def _score_document(text: str, query: str, keywords: set[str]) -> int:
    """Score a document's relevance to the query.

    Returns an integer score; higher is more relevant.
    """
    text_lower = text.lower()
    score = 0

    # Exact phrase match (highest value)
    if query in text_lower:
        score += 20

    # Keyword matches
    for kw in keywords:
        count = text_lower.count(kw)
        if count > 0:
            # Service/domain names get weighted more
            score += count * 2

    return score