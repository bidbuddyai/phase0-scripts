#!/usr/bin/env python3
"""
scrape_portal.py — Home Worker (Windows) ONLY
Downloads all project PDFs from a bid portal page into a local staging directory.

Primary:  Headless Chromium via Playwright + playwright-stealth.
Fallback: Chrome DevTools MCP / live Microsoft Edge on localhost:9222 if
          Playwright hits a bot-block, timeout, or auth failure.

Usage:
    python scrape_portal.py --url <portal_url> --slug <project-slug>
    python scrape_portal.py --url <portal_url> --slug <project-slug> --force-cdp

Output:
    C:\\Users\\Chase\\.openclaw\\workspace\\bids_staging\\<slug>\\
        raw_pdfs\\       — all downloaded PDFs
        metadata.json   — extracted project metadata
        scrape_log.json — method used + any errors
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path, PureWindowsPath
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Self-heal: pull latest scripts from GitHub on startup
# ---------------------------------------------------------------------------
def _self_update():
    import subprocess
    scripts_dir = Path(__file__).parent
    git_dir = scripts_dir / ".git"

    # Load PAT from secrets file
    token = None
    try:
        secrets_file = Path.home() / ".openclaw" / "secrets" / "integrations.env"
        if secrets_file.exists():
            for line in secrets_file.read_text().splitlines():
                if line.startswith("GITHUB_PAT="):
                    token = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

    if not token:
        print("[UPDATE] No GITHUB_PAT in secrets file -- skipping auto-update.", file=sys.stderr)
        return

    repo_url = f"https://bidbuddyai:{token}@github.com/bidbuddyai/phase0-scripts.git"

    try:
        if not git_dir.exists():
            print("[UPDATE] Bootstrapping git remote...", file=sys.stderr)
            subprocess.run(["git", "-C", str(scripts_dir), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(scripts_dir), "remote", "add", "origin", repo_url], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(scripts_dir), "fetch", "origin"], check=True, capture_output=True, timeout=30)
            subprocess.run(["git", "-C", str(scripts_dir), "reset", "--hard", "origin/main"], check=True, capture_output=True)
            print("[UPDATE] Bootstrap complete. Re-launching...", file=sys.stderr)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            subprocess.run(["git", "-C", str(scripts_dir), "remote", "set-url", "origin", repo_url], capture_output=True)
            result = subprocess.run(
                ["git", "-C", str(scripts_dir), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and "Already up to date" not in result.stdout:
                print(f"[UPDATE] Scripts updated: {result.stdout.strip()}", file=sys.stderr)
                os.execv(sys.executable, [sys.executable] + sys.argv)
            elif result.returncode != 0:
                print(f"[UPDATE] Pull failed: {result.stderr.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"[UPDATE] Git sync skipped: {e}", file=sys.stderr)

_self_update()

STAGING_BASE = Path(r"C:\Users\Chase\.openclaw\workspace\bids_staging")
CREDS_FILE = Path.home() / ".openclaw" / "secrets" / "bid-portals.env"
EDGE_CDP_URL = "http://localhost:9222"

load_dotenv(CREDS_FILE)


# ---------------------------------------------------------------------------
# Portal detection
# ---------------------------------------------------------------------------

def detect_portal(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "onlineplanservice" in host:
        return "agc"
    if "napc.pro" in host:
        return "napc"
    if "planetbids" in host or "vendorline" in host:
        return "planetbids"
    if "envirobidnet" in host:
        return "envirobidnet"
    if "bidnetdirect" in host or "bidnet.com" in host:
        return "bidnet"
    if "constructconnect" in host:
        return "constructconnect"
    if "buildingconnected" in host:
        return "buildingconnected"
    if "sam.gov" in host:
        return "samgov"
    return "generic"


# ---------------------------------------------------------------------------
# Login handlers (Playwright)
# ---------------------------------------------------------------------------

async def login_agc(page):
    await page.goto("https://www.onlineplanservice.com/login")
    await page.fill('input[name="email"], input[type="email"]', os.environ["AGC_USERNAME"])
    await page.fill('input[name="password"], input[type="password"]', os.environ["AGC_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


async def login_napc(page):
    await page.goto("https://www.napc.pro/login")
    await page.fill('input[name="email"], input[type="email"]', os.environ["NAPC_USERNAME"])
    await page.fill('input[name="password"], input[type="password"]', os.environ["NAPC_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


async def login_planetbids(page):
    await page.goto(os.environ["PLANETBIDS_VENDORLINE_URL"])
    await page.fill(
        'input[name="email"], input[type="email"], input[name="username"]',
        os.environ["PLANETBIDS_VENDORLINE_USERNAME"],
    )
    await page.fill('input[name="password"], input[type="password"]',
                    os.environ["PLANETBIDS_VENDORLINE_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"], input[value="Login"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


async def login_envirobidnet(page):
    await page.goto("https://www.envirobidnet.com/login")
    await page.fill('input[name="username"], input[name="email"]', os.environ["ENVIROBIDNET_USERNAME"])
    await page.fill('input[name="password"]', os.environ["ENVIROBIDNET_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


async def login_bidnet(page):
    await page.goto("https://www.bidnetdirect.com/login")
    await page.fill('input[name="email"], input[type="email"]', os.environ["BIDNET_USERNAME"])
    await page.fill('input[name="password"]', os.environ["BIDNET_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


async def login_constructconnect(page):
    await page.goto("https://app.constructconnect.com/login")
    await page.fill('input[name="email"], input[type="email"]', os.environ["CONSTRUCTCONNECT_USERNAME"])
    await page.fill('input[name="password"], input[type="password"]', os.environ["CONSTRUCTCONNECT_PASSWORD"])
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=15000)


LOGIN_HANDLERS = {
    "agc": login_agc,
    "napc": login_napc,
    "planetbids": login_planetbids,
    "envirobidnet": login_envirobidnet,
    "bidnet": login_bidnet,
    "constructconnect": login_constructconnect,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def collect_pdf_links_from_hrefs(links: list[str], base_url: str) -> list[str]:
    pdf_links = []
    for link in links:
        if link and (
            link.lower().endswith(".pdf")
            or "download" in link.lower()
            or "document" in link.lower()
            or "attachment" in link.lower()
            or "file" in link.lower()
        ):
            absolute = urljoin(base_url, link)
            if absolute not in pdf_links:
                pdf_links.append(absolute)
    return pdf_links


async def extract_metadata_from_page(page) -> dict:
    metadata = {}
    try:
        title = await page.title()
        metadata["page_title"] = title
        body_text = await page.inner_text("body")
        lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
        for line in lines:
            if re.search(r"bid\s+due|bid\s+date|closing\s+date", line, re.I):
                metadata["bid_date_raw"] = line[:200]
                break
        for line in lines:
            if re.search(r"agency|owner|entity|department|district", line, re.I):
                metadata["agency_raw"] = line[:200]
                break
        for line in lines:
            if re.search(r"engineer.s\s+estimate|estimated\s+value|\$[\d,]+", line, re.I):
                metadata["estimate_raw"] = line[:200]
                break
        for line in lines:
            if re.search(r"prevailing\s+wage", line, re.I):
                metadata["prevailing_wage"] = True
                break
        for line in lines:
            if re.search(r"bid\s+bond", line, re.I):
                metadata["bid_bond_raw"] = line[:200]
                break
    except Exception as e:
        metadata["extraction_error"] = str(e)
    return metadata


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-_\.]', '_', name)[:120]


# ---------------------------------------------------------------------------
# PRIMARY: Playwright + stealth
# ---------------------------------------------------------------------------

async def download_pdf_playwright(context, url: str, dest_dir: Path, index: int) -> str | None:
    try:
        page = await context.new_page()
        response = await page.goto(url, timeout=30000)
        if response and response.ok:
            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                body = await response.body()
                url_path = urlparse(url).path
                filename = sanitize_filename(Path(url_path).name) if url_path.lower().endswith(".pdf") \
                    else f"doc_{index:03d}.pdf"
                if not filename.lower().endswith(".pdf"):
                    filename = f"doc_{index:03d}.pdf"
                dest = dest_dir / filename
                dest.write_bytes(body)
                await page.close()
                return str(dest)
        await page.close()
    except Exception as e:
        print(f"  [PW WARN] Failed to download {url}: {e}", file=sys.stderr)
    return None


async def run_playwright(url: str, slug: str, portal: str, staging_dir: Path) -> dict:
    """
    Attempt scrape with Playwright + playwright-stealth.
    Raises on bot-block / auth failure so caller can pivot to CDP fallback.
    """
    from playwright.async_api import async_playwright

    # playwright_stealth API varies by version:
    #   >= 1.0.6  exports stealth_async (async)
    #   older     exports stealth (sync wrapper, also accepts async page)
    #   missing   skip stealth silently
    _apply_stealth = None
    # Try stealth_async (playwright-stealth >= 1.0.6)
    try:
        from playwright_stealth import stealth_async as _sa
        async def _apply_stealth(page):
            await _sa(page)
    except (ImportError, Exception):
        pass
    # Try stealth callable (some versions export it directly)
    if _apply_stealth is None:
        try:
            from playwright_stealth import stealth as _sf
            if callable(_sf):
                async def _apply_stealth(page):
                    _sf(page)
        except (ImportError, Exception):
            pass
    # Try Stealth class (newer API)
    if _apply_stealth is None:
        try:
            from playwright_stealth import Stealth
            _stealth_obj = Stealth()
            async def _apply_stealth(page):
                await _stealth_obj.apply_stealth_async(page)
        except (ImportError, Exception):
            pass
    # No stealth available -- proceed without it
    if _apply_stealth is None:
        async def _apply_stealth(page):
            pass

    pdf_dir = staging_dir / "raw_pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            accept_downloads=True,
        )
        page = await context.new_page()
        await _apply_stealth(page)

        if portal in LOGIN_HANDLERS:
            print(f"[PW] Logging in to {portal}...", file=sys.stderr)
            await LOGIN_HANDLERS[portal](page)
            print("[PW] Login OK", file=sys.stderr)

        print(f"[PW] Navigating to: {url}", file=sys.stderr)
        try:
            await page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"[PW] Navigation issue: {e} — checking for bot block...", file=sys.stderr)
            await page.wait_for_load_state("domcontentloaded")

        # Bot-block / Cloudflare detection
        page_text = await page.inner_text("body")
        bot_phrases = [
            "access denied", "403 forbidden", "cloudflare", "captcha",
            "verify you are human", "ddos-guard", "just a moment",
            "enable javascript and cookies", "challenge",
        ]
        if any(phrase in page_text.lower() for phrase in bot_phrases):
            await browser.close()
            raise RuntimeError(f"Bot block detected on {portal}: {page_text[:200]}")

        metadata = await extract_metadata_from_page(page)
        metadata.update({"url": url, "portal": portal, "slug": slug, "method": "playwright"})

        hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        pdf_links = collect_pdf_links_from_hrefs(hrefs, url)
        print(f"[PW] Found {len(pdf_links)} document links", file=sys.stderr)

        downloaded = []
        for i, pdf_url in enumerate(pdf_links[:30]):
            print(f"  [PW] Downloading [{i+1}/{min(len(pdf_links),30)}]: {pdf_url[:80]}", file=sys.stderr)
            local_path = await download_pdf_playwright(context, pdf_url, pdf_dir, i)
            if local_path:
                downloaded.append(local_path)

        metadata["downloaded_pdfs"] = downloaded
        metadata["pdf_count"] = len(downloaded)
        await browser.close()

    return metadata


# ---------------------------------------------------------------------------
# FALLBACK: Chrome DevTools Protocol via requests (connect to live Edge)
# ---------------------------------------------------------------------------

def run_cdp_fallback(url: str, slug: str, portal: str, staging_dir: Path) -> dict:
    """
    Connect to live Microsoft Edge on localhost:9222 using its existing session
    cookies. Navigate to the portal page and download PDFs via CDP.
    Edge uses the identical Chromium debugging protocol as Chrome.
    """
    import requests
    import time

    pdf_dir = staging_dir / "raw_pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    print(f"[CDP] Connecting to Edge on {EDGE_CDP_URL}...", file=sys.stderr)

    # Get available targets
    try:
        targets_resp = requests.get(f"{EDGE_CDP_URL}/json", timeout=10)
        targets = targets_resp.json()
    except Exception as e:
        raise RuntimeError(f"Cannot reach Edge on {EDGE_CDP_URL}: {e}")

    if not targets:
        raise RuntimeError("No open tabs found in Edge. Open the portal in Edge first.")

    # Prefer an existing tab already on the portal domain; otherwise use first page target
    portal_host = urlparse(url).hostname or ""
    page_targets = [t for t in targets if t.get("type") == "page"]
    matching = [t for t in page_targets if portal_host in t.get("url", "")]
    target = matching[0] if matching else (page_targets[0] if page_targets else None)

    if target is None:
        raise RuntimeError("No usable Edge page target found.")

    ws_url = target.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError(f"Target has no webSocketDebuggerUrl: {target}")

    import websocket  # websocket-client

    results = {"url": url, "portal": portal, "slug": slug, "method": "cdp_edge"}
    downloaded = []

    ws = websocket.create_connection(ws_url, timeout=30)
    call_id = 1

    def cdp_send(method, params=None):
        nonlocal call_id
        msg = json.dumps({"id": call_id, "method": method, "params": params or {}})
        ws.send(msg)
        call_id += 1
        # Read until we get our response (skip events)
        for _ in range(100):
            raw = ws.recv()
            data = json.loads(raw)
            if data.get("id") == call_id - 1:
                return data.get("result", {})

    # Navigate to project page
    print(f"[CDP] Navigating to {url}", file=sys.stderr)
    cdp_send("Page.navigate", {"url": url})
    time.sleep(4)  # Wait for page load

    # Get all anchor hrefs via JS eval
    result = cdp_send("Runtime.evaluate", {
        "expression": "Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
    })
    hrefs = result.get("result", {}).get("value", []) or []
    pdf_links = collect_pdf_links_from_hrefs(hrefs, url)
    print(f"[CDP] Found {len(pdf_links)} document links", file=sys.stderr)

    # Extract page title for metadata
    title_result = cdp_send("Runtime.evaluate", {"expression": "document.title"})
    page_title = title_result.get("result", {}).get("value", "")
    results["page_title"] = page_title

    # Get cookies to use in downloads (Edge's live session)
    cookies_result = cdp_send("Network.getAllCookies")
    cookies = cookies_result.get("cookies", [])
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies
                               if portal_host in c.get("domain", ""))

    ws.close()

    # Download PDFs using requests + session cookies
    session = requests.Session()
    if cookie_header:
        session.headers.update({"Cookie": cookie_header})
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": url,
    })

    for i, pdf_url in enumerate(pdf_links[:30]):
        print(f"  [CDP] Downloading [{i+1}/{min(len(pdf_links),30)}]: {pdf_url[:80]}", file=sys.stderr)
        try:
            resp = session.get(pdf_url, timeout=60, stream=True)
            content_type = resp.headers.get("content-type", "")
            if resp.ok and ("pdf" in content_type or pdf_url.lower().endswith(".pdf")):
                url_path = urlparse(pdf_url).path
                filename = sanitize_filename(Path(url_path).name) if url_path.lower().endswith(".pdf") \
                    else f"doc_{i:03d}.pdf"
                if not filename.lower().endswith(".pdf"):
                    filename = f"doc_{i:03d}.pdf"
                dest = pdf_dir / filename
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded.append(str(dest))
                print(f"    [CDP] Saved: {filename}", file=sys.stderr)
        except Exception as e:
            print(f"  [CDP WARN] {pdf_url}: {e}", file=sys.stderr)

    results["downloaded_pdfs"] = downloaded
    results["pdf_count"] = len(downloaded)
    return results


# ---------------------------------------------------------------------------
# Orchestrator: try Playwright, fall back to CDP
# ---------------------------------------------------------------------------

async def run(url: str, slug: str, force_cdp: bool = False) -> dict:
    portal = detect_portal(url)
    staging_dir = STAGING_BASE / slug

    print(f"Portal: {portal}", file=sys.stderr)
    print(f"Staging: {staging_dir}", file=sys.stderr)

    metadata = {}
    scrape_log = {"method": None, "playwright_error": None, "cdp_error": None}

    if not force_cdp:
        try:
            print("[PW] Attempting primary Playwright scrape...", file=sys.stderr)
            metadata = await run_playwright(url, slug, portal, staging_dir)
            scrape_log["method"] = "playwright"
            print("[PW] Primary scrape succeeded.", file=sys.stderr)
        except Exception as pw_err:
            scrape_log["playwright_error"] = str(pw_err)
            print(f"[PW] Primary scrape failed: {pw_err}", file=sys.stderr)
            print("[CDP] Pivoting to Edge CDP fallback...", file=sys.stderr)
            force_cdp = True

    if force_cdp:
        try:
            metadata = run_cdp_fallback(url, slug, portal, staging_dir)
            scrape_log["method"] = "cdp_edge"
            print("[CDP] Fallback scrape succeeded.", file=sys.stderr)
        except Exception as cdp_err:
            scrape_log["cdp_error"] = str(cdp_err)
            print(f"[CDP] Fallback also failed: {cdp_err}", file=sys.stderr)
            metadata = {
                "url": url, "portal": portal, "slug": slug,
                "pdf_count": 0, "downloaded_pdfs": [],
                "error": f"Both methods failed. PW: {scrape_log['playwright_error']} | CDP: {cdp_err}",
            }
            scrape_log["method"] = "failed"

    # Write metadata + scrape log
    meta_path = staging_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    scrape_log_path = staging_dir / "scrape_log.json"
    scrape_log_path.write_text(json.dumps(scrape_log, indent=2))

    print(f"\nDone. {metadata.get('pdf_count', 0)} PDFs in {staging_dir / 'raw_pdfs'}", file=sys.stderr)
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--force-cdp", action="store_true",
                        help="Skip Playwright and go straight to Edge CDP fallback")
    args = parser.parse_args()

    result = asyncio.run(run(args.url, args.slug, force_cdp=args.force_cdp))
    print(json.dumps({"status": "ok" if result.get("pdf_count", 0) > 0 else "warn",
                      "pdf_count": result.get("pdf_count", 0),
                      "method": result.get("method", "unknown")}))


if __name__ == "__main__":
    main()
