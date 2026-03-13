#!/usr/bin/env python3
"""
extract_scope.py — Home Worker (Windows) ONLY
Two-pass PyMuPDF extraction optimized for demolition/hazmat bid scope analysis.

Pass 1 (Front End Grab):
    Extract pages 1-50 of every project manual PDF.
    Captures bid dates, job walk dates, prime/sub requirements.

Pass 2 (Scope Hunt):
    Scan Table of Contents of remaining pages, then extract text ONLY from
    pages containing Division 02, Hazardous Materials, Asbestos, Demolition,
    or Scope of Work keywords.

Usage:
    python extract_scope.py --slug <project-slug>

Output:
    Prints JSON summary to stdout.
    Writes C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\<slug>\\scope_extract.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

STAGING_BASE = Path(r"C:\Users\Chase\.openclaw\workspace\bids_staging")

# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

FRONT_KEYWORDS = [
    r"bid\s+(due|date|opening|deadline)",
    r"closing\s+date",
    r"pre[\s-]?bid\s+(meeting|conference)",
    r"mandatory\s+job\s+walk",
    r"job\s+walk",
    r"site\s+visit",
    r"prevailing\s+wage",
    r"performance\s+bond",
    r"payment\s+bond",
    r"bid\s+bond",
    r"bonding\s+requirement",
    r"prime\s+contractor",
    r"subcontractor",
    r"sub[\s-]?contractor",
    r"license\s+(number|required|class)",
    r"contractor.s\s+license",
    r"engineer.s\s+estimate",
    r"estimated\s+(value|cost|amount)",
    r"liquidated\s+damages",
    r"contract\s+time",
    r"completion\s+date",
    r"franchise\s+hauler",
]

SCOPE_KEYWORDS = [
    r"division\s+0*2\b",
    r"hazardous\s+material",
    r"asbestos",
    r"lead\s+(paint|abatement|based)",
    r"demolition",
    r"scope\s+of\s+work",
    r"abatement",
    r"mold\s+remediation",
    r"environmental\s+remediation",
    r"selective\s+demo",
    r"structural\s+demo",
]

TOC_TRIGGER_KEYWORDS = [
    "division 02", "division2", "hazardous", "asbestos", "demolition",
    "scope of work", "abatement", "scope", "div 02",
]

FRONT_PATTERN = re.compile("|".join(FRONT_KEYWORDS), re.IGNORECASE)
SCOPE_PATTERN = re.compile("|".join(SCOPE_KEYWORDS), re.IGNORECASE)

FRONT_END_PAGES = 50          # Pages to always capture from the front
MAX_CHARS_PER_PDF = 10000     # Token budget per PDF
MAX_CHARS_TOTAL = 50000       # Total extraction budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_toc_page(page_text: str) -> bool:
    lower = page_text.lower()
    dot_leader = re.search(r"\.{3,}\s*\d+", page_text)
    toc_headers = ["table of contents", "contents", "index"]
    return any(h in lower for h in toc_headers) or bool(dot_leader)


def extract_toc_entries(text: str) -> list[str]:
    relevant = []
    for line in text.splitlines():
        lower = line.lower()
        if any(kw in lower for kw in TOC_TRIGGER_KEYWORDS):
            stripped = line.strip()
            if stripped:
                relevant.append(stripped)
    return relevant


def flag_text(text: str) -> dict:
    lower = text.lower()
    return {
        "has_asbestos": bool(re.search(r"asbestos", lower)),
        "has_division_02": bool(re.search(r"division\s*0*2\b", lower)),
        "has_prevailing_wage": bool(re.search(r"prevailing\s+wage", lower)),
        "has_bid_bond": bool(re.search(r"bid\s+bond", lower)),
        "has_performance_bond": bool(re.search(r"performance\s+bond", lower)),
        "has_franchise_hauler": bool(re.search(r"franchise\s+hauler", lower)),
        "has_demolition_scope": bool(re.search(r"demolition|abatement", lower)),
        "has_hazmat": bool(re.search(r"hazardous|hazmat|lead\s+paint|lead[\s-]based", lower)),
        "has_mandatory_job_walk": bool(re.search(r"mandatory\s+job\s+walk|mandatory.*site\s+visit", lower)),
        "has_bonding_requirement": bool(re.search(r"bond(?:ing)?\s+requirement", lower)),
    }


def merge_flags(a: dict, b: dict) -> dict:
    return {k: (a.get(k, False) or b.get(k, False)) for k in set(a) | set(b)}


# ---------------------------------------------------------------------------
# Per-PDF extraction
# ---------------------------------------------------------------------------

def scan_pdf(pdf_path: Path) -> dict:
    result = {
        "file": pdf_path.name,
        "total_pages": 0,
        "front_pages_extracted": [],
        "scope_pages_extracted": [],
        "toc_entries": [],
        "front_text": "",
        "scope_text": "",
        "flags": {},
    }

    try:
        doc = fitz.open(str(pdf_path))
        result["total_pages"] = len(doc)
        total_pages = len(doc)

        front_texts = []
        scope_texts = []
        combined_flags: dict = {}
        char_budget = MAX_CHARS_PER_PDF

        # ----------------------------------------------------------------
        # Pass 1 — Front End Grab: pages 1 to min(50, total)
        # ----------------------------------------------------------------
        front_limit = min(FRONT_END_PAGES, total_pages)
        for page_num in range(front_limit):
            page = doc[page_num]
            text = page.get_text()
            if not text.strip():
                continue
            # Always capture if it contains front-of-spec keywords
            if FRONT_PATTERN.search(text) or page_num < 10:
                snippet = text[:char_budget]
                char_budget -= len(snippet)
                if snippet:
                    front_texts.append(f"[Page {page_num+1}]\n{snippet}")
                    result["front_pages_extracted"].append(page_num + 1)
                    page_flags = flag_text(text)
                    combined_flags = merge_flags(combined_flags, page_flags)
            if char_budget <= 0:
                break

        # ----------------------------------------------------------------
        # Pass 2 — Scope Hunt: pages beyond first 50
        # ----------------------------------------------------------------
        if total_pages > FRONT_END_PAGES and char_budget > 0:
            # First collect TOC entries from pages 51+
            for page_num in range(front_limit, total_pages):
                page = doc[page_num]
                text = page.get_text()
                if not text.strip():
                    continue
                if is_toc_page(text):
                    result["toc_entries"].extend(extract_toc_entries(text))

            # Then extract keyword-matching pages
            for page_num in range(front_limit, total_pages):
                if char_budget <= 0:
                    break
                page = doc[page_num]
                text = page.get_text()
                if not text.strip():
                    continue
                if SCOPE_PATTERN.search(text):
                    snippet = text[:char_budget]
                    char_budget -= len(snippet)
                    if snippet:
                        scope_texts.append(f"[Page {page_num+1}]\n{snippet}")
                        result["scope_pages_extracted"].append(page_num + 1)
                        page_flags = flag_text(text)
                        combined_flags = merge_flags(combined_flags, page_flags)

        doc.close()
        result["front_text"] = "\n\n".join(front_texts)
        result["scope_text"] = "\n\n".join(scope_texts)
        result["flags"] = combined_flags

    except Exception as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run(slug: str) -> dict:
    staging_dir = STAGING_BASE / slug
    pdf_dir = staging_dir / "raw_pdfs"

    if not pdf_dir.exists():
        print(f"ERROR: No raw_pdfs directory at {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: No PDFs found in {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {len(pdfs)} PDFs (front-50-page grab + scope keyword hunt)...", file=sys.stderr)

    output = {
        "slug": slug,
        "pdf_count": len(pdfs),
        "scans": [],
        "combined_flags": {},
        "combined_text": "",
        "toc_entries": [],
        "total_chars_extracted": 0,
    }

    all_texts = []
    total_chars = 0
    combined_flags: dict = {}

    for pdf_path in pdfs:
        print(f"  Scanning: {pdf_path.name}", file=sys.stderr)
        scan = scan_pdf(pdf_path)
        output["scans"].append({
            "file": scan["file"],
            "total_pages": scan["total_pages"],
            "front_pages_extracted": scan["front_pages_extracted"],
            "scope_pages_extracted": scan["scope_pages_extracted"],
            "flags": scan["flags"],
            "toc_entries": scan["toc_entries"],
        })

        combined_flags = merge_flags(combined_flags, scan.get("flags", {}))
        output["toc_entries"].extend(scan["toc_entries"])

        full_text = ""
        if scan["front_text"]:
            full_text += f"--- FRONT (pp.1-{FRONT_END_PAGES}) ---\n{scan['front_text']}"
        if scan["scope_text"]:
            full_text += f"\n\n--- SCOPE SECTIONS ---\n{scan['scope_text']}"

        if full_text and total_chars < MAX_CHARS_TOTAL:
            chunk = full_text[:MAX_CHARS_TOTAL - total_chars]
            all_texts.append(f"=== {scan['file']} ===\n{chunk}")
            total_chars += len(chunk)

    output["combined_flags"] = combined_flags
    output["combined_text"] = "\n\n".join(all_texts)
    output["total_chars_extracted"] = total_chars

    # Write to staging
    out_path = staging_dir / "scope_extract.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Scope extract written to {out_path}", file=sys.stderr)

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    result = run(args.slug)
    summary = {
        "slug": result["slug"],
        "pdf_count": result["pdf_count"],
        "combined_flags": result["combined_flags"],
        "toc_entries": result["toc_entries"][:20],
        "relevant_front_pages": sum(len(s.get("front_pages_extracted", [])) for s in result["scans"]),
        "relevant_scope_pages": sum(len(s.get("scope_pages_extracted", [])) for s in result["scans"]),
        "total_chars_extracted": result["total_chars_extracted"],
        "output_file": str(STAGING_BASE / args.slug / "scope_extract.json"),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
