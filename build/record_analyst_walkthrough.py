"""Record the arriving analyst's whole path, from the capability list to a file.

An analyst who reads production-cost model output and has no license asks four
things in order: what does this solve, where does it refuse, how close does it
get, and can I take a run away. Nothing showed that path end to end, so a reader
had to assemble it from five separate clips.

The recording follows one person through it:

    for-analysts.html   the ability table, and the four No rows
    #v=commitment-test  a limit that carries a measurement, not an opinion
    #v=future-year      2028 solved day by day, on published plans
    #v=fuels            take both Sual units out of the model, then Run
    #v=contract-position  what that edit does to a book of contracts, in pesos
    #v=quick-scenario   drag a data center onto Luzon, watch the price move
    Take this scenario to Python   the same run as a file the CLI reads

Needs the COMBINED single-origin serve, because the first step is a real
navigation from the map's own page into the studio:

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/ && (cd .vercel_out && python3 serve.py 5200 &)
    python3 build/record_analyst_walkthrough.py

Writes docs/analyst-walkthrough.gif and .mp4.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5200"
ROOT = Path(__file__).resolve().parent.parent
REC = Path("/tmp/analyst-rec")
REC.mkdir(exist_ok=True)
OUT = ROOT / "docs" / "analyst-walkthrough.gif"
W, H = 1360, 850

CAP_JS = r"""
(args) => {
  const { title, url } = args;
  let el = document.getElementById('walk-cap');
  if (!el) { el = document.createElement('div'); el.id = 'walk-cap'; document.body.appendChild(el); }
  el.style.cssText = `position:fixed;left:50%;transform:translateX(-50%);bottom:22px;
    z-index:2147483647;font-family:'Fira Sans',system-ui,sans-serif;
    background:#0b0e13;color:#e9edf2;border:1px solid #2a333f;border-radius:12px;
    box-shadow:0 12px 44px rgba(0,0,0,.5);padding:13px 22px;width:1120px;
    max-width:calc(100% - 44px);display:flex;align-items:center;
    justify-content:space-between;gap:20px;`;
  el.innerHTML = `<span style="font-size:19px;font-weight:600;">${title}</span>` +
    (url ? `<span style="font-family:ui-monospace,Menlo,monospace;font-size:15px;
       color:#e2725b;background:#151a21;border:1px solid #2a333f;border-radius:7px;
       padding:5px 11px;">${url}</span>` : '');
}
"""


async def cap(page: Page, title: str, url: str = "") -> None:
    await page.evaluate(CAP_JS, {"title": title, "url": url})


async def scroll_to(page: Page, selector: str) -> None:
    await page.evaluate(
        "(s) => { const el = document.querySelector(s);"
        " if (el) el.scrollIntoView({behavior:'smooth', block:'start'}) }",
        selector,
    )


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(REC),
            record_video_size={"width": W, "height": H},
            device_scale_factor=2,
        )
        page = await ctx.new_page()

        # 1. the capability list, which is the first ninety seconds
        await page.goto(f"{BASE}/for-analysts.html", wait_until="load")
        await asyncio.sleep(2.0)
        await cap(
            page,
            "It solves seven things fully, three partly, and refuses four",
            "power-dispatch-studio.vercel.app/for-analysts.html",
        )
        await asyncio.sleep(2.0)
        await scroll_to(page, ".t-cap")
        await asyncio.sleep(3.4)
        rows = await page.evaluate(
            "() => document.querySelectorAll('.t-cap .n').length"
        )
        if rows != 4:
            raise SystemExit(f"expected 4 refusals on the ability table, saw {rows}")

        # 2. how close it gets, from the nightly build
        await cap(page, "Every refusal states a reason, and two carry a measurement")
        await asyncio.sleep(2.2)
        await scroll_to(page, ".t-acc")
        await asyncio.sleep(3.0)
        await cap(
            page, "The replay error is on the page, and the build rewrites it nightly"
        )
        await asyncio.sleep(2.6)

        # 3. a limit that was measured, not asserted
        await page.goto(f"{BASE}/studio/#v=commitment-test", wait_until="load")
        await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
        await asyncio.sleep(3.0)
        await cap(
            page,
            "Unit commitment was built and scored. It lost in all five series",
            "/studio/#v=commitment-test",
        )
        await asyncio.sleep(3.6)
        text = await page.inner_text(".view")
        if "-0.445" not in text:
            raise SystemExit("the commitment view is not showing its measured delta")

        # 4. a whole year, solved on published plans
        await cap(
            page,
            "A whole future year solves day by day, on the published demand path",
            "/studio/#v=future-year",
        )
        await page.evaluate("() => { window.location.hash = 'v=future-year' }")
        await asyncio.sleep(4.6)
        year = await page.inner_text(".view")
        if "2028" not in year:
            raise SystemExit("the future-year view is not showing a solved year")

        # 5. a real model edit, so the file that comes out carries it. The
        # levers preview and never write the model, which is right for a lever
        # and wrong for a demo of a downloadable run.
        await cap(
            page,
            "Take both 647 MW Sual units out of the model, and press Run",
            "/studio/#v=fuels",
        )
        await page.evaluate("() => { window.location.hash = 'v=fuels' }")
        await asyncio.sleep(2.4)
        box = page.get_by_label("coal Luzon avail")
        before_mw = float(await box.input_value())
        await box.fill(str(before_mw - 1294))
        await box.press("Tab")
        await asyncio.sleep(1.6)
        # the Run button's accessible name is its aria-label, never its text
        label = await page.inner_text(".bar__run")
        if label != "Run 1 edit":
            raise SystemExit(f"the model edit did not reach Run, which reads {label!r}")
        await page.click(".bar__run")
        await asyncio.sleep(2.4)

        # 6. the question a supplier actually brought, answered in pesos
        await cap(
            page,
            "The same edit, priced against your own contract book",
            "/studio/#v=contract-position",
        )
        await page.evaluate("() => { window.location.hash = 'v=contract-position' }")
        await asyncio.sleep(4.2)
        pos = await page.inner_text(".view")
        if "Cover on your Luzon load" not in pos:
            raise SystemExit("the contract view is not showing a settled position")
        if "does not move" in pos:
            raise SystemExit("the scenario left the position flat, so the beat is dead")
        print(f"  position headline: {pos.splitlines()[0]}")

        await cap(page, "Drag a data center onto Luzon, and every grid re-clears")
        await page.evaluate("() => { window.location.hash = 'v=quick-scenario' }")
        await asyncio.sleep(2.0)
        moved = await page.evaluate(
            """() => {
              const set = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              const el = [...document.querySelectorAll('input[type=range]')]
                .find(r => +r.max >= 500);
              if (!el) return false;
              const to = Math.round(+el.max * 0.7), from = +el.value, t0 = performance.now();
              return new Promise(r => { function f(t) { const k = Math.min(1, (t - t0) / 3200);
                set.call(el, String(Math.round(from + (to - from) * k)));
                el.dispatchEvent(new Event('input', { bubbles: true }));
                k < 1 ? requestAnimationFrame(f) : r(true); } requestAnimationFrame(f); });
            }"""
        )
        if not moved:
            raise SystemExit("no demand slider found in Quick what-if")
        await asyncio.sleep(2.8)

        # 6. the run leaves as a file the command line reads
        await page.evaluate(
            "() => { const h = [...document.querySelectorAll('.byo__head')]"
            ".find(e => e.textContent.includes('Python'));"
            " if (h) h.scrollIntoView({behavior:'smooth', block:'center'}) }"
        )
        await asyncio.sleep(1.8)
        await cap(
            page,
            "The same run downloads as a file, and the command line reads it back",
            "power-dispatch run --scenario yours.json",
        )
        async with page.expect_download() as dl:
            await page.get_by_role("button", name="Download scenario").click()
        saved = await dl.value
        name = saved.suggested_filename
        if not name.endswith(".json"):
            raise SystemExit(f"the scenario download produced {name!r}")
        await asyncio.sleep(3.2)
        msg = await page.inner_text(".byo__msg")
        print(f"  scenario file: {name}, studio reported {msg!r}")

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        webm = REC / "walk.webm"
        Path(vid).replace(webm)

    ss = "1.6"
    vf = "fps=10,scale=860:-1:flags=lanczos"
    pal = REC / "pal.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            ss,
            "-i",
            str(webm),
            "-vf",
            f"{vf},palettegen=max_colors=96:stats_mode=diff",
            str(pal),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            ss,
            "-i",
            str(webm),
            "-i",
            str(pal),
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
            str(OUT),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(["gifsicle", "-O3", str(OUT), "-o", str(OUT)], capture_output=True)
    mp4 = OUT.with_suffix(".mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            ss,
            "-i",
            str(webm),
            "-vf",
            "scale=1280:-2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "24",
            "-an",
            str(mp4),
        ],
        check=True,
        capture_output=True,
    )
    print(
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) and "
        f"{mp4.name} ({mp4.stat().st_size // 1024} KB)"
    )


asyncio.run(main())
