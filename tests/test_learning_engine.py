
import unittest
import os
import time
from agent.core.learning_engine import SelfLearningEngine

class TestSelfLearningEngine(unittest.TestCase):
    def setUp(self):
        self.test_db = "agent_data/test_learning.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.engine = SelfLearningEngine(self.test_db)

    def tearDown(self):
        import gc
        del self.engine
        gc.collect()

        for i in range(5):
            try:
                if os.path.exists(self.test_db):
                    os.remove(self.test_db)
                if os.path.exists(self.test_db + "-wal"):
                    os.remove(self.test_db + "-wal")
                if os.path.exists(self.test_db + "-shm"):
                    os.remove(self.test_db + "-shm")
                break
            except PermissionError:
                time.sleep(0.1)

    def test_record_and_suggest(self):
        # Record successful
        for _ in range(5):
            self.engine.record_outcome("test", "skill_A", "prompt", True, 1.0)
            
        # Record failures
        for _ in range(6):
            self.engine.record_outcome("test", "skill_B", "prompt", False, 1.0, "Error")
            
        suggestions = self.engine.suggest_skill_improvement()
        
        # skill_B has 0% success rate (6 fails), so should be suggested
        # skill_A has 100%, should not
        skills = [s['skill'] for s in suggestions]
        self.assertIn("skill_B", skills)
        self.assertNotIn("skill_A", skills)

if __name__ == '__main__':
    unittest.main()
