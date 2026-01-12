"""Capture screenshots for user guide."""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = "/src/docs/user-guide/screenshots"


async def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # 1. Home page - vision list
        page = await browser.new_page(viewport={"width": 1200, "height": 600})
        await page.goto(f"{BASE_URL}/vision/")
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{OUTPUT_DIR}/home.png")
        print("Captured home.png")
        await page.close()

        # 2. Canvas view
        page = await browser.new_page(viewport={"width": 1400, "height": 800})
        await page.goto(f"{BASE_URL}/vision/1/")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=f"{OUTPUT_DIR}/canvas.png")
        print("Captured canvas.png")

        # 3. Canvas groups (same as canvas for now)
        await page.screenshot(path=f"{OUTPUT_DIR}/canvas-groups.png")
        print("Captured canvas-groups.png")
        await page.close()

        # 4. Statement form - fresh page load
        page = await browser.new_page(viewport={"width": 800, "height": 600})
        await page.goto(f"{BASE_URL}/vision/1/")
        await page.wait_for_timeout(1000)
        try:
            btn = page.locator("[hx-get*='statement-form']").first
            await btn.click(timeout=5000)
            await page.wait_for_timeout(1500)
            # Get modal that's not bg-dark
            modal = page.locator(".modal-content:not(.bg-dark)").first
            if await modal.count() > 0 and await modal.is_visible():
                await modal.screenshot(path=f"{OUTPUT_DIR}/statement-form.png")
                print("Captured statement-form.png")
            else:
                # Try the visible modal
                modal = page.locator(".modal.show .modal-content").first
                if await modal.count() > 0:
                    await modal.screenshot(path=f"{OUTPUT_DIR}/statement-form.png")
                    print("Captured statement-form.png (alt)")
        except Exception as e:
            print(f"Could not capture statement-form: {e}")
        await page.close()

        # 5. Reference form - fresh page load
        page = await browser.new_page(viewport={"width": 800, "height": 600})
        await page.goto(f"{BASE_URL}/vision/1/")
        await page.wait_for_timeout(1000)
        try:
            btn = page.locator("[hx-get*='reference-form']").first
            await btn.click(timeout=5000)
            await page.wait_for_timeout(1500)
            modal = page.locator(".modal-content:not(.bg-dark)").first
            if await modal.count() > 0 and await modal.is_visible():
                await modal.screenshot(path=f"{OUTPUT_DIR}/reference-form.png")
                print("Captured reference-form.png")
            else:
                modal = page.locator(".modal.show .modal-content").first
                if await modal.count() > 0:
                    await modal.screenshot(path=f"{OUTPUT_DIR}/reference-form.png")
                    print("Captured reference-form.png (alt)")
        except Exception as e:
            print(f"Could not capture reference-form: {e}")
        await page.close()

        # 6. Version tabs - capture toolbar area
        page = await browser.new_page(viewport={"width": 1400, "height": 800})
        await page.goto(f"{BASE_URL}/vision/1/")
        await page.wait_for_timeout(1000)
        try:
            toolbar = page.locator(".d-flex.justify-content-between").first
            if await toolbar.count() > 0:
                await toolbar.screenshot(path=f"{OUTPUT_DIR}/version-tabs.png")
                print("Captured version-tabs.png")
            else:
                await page.screenshot(
                    path=f"{OUTPUT_DIR}/version-tabs.png",
                    clip={"x": 0, "y": 0, "width": 600, "height": 80}
                )
                print("Captured version-tabs.png (top clip)")
        except Exception as e:
            print(f"Could not capture version-tabs: {e}")
        await page.close()

        await browser.close()

    # List captured files
    print(f"\nScreenshots saved to {OUTPUT_DIR}/")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.png'):
            size = os.path.getsize(f"{OUTPUT_DIR}/{f}")
            print(f"  {f}: {size:,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
