from playwright.async_api import async_playwright
import logging
import asyncio

class BrowserTools:
    """
    Tools for interacting with the web using Playwright.
    """
    def __init__(self):
        self.logger = logging.getLogger("BrowserTools")
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def _init_browser(self):
        if not self.browser:
            self.playwright = await async_playwright().start()
            # Launch in headed mode so user can see what's happening
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            self.logger.info("Browser launched (Headed).")

    async def navigate_to(self, url: str) -> str:
        """
        Navigates the browser to the specified URL.
        """
        try:
            if not url.startswith("http"):
                url = "https://" + url
                
            await self._init_browser()
            await self.page.goto(url)
            title = await self.page.title()
            return f"Navigated to {url}. Page Title: {title}"
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            return f"Error navigating to {url}: {e}"

    async def read_content(self) -> str:
        """
        Reads the text content of the current page.
        """
        if not self.page: return "Error: Browser not open."
        try:
            content = await self.page.inner_text("body")
            return content[:2000] + "..." # Truncate for now
        except Exception as e:
            return f"Error reading content: {e}"
            
    async def close_browser(self) -> str:
        """
        Closes the browser instance.
        """
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
            if self.playwright:
                await self.playwright.stop()
            return "Browser closed."
        return "Browser was not open."
