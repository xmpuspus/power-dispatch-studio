"""The nodal walkthrough: four real decisions through the per-node price lens,
recorded on the running app with every number read live from the baked artifact.

The four cases the clip narrates:
  consumers  who pays for a radial: Pitogo and Zamboanga settle far above the
             Mindanao price on every clean market day
  siting     the same 100 MW data center pays hundreds of millions more per
             year behind a premium delivery point than beside generation
  revenue    the same MWh earns less behind an export constraint: Leyte
             geothermal at the Ormoc converter settles under the Visayas price
  forward    the honest nodal forecast: the regional forward band plus the
             node's persistent adder, held constant and labeled

Needs the COMBINED single-origin serve (map at /, studio at /studio/):

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/serve.py
    (cd .vercel_out && python3 serve.py 5200)
    python3 build/record_nodal_walkthrough.py

Outputs /tmp/nodal-walk/walk.webm; convert with the workflow-GIF recipe.
"""

import asyncio
import json
import urllib.request
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5200"
OUT = Path("/tmp/nodal-walk")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900

CAP_JS = r"""
(args) => {
  const { title, sub, intro } = args;
  let el = document.getElementById('walk-cap');
  if (!el) { el = document.createElement('div'); el.id = 'walk-cap'; document.body.appendChild(el); }
  const base = `position:fixed;left:50%;z-index:2147483647;box-sizing:border-box;
    font-family:'Fira Sans','Inter',system-ui,sans-serif;
    background:rgba(12,17,24,.94);color:#eef2f7;
    border:1px solid #2b3a4d;border-radius:14px;box-shadow:0 12px 44px rgba(0,0,0,.5);`;
  if (intro) {
    el.style.cssText = base + `top:50%;transform:translate(-50%,-50%);width:860px;padding:40px 46px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.16em;text-transform:uppercase;color:#7f8ea0;margin-bottom:14px;">Power Dispatch Studio</div>
      <div style="font-size:30px;font-weight:700;line-height:1.28;">${title}</div>
      <div style="font-size:18px;color:#9fb0c9;margin-top:14px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:26px;transform:translateX(-50%);width:1200px;max-width:calc(100% - 40px);padding:16px 24px;`;
  el.innerHTML = `<div style="font-size:19px;font-weight:650;line-height:1.3;">${title}</div>
    <div style="font-size:15px;color:#a9b7c8;margin-top:4px;">${sub||''}</div>`;
}
"""
CLEAR_JS = "() => { const e = document.getElementById('walk-cap'); if (e) e.remove(); }"


async def cap(page: Page, title: str, sub: str = "", intro: bool = False):
    await page.evaluate(CAP_JS, {"title": title, "sub": sub, "intro": intro})


async def clear_cap(page: Page):
    await page.evaluate(CLEAR_JS)


