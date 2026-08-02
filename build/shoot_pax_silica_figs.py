#!/usr/bin/env python3
"""Screenshot each Pax Silica figure card into docs/pax-silica-figs/.

Every card animates on scroll, so this scrolls it into view, waits for the
page's own ready flag and for the animation to settle, then shoots the card
element rather than the viewport.

    make serve &
    python3 build/shoot_pax_silica_figs.py
"""

import asyncio
import os

from playwright.async_api import async_playwright

BASE = os.environ.get("BASE", "http://localhost:8789")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "pax-silica-figs")

CARDS = [
    ("fig-grids", "grids"),
    ("fig-acwa", "acwa"),
    ("fig-land", "land"),
    ("fig-wires", "wires"),
    ("fig-record", "record"),
    ("fig-priceb", "priceb"),
    ("fig-own", "own"),
    ("fig-water", "water"),
    ("fig-site", "site"),
]


async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(
            viewport={"width": 1280, "height": 900}, device_scale_factor=2
        )
        await pg.goto(BASE + "/pax-silica.html", wait_until="networkidle")
        await pg.wait_for_function(
            "window.__pxdiag && window.__pxdiag.ready", timeout=30000
        )
        for cid, name in CARDS:
            el = pg.locator("#" + cid)
            if not await el.count():
                print("[MISS]", cid)
                continue
            await el.scroll_into_view_if_needed()
            await pg.wait_for_timeout(3200)
            path = os.path.join(OUT, name + ".png")
            await el.screenshot(path=path)
            print("wrote", path)
        await b.close()


asyncio.run(main())
