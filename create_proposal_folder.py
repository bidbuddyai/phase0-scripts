#!/usr/bin/env python3
"""
create_proposal_folder.py — Home Worker (Windows) ONLY
Creates a new proposal folder in B:\\Proposals\\Active and moves all staged
files (PDFs, scope extracts, demo sheet PNGs) from the local C:\\ staging
directory directly into the new B: drive folder.

Usage:
    python create_proposal_folder.py --number 2025-047 --name "Washington Middle School Demo" --slug washington-middle-school

Output:
    JSON: {
        "created": true,
        "path": "B:\\Proposals\\Active\\2025-047--Washington Middle School Demo",
        "moved_files": [...],
        "errors": [...]
    }

NOTE: Must run on "Home Worker" node. Staging directory lives at
      C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\<slug>\\
      The staging directory is permanently deleted after a successful move.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PROPOSALS_DIR = Path(r"B:\\")
STAGING_BASE = Path(r"C:\Users\Chase\.openclaw\workspace\bids_staging")


def sanitize_name(name: str) -> str:
    """Remove characters invalid in Windows file paths."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", name).strip(". ")
    return sanitized[:100]


def run(number: str, name: str, slug: str):
    if not PROPOSALS_DIR.exists():
        print(json.dumps({"error": f"B: drive not accessible: {PROPOSALS_DIR}", "created": False}))
        sys.exit(1)

    clean_name = sanitize_name(name)
    folder_name = f"{number}--{clean_name}"
    folder_path = PROPOSALS_DIR / folder_name
    staging_dir = STAGING_BASE / slug

    # -----------------------------------------------------------------------
    # Create B: drive folder
    # -----------------------------------------------------------------------
    if folder_path.exists():
        print(json.dumps({
            "created": False,
            "exists": True,
            "path": str(folder_path),
            "message": "Folder already exists — proceeding to move files.",
        }), file=sys.stderr)
    else:
        try:
            folder_path.mkdir(parents=True, exist_ok=False)
            print(f"Created: {folder_path}", file=sys.stderr)
        except Exception as e:
            print(json.dumps({"error": str(e), "created": False}))
            sys.exit(1)

    # -----------------------------------------------------------------------
    # Move all staged content to B: drive folder
    # -----------------------------------------------------------------------
    result = {
        "created": True,
        "path": str(folder_path),
        "folder_name": folder_name,
        "moved_files": [],
        "errors": [],
    }

    if not staging_dir.exists():
        result["errors"].append(f"Staging directory not found: {staging_dir}")
        print(json.dumps(result))
        return

    # Move raw_pdfs/ directory
    raw_pdfs_src = staging_dir / "raw_pdfs"
    if raw_pdfs_src.exists():
        dest = folder_path / "raw_pdfs"
        try:
            shutil.copytree(str(raw_pdfs_src), str(dest), dirs_exist_ok=True)
            result["moved_files"].append("raw_pdfs/")
            print(f"Moved raw_pdfs/ ({sum(1 for _ in raw_pdfs_src.glob('*.pdf'))} PDFs)", file=sys.stderr)
        except Exception as e:
            result["errors"].append({"item": "raw_pdfs/", "error": str(e)})

    # Move demo_sheets/ directory (PNGs)
    demo_sheets_src = staging_dir / "demo_sheets"
    if demo_sheets_src.exists():
        dest = folder_path / "demo_sheets"
        try:
            shutil.copytree(str(demo_sheets_src), str(dest), dirs_exist_ok=True)
            png_count = sum(1 for _ in demo_sheets_src.glob("*.png"))
            result["moved_files"].append(f"demo_sheets/ ({png_count} PNGs)")
            print(f"Moved demo_sheets/ ({png_count} PNGs)", file=sys.stderr)
        except Exception as e:
            result["errors"].append({"item": "demo_sheets/", "error": str(e)})

    # Move individual JSON/text files
    for fname in ["scope_extract.json", "metadata.json", "scrape_log.json"]:
        src = staging_dir / fname
        if src.exists():
            dest = folder_path / fname
            try:
                shutil.copy2(str(src), str(dest))
                result["moved_files"].append(fname)
                print(f"Moved {fname}", file=sys.stderr)
            except Exception as e:
                result["errors"].append({"item": fname, "error": str(e)})

    # Write BID_SUMMARY.txt into B: folder
    try:
        summary_lines = [
            f"Project: {name}",
            f"Proposal Number: {number}",
            f"Folder: {folder_path}",
            f"Slug: {slug}",
            "",
        ]
        scope_path = folder_path / "scope_extract.json"
        meta_path = folder_path / "metadata.json"
        if meta_path.exists():
            import json as _json
            with open(meta_path) as f:
                meta = _json.load(f)
            summary_lines += [
                f"Portal: {meta.get('portal', 'Unknown')}",
                f"Source URL: {meta.get('url', '')}",
                f"PDFs Downloaded: {meta.get('pdf_count', 0)}",
                f"Scrape Method: {meta.get('method', 'unknown')}",
            ]
            if "bid_date_raw" in meta:
                summary_lines.append(f"Bid Date: {meta['bid_date_raw']}")
            summary_lines.append("")
        if scope_path.exists():
            with open(scope_path) as f:
                scope = _json.load(f)
            flags = scope.get("combined_flags", {})
            summary_lines.append("Scope Flags:")
            for flag, val in flags.items():
                if val:
                    summary_lines.append(f"  [X] {flag}")
        (folder_path / "BID_SUMMARY.txt").write_text("\n".join(summary_lines))
        result["moved_files"].append("BID_SUMMARY.txt (generated)")
    except Exception as e:
        result["errors"].append({"item": "BID_SUMMARY.txt", "error": str(e)})

    # -----------------------------------------------------------------------
    # Permanently delete staging directory
    # -----------------------------------------------------------------------
    try:
        shutil.rmtree(str(staging_dir))
        result["staging_cleared"] = True
        print(f"Staging directory deleted: {staging_dir}", file=sys.stderr)
    except Exception as e:
        result["staging_cleared"] = False
        result["errors"].append({"item": "staging_cleanup", "error": str(e)})

    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", required=True, help="Proposal number e.g. 2025-047")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--slug", required=True, help="Project slug matching staging directory")
    args = parser.parse_args()
    run(args.number, args.name, args.slug)


if __name__ == "__main__":
    main()
