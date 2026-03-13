#!/usr/bin/env python3
"""
wipe_staging.py — Home Worker (Windows) ONLY
Permanently deletes a project staging directory from C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\.
Scope-locked: will only delete paths that are direct children of STAGING_BASE.
Never touches B: drive.

Usage:
    python wipe_staging.py --slug <project-slug>

Output:
    JSON: {"deleted": true, "path": "C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\<slug>"}
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

STAGING_BASE = Path(r"C:\Users\Chase\.openclaw\workspace\bids_staging")


def run(slug: str):
    # Validate slug is a simple name, not a path traversal attempt
    if any(c in slug for c in r"/\:*?\"<>|"):
        print(json.dumps({"error": f"Invalid slug: {slug}", "deleted": False}))
        sys.exit(1)

    staging_dir = STAGING_BASE / slug

    # Strict scope check: must be a direct child of STAGING_BASE, never B:
    try:
        staging_dir.resolve().relative_to(STAGING_BASE.resolve())
    except ValueError:
        print(json.dumps({"error": f"Path escape detected: {staging_dir}", "deleted": False}))
        sys.exit(1)

    if not staging_dir.exists():
        print(json.dumps({
            "deleted": False,
            "already_gone": True,
            "path": str(staging_dir),
            "message": "Staging directory does not exist — nothing to delete.",
        }))
        return

    try:
        shutil.rmtree(str(staging_dir))
        print(json.dumps({
            "deleted": True,
            "path": str(staging_dir),
        }))
    except Exception as e:
        print(json.dumps({"error": str(e), "deleted": False}))
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="Project slug (direct child of bids_staging)")
    args = parser.parse_args()
    run(args.slug)


if __name__ == "__main__":
    main()
