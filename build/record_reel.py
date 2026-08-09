"""Record the main map and studio functions from the running app.

The recording covers the five map modes, a data-center scenario, a Sual outage,
the historical price comparison, power-shortfall risk, and four analysis views.
Values shown on screen are read from the app.

Needs the COMBINED single-origin serve (map at /, studio at /studio/) so the
"Open the dispatch studio" link is a real navigation, not a cut:

    bash scripts/vercel_build.sh            # or the manual assemble
    (cd .vercel_out && python3 serve.py 5200)
    python3 build/record_reel.py

Outputs /tmp/reel/reel.webm. The recipe used to live in the README and was lost
in the 2026-07-31 rebuild, which meant the next regeneration re-improvised it
and the reel changed size and quality with no record of why. It lives here now.
The two commands below give 3.3 MB of mp4 and 11.8 MB of gif from a 70-second
1440x900 capture:

    ffmpeg -y -i /tmp/reel/reel.webm -c:v libx264 -pix_fmt yuv420p -crf 26 \
      -preset slow -movflags +faststart docs/reel.mp4

    ffmpeg -y -i /tmp/reel/reel.webm \
      -vf "fps=5,scale=900:-1:flags=lanczos,palettegen=max_colors=192:stats_mode=diff" \
      /tmp/reel/pal.png
    ffmpeg -y -i /tmp/reel/reel.webm -i /tmp/reel/pal.png \
      -lavfi "fps=5,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
      docs/reel.gif

Delete any older webm in /tmp/reel first and check the mtime before converting.
A stale webm converts without complaint and ships a demo of the previous build.
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
  if (!el) {
    el = document.createElement('div');
    el.id = 'reel-cap';
    document.body.appendChild(el);
  }
  const base = `position:fixed;left:50%;z-index:2147483647;box-sizing:border-box;
    font-family:'Fira Sans','Inter',system-ui,sans-serif;
    background:rgba(12,17,24,.94);color:#eef2f7;
    border:1px solid #2b3a4d;border-radius:14px;box-shadow:0 12px 44px rgba(0,0,0,.5);`;
  if (intro) {
    el.style.cssText = base + `top:50%;transform:translate(-50%,-50%);
      width:820px;padding:40px 46px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.16em;
      text-transform:uppercase;color:#7f8ea0;margin-bottom:14px;">
      Power Dispatch Studio</div>
      <div style="font-size:32px;font-weight:700;line-height:1.25;">${title}</div>
      <div style="font-size:18px;color:#9fb0c9;margin-top:14px;">${sub||''}</div>`;
    return;
  }
  el.style.cssText = base + `bottom:26px;transform:translateX(-50%);
    width:1200px;max-width:calc(100% - 40px);padding:16px 24px;`;
  el.innerHTML = `<div style="font-size:19px;font-weight:650;
    line-height:1.3;">${title}</div>
    <div style="font-size:15px;color:#a9b7c8;margin-top:4px;">${sub||''}</div>`;
}
"""
CLEAR_JS = "() => { const e = document.getElementById('reel-cap'); if (e) e.remove(); }"
# Smooth slider and number motion with real input events; the calculation updates live.
ANIM_JS = r"""
(args) => { const [id,to,ms]=args; const el=document.getElementById(id); if(!el) return;
  const from=+el.value, t0=performance.now();
  return new Promise(r=>{ function f(t){ const k=Math.min(1,(t-t0)/ms);
    el.value=Math.round(from+(to-from)*k);
    el.dispatchEvent(new Event('input',{bubbles:true}));
    k<1?requestAnimationFrame(f):r(); } requestAnimationFrame(f); }); }
"""


async def cap(page: Page, title: str, sub: str = "", intro: bool = False):
    await page.evaluate(CAP_JS, {"title": title, "sub": sub, "intro": intro})


async def clear_cap(page: Page):
    await page.evaluate(CLEAR_JS)


