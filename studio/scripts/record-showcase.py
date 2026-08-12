"""Record the historical comparison and the main studio tour.

  backcast : on the widest-swing recorded day, the cost model
             clears flat at the P6 floor while observed prices spike; toggle to
             the operator's own offer book and compare its evening ramp with
             recorded prices. Then show errors for the full date range.
  hero     : open the app, add data-center demand, trip Sual, switch to LNG,
             and compare the model with recorded prices.

    python3 scripts/record-showcase.py backcast|hero|all
Outputs a .webm per clip into /tmp/studio-rec.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

# Reuse the workflow recorder's controls and caption banner.
sys.path.insert(0, str(Path(__file__).parent))
import importlib

_wf = importlib.import_module("record-workflows")
Rec, enter, sim, sysm, view = _wf.Rec, _wf.enter, _wf.sim, _wf.sysm, _wf.view
run, pick_day, edit_cell, tile, input_value = (
    _wf.run,
    _wf.pick_day,
    _wf.edit_cell,
    _wf.tile,
    _wf.input_value,
)
scroll_top, scroll_to = _wf.scroll_top, _wf.scroll_to
BASE, OUT, W, H = _wf.BASE, _wf.OUT, _wf.W, _wf.H


async def engine(page: Page, label: str, hold: float = 2.4):
    """Choose which generation offers the replay uses."""
    await page.get_by_role("tab", name=label, exact=False).click()
    await asyncio.sleep(hold)


async def chrono(page: Page):
    await view(page, "Hourly market replay", settle=1.0)


# Historical price comparison.


async def backcast(page: Page):
    r = Rec(page, 4)
    await enter(page)
    await r.intro(
        "Does the model check out against real prices?",
        "Replay observed market days and score the clear against the operator's "
        "own published prices. No parameters are fit to target prices.",
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

    await r.clear()
    await engine(page, "Observed offers", hold=0.6)
    off_mean = await tile(page, "Mean price, Luzon")
    await r.cap(
        "Published offers follow the recorded evening ramp",
        f"Same day, the modeled lines follow the recorded evening ramp hour by "
        f"hour ({off_mean} mean). Across the archive, the offer-book replay "
        f"reaches 0.73 to 0.87 "
        f"correlation with observed prices and 88 to 99 percent of the "
        f"inter-island flow direction.",
    )
    await scroll_to(page, "svg", "center")
    await asyncio.sleep(4.2)

    await view(page, "Replay accuracy")
    await scroll_top(page)
    mae = await tile(page, "Mean absolute error (MAE), Luzon")
    await r.cap(
        "The full date range reports the model error for each grid",
        f"Every full-coverage day is scored against recorded prices "
        f"(Luzon MAE {mae}). The cost model's gap to observed is not hidden: it "
        f"is reported as a difference between the published-offer replay and "
        f"the cost calculation. The view recalculates it from the current "
        f"archive.",
    )
    await asyncio.sleep(4.4)
    await scroll_to(page, "table", "center")
    await asyncio.sleep(3.2)
    await r.clear()
    await asyncio.sleep(0.5)


# Main studio tour.


async def hero(page: Page):
    r = Rec(page, 7)
    await enter(page)
    await r.intro(
        "Power Dispatch Studio",
        "A browser dispatch model for the Philippine grid. Build a scenario, "
        "calculate it locally, and compare it with the operator's "
        "recorded prices.",
        hold=3.0,
    )

    # 1. the object model
    await sysm(page)
    await view(page, "Generators")
    await r.cap(
        "The model includes plants, grid links, and island demand",
        "Every plant comes from the Department of Energy list. The model clears "
        "three island grids connected by two high-voltage direct-current links.",
    )
    await asyncio.sleep(3.0)

    # 2-3. does it match reality? cost floor, then the operator's own bids
    await sim(page)
    await chrono(page)
    await pick_day(page, "widest swing")
    await asyncio.sleep(0.6)
    await r.cap(
        "The cost calculation misses the recorded evening price spike",
        "On the widest-swing day the cost model clears flat at the P6 floor while "
        "the observed price (dashed) spikes into the evening.",
    )
    await scroll_to(page, "svg", "center")
    await asyncio.sleep(2.8)
    await r.clear()
    await engine(page, "Observed offers", hold=0.6)
    await r.cap(
        "Published offers follow the recorded evening ramp",
        "The modeled lines now follow the observed evening ramp hour by hour. "
        "Across the archive the offer book reaches 0.73 to 0.87 correlation with "
        "recorded prices.",
    )
    await scroll_to(page, "svg", "center")
    await asyncio.sleep(3.8)

    # 4-5. add the government data-center demand forecast
    await engine(page, "Cost model", hold=0.5)
    await sysm(page)
    await view(page, "Regions")
    load = await input_value(page, "Luzon Load (evening)")
    tgt = int(load + 1500)
    await r.cap(
        "Add the government's 1.5 GW data-center demand forecast",
        f"Raise Luzon evening load {int(load):,} to {tgt:,} MW, a flat 24/7 "
        f"data-center shape.",
    )
    await edit_cell(page, "Luzon Load (evening)", str(tgt), hold=1.4)
    await run(page)
    await asyncio.sleep(0.5)
    await sim(page)
    await chrono(page)
    await pick_day(page, "demand peak")
    m2 = await tile(page, "Mean price, Luzon")
    pk = await tile(page, "Window peak")
    rent = await tile(page, "Congestion rent")
    await r.cap(
        "The evening price shifts from coal to oil as the grid link reaches its limit",
        f"Luzon mean rises to {m2}, peak {pk}; the Leyte-Luzon corridor binds, "
        f"congestion rent {rent}.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.2)

    # 6-7. stress it: trip both Sual units on top
    await sysm(page)
    await view(page, "Generators")
    await r.cap(
        "Now stress it: trip both 647 MW Sual units",
        "SPI U1 and U2, among the largest units on Luzon, to 0 MW.",
    )
    await edit_cell(page, "SPI U1 Dependable", "0", hold=0.8)
    await edit_cell(page, "SPI U2 Dependable", "0", hold=1.0)
    await run(page)
    await asyncio.sleep(0.5)
    await sim(page)
    await view(page, "Power-shortfall risk")
    lolp = await tile(page, "Shortfall chance, Luzon (LOLP)")
    await r.cap(
        "Luzon shortfall chance rises",
        f"With the added demand and both Sual units gone, Luzon "
        f"loss-of-load probability reaches {lolp}: a reliability draw, not a "
        f"forecast.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.4)

    await r.intro(
        "The model runs in your browser and shows its sources",
        "Published inputs cite public records, and model assumptions are labeled.",
        hold=4.0,
    )
    await asyncio.sleep(0.5)


WORKFLOWS = {"backcast": backcast, "hero": hero}


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
