
import unittest
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock Playwright
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()

from agent.skills.browser.skill import AdvancedBrowserSkill

class TestAdvancedBrowserSkill(unittest.TestCase):
    def setUp(self):
        self.config = {'browser': {'headless': True}}
        self.skill = AdvancedBrowserSkill(self.config)
        
        # Setup Playwright Mocks
        self.mock_page = AsyncMock()
        self.mock_page.goto = AsyncMock()
        self.mock_page.title.return_value = "Test Page"
        self.mock_page.url = "http://test.com"
        
        self.mock_context = AsyncMock()
        self.mock_context.new_page.return_value = self.mock_page
        
        self.mock_browser = AsyncMock()
        self.mock_browser.new_context.return_value = self.mock_context
        
        self.mock_pw = AsyncMock()
        self.mock_pw.chromium.launch.return_value = self.mock_browser
        
        # Inject mocks into skill manually since on_load is async and we want to control state
        self.skill.playwright = self.mock_pw
        self.skill.browser = self.mock_browser
        self.skill.context = self.mock_context
        self.skill.page = self.mock_page
        self.skill._loaded = True # Simulate loaded

    def test_browse_action(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self.skill.execute("browse", {"url": "http://example.com"})
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['title'], "Test Page")
        self.mock_page.goto.assert_called_with("http://example.com", wait_until="domcontentloaded")

    def test_click_action(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self.skill.execute("click", {"selector": "#btn"})
        )
        
        self.assertTrue(result.success)
        self.mock_page.click.assert_called_with("#btn")

if __name__ == '__main__':
    unittest.main()
