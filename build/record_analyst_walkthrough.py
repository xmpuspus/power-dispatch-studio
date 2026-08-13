"""Record the README's scenario, save, compare, and export walkthrough.

The clip saves a base replay, applies the 1,500 MW DICT reference case, runs it,
saves the changed replay, opens the automatic comparison, and exports the case
package. The reference case is an analyst assumption, not a project forecast.

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/ && (cd .vercel_out && python3 serve.py 5200 &)
    python3 build/record_analyst_walkthrough.py

An optional first argument replaces the default site URL. The script writes
docs/analyst-walkthrough.gif and docs/analyst-walkthrough.mp4.
"""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.async_api import Locator, Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5200"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "analyst-walkthrough.gif"
W, H = 1360, 850

CAPTION_JS = r"""
(args) => {
  const { title, detail } = args;
  let el = document.getElementById('readme-guide');
  if (!el) {
    el = document.createElement('div');
    el.id = 'readme-guide';
    const strong = document.createElement('strong');
    const small = document.createElement('span');
    el.append(strong, small);
    document.body.appendChild(el);
  }
  el.style.cssText = `position:fixed;left:50%;transform:translateX(-50%);bottom:20px;
    z-index:2147483647;font-family:'Fira Sans',system-ui,sans-serif;
    background:#0b0e13;color:#e9edf2;border:1px solid #3d4a5a;border-radius:10px;
    box-shadow:0 12px 40px rgba(0,0,0,.45);padding:12px 18px;width:980px;
    max-width:calc(100% - 40px);display:flex;align-items:baseline;gap:16px;`;
  const [strong, small] = el.children;
  strong.style.cssText = 'font-size:19px;font-weight:600;flex:none;';
  small.style.cssText = 'font-size:14px;color:#aeb9c7;';
  strong.textContent = title;
  small.textContent = detail || '';
}
"""

GUIDE_CSS = """
[data-readme-target] {
  outline: 3px solid #e2725b !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 0 7px rgba(226,114,91,.16) !important;
}
"""


async def caption(page: Page, title: str, detail: str = "") -> None:
    await page.evaluate(CAPTION_JS, {"title": title, "detail": detail})


async def target(page: Page, locator: Locator) -> None:
    await locator.scroll_into_view_if_needed()
    await page.locator("[data-readme-target]").evaluate_all(
        "els => els.forEach(el => el.removeAttribute('data-readme-target'))"
    )
    await locator.evaluate("el => el.setAttribute('data-readme-target', '')")
    box = await locator.bounding_box()
    if box:
        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


async def open_view(page: Page, slug: str, label: str) -> None:
    await page.evaluate("s => { window.location.hash = 'v=' + s }", slug)
    await page.wait_for_function(
        "label => document.querySelector('.bar__searchtxt')"
        "?.textContent?.trim() === label",
        arg=label,
        timeout=15000,
    )
    await page.wait_for_timeout(1500)


async def move_range(page: Page, locator: Locator, value: int) -> None:
    start = int(float(await locator.input_value()))
    step = 100 if value >= start else -100
    values = list(range(start + step, value, step)) + [value]
    for next_value in values:
        # React may replace a controlled input after each event. Evaluate on the
        # locator again so every step reaches the live slider.
        await locator.evaluate(
            """(el, nextValue) => {
              const set = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              set.call(el, String(nextValue));
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }""",
            next_value,
        )
        await page.wait_for_timeout(40)


