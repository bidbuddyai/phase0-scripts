#!/usr/bin/env python3
"""Read staging output files for a given slug. Fast, no external deps."""
import argparse
import json
import sys
from pathlib import Path

STAGING_BASE = Path(r"C:\Users\Chase\.openclaw\workspace\bids_staging")

parser = argparse.ArgumentParser()
parser.add_argument("--slug", required=True)
args = parser.parse_args()

staging = STAGING_BASE / args.slug

result = {"slug": args.slug, "staging_exists": staging.exists()}

if staging.exists():
    scrape_log = staging / "scrape_log.json"
    metadata = staging / "metadata.json"
    raw_pdfs = staging / "raw_pdfs"

    if scrape_log.exists():
        result["scrape_log"] = json.loads(scrape_log.read_text())
    if metadata.exists():
        result["metadata"] = json.loads(metadata.read_text())
    if raw_pdfs.exists():
        pdfs = list(raw_pdfs.glob("*.pdf"))
        result["pdf_files"] = [p.name for p in pdfs]
        result["pdf_count"] = len(pdfs)

    # Check bid-portals.env credentials
    creds_file = Path.home() / ".openclaw" / "secrets" / "bid-portals.env"
    result["creds_file_exists"] = creds_file.exists()
    if creds_file.exists():
        keys = [l.split("=")[0] for l in creds_file.read_text().splitlines()
                if "=" in l and not l.startswith("#")]
        result["cred_keys"] = keys

print(json.dumps(result, indent=2))
