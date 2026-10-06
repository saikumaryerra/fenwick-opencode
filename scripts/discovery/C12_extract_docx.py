#!/usr/bin/env python3
"""Step 4 — Extract every .docx, scan for tracked/hidden content, record metadata and all rules.
Standard library only: zipfile, xml.etree.ElementTree."""
import zipfile, os, re, xml.etree.ElementTree as ET

BASE = os.path.join(os.path.dirname(__file__), '../../fenwick-data-pack/documents')
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'discovery', 'output', 'C12_docx_extracts')

os.makedirs(OUT, exist_ok=True)

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
}

def extract_text_from_docx(path):
    """Return full text content from a .docx file."""
    texts = []
    try:
        with zipfile.ZipFile(path) as z:
            # Scan for tracked changes
            tracked = scan_tracked_changes(z)
            
            # Read document.xml
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)
            
            # Extract all text
            for t in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                if t.text:
                    texts.append(t.text)
            
            # Try to get document title from docProps
            title = ''
            try:
                core = z.read('docProps/core.xml')
                core_root = ET.fromstring(core)
                title_el = core_root.find('.//dc:title', NAMESPACES)
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
            except:
                pass
                
    except Exception as e:
        return f"[EXTRACTION ERROR: {e}]", {}, []
    
    full = '\n'.join(texts)
    return full, tracked, title


def scan_tracked_changes(z):
    """Look for tracked changes (revisions) in the document XML."""
    result = {'ins_count': 0, 'del_count': 0, 'has_revisions': False}
    try:
        xml_content = z.read('word/document.xml')
        # Quick string search for revision marks
        ins = xml_content.count(b'w:ins')
        dels = xml_content.count(b'w:del')
        result['ins_count'] = ins
        result['del_count'] = dels
        result['has_revisions'] = (ins > 0 or dels > 0)
        return result
    except:
        return result


def extract_metadata_quick(text):
    """Extract metadata fields: DRAFT, FINAL, version, owner, dates, etc."""
    meta = {}
    # Status markers
    if 'DRAFT' in text and 'FINAL' in text:
        meta['status'] = 'MIXED_DRAFT_FINAL'
    elif 'DRAFT' in text:
        meta['status'] = 'DRAFT'
    elif 'FINAL' in text:
        meta['status'] = 'FINAL'
    elif 'SUPERSEDED' in text:
        meta['status'] = 'SUPERSEDED'
    else:
        meta['status'] = 'UNMARKED'
    
    # Access/clearance markings
    if 'RESTRICTED' in text or 'restricted' in text:
        meta['marking_restricted'] = True
    if 'CONFIDENTIAL' in text:
        meta['marking_confidential'] = True
    if 'GENERAL' in text:
        meta['marking_general'] = True
    
    # Dates mentioned
    date_patterns = re.findall(r'\b(20\d{2})[-/]\d{2}[-/]\d{2}\b', text)
    meta['dates_iso'] = list(set(date_patterns))
    
    # Owner references
    owner_match = re.findall(r'(?:owner|author|prepared by|written by)[:\s]+([A-Za-z\s]+)', text[:2000], re.I)
    if owner_match:
        meta['owner_hint'] = owner_match[0].strip()
    
    return meta


def extract_rules(text, filename):
    """Extract concrete rules, numbers, policies stated in the document."""
    rules = []
    # Look for numbered lists, policies, procedures
    # Capture lines with actionable language
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # Numbered rules / steps
        if re.match(r'^\d+[\.\)]\s', line):
            rules.append(line[:200])
        # Lines with 'must', 'shall', 'required', 'policy', 'SLA', 'escalate'
        keywords = ['must', 'shall', 'required', 'policy', 'SLA', 'escalate', 'page', 
                    'acknowledge', 'should', 'never', 'always', 'access', 'clearance',
                    'permitted', 'authorized', 'restricted', 'general']
        lower_line = line.lower()
        for kw in keywords:
            if kw in lower_line:
                # Avoid duplicating very similar lines
                snippet = line[:200]
                if snippet not in [r[:200] for r in rules]:
                    rules.append(snippet)
                break
    
    return rules


# ---- MAIN ----
all_metadata = {}
all_rules = []

categories = {
    'policies': os.path.join(BASE, 'policies'),
    'postmortems': os.path.join(BASE, 'postmortems'),
    'runbooks': os.path.join(BASE, 'runbooks'),
}

summary_lines = []

for cat, dirpath in categories.items():
    for fn in sorted(os.listdir(dirpath)):
        if not fn.endswith('.docx'):
            continue
        fpath = os.path.join(dirpath, fn)
        print(f"\n{'='*70}")
        print(f"=== [{cat}] {fn} ===")
        print(f"{'='*70}")
        
        text, tracked, title_meta = extract_text_from_docx(fpath)
        meta = extract_metadata_quick(text)
        rules = extract_rules(text, fn)
        
        # Tracked changes
        if tracked['has_revisions']:
            print(f"  ** TRACKED CHANGES: {tracked['ins_count']} insertions, {tracked['del_count']} deletions")
        else:
            print(f"  No tracked changes detected")
        
        # Title from metadata
        print(f"  Title from docProps: {title_meta or '(none)'}")
        print(f"  Status: {meta.get('status', 'UNKNOWN')}")
        if meta.get('marking_restricted'):
            print(f"  ** MARKING: Contains RESTRICTED content")
        if meta.get('marking_general'):
            print(f"  ** MARKING: GENERAL access")
        if meta.get('owner_hint'):
            print(f"  Owner hint: {meta['owner_hint']}")
        
        print(f"\n  --- Full text extract ({len(text)} chars, {len(text.splitlines())} lines) ---")
        # Print full text with line prefix for review
        for i, line in enumerate(text.splitlines()):
            line_stripped = line.strip()
            if line_stripped:
                print(f"  {i:4d}: {line_stripped}")
        
        print(f"\n  --- Extracted rules/requirements ({len(rules)}) ---")
        for r in rules:
            print(f"    - {r}")
        
        # Save full extract
        safe_fn = fn.replace('.docx', '.txt')
        outpath = os.path.join(OUT, safe_fn)
        with open(outpath, 'w') as f:
            f.write(f"Source: {cat}/{fn}\n")
            f.write(f"Status: {meta.get('status', 'UNKNOWN')}\n")
            f.write(f"Tracked changes: {tracked['ins_count']} ins, {tracked['del_count']} del\n")
            f.write(f"Title from metadata: {title_meta or '(none)'}\n\n")
            f.write(text)
        
        record = {
            'file': fn,
            'category': cat,
            'status': meta.get('status', 'UNKNOWN'),
            'restricted': meta.get('marking_restricted', False),
            'tracked_changes': tracked['has_revisions'],
            'rules_count': len(rules),
            'char_count': len(text),
        }
        all_metadata[fn] = record
        all_rules.extend([(fn, r) for r in rules])

print(f"\n{'='*70}")
print("=== SUMMARY ===")
print(f"{'='*70}")
for fn, rec in sorted(all_metadata.items()):
    print(f"  {rec['category']}/{fn}")
    print(f"    Status: {rec['status']} | Restricted: {rec['restricted']} | Tracked: {rec['tracked_changes']} | Rules: {rec['rules_count']} | Size: {rec['char_count']} chars")
print()
print(f"Total documents: {len(all_metadata)}")
print(f"Total rules extracted: {len(all_rules)}")
print(f"Files saved to: {OUT}/")