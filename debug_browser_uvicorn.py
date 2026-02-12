"""Test Playwright in uvicorn-like environment (SelectorEventLoop)."""
import asyncio
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugUvicorn")

async def test_playwright():
    loop = asyncio.get_running_loop()
    logger.info(f"Event loop type: {type(loop).__name__}")
    
    try:
        from playwright.async_api import async_playwright
        logger.info("Starting Playwright...")
        pw = await async_playwright().start()
        logger.info("Playwright started!")
        
        browser = await pw.chromium.launch(headless=False)
        logger.info("Browser launched!")
        
        page = await browser.new_page()
        await page.goto("https://www.google.com")
        logger.info(f"Page title: {await page.title()}")
        
        await asyncio.sleep(3)
        await browser.close()
        await pw.stop()
        logger.info("Done!")
    except Exception as e:
        logger.error(f"Failed: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())

# Run WITHOUT ProactorEventLoop - mimics uvicorn's SelectorEventLoop
if __name__ == "__main__":
    # Don't set ProactorEventLoopPolicy - test with default SelectorEventLoop
    asyncio.run(test_playwright())
