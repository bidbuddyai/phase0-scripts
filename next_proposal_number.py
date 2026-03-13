#!/usr/bin/env python3
"""
next_proposal_number.py — Home Worker (Windows) ONLY
Scans B:\\ to determine the highest existing proposal number
and returns the next consecutive integer.

Folder naming convention: plain sequential integer at the start of the name.
Examples: "8337 City of LA Demo", "8336--LAUSD Abatement"

Usage:
    python next_proposal_number.py

Output:
    JSON: {"next_number": "8338", "last_number": "8337", "scanned": 5182}

NOTE: Must run on "Home Worker" node. B: drive is not accessible from the VPS.
"""

import json
import re
import sys
from pathlib import Path

PROPOSALS_DIR = Path(r"B:\\")


def parse_proposal_number(folder_name: str):
    """
    Extract leading integer from folder name.
    Handles: "8337 Project Name", "8337--Project Name", "8337_Project"
    Returns int or None.
    """
    m = re.match(r"^(\d+)[\s\-_]", folder_name)
    if m:
        return int(m.group(1))
    # Folder name is purely a number
    m = re.match(r"^(\d+)$", folder_name)
    if m:
        return int(m.group(1))
    return None


def run():
    if not PROPOSALS_DIR.exists():
        print(json.dumps({
            "error": f"Directory not found: {PROPOSALS_DIR}",
            "next_number": None,
        }))
        sys.exit(1)

    folders = [f for f in PROPOSALS_DIR.iterdir() if f.is_dir()]

    numbers = []
    for folder in folders:
        n = parse_proposal_number(folder.name)
        if n is not None:
            numbers.append((n, folder.name))

    if not numbers:
        print(json.dumps({
            "next_number": "1",
            "last_number": None,
            "scanned": len(folders),
        }))
        return

    numbers.sort(key=lambda x: x[0])
    last_num, last_folder = numbers[-1]

    print(json.dumps({
        "next_number": str(last_num + 1),
        "last_number": str(last_num),
        "last_folder": last_folder,
        "scanned": len(folders),
    }))


if __name__ == "__main__":
    run()
