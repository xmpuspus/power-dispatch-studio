"""Record the README's market-day walkthrough from the running Studio.

The clip follows the first workflow documented in README.md: choose a recorded
day and grid, inspect one hour, switch from the cost model to the published
offer book, open the evidence, and copy a shareable link.

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/ && (cd .vercel_out && python3 serve.py 5200 &)
    python3 build/record_studio_shell.py

An optional first argument replaces the default Studio URL. The script writes
docs/studio-shell.gif and docs/studio-shell.mp4.
"""

import asyncio
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.async_api import Locator, Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5200/studio/"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "studio-shell.gif"
W, H = 1360, 850
HOUR_18 = re.compile(r"^18:00,")

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


def encode(webm: Path) -> None:
    vf = "fps=8,scale=760:-1:flags=lanczos"
    with tempfile.TemporaryDirectory(prefix="pds-shell-encode-") as td:
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
    with tempfile.TemporaryDirectory(prefix="pds-shell-record-") as td:
        rec = Path(td)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                viewport={"width": W, "height": H},
                record_video_dir=str(rec),
                record_video_size={"width": W, "height": H},
                permissions=["clipboard-read", "clipboard-write"],
            )
            await ctx.add_init_script("localStorage.clear()")
            page = await ctx.new_page()
            await page.goto(f"{BASE}#v=chronology", wait_until="load")
            await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
            await page.add_style_tag(content=GUIDE_CSS)
            await page.wait_for_timeout(2300)

            day = page.get_by_label("Observed day to replay")
            await caption(
                page,
                "1. Choose a recorded day and island grid",
                "The date, grid and selected hour stay visible while you work.",
            )
            await target(page, day)
            await day.select_option("2026-07-22")
            await page.get_by_role("button", name="Visayas", exact=True).click()
            await page.wait_for_timeout(1800)

            hour = page.get_by_role("button", name=HOUR_18)
            await caption(
                page,
                "2. Click an hour to read the market record",
                "The strip shows recorded price, replay price, demand and the "
                "price-setting block.",
            )
            await target(page, hour)
            await hour.click()
            await page.wait_for_timeout(2200)

            offers = page.get_by_role("tab", name="Observed offers")
            await caption(
                page,
                "3. Switch between the cost model and published offers",
                "Both replays use the same recorded day and report their gap from "
                "the market price.",
            )
            await target(page, offers)
            await offers.click()
            await page.get_by_text("the day's book, as bid", exact=True).wait_for(
                timeout=15000
            )
            await page.wait_for_timeout(2500)

            evidence = page.locator(".viewevidence summary")
            await caption(
                page,
                "4. Open Evidence and sources before using a result",
                "The panel names the source, date, resolution and model status.",
            )
            await target(page, evidence)
            await evidence.click()
            await page.wait_for_timeout(2600)

            copy = page.get_by_role("button", name="Copy link")
            await caption(
                page,
                "5. Copy the exact view",
                "The link keeps the date, grid, run window and scenario settings.",
            )
            await target(page, copy)
            await copy.click()
            await page.get_by_text("Link copied", exact=True).wait_for(timeout=5000)
            await page.wait_for_timeout(2400)

            await ctx.close()
            video = await page.video.path()
            await browser.close()
            webm = rec / "studio-shell.webm"
            Path(video).replace(webm)

        encode(webm)

    print(
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) and "
        f"{OUT.with_suffix('.mp4').name} "
        f"({OUT.with_suffix('.mp4').stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    asyncio.run(main())
