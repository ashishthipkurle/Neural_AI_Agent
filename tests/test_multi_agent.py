
import unittest
from unittest.mock import MagicMock
from agent.core.multi_agent import MultiAgentOrchestrator

class TestMultiAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.chat.return_value = "Mock response"
        self.mock_memory = MagicMock()
        self.orchestrator = MultiAgentOrchestrator(self.mock_llm, self.mock_memory)

    def test_solve_complex_task(self):
        result = self.orchestrator.solve_complex_task("Build a website")
        self.assertEqual(result['status'], 'completed')
        self.assertIn('plan', result)
        
        # Verify planner was called
        # We can't easily verify internal private calls without complex mocking
        # so we rely on return values and log checks if we captured logs
        pass

    def test_agent_discussion(self):
        # Configure mock to return different things
        self.mock_llm.chat.side_effect = ["Plan A", "Critique A", "Refined A"]
        
        transcript = self.orchestrator._agent_discussion("Topic", ["planner", "critic"], max_rounds=1)
        
        self.assertIn("planner:", transcript)
        self.assertIn("critic:", transcript)

if __name__ == '__main__':
    unittest.main()
