"""Showcase recordings beyond the three what-if workflows.

  backcast : the trust clip. On the widest-swing observed day, the cost model
             clears flat at the P6 floor while observed prices spike; toggle to
             the operator's own offer book and the model tracks the real evening
             ramp hour by hour. Then the whole-window Backcast, nothing tuned.
  hero     : the end-to-end LinkedIn flow (open, build a data center, trip Sual,
             switch to LNG, prove it against real prices, close on free-not-PLEXOS).

    python3 scripts/record-showcase.py backcast|hero|all
Outputs a .webm per clip into /tmp/studio-rec.
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

# reuse the workflow recorder's helpers and caption banner
sys.path.insert(0, str(Path(__file__).parent))
import importlib
_wf = importlib.import_module("record-workflows")
Rec, enter, sim, sysm, view = _wf.Rec, _wf.enter, _wf.sim, _wf.sysm, _wf.view
run, pick_day, edit_cell, tile, input_value = (
    _wf.run, _wf.pick_day, _wf.edit_cell, _wf.tile, _wf.input_value)
scroll_top, scroll_to = _wf.scroll_top, _wf.scroll_to
BASE, OUT, W, H = _wf.BASE, _wf.OUT, _wf.W, _wf.H


async def engine(page: Page, label: str, hold: float = 2.4):
    """Flip the Chronology dispatch-engine segmented control (a role=tab)."""
    await page.get_by_role("tab", name=label, exact=False).click()
    await asyncio.sleep(hold)


async def chrono(page: Page):
    await page.get_by_role("button", name="Chronology", exact=False).first.click()
    await asyncio.sleep(1.0)


# ---- the backcast trust clip -------------------------------------------------

async def backcast(page: Page):
    r = Rec(page, 4)
    await enter(page)
    await r.intro(
        "Does the model check out against real prices?",
        "Replay observed market days and score the clear against the operator's "
        "own published prices. Nothing tuned.",
    )
    await sim(page)
    await chrono(page)
    await pick_day(page, "widest swing")
    await asyncio.sleep(0.6)

    base_mean = await tile(page, "Mean price, Luzon")
    await r.cap(
        "The cost model is a floor",
        f"On the widest-swing day it clears flat at the P6 coal floor "
        f"({base_mean} mean) while the observed price (dashed) spikes into the "
        f"evening. A cost stack sets the baseline, not the scarcity spike.",
    )
    await scroll_to(page, "svg", "center")
    await asyncio.sleep(3.4)

    await r.clear()  # drop the cost caption before the reveal so it never
    await engine(page, "Observed offers", hold=0.6)  # sits over the offers chart
    off_mean = await tile(page, "Mean price, Luzon")
    await r.cap(
        "Replay the operator's own bids and it tracks the real shape",
        f"Same day, cleared on the market's own offer book: the modeled lines "
        f"now follow the observed evening ramp hour by hour ({off_mean} mean). "
        f"Across the quarter the offer-book replay reaches 0.73 to 0.87 "
        f"correlation with observed prices and 88 to 99 percent of the "
        f"inter-island flow direction.",
    )
    await scroll_to(page, "svg", "center")
    await asyncio.sleep(4.2)

    await view(page, "Backcast")
    await scroll_top(page)
    mae = await tile(page, "MAE, Luzon")
    await r.cap(
        "The whole window, error stated, nothing tuned",
        f"Every full-coverage day scored against the observed price tape "
        f"(Luzon MAE {mae}). The cost model's gap to observed is not hidden: it "
        f"is itself a measured series, the offer premium the market bids over "
        f"cost. The live view recomputes this from the current archive daily.",
    )
    await asyncio.sleep(4.4)
    await scroll_to(page, "table", "center")
    await asyncio.sleep(3.2)
    await r.clear()
    await asyncio.sleep(0.5)


WORKFLOWS = {"backcast": backcast}


async def record_one(key: str):
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
        await WORKFLOWS[key](page)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / f"{key}.webm"
        Path(vid).replace(dest)
        print(f"{key}: {dest}")


async def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(WORKFLOWS) if which == "all" else [which]
    for k in keys:
        await record_one(k)


if __name__ == "__main__":
    asyncio.run(main())
