import re
from pathlib import Path

target = Path(r"C:\Users\Chase\.openclaw\workspace\skills\phase0-bid-copilot\scripts\scrape_portal.py")
text = target.read_text(encoding="utf-8")

OLD_IMPORT = "    from playwright_stealth import stealth_async\n"
NEW_IMPORT = """    # playwright_stealth API varies by version:
    #   >= 1.0.6  exports stealth_async (async)
    #   older     exports stealth (sync wrapper)
    #   missing   skip stealth silently
    try:
        from playwright_stealth import stealth_async as _stealth_async
        async def _apply_stealth(page):
            await _stealth_async(page)
    except ImportError:
        try:
            from playwright_stealth import stealth as _stealth_sync
            async def _apply_stealth(page):
                _stealth_sync(page)
        except ImportError:
            async def _apply_stealth(page):
                pass
"""

OLD_CALL = "        await stealth_async(page)\n"
NEW_CALL = "        await _apply_stealth(page)\n"

if OLD_IMPORT in text:
    text = text.replace(OLD_IMPORT, NEW_IMPORT)
    text = text.replace(OLD_CALL, NEW_CALL)
    target.write_text(text, encoding="utf-8")
    print("PATCHED_OK")
elif "_apply_stealth" in text:
    print("ALREADY_PATCHED")
else:
    idx = text.find("stealth")
    print(f"NOT_FOUND idx={idx}")
    if idx >= 0:
        print(repr(text[max(0, idx-20):idx+150]))
