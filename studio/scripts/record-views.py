"""Record one GIF per analysis view from the running studio.

Each recording opens the app, names the view, waits for its calculation, and
shows the result. The recordings use the real interface, not still images.

Usage:
    python3 scripts/record-views.py week|forward|...|all
Outputs a .webm per view into /tmp/studio-viewrec; convert with the ffmpeg
two-pass palette recipe (scripts/convert-views.sh).

The three run-scoped views (capture, portfolio, crossrun) read saved hourly market
replays, so those recordings save one or two runs first, exactly as an analyst
would before opening them.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5200/studio/"
OUT = Path("/tmp/studio-viewrec")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900

CAPTION_JS = r"""
(args) => {
  const { title, sub, intro } = args;
  let el = document.getElementById('demo-cap');
  if (!el) {
    el = document.createElement('div');
    el.id = 'demo-cap';
    document.body.appendChild(el);
  }
  const base = `position:fixed;left:50%;transform:translateX(-50%);z-index:2147483647;
    box-sizing:border-box;font-family:'Fira Sans',system-ui,sans-serif;
    background:var(--surface,#12161c);color:var(--text,#e9edf2);
    border:1px solid var(--border,#2a333f);border-radius:14px;
    box-shadow:0 10px 40px rgba(0,0,0,.45);`;
  if (intro) {
    el.style.cssText = base + `bottom:50%;transform:translate(-50%,50%);
      width:720px;padding:30px 38px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.14em;
        text-transform:uppercase;
        color:var(--muted,#8a97a6);margin-bottom:10px;">Power Dispatch Studio</div>
      <div style="font-size:28px;font-weight:700;line-height:1.25;">${title}</div>
      <div style="font-size:16px;color:var(--muted,#9aa7b6);
        margin-top:11px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:20px;width:1150px;max-width:calc(100% - 40px);
    padding:14px 22px;`;
  el.innerHTML = `<div style="font-size:18px;font-weight:650;">${title}</div>
    ${sub ? `<div style="font-size:14px;color:var(--muted,#9aa7b6);
      margin-top:3px;">${sub}</div>` : ''}`;
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
    # the question rail replaced the System/Simulation tabs; open every group
    await page.evaluate(
        """() => {
          document.querySelectorAll('.rail__grouphead').forEach(b => {
            if (b.getAttribute('aria-expanded') === 'false') b.click()
          })
        }"""
    )
    await asyncio.sleep(0.35)


async def view(page: Page, name: str, settle: float = 1.2):
    await page.get_by_role("button", name=name, exact=False).first.click()
    await asyncio.sleep(settle)


async def save_runs(page: Page, n: int):
    """Save n hourly replay calculations for the run comparison views."""
    await view(page, "Hourly market replay", settle=1.4)
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
    {
        "key": "backcast",
        "label": "Historical replay",
        "title": "Market records show the model's error",
        "sub": "The operator's published offers are compared with recorded "
        "prices. The cost-only calculation is one click away.",
        "settle": 2.2,
    },
    {
        "key": "explain",
        "label": "Explain a day",
        "title": "Recorded costs, offers, and grid limits explain one market day",
        "sub": "The evening price is split into the cost calculation, the "
        "difference from published offers, and equipment at a binding limit.",
        "settle": 2.4,
    },
    {
        "key": "week",
        "label": "Inter-day storage (168 hours)",
        "title": "Storage carries energy across midnight for seven days",
        "sub": "One 168-hour calculation tracks the battery state of charge "
        "across day boundaries.",
        "settle": 1.8,
    },
    {
        "key": "forward",
        "label": "Possible future price range",
        "title": "Possible price range through 2030",
        "sub": "Recorded market days are re-priced under Department of Energy "
        "Power Development Plan demand growth.",
        "settle": 1.6,
    },
    {
        "key": "multiyear",
        "label": "Prices and spare capacity by year",
        "title": "Prices and spare capacity through 2040",
        "sub": "Three policy cases show when existing plants can no longer "
        "cover projected demand through 2040.",
        "settle": 1.6,
    },
    {
        "key": "ensembles",
        "label": "Range across repeated simulations",
        "title": "Price range across repeated simulations",
        "sub": "Repeated simulations report the 10th percentile, median, and "
        "90th percentile for each grid.",
        "settle": 2.8,
    },
    {
        "key": "expansion",
        "label": "Lowest-cost expansion mix",
        "title": "Lowest-cost new capacity compared with DOE projects",
        "sub": "The lowest-cost modeled additions are compared with projects "
        "listed by the Department of Energy.",
        "settle": 1.8,
    },
    {
        "key": "capture",
        "label": "Average price earned by each technology",
        "title": "Average price earned by each technology",
        "sub": "The capture price weights each hourly price by generation.",
        "settle": 1.6,
        "prep": 1,
    },
    {
        "key": "portfolio",
        "label": "Generator portfolio value",
        "title": "Generator portfolio and contract value",
        "sub": "A contract for differences (CfD) payment is compared with the "
        "WESM price for each owner.",
        "settle": 1.6,
        "prep": 1,
    },
    {
        "key": "crossrun",
        "label": "Compare one measure across runs",
        "title": "Saved runs compared side by side",
        "sub": "One table compares saved runs. A second view ranks each "
        "what-if by price effect.",
        "settle": 1.8,
        "prep": 2,
    },
    {
        "key": "rtdoe5",
        "label": "5-minute replay",
        "title": "Five-minute replay",
        "sub": "All 288 five-minute intervals show brief high-price periods "
        "hidden by hourly averages.",
        "settle": 1.8,
    },
    {
        "key": "nodal",
        "label": "Prices at grid connection points",
        "title": "Recorded prices at grid connection points",
        "sub": "Each node's recorded price is compared with its island grid's "
        "regional price.",
        "settle": 1.8,
    },
    {
        "key": "lossval",
        "label": "Transmission-loss check",
        "title": "Estimated transmission losses checked against market prices",
        "sub": "Network physics tested against the market's own per-node prices.",
        "settle": 1.8,
    },
    {
        "key": "vintage",
        "label": "Assumptions",
        "title": "Each model assumption shows its source and date",
        "sub": "Recorded inputs, calculated values, and chosen assumptions are "
        "identified separately.",
        "settle": 1.4,
    },
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
        # Scroll to show the table or chart below the main result.
        await page.mouse.wheel(0, 260)
        await asyncio.sleep(1.8)
        if spec["key"] == "explain":
            # switch the market day to show any past evening peak decomposes
            try:
                sel = page.get_by_label("Explain day")
                vals = [
                    await o.get_attribute("value")
                    for o in await sel.locator("option").all()
                ]
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
