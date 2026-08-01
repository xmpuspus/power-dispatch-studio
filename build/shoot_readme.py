"""Render README.md through GitHub's own markdown API and screenshot it.

A README is a rendered page, and the only honest way to check one is to look at
it. This posts the file to api.github.com/markdown, wraps the returned HTML in
GitHub's stylesheet, and shoots it at a desktop and a phone width.

Rendered without repo context on purpose: with context GitHub rewrites every
relative path to an absolute /owner/repo/raw/... URL, and then none of the
local images resolve. Without it the paths stay relative and the <base> tag
below points them at the working tree, so what you see is the working tree.

Mode is "markdown", not "gfm". Both render tables, but "gfm" is the comment
renderer and turns every single newline into a <br>, which is not how GitHub
renders a file. Under "gfm" this README's badges stack into a column and every
wrapped source line becomes its own visual line, which looks like a layout bug
in the README and is a bug in the harness.

    python3 build/shoot_readme.py
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tmp" / "readme-shots"
CSS = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css"


def render_html() -> str:
    body = json.dumps({"text": (ROOT / "README.md").read_text(), "mode": "markdown"}).encode()
    req = urllib.request.Request(
        "https://api.github.com/markdown", data=body,
        headers={"Content-Type": "application/json", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        inner = r.read().decode()
    return f"""<!doctype html><html><head><meta charset="utf-8">
<base href="file://{ROOT}/">
<link rel="stylesheet" href="{CSS}">
<style>
  body {{ margin:0; background:#fff; }}
  .markdown-body {{ box-sizing:border-box; max-width:1012px; margin:0 auto; padding:32px; }}
  @media (max-width:500px) {{ .markdown-body {{ padding:14px; }} }}
</style></head><body><article class="markdown-body">{inner}</article></body></html>"""


def main() -> None:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    page_html = OUT / "readme.html"
    page_html.write_text(render_html())

    shots = [("desktop", 1920, 1080), ("mobile", 390, 844)]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, w, h in shots:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(page_html.as_uri(), wait_until="load")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / f"{name}-fold.png"))
            full = OUT / f"{name}-full.png"
            page.screenshot(path=str(full), full_page=True)
            height = page.evaluate("() => document.body.scrollHeight")
            print(f"{name}: fold {w}x{h}, full page {w}x{height}")
            # a readable strip of the studio section, where the new material sits
            page.evaluate(
                """() => { const h = [...document.querySelectorAll('h2')]
                     .find(x => x.textContent.includes('39 views'));
                   if (h) h.scrollIntoView(); }"""
            )
            page.wait_for_timeout(900)
            page.screenshot(path=str(OUT / f"{name}-studio.png"))
            subprocess.run(["sips", "-Z", "1700", str(full)], capture_output=True)
            page.close()
        browser.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