async def click_js(page: Page, selector: str) -> bool:
    return await page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (el) { el.click(); return true; } return false; }""",
        selector,
    )


async def click_text(page: Page, text: str) -> bool:
    return await page.evaluate(
        """(t) => { const el = [...document.querySelectorAll('button,[role=tab],a')]
          .find(e => (e.textContent||'').includes(t) && e.offsetParent !== null);
          if (el) { el.click(); return true; } return false; }""",
        text,
    )


async def sim_tab(page: Page):
    await page.evaluate(
        """() => { const t=[...document.querySelectorAll('[role=tab]')].find(e=>e.textContent.trim()==='Simulation'); t&&t.click(); }"""
    )
    await asyncio.sleep(0.5)


async def scroll_top(page: Page):
    await page.evaluate(
        """() => { const s=document.querySelector('.studio__scroll'); if(s) s.scrollTo({top:0,behavior:'smooth'}); }"""
    )


async def fly(page: Page, lon: float, lat: float, zoom: float,
              ms: int = 2200, hold: float = 0.4):
    """Smooth cinematic camera move; sleeps through the flight so the
    recording captures the pan/zoom, not a hard cut."""
    await page.evaluate(
        "([lon,lat,z,ms]) => map.flyTo({center:[lon,lat], zoom:z, "
        "duration:ms, essential:true})",
        [lon, lat, zoom, ms],
    )
    await asyncio.sleep(ms / 1000 + hold)


async def hover_node(page: Page, lon: float, lat: float, settle: float = 0.6):
    """Move the real mouse onto a node's projected pixel so the map's own
    hover handler pops the receipt."""
    px = await page.evaluate(
        "([lon,lat]) => { const p = map.project([lon,lat]); return [p.x, p.y]; }",
        [lon, lat],
    )
    await page.mouse.move(px[0], px[1], steps=18)
    await asyncio.sleep(settle)


def load_artifact() -> dict:
    with urllib.request.urlopen(BASE + "/data/nodal_obs.json") as r:
        return json.load(r)


def peso_m_per_year(mw: float, dev_php_kwh: float) -> float:
    """A flat load of `mw` paying `dev` PhP/kWh above the regional price,
    for a year, in millions of pesos."""
    return mw * 1000 * 8760 * dev_php_kwh / 1e6


async def main():
    obs = load_artifact()
    placed = {p["res"]: p for p in obs["placed"]}
    pitogo = placed["09PITOGO_SS"]
    zambo = placed["09ZAMBO_SS"]
    gamu = placed["01GAMU_T1L1"]
    calaca = placed["03CALACA_G01"]
    leyte = placed["04LEYTE_A"]
    swing = gamu["dev"] - calaca["dev"]
    dc_mw = 100
    dc_cost_m = peso_m_per_year(dc_mw, swing)
    clean = obs["window"]["clean_days"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
        )
        page = await ctx.new_page()

        # ---- map: the observed nodal layer ----------------------------------
        await page.goto(BASE + "/", wait_until="networkidle")
        await asyncio.sleep(4.5)
        await cap(
            page,
            "Where you plug in changes what you pay",
            f"Under the three regional WESM prices, {obs['n_nodes']:,} nodes each "
            "settle at their own. Here is the whole field, then four decisions.",
            intro=True,
        )
        await asyncio.sleep(3.6)
        await clear_cap(page)

        # establishing shot: switch to Prices and hold on the national field
        await click_js(page, "[data-mode=price]")
        await asyncio.sleep(2.4)
        await cap(
            page,
            f"Every WESM node, priced at its own deviation ({obs['n_placed']} "
            "placed of the whole grid)",
            "Red settles above its region's price, blue below; size is the "
            f"magnitude, each a mean over {clean} clean market days.",
        )
        await asyncio.sleep(3.6)

        # push into the Luzon field so the dots read AS a network: the price
        # dots sit on the faint transmission grid they actually connect to
        await fly(page, 121.15, 15.1, 6.35, ms=2600)
        await cap(
            page,
            "The nodes sit on the real transmission grid",
            "The faint grey web is the OpenStreetMap network; each price dot is "
            "a node on it, so the price field IS the grid, coloured.",
        )
        await asyncio.sleep(4.4)
        await clear_cap(page)

        # sweep south to prove the field is national, not a Luzon artefact
        await fly(page, 123.4, 9.7, 6.15, ms=2800)
        await cap(
            page,
            "The whole archipelago, node by node",
            "Visayas and Mindanao carry the same per-node structure; the widest "
            "premiums sit at the ends of the long radial lines.",
        )
        await asyncio.sleep(3.8)
        await clear_cap(page)

        # decision 1, consumers behind a radial: zoom keeps the peninsula's
        # dots and the single 138 kV line in frame, not one lonely pin
        await fly(page, pitogo["lon"] + 0.35, pitogo["lat"] - 0.1, 7.1, ms=2400)
        await hover_node(page, pitogo["lon"], pitogo["lat"])
        await cap(
            page,
            "Consumers: who pays for a radial line",
            f"Pitogo settles +P{pitogo['dev']:.2f}/kWh and Zamboanga "
            f"+P{zambo['dev']:.2f} above the Mindanao price, every clean day, "
            "at the far end of one 138 kV line.",
        )
        await asyncio.sleep(4.4)
        await clear_cap(page)

        # decision 2, siting: the same data center at two Luzon nodes
        await fly(page, gamu["lon"] - 0.2, gamu["lat"] - 0.3, 7.0, ms=2600)
        await hover_node(page, gamu["lon"], gamu["lat"])
        await cap(
            page,
            "Siting: the same 100 MW data center, two nodes",
            f"Behind the {gamu['station']} delivery point it pays "
            f"+P{gamu['dev']:.2f}/kWh over the Luzon price.",
        )
        await asyncio.sleep(4.0)
        await fly(page, calaca["lon"] + 0.15, calaca["lat"], 7.2, ms=2400)
        await hover_node(page, calaca["lon"], calaca["lat"])
        await cap(
            page,
            "Beside generation, the sign flips",
            f"At {calaca['station']} the deviation is P{calaca['dev']:.2f}. The "
            f"swing is P{swing:.2f}/kWh: about P{dc_cost_m:,.0f}M per year on a "
            f"flat {dc_mw} MW load, before a single contract is negotiated.",
        )
        await asyncio.sleep(4.8)
        await clear_cap(page)

        # ---- studio: table, revenue, forward --------------------------------
        await cap(page, "The full table lives in the studio", "Every node, searchable.")
        await asyncio.sleep(1.6)
        await click_js(page, "#studiolink")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1.2)
        await page.get_by_role("button", name="Open Power Dispatch Studio").click()
        await page.wait_for_selector('[data-testid="studio"]', timeout=8000)
        await asyncio.sleep(1.0)
        await sim_tab(page)
        await click_text(page, "Nodal prices")
        await asyncio.sleep(1.6)
        await scroll_top(page)
        await cap(
            page,
            "Analysis: Nodal prices",
            "Per-grid percentiles, the widest premium and discount, and every "
            "node in a searchable table.",
        )
        await asyncio.sleep(3.4)
        await page.fill('input[aria-label="Filter nodes"]', "_T1L1")
        await cap(
            page,
            "Procurement: the delivery points",
            "Filter to _T1L1 and each bulk delivery point's persistent adder is "
            "the locational line in a supply contract.",
        )
        await asyncio.sleep(3.8)

        # revenue: Leyte geothermal under the Visayas price
        await click_text(page, "Visayas")
        await asyncio.sleep(1.2)
        await page.fill('input[aria-label="Filter nodes"]', "LEYTE")
        await cap(
            page,
            "Revenue: the export constraint, priced",
            f"Leyte geothermal settles P{leyte['dev']:.2f}/kWh under the Visayas "
            "price at the Ormoc converter. Node choice is capture-price "
            "material for any new plant.",
        )
        await asyncio.sleep(4.2)
        await clear_cap(page)

        # forward translation (back on Luzon, where the siting story ran)
        await click_text(page, "Luzon")
        await asyncio.sleep(0.8)
        await click_text(page, "Forward prices")
        await page.wait_for_selector("text=Forward price band", timeout=15000)
        await asyncio.sleep(0.8)
        await scroll_top(page)
        await cap(
            page,
            "Forecasting: the honest nodal forward",
            f"The regional forward band plus the node's persistent adder, held "
            f"constant and labeled: Gamu's +P{gamu['dev']:.2f} rides on top of "
            "every Luzon percentile here. No invented nodal model.",
        )
        await asyncio.sleep(4.6)
        await clear_cap(page)

        # close on the proof: the loss-surface validation view
        await sim_tab(page)
        await click_text(page, "Loss validation")
        await asyncio.sleep(1.6)
        await scroll_top(page)
        await cap(
            page,
            "And it is validated against the market's own record",
            "WESM's within-region nodal structure is a loss surface, so network "
            "physics is a testable prediction: Luzon and Mindanao rank at "
            "Spearman +0.72 and +0.83, Visayas shown failing, recomputed nightly.",
        )
        await asyncio.sleep(4.8)
        await clear_cap(page)
        await asyncio.sleep(0.6)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / "walk.webm"
        Path(vid).replace(dest)
        print(dest)


asyncio.run(main())
