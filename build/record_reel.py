"""One reel across the whole platform: the map's five modes and in-browser
simulate, a real click through to the studio, the Start-simulating onboarding,
a live Quick-scenario what-if (data-center wave, then a Sual trip), the backcast
proof, reliability, and a fast sweep of the deep analyses. Every number on screen
is read live from the running app.

Needs the COMBINED single-origin serve (map at /, studio at /studio/) so the
"Open the dispatch studio" link is a real navigation, not a cut:

    bash scripts/vercel_build.sh            # or the manual assemble
    (cd .vercel_out && python3 serve.py 5200)
    python3 build/record_reel.py

Outputs /tmp/reel/reel.webm; convert with the ffmpeg recipe in the README.
"""

import asyncio
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5200"
OUT = Path("/tmp/reel")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900

# caption banner: explicit colors (no CSS vars) so it reads the same on the map
# and in the studio, and re-injected after the cross-page navigation.
CAP_JS = r"""
(args) => {
  const { title, sub, intro } = args;
  let el = document.getElementById('reel-cap');
  if (!el) { el = document.createElement('div'); el.id = 'reel-cap'; document.body.appendChild(el); }
  const base = `position:fixed;left:50%;z-index:2147483647;box-sizing:border-box;
    font-family:'Fira Sans','Inter',system-ui,sans-serif;
    background:rgba(12,17,24,.94);color:#eef2f7;
    border:1px solid #2b3a4d;border-radius:14px;box-shadow:0 12px 44px rgba(0,0,0,.5);`;
  if (intro) {
    el.style.cssText = base + `top:50%;transform:translate(-50%,-50%);width:820px;padding:40px 46px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.16em;text-transform:uppercase;color:#7f8ea0;margin-bottom:14px;">Power Dispatch Studio</div>
      <div style="font-size:32px;font-weight:700;line-height:1.25;">${title}</div>
      <div style="font-size:18px;color:#9fb0c9;margin-top:14px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:26px;transform:translateX(-50%);width:1200px;max-width:calc(100% - 40px);padding:16px 24px;`;
  el.innerHTML = `<div style="font-size:19px;font-weight:650;line-height:1.3;">${title}</div>
    <div style="font-size:15px;color:#a9b7c8;margin-top:4px;">${sub||''}</div>`;
}
"""
CLEAR_JS = "() => { const e = document.getElementById('reel-cap'); if (e) e.remove(); }"
# smooth slider/number ramp with real input events (the tool re-clears live)
ANIM_JS = r"""
(args) => { const [id,to,ms]=args; const el=document.getElementById(id); if(!el) return;
  const from=+el.value, t0=performance.now();
  return new Promise(r=>{ function f(t){ const k=Math.min(1,(t-t0)/ms);
    el.value=Math.round(from+(to-from)*k); el.dispatchEvent(new Event('input',{bubbles:true}));
    k<1?requestAnimationFrame(f):r(); } requestAnimationFrame(f); }); }
"""


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


async def map_beats(page: Page):
    await page.goto(BASE + "/", wait_until="networkidle")
    await asyncio.sleep(4.5)  # basemap tiles + baked data
    await cap(
        page,
        "Can the Philippine grid host the announced data-center wave?",
        "A production-cost model of the WESM, built on the market operator's own public files.",
        intro=True,
    )
    await asyncio.sleep(3.2)
    await clear_cap(page)
    await asyncio.sleep(0.3)

    await click_js(page, "[data-mode=supply]")
    await cap(page, "Supply", "The May 2026 system margin against the announced megawatts.")
    await asyncio.sleep(2.6)
    await click_js(page, "[data-mode=choke]")
    await cap(page, "Choke points", "Named 230 kV equipment ranked by days at a binding limit.")
    await asyncio.sleep(2.6)
    await click_js(page, "[data-mode=price]")
    await cap(page, "Prices", "The three island grids fanning apart after the market reopened.")
    await asyncio.sleep(2.6)

    # simulate on the map: add a data center, the clearing price flips coal to oil
    await click_js(page, "[data-mode=simulate]")
    await asyncio.sleep(1.6)
    await cap(page, "Simulate, in your browser", "Add a data center and the merit-order price re-clears live.")
    await page.evaluate(ANIM_JS, ["sim-dc", 3000, 3600])
    await asyncio.sleep(3.6)
    await clear_cap(page)


