"""Record the map's Simulate (merit-order dispatch) walkthrough, then data build
docs/dispatch-demo.gif.

The previous recorder cached generated JSON across sessions. Playwright opens a
fresh browser context for every run and reads the current data.

    make serve                          # web/ on :8789
    python3 build/record_dispatch_demo.py [base_url]

The recording uses real input events and reads current results. It opens Simulate
on Luzon, increases data-center
the added demand until the clearing price changes from coal to oil, remove a Sual unit,
relieve the feeding corridor, then reset and switch to the tighter Visayas
stack.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8789/"
ROOT = Path(__file__).resolve().parent.parent
REC = Path("/tmp/dispatch-rec")
REC.mkdir(exist_ok=True)
OUT = ROOT / "docs" / "dispatch-demo.gif"
W, H = 1280, 800

ANIM_JS = r"""
(args) => {
  const [id, to, ms] = args;
  const el = document.getElementById(id);
  if (!el) return;
  const from = +el.value, t0 = performance.now();
  return new Promise(r => { function f(t){ const k = Math.min(1, (t - t0) / ms);
    el.value = Math.round(from + (to - from) * k);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    k < 1 ? requestAnimationFrame(f) : r(); } requestAnimationFrame(f); }); }
"""


async def anim(page: Page, sid: str, to: int, ms: int):
    await page.evaluate(ANIM_JS, [sid, to, ms])
    await asyncio.sleep(ms / 1000 + 0.2)


async def fly(page: Page, lng: float, lat: float, zoom: float, ms: int = 1000):
    await page.evaluate(
        "(a) => map.flyTo({ center: [a.lng, a.lat], zoom: a.zoom, duration: a.ms })",
        {"lng": lng, "lat": lat, "zoom": zoom, "ms": ms},
    )
    await asyncio.sleep(ms / 1000 + 0.2)


async def set_select(page: Page, sid: str, value: str):
    await page.evaluate(
        "(a) => { const el = document.getElementById(a.id); if (!el) return; "
        "el.value = a.v; el.dispatchEvent(new Event('change', {bubbles:true})); }",
        {"id": sid, "v": value},
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(REC),
            record_video_size={"width": W, "height": H},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_function(
            "() => window.__diag && window.__diag.ready", timeout=15000
        )
        await asyncio.sleep(1.0)

        # enter Simulate on Luzon (coal margin), ease onto the DC cluster
        await page.evaluate(
            "() => document.querySelector('[data-mode=simulate]').click()"
        )
        await asyncio.sleep(0.8)
        await fly(page, 121.0, 14.9, 6.0, 1000)
        await asyncio.sleep(1.4)

        # Increase data-center demand until the oil block sets the price.
        await anim(page, "sim-dc", 3000, 3600)
        await asyncio.sleep(1.8)

        # Remove a Sual unit after adding demand; a supply shortfall opens.
        await set_select(page, "sim-trip", "Sual")
        await asyncio.sleep(2.4)

        # relieve the feeding corridor (extra inter-island import): shortfall shrinks
        await anim(page, "sim-imp", 250, 2200)
        await asyncio.sleep(2.0)

        # Reset, switch to the tighter Visayas supply stack, and add demand again.
        await anim(page, "sim-dc", 0, 900)
        await set_select(page, "sim-trip", "")
        await asyncio.sleep(0.6)
        await page.evaluate(
            """() => {
              const b = document.querySelector('.gsel[data-grid=visayas]');
              if (b) b.click();
            }"""
        )
        await asyncio.sleep(1.6)
        await anim(page, "sim-dc", 700, 2200)
        await asyncio.sleep(2.0)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        webm = REC / "dispatch-demo.webm"
        Path(vid).replace(webm)

    vf = "fps=13,scale=880:-1:flags=lanczos"
    pal = REC / "dispatch-pal.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1.4",
            "-i",
            str(webm),
            "-vf",
            f"{vf},palettegen=max_colors=128:stats_mode=diff",
            str(pal),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1.4",
            "-i",
            str(webm),
            "-i",
            str(pal),
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            str(OUT),
        ],
        check=True,
        capture_output=True,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


asyncio.run(main())