def encode(webm: Path) -> None:
    vf = "fps=8,scale=760:-1:flags=lanczos"
    with tempfile.TemporaryDirectory(prefix="pds-walk-encode-") as td:
        pal = Path(td) / "palette.png"
        raw = Path(td) / "raw.gif"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                "1.8",
                "-i",
                str(webm),
                "-vf",
                f"{vf},palettegen=max_colors=72:stats_mode=diff",
                str(pal),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                "1.8",
                "-i",
                str(webm),
                "-i",
                str(pal),
                "-lavfi",
                f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                str(raw),
            ],
            check=True,
        )
        packed = subprocess.run(
            ["gifsicle", "-O3", "--lossy=25", str(raw), "-o", str(OUT)],
            capture_output=True,
        )
        if packed.returncode != 0:
            raw.replace(OUT)

    mp4 = OUT.with_suffix(".mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            "1.8",
            "-i",
            str(webm),
            "-vf",
            "scale=1280:-2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "25",
            "-an",
            str(mp4),
        ],
        check=True,
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pds-walk-record-") as td:
        rec = Path(td)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                viewport={"width": W, "height": H},
                record_video_dir=str(rec),
                record_video_size={"width": W, "height": H},
            )
            await ctx.add_init_script("localStorage.clear()")
            page = await ctx.new_page()
            await page.goto(f"{BASE}/studio/#v=chronology", wait_until="load")
            await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
            await page.add_style_tag(content=GUIDE_CSS)
            await page.wait_for_timeout(2300)
            await page.get_by_label("Observed day to replay").select_option(
                "2026-07-22"
            )
            await page.wait_for_timeout(1700)

            save = page.get_by_role("button", name="Save run")
            await caption(
                page,
                "1. Save the base run before changing it",
                "A saved run keeps the date, inputs and hourly results in this "
                "browser.",
            )
            await target(page, save)
            await save.click()
            await page.get_by_text("Run saved", exact=True).wait_for(timeout=5000)
            await page.wait_for_timeout(1900)

            await open_view(page, "quick-scenario", "Scenario builder")
            preset = page.get_by_test_id("preset-dict-1500")
            await caption(
                page,
                "2. Start from a task preset",
                "The DICT case adds the 1,500 MW reference scale to Luzon. It is "
                "not a project forecast.",
            )
            await target(page, preset)
            await preset.click()
            await page.wait_for_timeout(1800)
            if (
                await page.get_by_label("Scenario name").input_value()
                != "DICT 1,500 MW reference"
            ):
                raise SystemExit("the preset did not name the scenario")
            if (await page.locator(".bar__run").inner_text()).strip() != "Run 1 change":
                raise SystemExit("the scenario change did not reach the Run button")

            run = page.locator(".bar__run")
            await caption(
                page,
                "3. Press Run before reading the scenario result",
                "The result status says when the preset is included.",
            )
            await target(page, run)
            await run.click()
            await page.get_by_text("Results current", exact=True).first.wait_for(
                timeout=15000
            )
            luzon_price = await page.locator(
                'button[title="Show Luzon in views that analyze one grid"] .dock__price'
            ).inner_text()
            if "6.00" not in luzon_price:
                raise SystemExit(
                    "the DICT reference case did not produce the expected Luzon price: "
                    + repr(luzon_price)
                )
            await page.wait_for_timeout(2400)

            await open_view(page, "chronology", "Hourly market replay")
            await page.wait_for_function(
                "() => document.querySelector('.view')?.innerText"
                "?.includes('₱9.65 /kWh')",
                timeout=15000,
            )
            await page.get_by_label("Run name").fill(
                "DICT 1,500 MW reference, 22 July 2026"
            )
            save = page.get_by_role("button", name="Save run")
            await caption(
                page,
                "4. Wait for the day totals, then save the changed run",
                "Name the run so the comparison can stand on its own.",
            )
            await target(page, save)
            await save.click()
            await page.get_by_text("Run saved", exact=True).wait_for(timeout=5000)
            count = await page.evaluate(
                """() => JSON.parse(
                  localStorage.getItem('power-dispatch-studio-runs-v1') || '{"runs":[]}'
                ).runs.length"""
            )
            if count != 2:
                raise SystemExit(f"expected two saved runs, found {count}")
            await page.wait_for_timeout(1900)

            await open_view(page, "saved-runs", "Saved runs")
            archive = page.locator(".panel").filter(
                has_text="Each saved run keeps its scenario settings"
            )
            rows = archive.locator(".propgrid tbody tr")
            if await rows.count() != 2:
                raise SystemExit("Saved runs did not show the base and changed cases")
            await caption(
                page,
                "5. Saved runs keeps the reference and the changed case",
                "Each row states its active assumption and has one portable case file.",
            )
            await target(page, rows.first)
            await page.wait_for_timeout(2800)

            comparison = page.locator(".propgrid.compare")
            comparison_text = await comparison.inner_text()
            if "₱9.65" not in comparison_text or "+₱3.65" not in comparison_text:
                raise SystemExit(
                    "the saved-run comparison did not show the DICT result: "
                    + repr(comparison_text)
                )
            chart_text = await page.locator("svg.chart").last.text_content() or ""
            if "A: Luzon" not in chart_text or "B: Luzon" not in chart_text:
                raise SystemExit(
                    "the comparison chart did not select the grid with the largest "
                    "price change"
                )
            summary = page.locator(".run-comparison-summary")
            await summary.evaluate(
                "el => el.scrollIntoView({block: 'center', behavior: 'instant'})"
            )
            await caption(
                page,
                "6. Read the comparison summary first",
                "It states the assumption, largest price move, unserved energy and "
                "corridor status.",
            )
            await target(page, summary)
            await page.wait_for_timeout(2800)

            export_case = rows.first.get_by_role("button", name="Export case")
            await caption(
                page,
                "7. Take the full case out of the browser",
                "One file keeps assumptions, sources, results and chart data.",
            )
            await target(page, export_case)
            await page.wait_for_timeout(2800)

            await ctx.close()
            video = await page.video.path()
            await browser.close()
            webm = rec / "analyst-walkthrough.webm"
            Path(video).replace(webm)

        encode(webm)

    print(
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) and "
        f"{OUT.with_suffix('.mp4').name} "
        f"({OUT.with_suffix('.mp4').stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    asyncio.run(main())
