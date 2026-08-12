"""Record the map's five-mode tour and write ``docs/hero.gif``.

The map pans and zooms to each region, shows the archived constraint record on
hover, and increases data-center demand so the lowest-cost-first price changes
from coal to oil.

    make serve                          # web/ on :8789
    python3 build/record_map_hero.py [base_url]

The script records a WebM file in /tmp/map-rec and converts it to a 900-pixel GIF
at 14 frames per second.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8789/"
ROOT = Path(__file__).resolve().parent.parent
REC = Path("/tmp/map-rec")
REC.mkdir(exist_ok=True)
OUT = ROOT / "docs" / "hero.gif"
W, H = 1280, 800

# Move the slider with real input events so the price recalculates on screen.
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


async def mode(page: Page, m: str):
    await page.evaluate(
        "(m) => document.querySelector('[data-mode=' + m + ']').click()", m
    )


async def fly(page: Page, lng: float, lat: float, zoom: float, ms: int = 1100):
    await page.evaluate(
        "(a) => map.flyTo({ center: [a.lng, a.lat], zoom: a.zoom, duration: a.ms })",
        {"lng": lng, "lat": lat, "zoom": zoom, "ms": ms},
    )
    await asyncio.sleep(ms / 1000 + 0.2)


async def hover_choke(page: Page):
    # hover a real rendered choke-line feature at its midpoint; fires the map's own
    # mousemove handler with real properties, so the popup is live data, not a mockup
    loc = await page.evaluate(
        """() => {
          const f = map.queryRenderedFeatures({ layers: ['choke-line'] });
          if (!f.length) return null;
          const g = f[0].geometry;
          const line = g.type === 'MultiLineString' ? g.coordinates[0] : g.coordinates;
          const c = line[Math.floor(line.length / 2)];
          const p = map.project(c); const r = map.getCanvas().getBoundingClientRect();
          return { x: r.left + p.x, y: r.top + p.y };
        }"""
    )
    if loc:
        await page.mouse.move(loc["x"], loc["y"])
        await asyncio.sleep(0.15)
        await page.mouse.move(loc["x"] + 1, loc["y"] + 1)  # nudge so the hover fires


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
        # wait for the real ready flag, not a blind sleep, then a short settle. The
        # blank + loading-results lead gets trimmed off the gif below.
        await page.wait_for_function(
            "() => window.__diag && window.__diag.ready", timeout=15000
        )
        await asyncio.sleep(1.0)

        # Supply: announced-demand bars, then the Luzon data-center cluster.
        await mode(page, "supply")
        await asyncio.sleep(0.5)
        await fly(page, 121.0, 14.9, 6.1, 1000)
        await asyncio.sleep(1.0)

        # Choke points: zoom to the Visayas corridor and hover its live receipt
        await mode(page, "choke")
        await asyncio.sleep(0.5)
        await fly(page, 123.9, 10.8, 6.9, 1000)
        await hover_choke(page)
        await asyncio.sleep(1.7)

        # Prices: keep the national view so node-price differences remain visible at
        # once. The second push into Luzon used to sit here and is gone: a pan
        # repaints every pixel, so a second of it costs 0.41 MB of gif against
        # 0.22 MB for a second where only a panel changes. Measured on this
        # recording. The corridor fly above earns its bytes because the corridor
        # is the subject; this one only moved the camera.
        await mode(page, "price")
        await page.mouse.move(W / 2, 40)  # drop the hover popup
        await fly(page, 122.2, 12.2, 5.2, 900)
        await asyncio.sleep(1.9)

        # Drivers: the day-by-day archive feed. Still, for the same reason.
        await mode(page, "drivers")
        await asyncio.sleep(1.5)

        # Add a data center; the merit-order price recalculates from coal to oil.
        await mode(page, "simulate")
        await asyncio.sleep(0.8)
        await fly(page, 121.0, 14.9, 6.0, 900)
        await page.evaluate(ANIM_JS, ["sim-dc", 3000, 3400])
        await asyncio.sleep(1.8)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        webm = REC / "map-hero.webm"
        Path(vid).replace(webm)

    # data build docs/hero.gif. -ss trims the blank + load lead so the loop opens clean
    # on the Supply view. The recipe is the one measured smallest on this footage
    # at a quality that still reads: 11 fps and 820 px cost about a third of what
    # 13 fps and 900 px did, and 96 colors against 128 cost another fifth.
    # gifsicle then packs it; --lossy is not used, it moved this file under 2%.
    vf = "fps=11,scale=820:-1:flags=lanczos"
    pal = REC / "hero-pal.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1.6",
            "-i",
            str(webm),
            "-vf",
            f"{vf},palettegen=max_colors=96:stats_mode=diff",
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
            "1.6",
            "-i",
            str(webm),
            "-i",
            str(pal),
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            str(OUT),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(["gifsicle", "-O3", str(OUT), "-o", str(OUT)], capture_output=True)

    # the full-resolution version to share, the same pattern the reel and the
    # studio pass already follow: the gif is the preview, the mp4 is the copy
    mp4 = OUT.with_suffix(".mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1.6",
            "-i",
            str(webm),
            "-vf",
            "scale=1280:-2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "24",
            "-an",
            str(mp4),
        ],
        check=True,
        capture_output=True,
    )
    print(
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) "
        f"and {mp4.name} ({mp4.stat().st_size // 1024} KB)"
    )


asyncio.run(main())
