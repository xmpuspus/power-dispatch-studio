#!/usr/bin/env python3
"""Record the siting what-if, done inside the studio.

This replaces the terminal recording that walked the same question through
one-off scripts. The tool answers it now, so the walkthrough shows the tool.

The clip follows one question end to end. An announced campus wants 3,000 MW at
New Clark City. What can the two lines into that site actually deliver, what
does adding a solar farm change at the hour that matters, how much of its own
plant closes the gap, and what happens when a circuit goes out.

Every number on screen is read live from the running app, which reads the baked
limits from pipeline/sites.py.

Needs the COMBINED single-origin serve (map at /, studio at /studio/):

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/serve.py
    (cd .vercel_out && python3 serve.py 5200)

Outputs /tmp/siting-walk/walk.webm; convert with the workflow-GIF recipe.
"""

import asyncio
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = "http://localhost:5200"
OUT = Path("/tmp/siting-walk")
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
    border:1px solid #2b3a4d;border-radius:14px;box-shadow:0 12px 44px rgba(0,0,0,.5);
    pointer-events:none;`;
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

# React ignores a plain value assignment on a controlled input, so the native
# setter has to be called before the event is dispatched or the slider snaps
# straight back and the recording shows nothing moving.
SET_RANGE = r"""
(args) => {
  const [idx, val] = args;
  const el = document.querySelectorAll('.sites__side input[type=range]')[idx];
  if (!el) return false;
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, String(val));
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}
"""


async def cap(page: Page, title: str, sub: str = "", intro: bool = False):
    await page.evaluate(CAP_JS, {"title": title, "sub": sub, "intro": intro})


async def clear_cap(page: Page):
    await page.evaluate(CLEAR_JS)


async def ramp(page: Page, idx: int, target: float, steps: int = 22,
               settle: float = 0.05):
    """Walk a slider to its value so the bar animates instead of jumping."""
    for i in range(1, steps + 1):
        await page.evaluate(SET_RANGE, [idx, round(target * i / steps)])
        await asyncio.sleep(settle)


async def read_bar(page: Page) -> str:
    return await page.evaluate(
        "() => document.querySelector('.site-bar')?.textContent.trim() || ''")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
        )
        page = await ctx.new_page()

        await page.goto(f"{BASE}/studio/", wait_until="networkidle")
        await asyncio.sleep(1.2)
        await cap(
            page,
            "An announced campus wants 3,000 MW.",
            "What can the wires into that site actually deliver?",
            intro=True,
        )
        await asyncio.sleep(3.4)
        await clear_cap(page)

        # the studio boots behind a gate, same as the deployed site
        await page.get_by_role("button", name="Open Power Dispatch Studio").click()
        await asyncio.sleep(1.6)

        # into the siting view
        await page.locator(".rail__grouphead", has_text="Where it can sit").click()
        await asyncio.sleep(0.6)
        await page.locator(".rail__item", has_text="Siting a new load").click()
        await asyncio.sleep(1.6)

        await cap(page, "Every announced site, and what its lines can take",
                  "The tight ones are marked. Fairview and Quezon City can take nothing.")
        await asyncio.sleep(3.6)

        await cap(page, "Pax Silica, New Clark City",
                  "3,000 MW of demand against two Concepcion to Clark circuits.")
        await asyncio.sleep(3.2)
        print("grid only:", await read_bar(page))

        await cap(page, "769 MW arrives. 2,231 MW has no source.",
                  "The red band is demand with nothing behind it, at 7pm.")
        await asyncio.sleep(3.6)

        # the day strip explains why the evening is the hard hour
        await cap(page, "The limit moves through the day",
                  "And its own solar has stopped by the evening, which is when demand peaks.")
        await asyncio.sleep(3.8)

        # add a solar farm: nothing changes at 7pm
        await cap(page, "Add the 500 MW solar farm",
                  "Watch the evening peak. It does not move.")
        await ramp(page, 2, 500)
        await asyncio.sleep(2.8)
        print("with solar at 7pm:", await read_bar(page))

        # move to noon so the gold band appears, then back to the evening
        await page.evaluate(
            """() => { const s=[...document.querySelectorAll('.daystrip rect')];
                 if (s[12]) s[12].dispatchEvent(new MouseEvent('click',{bubbles:true})); }"""
        )
        await asyncio.sleep(1.0)
        await cap(page, "At noon the solar does work",
                  "The gold band is the site's own sun, covering part of the demand.")
        await asyncio.sleep(3.2)
        print("with solar at noon:", await read_bar(page))

        await page.evaluate(
            """() => { const s=[...document.querySelectorAll('.daystrip rect')];
                 if (s[19]) s[19].dispatchEvent(new MouseEvent('click',{bubbles:true})); }"""
        )
        await asyncio.sleep(1.0)
        await cap(page, "Back at 7pm the gold is gone",
                  "Which is why the campus has to make its own power, not just buy panels.")
        await asyncio.sleep(3.4)

        # build its own plant
        await cap(page, "Give it a 2,500 MW power station of its own",
                  "The red closes as the navy band grows.")
        await ramp(page, 1, 2500, steps=26)
        await asyncio.sleep(2.6)
        print("own plant:", await read_bar(page))

        await cap(page, "Every megawatt now has a source",
                  "It still draws 500 MW over the lines, so this is most of its power, not all.")
        await asyncio.sleep(3.4)

        # the contingency
        await cap(page, "Now take out one of its two circuits",
                  "One of them is the site's only way to the rest of the grid.")
        await asyncio.sleep(2.4)
        await page.locator(".lever--check span").first.click()
        await asyncio.sleep(1.4)
        print("with outage:", await read_bar(page))
        await cap(page, "The 500 MW it was importing now has no source",
                  "Building your own station moves the problem from supply to backup.")
        await asyncio.sleep(4.0)

        await cap(
            page,
            "Solved on the public grid map, in the tool.",
            "Line ratings are estimates. NGCP does not publish them.",
            intro=True,
        )
        await asyncio.sleep(3.4)
        await clear_cap(page)

        await ctx.close()
        await browser.close()
        vid = await page.video.path() if page.video else None
        if vid:
            webm = OUT / "walk.webm"
            Path(vid).replace(webm)
            print(webm)


if __name__ == "__main__":
    asyncio.run(main())
