"""Record the map's Simulate-mode dispatch clip with a fresh Playwright context
(no persistent cache), so it captures the current map. Outputs a webm to
/tmp/map-rec; convert with the ffmpeg palette recipe.

Usage: python3 build/record_map_dispatch.py [base_url]
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8790/"
OUT = Path("/tmp/map-rec")
OUT.mkdir(exist_ok=True)


async def set_slider(page, needle: str, value: int):
    # find the range input under the labeled control and set it, firing input
    await page.evaluate(
        """([needle, value]) => {
          const labels = [...document.querySelectorAll('label, .sim-row, .ctl, div')];
          let input = null;
          for (const el of document.querySelectorAll('input[type=range]')) {
            const around = (el.closest('div')?.textContent || '') + (el.previousElementSibling?.textContent || '');
            if (around.toLowerCase().includes(needle.toLowerCase())) { input = el; break; }
          }
          input = input || document.querySelector('input[type=range]');
          if (input) {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, String(value));
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }""",
        [needle, value],
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
        await asyncio.sleep(4.0)  # basemap tiles + baked data
        await page.get_by_text("Simulate", exact=False).first.click()
        await asyncio.sleep(3.0)
        # add a data-center load: the price flips coal to oil on the clean map
        await set_slider(page, "data center", 1500)
        await asyncio.sleep(3.0)
        await set_slider(page, "data center", 3000)
        await asyncio.sleep(3.0)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / "map-dispatch.webm"
        Path(vid).replace(dest)
        print(dest)


asyncio.run(main())