async def studio_beats(page: Page):
    # real click-through to the studio (single origin: /studio/)
    await cap(page, "Open the dispatch studio", "Edit the fleet, replay observed days, read the backcast.")
    await asyncio.sleep(1.8)
    await click_js(page, "#studiolink")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1.2)
    # studio landing splash -> open
    await page.get_by_role("button", name="Open Power Dispatch Studio").click()
    await page.wait_for_selector('[data-testid="studio"]', timeout=8000)
    await asyncio.sleep(1.0)

    # onboarding: the Start-simulating banner on the Generators landing
    await cap(page, "Start simulating", "The studio opens on the real DOE fleet and points the way in.")
    await asyncio.sleep(2.4)
    await click_text(page, "Start simulating")
    await asyncio.sleep(1.2)

    # Quick scenario: a live what-if, no Run (native setter so React re-clears)
    await cap(page, "A data-center wave", "Drag the lever, the three grids re-clear live, no Run.")
    await ramp_lever(page, "Add a data center", 2500, 3000)
    await asyncio.sleep(2.8)  # hold on the coal-to-oil flip
    await cap(page, "Trip the biggest unit", "A Sual coal unit drops on top of the wave.")
    await trip_unit(page, "Sual")
    await asyncio.sleep(2.6)
    await clear_cap(page)

    # Backcast: the proof
    await sim_tab(page)
    await click_text(page, "Backcast")
    await asyncio.sleep(1.0)
    await scroll_top(page)
    await cap(page, "Does the model track reality?", "The cost model against the observed price tape. Nothing tuned.")
    await asyncio.sleep(3.0)
    await click_text(page, "Observed offers")
    await cap(page, "On the operator's own offer book", "The modeled evening tracks the observed ramp, hour by hour.")
    await asyncio.sleep(3.2)
    await clear_cap(page)

    # Reliability
    await click_text(page, "Reliability")
    await asyncio.sleep(1.0)
    await scroll_top(page)
    await cap(page, "Probabilistic reliability", "Forced-outage Monte Carlo. Loss-of-load probability, not a point estimate.")
    await asyncio.sleep(3.0)
    await clear_cap(page)

    # analysis breadth: a fast sweep of the deep views
    await cap(page, "And the deep analyses", "Reserve market, the Meralco bill, forward prices, emissions, and more.")
    for name in ["Reserve market", "Bill impact", "Forward prices", "Emissions"]:
        ok = await click_text(page, name)
        if ok:
            await asyncio.sleep(0.4)
            await scroll_top(page)
            await asyncio.sleep(1.3)

    await clear_cap(page)
    await cap(
        page,
        "Free, open, and every number sourced.",
        "power-dispatch-studio.vercel.app",
        intro=True,
    )
    await asyncio.sleep(3.2)
    await clear_cap(page)


async def ramp_lever(page: Page, label: str, to: int, ms: int):
    # React controlled input: use the native value setter so onChange fires
    await page.evaluate(
        """(args) => { const [label,to,ms]=args;
          const setV=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
          const l=[...document.querySelectorAll('.lever')].find(x=>x.textContent.includes(label));
          const el=l && l.querySelector('input[type=range]'); if(!el) return;
          const from=+el.value, t0=performance.now();
          return new Promise(r=>{ function f(t){ const k=Math.min(1,(t-t0)/ms);
            const nv=Math.round((from+(to-from)*k)/50)*50; setV.call(el,String(nv));
            el.dispatchEvent(new Event('input',{bubbles:true}));
            k<1?requestAnimationFrame(f):r(); } requestAnimationFrame(f); }); }""",
        [label, to, ms],
    )


async def trip_unit(page: Page, needle: str):
    await page.evaluate(
        """(needle) => { const setV=Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype,'value').set;
          const l=[...document.querySelectorAll('.lever')].find(x=>/Trip a unit/.test(x.textContent));
          const sel=l && l.querySelector('select'); if(!sel) return;
          const opt=[...sel.options].find(o=>o.text.includes(needle)); if(!opt) return;
          setV.call(sel,opt.value); sel.dispatchEvent(new Event('change',{bubbles:true})); }""",
        needle,
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
    await asyncio.sleep(0.8)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
            device_scale_factor=1,
        )
        page = await ctx.new_page()
        await map_beats(page)
        await studio_beats(page)
        await asyncio.sleep(0.5)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / "reel.webm"
        Path(vid).replace(dest)
        print(dest)


if __name__ == "__main__":
    asyncio.run(main())
