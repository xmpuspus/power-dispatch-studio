#!/usr/bin/env python3
"""Record the siting calculation inside the studio.

An announced campus wants 3,000 MW at
New Clark City. What can the two lines into that site actually deliver, what
does adding a solar farm change at the hour that matters, how much of its own
plant closes the gap, and what happens when a circuit goes out.

Caption values are read from the running app, which reads the generated limits
from pipeline/sites.py.

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
  if (!el) {
    el = document.createElement('div');
    el.id = 'walk-cap';
    document.body.appendChild(el);
  }
  const base = `position:fixed;left:50%;z-index:2147483647;box-sizing:border-box;
    font-family:'Fira Sans','Inter',system-ui,sans-serif;
    background:rgba(12,17,24,.94);color:#eef2f7;
    border:1px solid #2b3a4d;border-radius:14px;box-shadow:0 12px 44px rgba(0,0,0,.5);
    pointer-events:none;`;
  if (intro) {
    el.style.cssText = base + `top:50%;transform:translate(-50%,-50%);
      width:860px;padding:40px 46px;text-align:center;`;
    el.innerHTML = `<div style="font-size:14px;letter-spacing:.16em;
      text-transform:uppercase;color:#7f8ea0;margin-bottom:14px;">
      Power Dispatch Studio</div>
      <div style="font-size:30px;font-weight:700;line-height:1.28;">${title}</div>
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
CLEAR_JS = """() => {
  const e = document.getElementById('walk-cap');
  if (e) e.remove();
}"""

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


async def ramp(
    page: Page, idx: int, target: float, steps: int = 22, settle: float = 0.05
):
    """Walk a slider to its value so the bar animates instead of jumping."""
    for i in range(1, steps + 1):
        await page.evaluate(SET_RANGE, [idx, round(target * i / steps)])
        await asyncio.sleep(settle)


async def read_bar(page: Page) -> str:
    return await page.evaluate(
        "() => document.querySelector('.site-bar')?.textContent.trim() || ''"
    )


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

        # Open the studio from its landing screen.
        await page.get_by_role("button", name="Open Power Dispatch Studio").click()
        await asyncio.sleep(1.6)

        # Open the siting view.
        await page.locator(
            ".rail__grouphead", has_text="Where new demand can connect"
        ).click()
        await asyncio.sleep(0.6)
        await page.locator(".rail__item", has_text="Siting a new load").click()
        await asyncio.sleep(1.6)

        await cap(
            page,
            "Fairview and Quezon City have no spare grid capacity in this model",
            "The view lists each announced site and its estimated capacity before "
            "a local circuit reaches its rating.",
        )
        await asyncio.sleep(3.6)

        await cap(
            page,
            "Pax Silica, New Clark City",
            "3,000 MW of demand against two Concepcion to Clark circuits.",
        )
        await asyncio.sleep(3.2)
        print("grid only:", await read_bar(page))

        await cap(
            page,
            "The grid supplies 769 MW; 2,231 MW remains unmet",
            "At 7pm, the red band is demand that available supply cannot cover.",
        )
        await asyncio.sleep(3.6)

        # Show why the evening is the limiting hour.
        await cap(
            page,
            "The largest supply gap occurs at the 7pm demand peak",
            "On-site solar output has fallen to zero by the evening peak.",
        )
        await asyncio.sleep(3.8)

        # Add a solar farm. It does not change the 7pm result.
        await cap(
            page,
            "Add the 500 MW solar farm",
            "The added solar does not reduce the 7pm supply gap.",
        )
        await ramp(page, 2, 500)
        await asyncio.sleep(2.8)
        print("with solar at 7pm:", await read_bar(page))

        # Move to noon, then back to the evening.
        await page.evaluate(
            """() => {
              const s = [...document.querySelectorAll('.daystrip rect')];
              if (s[12]) {
                s[12].dispatchEvent(new MouseEvent('click', {bubbles:true}));
              }
            }"""
        )
        await asyncio.sleep(1.0)
        await cap(
            page,
            "At noon, 500 MW of on-site solar covers part of demand",
            "On-site solar generation appears only during daylight hours.",
        )
        await asyncio.sleep(3.2)
        print("with solar at noon:", await read_bar(page))

        await page.evaluate(
            """() => {
              const s = [...document.querySelectorAll('.daystrip rect')];
              if (s[19]) {
                s[19].dispatchEvent(new MouseEvent('click', {bubbles:true}));
              }
            }"""
        )
        await asyncio.sleep(1.0)
        await cap(
            page,
            "At 7pm, on-site solar generation is zero",
            "Evening demand must be covered by the grid or another on-site source.",
        )
        await asyncio.sleep(3.4)

        # Add an on-site power station.
        await cap(
            page,
            "A 2,500 MW on-site power station covers most demand",
            "Unmet demand falls as on-site generation increases.",
        )
        await ramp(page, 1, 2500, steps=26)
        await asyncio.sleep(2.6)
        print("own plant:", await read_bar(page))

        await cap(
            page,
            "The grid and the site's power station now meet all 3,000 MW",
            "It still draws 500 MW over the lines, so the site's station supplies "
            "most of its power, not all.",
        )
        await asyncio.sleep(3.4)

        # Remove one circuit.
        await cap(
            page,
            "Now take out one of its two circuits",
            "One of them is the site's only way to the rest of the grid.",
        )
        await asyncio.sleep(2.4)
        await page.locator(".lever--check span").first.click()
        await asyncio.sleep(1.4)
        print("with outage:", await read_bar(page))
        await cap(
            page,
            "A circuit outage leaves the remaining 500 MW unmet",
            "The on-site station covers 2,500 MW but still needs backup for the "
            "grid import.",
        )
        await asyncio.sleep(4.0)

        await cap(
            page,
            "The site still depends on estimated transmission limits",
            "NGCP does not publish the line ratings used in this calculation.",
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
