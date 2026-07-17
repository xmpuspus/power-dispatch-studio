"""Record one real GIF per new analysis view (the 2026-07-14 analyst-workflow
build-out). Each recording opens the actual studio in Playwright, drops a title
card naming the view, navigates to it, lets it solve, and holds on the payoff.
Real motion capture of the running app, never stitched screenshots.

Usage:
    python3 scripts/record-views.py week|forward|...|all
Outputs a .webm per view into /tmp/studio-viewrec; convert with the ffmpeg
two-pass palette recipe (scripts/convert-views.sh).

The three run-scoped views (capture, portfolio, crossrun) read saved chronology
runs, so those recordings freeze one or two runs first, exactly as an analyst
would before opening them.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5188/"
OUT = Path("/tmp/studio-viewrec")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900

CAPTION_JS = r"""
(args) => {
  const { title, sub, intro } = args;
  let el = document.getElementById('demo-cap');
  if (!el) { el = document.createElement('div'); el.id = 'demo-cap'; document.body.appendChild(el); }
  const base = `position:fixed;left:50%;transform:translateX(-50%);z-index:2147483647;
    box-sizing:border-box;font-family:'Fira Sans',system-ui,sans-serif;
    background:var(--surface,#12161c);color:var(--text,#e9edf2);
    border:1px solid var(--border,#2a333f);border-radius:14px;
    box-shadow:0 10px 40px rgba(0,0,0,.45);`;
  if (intro) {
    el.style.cssText = base + `bottom:50%;transform:translate(-50%,50%);
      width:720px;padding:30px 38px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.14em;text-transform:uppercase;
        color:var(--muted,#8a97a6);margin-bottom:10px;">Power Dispatch Studio</div>
      <div style="font-size:28px;font-weight:700;line-height:1.25;">${title}</div>
      <div style="font-size:16px;color:var(--muted,#9aa7b6);margin-top:11px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:20px;width:1150px;max-width:calc(100% - 40px);
    padding:14px 22px;`;
  el.innerHTML = `<div style="font-size:18px;font-weight:650;">${title}</div>
    ${sub ? `<div style="font-size:14px;color:var(--muted,#9aa7b6);margin-top:3px;">${sub}</div>` : ''}`;
}
"""


async def caption(page, title, sub="", intro=False):
    await page.evaluate(CAPTION_JS, {"title": title, "sub": sub, "intro": intro})


async def clear_cap(page):
    await page.evaluate("() => document.getElementById('demo-cap')?.remove()")


async def enter(page: Page):
    await page.goto(BASE, wait_until="networkidle")
    await asyncio.sleep(0.6)
    await page.get_by_role("button", name="Open Power Dispatch Studio").click()
    await page.wait_for_selector('[data-testid="studio"]', timeout=8000)
    await asyncio.sleep(0.6)


async def sim(page: Page):
    await page.get_by_role("tab", name="Simulation").click()
    await asyncio.sleep(0.35)


async def view(page: Page, name: str, settle: float = 1.2):
    await page.get_by_role("button", name=name, exact=False).first.click()
    await asyncio.sleep(settle)


async def save_runs(page: Page, n: int):
    """Freeze n distinct chronology solves so the run-scoped views have data."""
    await view(page, "Chronology", settle=1.4)
    sel = page.get_by_label("Observed day to replay")
    opts = await sel.locator("option").all()
    values = [await o.get_attribute("value") for o in opts]
    for i in range(n):
        if i < len(values):
            await sel.select_option(value=values[-(i + 1)])
            await asyncio.sleep(1.0)
        await page.get_by_role("button", name="Save run").click()
        await asyncio.sleep(0.7)


VIEWS = [
    {"key": "backcast", "label": "Backcast", "title": "Validated on history",
     "sub": "Opens on the operator's own offer books, the calibrated view; the pure cost model is the counterfactual one click away.",
     "settle": 2.2},
    {"key": "explain", "label": "Explain a day", "title": "Explain a day",
     "sub": "Any past market day's evening peak split into fundamentals, the offer premium the market bid on top, and the equipment that bound the grid.",
     "settle": 2.4},
    {"key": "week", "label": "Native week", "title": "Native week (168-hour LP)",
     "sub": "The battery state of charge carries across midnight; the day engine resets it.",
     "settle": 1.8},
    {"key": "forward", "label": "Forward prices", "title": "Forward prices",
     "sub": "A price band to 2030 from the observed library and DOE PDP demand growth.",
     "settle": 1.6},
    {"key": "multiyear", "label": "Multi-year path", "title": "Multi-year price path",
     "sub": "To 2040 under three policy scenarios; a fixed fleet saturates at its cap.",
     "settle": 1.6},
    {"key": "ensembles", "label": "Ensembles", "title": "Scenario ensembles",
     "sub": "Seeded Monte Carlo joint draws: P10, median, P90 per grid.",
     "settle": 2.8},
    {"key": "expansion", "label": "Expansion mix", "title": "Expansion mix",
     "sub": "Greenfield least-cost capacity vs the DOE plan.",
     "settle": 1.8},
    {"key": "capture", "label": "Capture prices", "title": "Capture prices",
     "sub": "Generation-weighted capture price per technology.",
     "settle": 1.6, "prep": 1},
    {"key": "portfolio", "label": "Portfolio", "title": "Portfolio valuation",
     "sub": "Contract-for-differences against WESM, by owner position.",
     "settle": 1.6, "prep": 1},
    {"key": "crossrun", "label": "Cross-run", "title": "Cross-run analytics",
     "sub": "A metric matrix across saved runs plus a lever tornado.",
     "settle": 1.8, "prep": 2},
    {"key": "rtdoe5", "label": "5-minute replay", "title": "Five-minute replay",
     "sub": "288 five-minute intervals: the scarcity spikes the hourly replay smooths.",
     "settle": 1.8},
    {"key": "nodal", "label": "Nodal prices", "title": "Nodal prices, observed",
     "sub": "Per-node deviations from the regional price; observed, not modeled.",
     "settle": 1.8},
    {"key": "lossval", "label": "Loss validation", "title": "Loss-surface validation",
     "sub": "Network physics tested against the market's own per-node prices.",
     "settle": 1.8},
    {"key": "vintage", "label": "Assumptions", "title": "Assumptions and vintage",
     "sub": "Every model assumption with its primary source and date.",
     "settle": 1.4},
]
BY_KEY = {v["key"]: v for v in VIEWS}


async def record_one(spec: dict):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
            color_scheme="light",
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await enter(page)
        await caption(page, spec["title"], spec["sub"], intro=True)
        await asyncio.sleep(2.4)
        await clear_cap(page)
        await sim(page)
        if spec.get("prep"):
            await save_runs(page, spec["prep"])
        await view(page, spec["label"], settle=spec["settle"])
        await caption(page, spec["title"], spec["sub"])
        await asyncio.sleep(2.6)
        # a slow scroll to reveal the table/chart below the payoff tiles
        await page.mouse.wheel(0, 260)
        await asyncio.sleep(1.8)
        if spec["key"] == "explain":
            # switch the market day to show any past evening peak decomposes
            try:
                sel = page.get_by_label("Explain day")
                vals = [await o.get_attribute("value") for o in await sel.locator("option").all()]
                if len(vals) > 10:
                    await sel.select_option(value=vals[-11])
                    await asyncio.sleep(2.4)
            except Exception:
                pass
        await clear_cap(page)
        await asyncio.sleep(0.3)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / f"{spec['key']}.webm"
        Path(vid).replace(dest)
        print(f"{spec['key']}: {dest}")


async def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(BY_KEY) if which == "all" else [which]
    for k in keys:
        await record_one(BY_KEY[k])


if __name__ == "__main__":
    asyncio.run(main())
