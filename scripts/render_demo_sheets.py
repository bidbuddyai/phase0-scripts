#!/usr/bin/env python3
"""
render_demo_sheets.py — Home Worker (Windows) ONLY
Scans architectural drawing PDFs for demolition/demo plan sheets.
Identifies pages indexed as "Demo", "Demolition", or "AD" in their title blocks.
Renders matching pages as high-resolution PNGs into the active staging folder.

Usage:
    python render_demo_sheets.py --slug <project-slug>

Output:
    C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\<slug>\\demo_sheets\\*.png
    Prints JSON summary to stdout.
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
# Sheet index patterns — title blocks that indicate demo/demolition drawings
# ---------------------------------------------------------------------------

DEMO_SHEET_PATTERNS = [
    r"\bD\s*-?\s*\d+\b",           # D-1, D-2, D01, D 01
    r"\bAD\s*-?\s*\d+\b",          # AD-1, AD-01 (Architectural Demo)
    r"\bDEM\s*-?\s*\d+\b",         # DEM-01
    r"\bC\s*-?\s*\d+\b",           # C-1 Civil grading (often contains demo)
    r"\bDEMO\b",
    r"\bDEMOLITION\b",
    r"\bDEMOLITION\s+PLAN\b",
    r"\bSELECTIVE\s+(DEMO|DEMOLITION)\b",
    r"\bHAZMAT\b",
    r"\bABATEMENT\s+PLAN\b",
    r"\bSITE\s+DEMO\b",
    r"\bSITE\s+DEMOLITION\b",
    r"\bPARTIAL\s+DEMO\b",
]

DEMO_PATTERN = re.compile("|".join(DEMO_SHEET_PATTERNS), re.IGNORECASE)

RENDER_DPI = 200  # High resolution for field-legible drawings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_demo_sheet(page, page_num: int) -> tuple[bool, str]:
    """
    Returns (True, reason) if this page looks like a demo/demolition drawing.
    Checks both explicit sheet index patterns and sparse-text heuristic.
    """
    text = page.get_text()

    # Explicit pattern match anywhere on the page (title block)
    match = DEMO_PATTERN.search(text)
    if match:
        return True, f"Sheet index match: '{match.group()}'"

    # Heuristic: sparse text with demo-related words = likely a drawing page
    words = text.split()
    if 5 < len(words) < 500:
        lower = text.lower()
        demo_kw = ["demo", "demolition", "abatement", "hazmat", "remove", "removal",
                   "selective", "strip", "strip-out"]
        if any(kw in lower for kw in demo_kw):
            return True, "Sparse text with demolition keywords (probable drawing page)"

    return False, ""


def render_page_as_png(page, output_path: Path, dpi: int = RENDER_DPI) -> Path:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(str(output_path))
    return output_path


def extract_sf_from_page(page) -> str:
    text = page.get_text()
    sf_patterns = [
        r"([\d,]+)\s*(?:s\.?f\.?|sq\.?\s*ft\.?|square\s+feet)",
        r"([\d,]+)\s*gsf",
        r"([\d,]+)\s*(?:SF|GFA|gross\s+floor)",
    ]
    findings = []
    for pattern in sf_patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            num = match.replace(",", "")
            if num.isdigit() and int(num) > 100:
                findings.append(f"{int(num):,} SF")
    return " | ".join(set(findings[:5])) if findings else "Unable to determine"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run(slug: str) -> dict:
    staging_dir = STAGING_BASE / slug
    pdf_dir = staging_dir / "raw_pdfs"
    demo_dir = staging_dir / "demo_sheets"
    demo_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_dir.exists():
        print(f"ERROR: No raw_pdfs at {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    output = {
        "slug": slug,
        "demo_sheets_found": 0,
        "sf_findings": [],
        "rendered_pngs": [],
        "skipped_pdfs": [],
        "demo_dir": str(demo_dir),
    }

    sheet_index = 0
    MAX_SHEETS = 25  # Safety cap

    for pdf_path in pdfs:
        if sheet_index >= MAX_SHEETS:
            break
        print(f"Scanning: {pdf_path.name}", file=sys.stderr)
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            output["skipped_pdfs"].append({"file": pdf_path.name, "error": str(e)})
            continue

        for page_num in range(len(doc)):
            if sheet_index >= MAX_SHEETS:
                break
            page = doc[page_num]
            is_demo, reason = is_demo_sheet(page, page_num)

            if is_demo:
                sheet_index += 1
                png_name = f"demo_{sheet_index:03d}_p{page_num+1}_{pdf_path.stem}.png"
                png_path = demo_dir / png_name

                print(f"  Demo sheet: {pdf_path.name} p{page_num+1} — {reason}", file=sys.stderr)
                render_page_as_png(page, png_path)

                sf = extract_sf_from_page(page)
                output["rendered_pngs"].append({
                    "file": png_name,
                    "source_pdf": pdf_path.name,
                    "page": page_num + 1,
                    "reason": reason,
                    "sf_text": sf,
                })
                if sf != "Unable to determine":
                    output["sf_findings"].append(f"{pdf_path.name} p{page_num+1}: {sf}")

                output["demo_sheets_found"] += 1

        doc.close()

    print(f"\nRendered {output['demo_sheets_found']} demo sheet PNGs to {demo_dir}", file=sys.stderr)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    result = run(args.slug)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
