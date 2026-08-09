"""Record the studio shell: command palette, question rail, run summary, deep link.

The shell was rebuilt on 2026-07-31 around the analyst's question rather than
the model's object classes, and no demo showed it. Every existing clip opens on
a view and stays there, so a reader could not see how a person gets between 39
views, or that each one is a URL they can send to a colleague.

The recording stays short because the static studio interface uses about 0.09
MB per second at 820 px, compared with 0.22 MB for the moving map.

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/ && (cd .vercel_out && python3 serve.py 5200 &)
    python3 build/record_studio_shell.py

Writes docs/studio-shell.gif and docs/studio-shell.mp4.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5200/studio/"
ROOT = Path(__file__).resolve().parent.parent
REC = Path("/tmp/shell-rec")
REC.mkdir(exist_ok=True)
OUT = ROOT / "docs" / "studio-shell.gif"
W, H = 1360, 850

# The caption includes the address because the recording omits browser controls.
CAP_JS = r"""
(args) => {
  const { title, url } = args;
  let el = document.getElementById('shell-cap');
  if (!el) { el = document.createElement('div'); el.id = 'shell-cap'; document.body.appendChild(el); }
  el.style.cssText = `position:fixed;left:50%;transform:translateX(-50%);bottom:22px;
    z-index:2147483647;font-family:'Fira Sans',system-ui,sans-serif;
    background:#0b0e13;color:#e9edf2;border:1px solid #2a333f;border-radius:12px;
    box-shadow:0 12px 44px rgba(0,0,0,.5);padding:13px 22px;width:1080px;
    max-width:calc(100% - 44px);display:flex;align-items:center;
    justify-content:space-between;gap:20px;`;
  el.innerHTML = `<span style="font-size:19px;font-weight:600;">${title}</span>` +
    (url ? `<span style="font-family:ui-monospace,Menlo,monospace;font-size:16px;
       color:#e2725b;background:#151a21;border:1px solid #2a333f;border-radius:7px;
       padding:5px 11px;">${url}</span>` : '');
}
"""


async def cap(page: Page, title: str, url: str = "") -> None:
    await page.evaluate(CAP_JS, {"title": title, "url": url})


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
        await page.goto(f"{BASE}#v=chronology", wait_until="load")
        await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
        # The base case is calculated on load. Run stays disabled until an edit.
        await asyncio.sleep(3.0)

        # Use a query that matches the Marginal units alias list.
        await cap(page, "Command palette: press Cmd K and type what you want to know")
        await asyncio.sleep(1.2)
        await page.keyboard.press("Meta+k")
        await page.wait_for_selector(".pal__scrim", timeout=5000)
        await asyncio.sleep(0.7)
        for ch in "price setter":
            await page.keyboard.type(ch)
            await asyncio.sleep(0.07)
        await asyncio.sleep(1.4)
        await page.keyboard.press("Enter")
        await page.wait_for_selector(".pal__scrim", state="detached", timeout=5000)
        await asyncio.sleep(1.4)
        landed = (await page.inner_text(".bar__searchtxt")).strip()
        if landed != "Marginal units":
            raise SystemExit(f"command palette opened {landed!r}")

        # Show the URL written by the command palette.
        await cap(
            page,
            "Every view is its own URL, so a view is sendable",
            "power-dispatch-studio.vercel.app/studio/#v=marginal-units",
        )
        await asyncio.sleep(2.4)

        # Expand the 40 views grouped by the question each view answers.
        await cap(page, "The rail groups all 40 views by the question they answer")
        await asyncio.sleep(0.8)
        await page.evaluate(
            "() => { document.querySelectorAll('.rail__grouphead').forEach(b => {"
            " if (b.getAttribute('aria-expanded') === 'false') b.click() }) }"
        )
        await asyncio.sleep(2.0)
        await page.get_by_role(
            "button", name="Loss of one major unit (N-1)", exact=False
        ).first.click()
        await asyncio.sleep(1.8)
        landed = (await page.inner_text(".bar__searchtxt")).strip()
        if landed != "Loss of one major unit (N-1)":
            raise SystemExit(f"navigation rail opened {landed!r}")

        # Move a slider and show the recalculated price without pressing Run.
        await cap(
            page, "Move a slider and the run summary recalculates, with no Run needed"
        )
        await page.evaluate(
            "(s) => { window.location.hash = 'v=' + s }", "quick-scenario"
        )
        await asyncio.sleep(1.8)
        moved = await page.evaluate(
            """() => {
              const set = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
              const el = [...document.querySelectorAll('input[type=range]')]
                .find(r => +r.max >= 500);
              if (!el) return false;
              const to = Math.round(+el.max * 0.62), from = +el.value, t0 = performance.now();
              return new Promise(r => { function f(t) { const k = Math.min(1, (t - t0) / 3000);
                set.call(el, String(Math.round(from + (to - from) * k)));
                el.dispatchEvent(new Event('input', { bubbles: true }));
                k < 1 ? requestAnimationFrame(f) : r(true); } requestAnimationFrame(f); });
            }"""
        )
        if not moved:
            print("WARNING: no range slider found, the run-summary segment is missing")
        await asyncio.sleep(2.6)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        webm = REC / "shell.webm"
        Path(vid).replace(webm)

    # trim the blank + load lead so the loop opens on the first caption
    ss = "3.4"
    vf = "fps=11,scale=820:-1:flags=lanczos"
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
        f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) "
        f"and {mp4.name} ({mp4.stat().st_size // 1024} KB)"
    )


asyncio.run(main())
