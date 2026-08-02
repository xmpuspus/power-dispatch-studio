#!/usr/bin/env python3
"""Record the Pax Silica charts as a sequence of animated sections.

Not a page scroll. Each figure card is moved onto a centered stage, rebuilt at
that width, played from zero, held while it finishes, then cut to the next one.
A title card opens the clip, because a feed renders frame one as the thumbnail.

Everything on screen is the live page reading the generated numbers, so the montage
cannot show a figure the site does not.

Needs `make serve` running (web/serve.py on :8789, per the Makefile, or set
BASE). Writes docs/pax-silica-scale.mp4 and .gif via the ffmpeg recipe below.

    make serve &
    python3 build/record_pax_silica_scale.py
"""

import asyncio
import os
import subprocess

from playwright.async_api import async_playwright

BASE = os.environ.get("BASE", "http://localhost:8789")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
REC = "/tmp/pax_montage"
W, H = 1280, 880
CARD_W = 940  # every card fits at this width (tallest is the map, ~700)
MAG = 1.36  # ceiling on the magnify-to-fill-the-frame scale

# (figure id, seconds to hold once it starts playing). The own-station card
# flips to its broken-generator state at 2.6s, so it needs the longest hold.
SECTIONS = [
    ("fig-grids", 3.4),
    ("fig-acwa", 3.0),
    ("fig-land", 3.6),
    ("fig-wires", 3.2),
    ("fig-record", 2.6),
    ("fig-priceb", 3.4),
    ("fig-own", 5.4),
    ("fig-water", 3.6),
    # the land card is tall: five runs of squares plus its note. Staged wider,
    # the runs reflow into fewer rows and the magnifier stops shrinking it.
    ("fig-site", 3.8, 1220),
]

STAGE = r"""
() => {
  const bg = getComputedStyle(document.body).backgroundColor;
  const s = document.createElement('div');
  s.id = 'mstage';
  s.style.cssText = 'position:fixed; inset:0; z-index:99999; background:' + bg +
    '; display:flex; align-items:center; justify-content:center; overflow:hidden;';
  document.body.appendChild(s);
  const inner = document.createElement('div');
  inner.id = 'minner';
  s.appendChild(inner);
  const css = document.createElement('style');
  // The raw URL list is unreadable at montage scale. The source list is
  // already a named link in the line above, so it comes off the stage. Nothing
  // Other page content is hidden; each section still shows its sources.
  css.textContent = '#mstage .replay{display:none !important;}' +
    '#mstage .rawline{display:none !important;}' +
    '#minner .fig{margin:0 !important;}';
  document.head.appendChild(css);
  // a staged card is put back where it came from before the next one is
  // staged: the solar builder writes into two cards at once, so every card
  // has to stay in the document even while another one is on stage
  let held = null, home = null;
  const restore = () => {
    if (held && home) home.parent.insertBefore(held, home.next);
    held = null; home = null;
    inner.innerHTML = '';
  };
  window.__m = {
    title(html){
      restore();
      inner.style.transform = 'none';
      inner.style.width = '900px';
      inner.innerHTML = html;
    },
    card(id, w){
      const fig = document.getElementById(id);
      if (!fig) return null;
      restore();
      home = { parent: fig.parentNode, next: fig.nextSibling };
      held = fig;
      inner.style.transform = 'none';
      inner.style.width = w + 'px';
      inner.appendChild(fig);
      return true;
    },
    // magnify the staged card until it fills the frame. The transform is set
    // BEFORE the animation runs, so the compositor rasterizes the text at its
    // final size instead of scaling up a 1x bitmap.
    fit(cap){
      const pad = 40;
      inner.style.transform = 'none';
      const r = inner.getBoundingClientRect();
      const k = Math.min(cap, (window.innerHeight - pad) / r.height,
                              (window.innerWidth - pad) / r.width);
      inner.style.transform = 'scale(' + k.toFixed(4) + ')';
      return k;
    },
  };
}
"""

TITLE = """
<div style="font-family:'Helvetica Neue',Helvetica,Arial,sans-serif">
  <div style="font-size:13px; letter-spacing:.14em; text-transform:uppercase;
    color:#7d7d85; margin-bottom:14px">Pax Silica, New Clark City, Tarlac</div>
  <div style="font-size:44px; font-weight:700; line-height:1.18;
    letter-spacing:-.02em; color:#02000D">The Bases Conversion and Development
    Authority says its Pax Silica campus will need
    <span style="color:#A65E46">3,000 MW</span> of power and
    <span style="color:#A65E46">65 to 90 million liters</span> of water a day.</div>
  <div style="font-size:20px; color:#3d3d47; margin-top:18px">Both are figures at
    full development, which BCDA puts 10 to 15 years after construction starts in
    2028.</div>
  <div style="font-size:20px; color:#3d3d47; margin-top:10px">Nine charts compare
    the announced demand with Philippine grid, solar, water, and land records.</div>
</div>
"""


async def main():
    os.makedirs(REC, exist_ok=True)
    for f in os.listdir(REC):
        if f.endswith(".webm"):
            os.remove(os.path.join(REC, f))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=REC,
            record_video_size={"width": W, "height": H},
        )
        page = await ctx.new_page()
        await page.goto(BASE + "/pax-silica.html")
        await page.wait_for_function("window.__pxdiag && window.__pxdiag.ready")
        await page.evaluate(STAGE)

        await page.evaluate("(h) => window.__m.title(h)", TITLE)
        await page.evaluate("(c) => window.__m.fit(c)", MAG)
        await asyncio.sleep(2.4)

        for section in SECTIONS:
            fid, hold = section[0], section[1]
            width = section[2] if len(section) > 2 else CARD_W
            ok = await page.evaluate(
                "([id, w]) => window.__m.card(id, w)", [fid, width]
            )
            if not ok:
                print("missing card:", fid)
                continue
            # build once to settle the card's real height at this width, size
            # the magnification to that, then replay so the animation runs
            # inside the already-scaled layer
            await page.evaluate("(id) => window.__pxplay(id)", fid)
            if fid == "fig-land":  # basemap tiles are network
                await page.wait_for_function(
                    "[...document.querySelectorAll('#land-map img')]"
                    ".every(i => i.complete)",
                    timeout=15000,
                )
            k = await page.evaluate("(c) => window.__m.fit(c)", MAG)
            await page.evaluate("(id) => window.__pxplay(id)", fid)
            print(f"{fid}: scale {k:.2f}, hold {hold}s")
            await asyncio.sleep(hold)

        await asyncio.sleep(0.6)
        await ctx.close()
        await browser.close()

    webm = next(f for f in os.listdir(REC) if f.endswith(".webm"))
    src = os.path.join(REC, webm)
    mp4 = os.path.join(DOCS, "pax-silica-scale.mp4")
    gif = os.path.join(DOCS, "pax-silica-scale.gif")
    pal = "/tmp/pax_montage_pal.png"

    def run(a):
        subprocess.run(
            a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-tune",
            "stillimage",
            mp4,
        ]
    )
    vf = "fps=10,scale=960:-1:flags=lanczos"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-vf",
            vf + ",palettegen=stats_mode=diff",
            "-update",
            "1",
            "-frames:v",
            "1",
            pal,
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-i",
            pal,
            "-lavfi",
            vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            gif,
        ]
    )
    for p in (mp4, gif):
        print("wrote", p, f"({os.path.getsize(p) // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
