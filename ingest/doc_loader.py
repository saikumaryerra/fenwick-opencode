"""Parse 14 .docx files, extract text, detect restricted flag.

Documents are discovered by scanning the store (F-09), not only by CSV links.
"""

import os
from pathlib import Path

try:
    from docx import Document
except ImportError:
    Document = None  # type: ignore


DOCUMENTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "fenwick-data-pack", "documents"
)

# Sensitivity is determined by the document's OWN body per policy_access_and_clearance.docx.
# The document's own body determines sensitivity, not keyword presence.

# Restricted classifier: a standalone line "RESTRICTED" indicates classified content.
# Policy documents in the policies/ directory are general-access by definition.
_RESTRICTED_LINE = "restricted"  # check for a line starting with or matching this

# File-level hints for restricted status (filename or path hints).
_FILE_RESTRICTED_HINTS = [
    "restricted",
    "security",
]


def extract_text(filepath: str) -> str:
    """Extract text from a .docx file.

    Returns empty string if python-docx is not installed or on error.
    """
    if Document is None:
        return ""
    try:
        doc = Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def _body_implies_restricted(text: str) -> bool:
    """Check if the document body text indicates restricted status.

    The document's own body determines sensitivity, not keyword presence.
    A document that contains the word 'restricted' in a procedural or
    policy context (e.g. 'this policy defines restricted clearance') is
    NOT itself restricted.
    
    A document that explicitly classifies itself as RESTRICTED (all-caps
    classifier marker, typically on its own line) IS restricted.
    """
    if not text or not text.strip():
        return False

    # Check for an all-caps "RESTRICTED" classifier: a line that starts with
    # "RESTRICTED" (standalone classifier marker, not procedural use).
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "RESTRICTED" or stripped.startswith("RESTRICTED —"):
            return True

    return False


def _filename_hints_restricted(filepath: str) -> bool:
    """Check filename for restricted hints."""
    fname = Path(filepath).name.lower()
    for hint in _FILE_RESTRICTED_HINTS:
        if hint in fname:
            return True
    return False


def is_restricted(filepath: str, text: str | None = None) -> bool:
    """Determine if a document is restricted-access.

    Uses body text when available; falls back to filename hints
    when text is empty (e.g. python-docx unavailable).
    """
    if text is None:
        text = extract_text(filepath)
    if text.strip():
        return _body_implies_restricted(text)
    # Fallback to filename hints if no body text.
    return _filename_hints_restricted(filepath)


def _scan_docx_files(root: str) -> list[str]:
    """Recursively find all .docx files under a directory."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".docx"):
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def load_documents() -> dict[str, dict]:
    """Load all documents from the documents directory.

    Returns a dict keyed by filename (basename), with keys:
      - path: full file path
      - text: extracted text content
      - restricted: bool, whether the document is restricted-access
      - is_draft: bool, whether filename contains _DRAFT
      - is_superseded: bool, whether filename contains superseded
      - category: subdirectory (runbooks, postmortems, policies)
      - doc_family: base name without status/draft/version markers
    """
    docs = {}
    for filepath in _scan_docx_files(DOCUMENTS_DIR):
        fname = os.path.basename(filepath)
        text = extract_text(filepath)
        rel_dir = os.path.relpath(os.path.dirname(filepath), DOCUMENTS_DIR)
        docs[fname] = {
            "path": filepath,
            "text": text,
            "restricted": is_restricted(filepath, text),
            "is_draft": "_DRAFT" in fname,
            "is_superseded": "superseded" in fname.lower(),
            "category": rel_dir,
            "doc_family": _doc_family(fname),
        }
    return docs


def _doc_family(filename: str) -> str:
    """Extract the document family name by stripping status/draft markers."""
    name = filename.replace(".docx", "")
    for suffix in ["_DRAFT_superseded", "_DRAFT", "_FINAL"]:
        name = name.replace(suffix, "")
    return name


def find_documents_by_family(
    docs: dict[str, dict], family: str
) -> list[tuple[str, dict]]:
    """Find all documents in a family, sorted by version (FINAL > DRAFT)."""
    matches = []
    for fname, meta in docs.items():
        if meta["doc_family"] == family:
            matches.append((fname, meta))

    def _sort_key(item):
        fname = item[0]
        if "FINAL" in fname:
            return 0
        if "DRAFT" in fname:
            return 1
        return 2

    return sorted(matches, key=_sort_key)


def get_current_doc_version(docs: dict[str, dict], family: str) -> dict | None:
    """Get the current version of a document family.

    The current version is the one with FINAL status, or the highest
    non-superseded version. Skips superseded documents.
    """
    candidates = []
    for fname, meta in docs.items():
        if meta["doc_family"] != family:
            continue
        if meta["is_superseded"]:
            continue
        candidates.append((fname, meta))

    if not candidates:
        return None

    # Prefer FINAL, then DRAFT, then others
    def _key(item):
        fname = item[0]
        if "FINAL" in fname:
            return 0
        if "DRAFT" in fname:
            return 1
        return 2

    candidates.sort(key=_key)
    return candidates[0][1]