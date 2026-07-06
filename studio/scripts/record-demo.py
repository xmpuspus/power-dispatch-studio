import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:5173/"
OUT = Path("/tmp/studio-rec")
OUT.mkdir(exist_ok=True)
W, H = 1280, 760


async def click_text(page, selector, text, pause=0.4):
    el = page.locator(selector, has_text=text).first
    await el.scroll_into_view_if_needed()
    await el.hover()
    await asyncio.sleep(pause)
    await el.click()


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
        await asyncio.sleep(3.5)  # landing hero + map settle

        await click_text(page, ".btn--primary", "Open PLEXOS Studio")
        await asyncio.sleep(4)  # coupled flows (default view)

        await click_text(page, ".tree__item", "Price duration")
        await asyncio.sleep(3)
        # switch the grid to Visayas on a grid-scoped view
        await click_text(page, ".segmented__item", "Visayas")
        await asyncio.sleep(2.5)

        await click_text(page, ".tree__item", "Reliability")
        await asyncio.sleep(3.5)

        await click_text(page, ".tree__item", "Merit order")
        await asyncio.sleep(3)

        # toggle dark theme from the studio bar
        await page.locator(".studio__barright .btn--icon").first.click()
        await asyncio.sleep(3.5)

        await click_text(page, ".btn--ghost", "Close studio")
        await asyncio.sleep(1.5)

        await ctx.close()
        vid = await page.video.path()
        await browser.close()
        print(vid)


asyncio.run(main())
