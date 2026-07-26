#!/usr/bin/env python3
"""Record a real scroll-through of web/pax-silica.html.

Needs `make serve` running (web/serve.py on :8789, per the Makefile, or set
BASE). Scrolls the live page, letting each beat's IntersectionObserver-triggered
animation play, and captures a real video (no mockup, no stitched screenshots,
per project convention). Outputs a .webm under /tmp; convert to mp4/gif after.

    make serve &
    python3 build/record_pax_silica_scale.py
"""
import asyncio
import os

from playwright.async_api import async_playwright

BASE = os.environ.get("BASE", "http://localhost:8789")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = "/tmp/pax_scale_rec"
os.makedirs(OUT_DIR, exist_ok=True)
W, H = 1280, 800


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=OUT_DIR,
            record_video_size={"width": W, "height": H},
        )
        page = await ctx.new_page()
        await page.goto(BASE + "/pax-silica.html")
        await page.wait_for_function("window.__pxdiag && window.__pxdiag.ready")
        await asyncio.sleep(1.0)

        total = await page.evaluate("document.body.scrollHeight")
        beats = ["b-power", "b-sun", "b-wires", "b-priceb", "b-own", "b-water", "b-close"]
        for bid in beats:
            await page.evaluate(
                "(id) => document.getElementById(id)"
                ".scrollIntoView({behavior:'smooth', block:'start'})",
                bid,
            )
            # smooth-scroll settle, then let the beat's animation play out
            await asyncio.sleep(1.1)
            await asyncio.sleep(3.4 if bid == "b-own" else 2.2)
        await page.evaluate(
            "window.scrollTo({top: document.body.scrollHeight, behavior:'smooth'})"
        )
        await asyncio.sleep(1.4)

        await ctx.close()
        await browser.close()
    files = [f for f in os.listdir(OUT_DIR) if f.endswith(".webm")]
    print("recorded", files, "in", OUT_DIR)


if __name__ == "__main__":
    asyncio.run(main())
