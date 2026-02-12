
import unittest
import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['duckduckgo_search'] = MagicMock()
sys.modules['newspaper'] = MagicMock()

from agent.skills.research.skill import DeepResearchSkill

class TestDeepResearchSkill(unittest.TestCase):
    def setUp(self):
        self.skill = DeepResearchSkill({}, MagicMock())

    def test_can_handle(self):
        self.assertTrue(self.skill.can_handle("research AI agents") > 0.5)
        self.assertEqual(self.skill.can_handle("hello"), 0.0)

    def test_execute_flow(self):
        # Setup mocks
        import duckduckgo_search
        ddgs_instance = MagicMock()
        duckduckgo_search.DDGS.return_value.__enter__.return_value = ddgs_instance
        
        # Mock search results
        ddgs_instance.text.return_value = [
            {'title': 'Result 1', 'href': 'http://test.com', 'body': 'Snippet 1'}
        ]
        
        result = self.skill.execute("deep_research", {"topic": "AI"})
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['status'], 'completed')
        self.assertIn('report_path', result.data)
        self.assertTrue(result.data['report_path'].endswith('.md'))

if __name__ == '__main__':
    unittest.main()
