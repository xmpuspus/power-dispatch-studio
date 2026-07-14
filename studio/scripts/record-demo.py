import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://localhost:5188/"
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
        await asyncio.sleep(3.0)  # landing hero + stat tiles settle

        # into the studio: the Generators grid is the DOE per-plant fleet
        await tap(page, page.get_by_role("button", name="Open Power Dispatch Studio"),
                  pause_after=2.8)

        # trip a Sual unit in the Properties grid: SPI U1 from 647 to 0 MW
        spi = page.locator('input[aria-label="SPI U1 Dependable"]')
        await spi.scroll_into_view_if_needed()
        await spi.hover()
        await asyncio.sleep(0.5)
        await spi.fill("0")
        await asyncio.sleep(1.6)  # edited cell highlights, status goes Unsolved

        # Run: the model re-solves, the status flips to Solved
        await tap(page, page.get_by_role("button", name="Run the simulation"),
                  pause_after=1.6)

        # Chronology: replay an observed day on the edited model
        await tap(page, page.get_by_role("tab", name="Simulation"), pause_after=0.7)
        await tap(page, page.get_by_role("button", name="Chronology"),
                  pause_after=3.2)
        # scroll through dispatch-by-fuel and the storage state of charge
        await page.mouse.move(W // 2, H // 2)
        for _ in range(3):
            await page.mouse.wheel(0, 420)
            await asyncio.sleep(1.2)
        await asyncio.sleep(0.8)
        for _ in range(3):
            await page.mouse.wheel(0, -560)
            await asyncio.sleep(0.4)

        # freeze the solve as a run, then the runs ledger
        await tap(page, page.get_by_role("button", name="Save run"), pause_after=1.4)
        await tap(page, page.get_by_role("button", name="Saved runs"),
                  pause_after=2.6)

        # the backcast: the base model against the observed price tape
        await tap(page, page.get_by_role("button", name="Backcast"), pause_after=3.4)
        await page.mouse.wheel(0, 420)
        await asyncio.sleep(2.0)
        await page.mouse.wheel(0, -420)
        await asyncio.sleep(0.6)

        # flip to the dark theme, then close
        await page.locator(".studio__barright .btn--icon").first.click()
        await asyncio.sleep(2.6)
        await tap(page, page.get_by_role("button", name="Close studio"),
                  pause_after=1.2)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        print(vid)


asyncio.run(main())
