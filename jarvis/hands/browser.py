"""
INDRA Browser Control -- Playwright browser automation (headful Chromium).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("Browser")

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright not installed -- browser automation unavailable")


class Browser:
    """Playwright-based browser automation. Headful (visible) Chromium."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    def _ensure_browser(self):
        """Lazily start browser on first use."""
        if self._page and not self._page.is_closed():
            return

        if not HAS_PLAYWRIGHT:
            logger.error("Playwright unavailable")
            return

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=False,
                args=["--start-maximized"]
            )
            context = self._browser.new_context(
                viewport=None,  # Use full window size
                no_viewport=True
            )
            self._page = context.new_page()
            logger.info("Browser launched (Chromium, headful)")
        except Exception as e:
            logger.error(f"Browser launch failed: {e}")

    def open_url(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigate to a URL."""
        self._ensure_browser()
        if not self._page:
            return

        try:
            if not url.startswith("http"):
                url = f"https://{url}"
            self._page.goto(url, wait_until=wait_until, timeout=30000)
            logger.info(f"Navigated to: {url}")
        except Exception as e:
            logger.error(f"Navigation failed: {e}")

    def click(self, selector: str, timeout: int = 5000):
        """Click an element by CSS selector or text."""
        if not self._page:
            return False
        try:
            self._page.click(selector, timeout=timeout)
            logger.debug(f"Clicked: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Click failed ({selector}): {e}")
            return False

    def type_text(self, selector: str, text: str):
        """Type text into a field."""
        if not self._page:
            return
        try:
            self._page.fill(selector, text)
            logger.debug(f"Typed into {selector}: {text[:30]}...")
        except Exception as e:
            logger.warning(f"Type failed ({selector}): {e}")

    def press_key(self, key: str):
        """Press a keyboard key in the browser."""
        if not self._page:
            return
        try:
            self._page.keyboard.press(key)
        except Exception as e:
            logger.warning(f"Key press failed: {e}")

    def get_text(self, selector: str) -> str:
        """Get text content of an element."""
        if not self._page:
            return ""
        try:
            return self._page.text_content(selector, timeout=3000) or ""
        except Exception:
            return ""

    def get_page_title(self) -> str:
        """Get current page title."""
        if not self._page:
            return ""
        try:
            return self._page.title()
        except Exception:
            return ""

    def get_url(self) -> str:
        """Get current URL."""
        if not self._page:
            return ""
        try:
            return self._page.url
        except Exception:
            return ""

    def screenshot_b64(self) -> str:
        """Take a screenshot of the browser page as base64."""
        if not self._page:
            return ""
        try:
            import base64
            buf = self._page.screenshot(type="jpeg", quality=70)
            return base64.b64encode(buf).decode("utf-8")
        except Exception:
            return ""

    def wait(self, ms: int = 1000):
        """Wait for a specified duration."""
        if self._page:
            self._page.wait_for_timeout(ms)

    def close(self):
        """Close the browser."""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            logger.info("Browser closed")
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._playwright = None
