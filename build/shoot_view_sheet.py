"""Open all Studio views by deep link, shoot each one, and tile them into a sheet.

The script also checks every deep link. `#v=<slug>` is
read by `studio/src/shell/nav.ts`, and nothing else opens every slug. A slug
that stops resolving leaves the shell on its previous view, so the script
compares the shell's own current-view label against the label `nav.ts` declares
and fails on any mismatch. Without that check, a broken link could show the
previous view without reporting an error.

    bash scripts/vercel_build.sh
    cp web/serve.py .vercel_out/ && (cd .vercel_out && python3 serve.py 5200 &)
    python3 build/shoot_view_sheet.py

Writes docs/views-contact-sheet.png and prints one line per view.
"""

import asyncio
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
NAV = ROOT / "studio" / "src" / "shell" / "nav.ts"
OUT = ROOT / "docs" / "views-contact-sheet.png"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5200/studio/"
W, H = 1360, 850
# Five columns keep each view large enough to inspect on the generated sheet.
COLS = 5

# The tile is the main pane only. The rail and run dock repeat on every route.
LABEL_JS = r"""
(args) => {
  const [group, label] = args;
  const main = document.querySelector('.studio__main');
  if (!main) return;
  main.style.position = 'relative';
  let el = document.getElementById('sheet-cap');
  if (!el) {
    el = document.createElement('div');
    el.id = 'sheet-cap';
    main.appendChild(el);
  }
  el.style.cssText = `position:absolute;left:0;right:0;top:0;z-index:2147483647;
    font-family:'Fira Sans',system-ui,sans-serif;background:#0b0e13;color:#e9edf2;
    padding:13px 20px;border-bottom:3px solid #e2725b;display:flex;
    align-items:baseline;gap:14px;`;
  el.innerHTML = `<span style="font-size:29px;font-weight:700;">${label}</span>
    <span style="font-size:20px;color:#8a97a6;">${group}</span>`;
}
"""


def destinations() -> list[dict]:
    """Parse slug, label and group out of nav.ts, the one place they are declared."""
    src = NAV.read_text()
    body = src[src.index("export const GROUPS") : src.index("export const ALL_DESTS")]
    out: list[dict] = []
    group = ""
    for chunk in re.finditer(
        r"label:\s*(?:'([^']*)'|\"([^\"]*)\")|slug:\s*'([^']+)'", body
    ):
        lab, lab2, slug = chunk.group(1), chunk.group(2), chunk.group(3)
        if slug:
            out.append({"slug": slug, "label": None, "group": group})
        elif out and out[-1]["label"] is None:
            out[-1]["label"] = lab or lab2
        else:
            group = lab or lab2
    return out


async def shoot(shots: Path) -> list[dict]:
    dests = destinations()
    rows: list[dict] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(
            viewport={"width": W, "height": H}, device_scale_factor=1
        )
        # The solver keeps the event loop busy, so networkidle never settles.
        # Load once behind a deep link, then drive the rest through hashchange,
        # which is the same path a shared link takes.
        await page.goto(f"{BASE}#v={dests[0]['slug']}", wait_until="load")
        await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
        await page.wait_for_timeout(2500)
        # No Run click here: the base case is already solved on load, and
        # Run stays disabled until an edit exists, so clicking it only burns the
        # 30-second Playwright retry.
        #
        # Five views read saved hourly market replays and say "no saved run yet" until
        # one exists: capture prices, portfolio, compare, saved runs, cross-run.
        # Save two, the way an analyst would before opening them.
        try:
            await page.evaluate("() => { window.location.hash = 'v=chronology' }")
            await page.wait_for_timeout(2200)
            sel = page.get_by_label("Observed day to replay")
            values = [
                await o.get_attribute("value")
                for o in await sel.locator("option").all()
            ]
            for i in range(2):
                if i < len(values):
                    await sel.select_option(value=values[-(i + 1)])
                    await page.wait_for_timeout(1600)
                await page.get_by_role("button", name="Save run").click()
                await page.wait_for_timeout(900)
        except Exception as exc:
            print(f"  note: could not save runs ({exc}); run-scoped tiles stay empty")
        for i, d in enumerate(dests):
            await page.evaluate("(s) => { window.location.hash = 'v=' + s }", d["slug"])
            await page.wait_for_timeout(1400)
            seen = ""
            try:
                seen = (await page.inner_text(".bar__searchtxt")).strip()
            except Exception:
                pass
            ok = seen == d["label"]
            await page.evaluate(LABEL_JS, [d["group"], d["label"]])
            await page.wait_for_timeout(150)
            await page.locator(".studio__main").screenshot(
                path=str(shots / f"{i:02d}.png")
            )
            rows.append({**d, "seen": seen, "ok": ok})
            print(
                ("  ok   " if ok else "  WRONG") + f" #v={d['slug']:<18} "
                f"expected {d['label']!r}, shell shows {seen!r}"
            )
        await browser.close()
    return rows


def tile(shots: Path, n: int) -> None:
    files = sorted(shots.glob("*.png"))
    cell_w, cell_h = 430, 270
    filters = []
    layout = []
    for i in range(n):
        filters.append(
            f"[{i}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
            f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:color=#0b0e13[v{i}]"
        )
        layout.append(f"{(i % COLS) * cell_w}_{(i // COLS) * cell_h}")
    inputs = "".join(f"[v{i}]" for i in range(n))
    filters.append(
        f"{inputs}xstack=inputs={n}:layout={'|'.join(layout)}:fill=#0b0e13[out]"
    )
    command = ["ffmpeg", "-v", "error", "-y"]
    for path in files:
        command.extend(["-i", str(path)])
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-frames:v",
            "1",
            str(OUT),
        ]
    )
    subprocess.run(
        command,
        check=True,
    )
    subprocess.run(["sips", "-Z", "1900", str(OUT)], capture_output=True)


async def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        shots = Path(td)
        rows = await shoot(shots)
        tile(shots, len(rows))
    bad = [r for r in rows if not r["ok"]]
    size = OUT.stat().st_size / 1048576
    print(
        f"\n{len(rows)} views, {len(bad)} wrong -> "
        f"{OUT.relative_to(ROOT)} ({size:.2f} MB)"
    )
    if bad:
        sys.exit(
            f"{len(bad)} deep links did not resolve: "
            + ", ".join(r["slug"] for r in bad)
        )


if __name__ == "__main__":
    asyncio.run(main())
