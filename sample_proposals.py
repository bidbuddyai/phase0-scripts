#!/usr/bin/env python3
"""Samples the most recent 20 folder names from B: to determine naming convention."""
import json
from pathlib import Path

PROPOSALS_DIR = Path(r"B:\\")

folders = sorted(
    [f.name for f in PROPOSALS_DIR.iterdir() if f.is_dir()],
    reverse=True
)[:30]

print(json.dumps({"sample": folders, "total": len(list(PROPOSALS_DIR.iterdir()))}))
