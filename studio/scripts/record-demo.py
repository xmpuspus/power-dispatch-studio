import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://localhost:5200/studio/"
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
        # /studio/ opens the studio itself. It used to stop at a second copy of
        # the map, which this bundle no longer carries.
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_selector('[data-testid="studio"]', timeout=20000)
        await asyncio.sleep(3.0)  # the base case solves on load

        # The studio opens on the what-if controls, so reach the fleet table first.
        await page.evaluate(
            """() => { document.querySelectorAll('.rail__grouphead').forEach(b => {
                 if (b.getAttribute('aria-expanded') === 'false') b.click() }) }"""
        )
        await asyncio.sleep(0.4)
        await tap(
            page,
            page.get_by_role("button", name="Generators", exact=True),
            pause_after=1.4,
        )

        # trip a Sual unit in the Properties grid: SPI U1 from 647 to 0 MW
        spi = page.locator('input[aria-label="SPI U1 Dependable"]')
        await spi.scroll_into_view_if_needed()
        await spi.hover()
        await asyncio.sleep(0.5)
        await spi.fill("0")
        await asyncio.sleep(1.6)  # edited cell highlights, status goes Unsolved

        # Run: the model re-solves, the status flips to Solved
        await tap(
            # the class, not the aria label: Run now names its edit count and is
            # absent while nothing waits
            page,
            page.locator(".bar__run"),
            pause_after=1.6,
        )

        # Hourly market replay: run an observed day on the edited model
        # the question rail replaced the System/Simulation tabs; open every group
        await page.evaluate(
            """() => {
              document.querySelectorAll('.rail__grouphead').forEach(b => {
                if (b.getAttribute('aria-expanded') === 'false') b.click()
              })
            }"""
        )
        await tap(
            page,
            page.get_by_role("button", name="Hourly market replay"),
            pause_after=3.2,
        )
        # scroll through dispatch-by-fuel and the storage state of charge
        await page.mouse.move(W // 2, H // 2)
        for _ in range(3):
            await page.mouse.wheel(0, 420)
            await asyncio.sleep(1.2)
        await asyncio.sleep(0.8)
        for _ in range(3):
            await page.mouse.wheel(0, -560)
            await asyncio.sleep(0.4)

        # Save the calculation, then open the saved-runs list.
        await tap(page, page.get_by_role("button", name="Save run"), pause_after=1.4)
        await tap(
            page,
            page.get_by_role("button", name="Saved simulation runs"),
            pause_after=2.6,
        )

        # Compare the base model with recorded prices.
        await tap(
            page,
            page.get_by_role("button", name="Historical replay"),
            pause_after=3.4,
        )
        await page.mouse.wheel(0, 420)
        await asyncio.sleep(2.0)
        await page.mouse.wheel(0, -420)
        await asyncio.sleep(0.6)

        # Compare the transmission-loss calculation with recorded node prices.
        # per-node prices, the newest analysis surface
        await tap(
            page,
            page.get_by_role("button", name="Transmission-loss check"),
            pause_after=3.4,
        )
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(2.2)
        await page.mouse.wheel(0, -300)
        await asyncio.sleep(0.6)

        # flip to the dark theme, where the loss-validation panels remap
        await page.locator('.bar button[aria-label^="Switch to"]').click()
        await asyncio.sleep(3.2)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        print(vid)


asyncio.run(main())