async def click_js(page: Page, selector: str) -> bool:
    return await page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (el) { el.click(); return true; }
          return false;
        }""",
        selector,
    )


async def click_text(page: Page, text: str) -> bool:
    return await page.evaluate(
        """(t) => { const el = [...document.querySelectorAll('button,[role=tab],a')]
          .find(e => (e.textContent||'').includes(t) && e.offsetParent !== null);
          if (el) { el.click(); return true; } return false; }""",
        text,
    )


async def record_map(page: Page):
    await page.goto(BASE + "/", wait_until="networkidle")
    await asyncio.sleep(4.5)  # basemap tiles + generated data
    await cap(
        page,
        "Can the Philippine grid carry the announced data-center demand?",
        "A production-cost model of the WESM, built on the market operator's "
        "public files.",
        intro=True,
    )
    await asyncio.sleep(3.2)
    await clear_cap(page)
    await asyncio.sleep(0.3)

    await click_js(page, "[data-mode=supply]")
    await cap(
        page,
        "Can existing supply cover announced data-center demand?",
        "The May 2026 system margin is shown beside each announced project "
        "or forecast.",
    )
    await asyncio.sleep(2.6)
    await click_js(page, "[data-mode=choke]")
    await cap(
        page,
        "The Leyte-Cebu corridor reached a binding limit most often",
        "Named 230 kV equipment ranked by days at a binding limit.",
    )
    await asyncio.sleep(2.6)
    await click_js(page, "[data-mode=price]")
    await cap(
        page,
        "Island-grid prices separated after market pricing resumed",
        "Recorded daily prices for Luzon, Visayas, and Mindanao.",
    )
    await asyncio.sleep(2.6)

    # simulate on the map: add a data center, the clearing price flips coal to oil
    await click_js(page, "[data-mode=simulate]")
    await asyncio.sleep(1.6)
    await cap(
        page,
        "Test a scenario in your browser",
        "Add a data center and the lowest-cost-first price clears again.",
    )
    await page.evaluate(ANIM_JS, ["sim-dc", 3000, 3600])
    await asyncio.sleep(3.6)
    await clear_cap(page)


async def record_studio(page: Page):
    # real click-through to the studio (single origin: /studio/)
    await cap(
        page,
        "Open the dispatch studio",
        "Edit the fleet, replay recorded days, and check the historical replay.",
    )
    await asyncio.sleep(1.8)
    await click_js(page, "#studiolink")
    await page.wait_for_load_state("networkidle")
    # /studio/ opens the studio itself. It used to stop at a second copy of the
    # map, which carried the copy the real map replaced on 2026-08-03.
    await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
    await asyncio.sleep(2.2)

    # The studio opens on the what-if controls, with results pinned on the right.
    await cap(
        page,
        "What-if controls sit beside the calculated grid prices",
        "What-if settings on the left, and every grid's cleared price on the right.",
    )
    await asyncio.sleep(2.8)

    # Quick scenario updates live without the Run button.
    await cap(
        page,
        "Add data-center demand",
        "Move the slider and all three grid prices recalculate without pressing Run.",
    )
    await ramp_lever(page, "Add a data center", 2500, 3000)
    await asyncio.sleep(2.8)  # hold on the coal-to-oil flip
    await cap(
        page,
        "Remove the biggest unit",
        "A Sual coal unit goes out after demand increases.",
    )
    await trip_unit(page, "Sual")
    await asyncio.sleep(2.6)
    await clear_cap(page)

    # Historical comparison.
    await sim_tab(page)
    await click_text(page, "Historical replay")
    await asyncio.sleep(1.0)
    await scroll_top(page)
    await cap(
        page,
        "The historical replay reports the model's price error",
        "The cost calculation is compared with recorded prices for every "
        "complete market day.",
    )
    await asyncio.sleep(3.0)
    await click_text(page, "Observed offers")
    await cap(
        page,
        "Published offers follow the recorded evening ramp",
        "Across the archive, price correlation is 0.73 to 0.87 by grid.",
    )
    await asyncio.sleep(3.2)
    await clear_cap(page)

    # Reliability
    await click_text(page, "Power-shortfall risk")
    await asyncio.sleep(1.0)
    await scroll_top(page)
    await cap(
        page,
        "Chance of a power shortfall",
        "Repeated simulations apply random plant outages and report "
        "loss-of-load probability (LOLP).",
    )
    await asyncio.sleep(3.0)
    await clear_cap(page)

    # Four additional analysis views.
    await cap(
        page,
        "The studio calculates reserves, bills, future cases, and emissions",
        "Open each view from the same scenario.",
    )
    for name in [
        "Backup capacity market",
        "Bill impact",
        "Possible future price range",
        "Emissions",
    ]:
        ok = await click_text(page, name)
        if ok:
            await asyncio.sleep(0.4)
            await scroll_top(page)
            await asyncio.sleep(1.3)

    await clear_cap(page)
    await cap(
        page,
        "Public sources and labeled assumptions appear beside the results.",
        "power-dispatch-studio.vercel.app",
        intro=True,
    )
    await asyncio.sleep(3.2)
    await clear_cap(page)


async def ramp_lever(page: Page, label: str, to: int, ms: int):
    # React controlled input: use the native value setter so onChange fires
    await page.evaluate(
        """(args) => { const [label,to,ms]=args;
          const setV=Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,'value').set;
          const l=[...document.querySelectorAll('.lever')]
            .find(x=>x.textContent.includes(label));
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
        """(needle) => { const setV=Object.getOwnPropertyDescriptor(
            window.HTMLSelectElement.prototype,'value').set;
          const l=[...document.querySelectorAll('.lever')]
            .find(x=>/Trip a unit/.test(x.textContent));
          const sel=l && l.querySelector('select'); if(!sel) return;
          const opt=[...sel.options].find(o=>o.text.includes(needle)); if(!opt) return;
          setV.call(sel,opt.value);
          sel.dispatchEvent(new Event('change',{bubbles:true})); }""",
        needle,
    )


async def sim_tab(page: Page):
    """Open every group in the question rail, so a view is one click away."""
    await page.evaluate(
        """() => { document.querySelectorAll('.rail__grouphead').forEach(b => {
             if (b.getAttribute('aria-expanded') === 'false') b.click() }) }"""
    )
    await asyncio.sleep(0.5)


async def scroll_top(page: Page):
    await page.evaluate(
        """() => {
          const s=document.querySelector('.studio__scroll');
          if(s) s.scrollTo({top:0,behavior:'smooth'});
        }"""
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
        await record_map(page)
        await record_studio(page)
        await asyncio.sleep(0.5)
        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        dest = OUT / "reel.webm"
        Path(vid).replace(dest)
        print(dest)


if __name__ == "__main__":
    asyncio.run(main())
