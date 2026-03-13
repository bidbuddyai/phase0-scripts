"""Diagnostic: check scrape_portal.py stealth import status and Python env on Home Worker."""
import sys
import subprocess
from pathlib import Path

print(f"Python: {sys.version}")
print(f"Python exe: {sys.executable}")

# Check playwright-stealth installed version
try:
    import importlib.metadata
    version = importlib.metadata.version("playwright-stealth")
    print(f"playwright-stealth version: {version}")
except Exception as e:
    print(f"playwright-stealth not found: {e}")

# Check what stealth exports
try:
    import playwright_stealth
    exports = dir(playwright_stealth)
    stealth_exports = [x for x in exports if "stealth" in x.lower()]
    print(f"playwright_stealth exports: {stealth_exports}")
except Exception as e:
    print(f"Cannot import playwright_stealth: {e}")

# Check what the current scrape_portal.py has around stealth
script_path = Path(r"C:\Users\Chase\.openclaw\workspace\skills\phase0-bid-copilot\scripts\scrape_portal.py")
if script_path.exists():
    text = script_path.read_text(encoding="utf-8")
    idx = text.find("stealth")
    if idx >= 0:
        print(f"\nscrape_portal.py stealth context (char {idx}):")
        print(text[max(0, idx-10):idx+300])
    else:
        print("No 'stealth' found in scrape_portal.py")
    # Check if already patched
    if "_apply_stealth" in text:
        print("\nStatus: ALREADY PATCHED")
    elif "stealth_async" in text:
        print("\nStatus: NEEDS PATCH (old stealth_async import present)")
else:
    print(f"scrape_portal.py not found at {script_path}")

# Check playwright install
try:
    import importlib.metadata
    pw_version = importlib.metadata.version("playwright")
    print(f"\nplaywright version: {pw_version}")
except Exception as e:
    print(f"playwright not found: {e}")

# Check bid-portals.env exists
from pathlib import Path as P
creds = P.home() / ".openclaw" / "secrets" / "bid-portals.env"
print(f"\nbid-portals.env exists: {creds.exists()} ({creds})")
if creds.exists():
    lines = creds.read_text().splitlines()
    keys = [l.split("=")[0] for l in lines if "=" in l and not l.startswith("#")]
    print(f"Credential keys present: {keys}")
