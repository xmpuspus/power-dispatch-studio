import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:5173/"
OUT = Path("/tmp/studio-rec")
OUT.mkdir(exist_ok=True)
W, H = 1400, 840


async def tap(page, locator, pause_before=0.35, pause_after=1.4):
    """Hover then click a locator, with pauses so the GIF reads."""
    el = locator.first
    await el.scroll_into_view_if_needed()
    await el.hover()
    await asyncio.sleep(pause_before)
    await el.click()
    await asyncio.sleep(pause_after)


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
        await page.goto(BASE, wait_until="networkidle")
        await asyncio.sleep(3.2)  # landing hero + stat tiles settle

        # into the studio, which opens on the editable Generators property grid
        await tap(page, page.get_by_role("button", name="Open PLEXOS Studio"),
                  pause_after=2.6)

        # edit a named unit in the Properties grid: cut Sual from 1294 to 600 MW
        sual = page.locator('input[aria-label="Sual Max capacity"]')
        await sual.scroll_into_view_if_needed()
        await sual.hover()
        await asyncio.sleep(0.4)
        await sual.fill("600")
        await asyncio.sleep(1.8)  # edited cell highlights, status goes Unsolved

        # show the Memberships tab (object relations), then back to Properties
        await tap(page, page.get_by_role("tab", name="Memberships"), pause_after=2.4)
        await tap(page, page.get_by_role("tab", name="Properties"), pause_after=1.2)

        # Run: the model re-solves, the status flips to Solved
        await tap(page, page.get_by_role("button", name="Run the simulation"),
                  pause_after=1.8)

        # browse the Solution: merit order (reserve margin has moved), coupled flows
        await tap(page, page.get_by_role("tab", name="Simulation"), pause_after=0.8)
        await tap(page, page.get_by_role("button", name="Merit order"), pause_after=2.8)
        await tap(page, page.get_by_role("button", name="Coupled flows"), pause_after=2.6)
        await tap(page, page.get_by_role("button", name="Reliability"), pause_after=3.0)

        # a second scenario: add it, edit a region load, compare side by side
        await tap(page, page.get_by_role("button", name="+ New"), pause_after=1.0)
        await tap(page, page.get_by_role("tab", name="System"), pause_after=0.6)
        await tap(page, page.get_by_role("button", name="Regions"), pause_after=1.0)
        load = page.locator('input[aria-label="Luzon Load (evening)"]')
        await load.scroll_into_view_if_needed()
        await load.hover()
        await asyncio.sleep(0.4)
        await load.fill("16031")
        await asyncio.sleep(1.4)
        await tap(page, page.get_by_role("tab", name="Simulation"), pause_after=0.6)
        await tap(page, page.get_by_role("button", name="Compare scenarios"),
                  pause_after=3.2)

        # an Analysis view with no base-PLEXOS equal: the market-power lens
        await tap(page, page.get_by_role("button", name="Market power"), pause_after=3.0)

        # flip to the dark theme, then close
        await page.locator(".studio__barright .btn--icon").first.click()
        await asyncio.sleep(3.0)
        await tap(page, page.get_by_role("button", name="Close studio"), pause_after=1.4)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        print(vid)


asyncio.run(main())
