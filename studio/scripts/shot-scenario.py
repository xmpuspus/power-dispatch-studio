import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:5173/"
OUT = Path("/tmp/scn-qa")
OUT.mkdir(exist_ok=True)


async def shot(page, name, theme, vw, vh):
    await page.set_viewport_size({"width": vw, "height": vh})
    await page.goto(BASE, wait_until="networkidle")
    # force theme
    await page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
    await page.get_by_role("button", name="Open PLEXOS Studio").click()
    await page.wait_for_selector('[data-testid="scenario"]', timeout=8000)
    await page.wait_for_timeout(700)
    p = OUT / f"{name}.png"
    await page.screenshot(path=str(p), full_page=True)
    print("wrote", p)
    return page


async def interact(page):
    # drive the DC + relief scenario on Visayas to show the congested->relieved story
    # switch grid to Visayas via the top segmented control
    await page.get_by_role("tab", name="Visayas").click()
    await page.wait_for_timeout(300)
    sliders = page.locator("input.lever__range")
    # addDC is the first slider; push it to bind the corridor
    await sliders.nth(0).fill("900")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(OUT / "visayas-congested.png"), full_page=True)
    print("wrote visayas-congested")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        await shot(page, "light-1920", "light", 1920, 1080)
        await shot(page, "dark-1440", "dark", 1440, 900)
        await shot(page, "light-again", "light", 1440, 900)
        await interact(page)
        await b.close()


asyncio.run(main())
