"""Record the three README workflows from the running studio.

Each recording edits an input, runs the calculation, and reads the result. Values
shown in captions are read from the app so they stay in sync with the current data.

Usage:
    python3 scripts/record-workflows.py wf1|wf2|wf3|all
Outputs a .webm per workflow into /tmp/studio-rec; convert with the ffmpeg recipe
in the studio README.

The workflows cover a 1,500 MW Luzon load increase, an outage of both 647 MW
Sual units, and a change from Malampaya gas to imported LNG.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5200/studio/"
OUT = Path("/tmp/studio-rec")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900

# Caption overlay.

CAPTION_JS = r"""
(args) => {
  const { step, total, title, sub, intro } = args;
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
      width:760px;padding:34px 40px;text-align:center;`;
    el.innerHTML = `<div style="font-size:15px;letter-spacing:.14em;
        text-transform:uppercase;
        color:var(--muted,#8a97a6);margin-bottom:12px;">Power Dispatch Studio</div>
      <div style="font-size:30px;font-weight:700;line-height:1.25;">${title}</div>
      <div style="font-size:17px;color:var(--muted,#9aa7b6);
        margin-top:12px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:20px;width:1180px;max-width:calc(100% - 40px);
    padding:16px 22px;display:flex;gap:16px;align-items:center;`;
  el.innerHTML = `
    <div style="flex:none;font-family:'Fira Code',monospace;font-size:13px;
      font-weight:600;
      color:var(--on-primary,#0b0f14);background:var(--primary,#4f8cff);
      border-radius:999px;padding:5px 11px;">${step}/${total}</div>
    <div style="min-width:0;">
      <div style="font-size:18px;font-weight:650;line-height:1.3;">${title}</div>
      ${sub ? `<div style="font-size:14.5px;color:var(--muted,#9aa7b6);margin-top:3px;
        line-height:1.35;">${sub}</div>` : ''}
    </div>`;
}
"""


class Rec:
    def __init__(self, page: Page, total: int):
        self.page = page
        self.total = total
        self.step = 0

    async def intro(self, title: str, sub: str = "", hold: float = 2.6):
        await self.page.evaluate(
            CAPTION_JS, {"intro": True, "title": title, "sub": sub}
        )
        await asyncio.sleep(hold)
        await self.clear()  # don't let the title card linger over the first view
        await asyncio.sleep(0.2)

    async def cap(self, title: str, sub: str = "", advance: bool = True):
        if advance:
            self.step += 1
        await self.page.evaluate(
            CAPTION_JS,
            {"step": self.step, "total": self.total, "title": title, "sub": sub},
        )

    async def clear(self):
        await self.page.evaluate("() => document.getElementById('demo-cap')?.remove()")


# Interaction helpers.


async def enter(page: Page):
    await page.goto(BASE, wait_until="networkidle")
    await asyncio.sleep(0.6)
    await page.get_by_role("button", name="Open Power Dispatch Studio").click()
    await page.wait_for_selector('[data-testid="studio"]', timeout=8000)
    await asyncio.sleep(0.7)


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


async def sysm(page: Page):
    # the input tables live in the rail's Model inputs group; sim() opens all
    await sim(page)


async def view(page: Page, name: str, settle: float = 0.9):
    await page.get_by_role("button", name=name, exact=False).first.click()
    await asyncio.sleep(settle)


async def run(page: Page):
    await page.get_by_role("button", name="Run the simulation").click()
    await asyncio.sleep(0.8)


async def pick_day(page: Page, needle: str):
    sel = page.get_by_label("Observed day to replay")
    for o in await sel.locator("option").all():
        if needle in (await o.inner_text()):
            await sel.select_option(value=await o.get_attribute("value"))
            await asyncio.sleep(0.7)
            return


async def edit_cell(page: Page, label: str, value: str, hold: float = 1.1):
    cell = page.get_by_label(label)
    await cell.scroll_into_view_if_needed()
    await cell.hover()
    await asyncio.sleep(0.35)
    await cell.fill(value)
    await cell.blur()
    await asyncio.sleep(hold)


async def scroll_to(page: Page, selector: str, block: str = "center"):
    await page.evaluate(
        """([sel, block]) => {
          const el = [...document.querySelectorAll(sel)]
            .find(e => e.offsetParent !== null);
          if (el) el.scrollIntoView({behavior:'smooth', block});
        }""",
        [selector, block],
    )
    await asyncio.sleep(0.9)


async def scroll_top(page: Page):
    """Keep the view's main result above the caption banner."""
    await page.evaluate(
        """() => {
          const s = document.querySelector('.studio__scroll');
          if (s) s.scrollTo({top:0, behavior:'smooth'});
          window.scrollTo({top:0, behavior:'smooth'});
        }"""
    )
    await asyncio.sleep(0.9)


async def tile(page: Page, label: str) -> str:
    """Read a StatTile value from the running app for use in a caption."""
    loc = page.locator(".stat", has=page.locator(".stat__label", has_text=label))
    v = await loc.first.locator(".stat__value").inner_text()
    return " ".join(v.split())


async def compare_delta(page: Page, row_label: str) -> str:
    """The B-A cell of a Compare-two-runs row, read live."""
    row = page.locator("tr", has=page.locator("td", has_text=row_label)).first
    cells = row.locator("td")
    n = await cells.count()
    v = await cells.nth(n - 1).inner_text()
    return " ".join(v.split())


async def input_value(page: Page, aria_label: str) -> float:
    v = await page.locator(f'input[aria-label="{aria_label}"]').first.input_value()
    return float(v.replace(",", ""))


# Workflow 1: price a data-center build.


async def wf1(page: Page):
    r = Rec(page, 6)
    await enter(page)
    await r.intro(
        "Workflow 1: Price a data-center build",
        "Raise Luzon load by the announced MW and read what the evening costs.",
    )

    await sim(page)
    await view(page, "Hourly market replay")
    await pick_day(page, "demand peak")
    wf1_base_mean = await tile(page, "Mean price, Luzon")
    await r.cap(
        "Base case, the demand-peak day",
        f"The Luzon day clears at a {wf1_base_mean} mean on the coal margin.",
    )
    await scroll_top(page)
    await asyncio.sleep(2.6)

    await sysm(page)
    await view(page, "Regions")
    wf1_load = await input_value(page, "Luzon Load (evening)")
    wf1_target = int(wf1_load + 1500)
    await r.cap(
        "Add the 1,500 MW 2028 government forecast",
        f"The grid load edit adds the same demand in all 24 hours. "
        f"Luzon {int(wf1_load):,} to {wf1_target:,} MW.",
    )
    await edit_cell(page, "Luzon Load (evening)", str(wf1_target), hold=1.6)

    await r.cap(
        "Calculate all three island grids together",
        "The model balances supply, demand, and power transfers between the grids.",
    )
    await run(page)
    await asyncio.sleep(0.6)

    await sim(page)
    await view(page, "Hourly market replay")
    await pick_day(page, "demand peak")
    wf1_mean2 = await tile(page, "Mean price, Luzon")
    wf1_peak2 = await tile(page, "Window peak")
    wf1_rent2 = await tile(page, "Congestion rent")
    await r.cap(
        "The evening flips coal to oil",
        f"Mean {wf1_base_mean} to {wf1_mean2}, peak {wf1_peak2}. "
        "The added load reaches the Leyte-Luzon high-voltage direct-current "
        "link limit; congestion rent "
        f"{wf1_rent2}.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.0)
    await scroll_to(page, "svg[aria-label='Dispatch by fuel over the run window']")
    await asyncio.sleep(2.6)

    await r.cap(
        "Save this run, then restore the base case",
        "A saved run keeps the settings, time window, and hourly results "
        "for comparison.",
    )
    await scroll_to(page, ".chrono__controls", block="start")
    await page.get_by_role("button", name="Save run").click()
    await asyncio.sleep(1.4)
    await sysm(page)
    await view(page, "Regions")
    await page.get_by_role("button", name="Revert to base value").first.click()
    await asyncio.sleep(1.0)
    await run(page)
    await sim(page)
    await view(page, "Hourly market replay")
    await pick_day(page, "demand peak")
    await page.get_by_role("button", name="Save run").click()
    await asyncio.sleep(1.2)

    await view(page, "Saved simulation runs")
    await scroll_to(page, "table", block="center")
    d_mean = await compare_delta(page, "Mean price, Luzon")
    d_rent = await compare_delta(page, "Congestion rent")
    await r.cap(
        "Compare two runs: the price of the build",
        f"The build costs {d_mean}/kWh on the Luzon day and {d_rent}M "
        "in congestion rent.",
    )
    await asyncio.sleep(4.2)
    await r.clear()
    await asyncio.sleep(0.6)


# Workflow 2: test an outage of the two largest Sual units.


async def wf2(page: Page):
    r = Rec(page, 6)
    await enter(page)
    await r.intro(
        "Workflow 2: Remove two major Luzon units",
        "Take the two 647 MW Sual units out of service and recalculate shortfall risk.",
    )

    await sim(page)
    await view(page, "Power-shortfall risk")
    wf2_base_lolp = await tile(page, "Shortfall chance, Luzon (LOLP)")
    wf2_base_p99 = await tile(page, "1-in-100 shed, Luzon")
    await r.cap(
        "Current Luzon shortfall chance",
        f"With the current settings, Luzon shortfall chance is {wf2_base_lolp}; "
        f"the 1-in-100 shortfall is {wf2_base_p99} MW.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.0)

    await sysm(page)
    await view(page, "Generators")
    await r.cap(
        "Trip the plant: zero both 647 MW Sual units",
        "SPI U1 and SPI U2, among the largest units on the Luzon grid, to 0 MW.",
    )
    await edit_cell(page, "SPI U1 Dependable", "0", hold=0.9)
    await edit_cell(page, "SPI U2 Dependable", "0", hold=1.3)

    await r.cap(
        "Recalculate dispatch and power-shortfall risk",
        "The model clears the three grids again, then repeats the calculation "
        "with random plant outages.",
    )
    await run(page)
    await asyncio.sleep(0.6)

    await sim(page)
    await view(page, "Power-shortfall risk")
    wf2_lolp = await tile(page, "Shortfall chance, Luzon (LOLP)")
    await r.cap(
        f"Luzon shortfall chance rises to {wf2_lolp}",
        f"Base case {wf2_base_lolp}: removing 1,294 MW of coal reduces "
        "Luzon's evening supply margin.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.4)

    await view(page, "Loss of one major unit (N-1)")
    await scroll_to(page, "table")
    await r.cap(
        "A second large-unit outage pushes Luzon from coal to oil",
        "The table shows the price after each remaining unit is taken out of service.",
    )
    await asyncio.sleep(4.0)

    await view(page, "Hourly market replay")
    await pick_day(page, "demand peak")
    wf2_mean = await tile(page, "Mean price, Luzon")
    wf2_rent = await tile(page, "Congestion rent")
    await r.cap(
        "The selected day clears at a higher price without a power shortfall",
        f"With both Sual units out, the selected evening still serves all demand. "
        f"The {wf2_lolp} shortfall chance comes from repeated outage "
        f"simulations, not this day. Luzon mean {wf2_mean}; congestion rent "
        f"{wf2_rent} when the links reach their limits.",
    )
    await scroll_top(page)
    await asyncio.sleep(3.2)
    await scroll_to(page, "svg[aria-label='Dispatch by fuel over the run window']")
    await asyncio.sleep(2.6)
    await r.clear()
    await asyncio.sleep(0.6)


# Workflow 3: test a switch from Malampaya gas to imported LNG.


async def wf3(page: Page):
    r = Rec(page, 8)
    await enter(page)
    await r.intro(
        "Workflow 3: Test Malampaya gas depletion",
        "Reprice gas from Malampaya to imported liquefied natural gas, then "
        "combine it with added demand and dry-year hydrology.",
    )

    await sim(page)
    await view(page, "Hourly market replay")
    await pick_day(page, "widest swing")
    wf3_base_mean = await tile(page, "Mean price, Luzon")
    await r.cap(
        "Base case: gas at the Malampaya cost ₱4.80",
        f"The Luzon day clears at a {wf3_base_mean} mean on the coal margin.",
    )
    await scroll_top(page)
    await asyncio.sleep(2.6)

    await sysm(page)
    await view(page, "Fuels")
    await r.cap(
        "Malampaya depletes: reprice gas to imported LNG",
        "Natural gas ₱4.80 to ₱10.30/kWh, the imported-LNG estimate.",
    )
    await edit_cell(page, "natural gas Price", "10.30", hold=1.6)

    await r.cap(
        "Recalculate with imported LNG",
        "The model rebuilds the lowest-cost-first supply order and calculates "
        "new prices.",
    )
    await run(page)
    await asyncio.sleep(0.6)

    await sim(page)
    await view(page, "Hourly market replay")
    await pick_day(page, "widest swing")
    wf3_mean2 = await tile(page, "Mean price, Luzon")
    wf3_rent2 = await tile(page, "Congestion rent")
    await r.cap(
        "The whole price shape lifts to the gas cost",
        f"Mean {wf3_base_mean} to {wf3_mean2}. Natural gas, not coal, now "
        "sets the price. "
        f"Congestion rent {wf3_rent2}.",
    )
    await scroll_top(page)
    await asyncio.sleep(2.8)
    await scroll_to(page, "svg[aria-label='Hourly series over the run window']")
    await asyncio.sleep(2.6)

    await r.cap(
        "Share the exact scenario",
        "Copy link stores the scenario and run window in the URL. No project "
        "file is needed.",
    )
    await scroll_to(page, ".chrono__controls", block="start")
    await page.get_by_role("button", name="Copy link").click()
    await asyncio.sleep(2.2)

    await sysm(page)
    await view(page, "Quick what-if")
    await page.wait_for_selector('[data-testid="scenario"]')

    await page.get_by_text("Switch gas to imported LNG").click()
    await asyncio.sleep(0.4)
    await scroll_top(page)  # keep the Clearing price / vs-base tiles in frame
    wf3_cp1 = await tile(page, "Clearing price")
    wf3_vs1 = await tile(page, "vs base case")
    await r.cap(
        "First change: switch to imported liquefied natural gas",
        f"Each setting recalculates prices. LNG alone: {wf3_cp1}, {wf3_vs1} over base.",
    )
    await asyncio.sleep(3.0)

    dc = page.locator("input.lever__range").first
    for v in ("500", "1000", "1500"):
        await dc.fill(v)
        await asyncio.sleep(0.35)
    await scroll_top(page)
    wf3_cp2 = await tile(page, "Clearing price")
    await r.cap(
        "Add the announced 1,500 MW build",
        f"The evening clears at {wf3_cp2} with the build on top of LNG pricing.",
    )
    await asyncio.sleep(3.0)

    await page.get_by_role("button", name="Dry (El Nino)").click()
    await asyncio.sleep(0.4)
    await scroll_top(page)
    wf3_cp3 = await tile(page, "Clearing price")
    wf3_vs3 = await tile(page, "vs base case")
    await r.cap(
        "Less hydro plus added demand pushes the evening price to oil",
        f"Clearing price {wf3_cp3}, {wf3_vs3}/kWh vs base. Each change alone "
        "stops short of oil; together they cross it.",
    )
    await asyncio.sleep(3.6)
    await r.clear()
    await asyncio.sleep(0.6)


WORKFLOWS = {"wf1": wf1, "wf2": wf2, "wf3": wf3}


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
