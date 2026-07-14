"""Record the map's five-mode tour (the README hero) with a fresh Playwright
context, so it captures the current, scrubbed map. Outputs a webm to /tmp/map-rec.

Usage: python3 build/record_map_hero.py [base_url]
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8790/"
OUT = Path("/tmp/map-rec")
OUT.mkdir(exist_ok=True)


async def tab(page, label: str, hold: float = 2.6):
    await page.get_by_text(label, exact=False).first.click()
    await asyncio.sleep(hold)


async def set_dc(page, value: int):
    await page.evaluate(
        """(value) => {
          const input = document.querySelector('input[type=range]');
          if (input) {
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            s.call(input, String(value));
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }""",
        value,
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(OUT),
            record_video_size={"width": 1280, "height": 800},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await asyncio.sleep(4.5)  # basemap tiles + baked data
        await tab(page, "1 Supply", 2.8)
        await tab(page, "2 Choke points", 2.6)
        await tab(page, "3 Prices", 2.6)
        await tab(page, "Drivers", 2.6)
        await tab(page, "Simulate", 2.4)
        await set_dc(page, 1500)
        await asyncio.sleep(2.8)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / "map-hero.webm"
        Path(vid).replace(dest)
        print(dest)


asyncio.run(main())
