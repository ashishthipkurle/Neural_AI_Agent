
import unittest
import os
import shutil
from agent.memory.personal_memory import PersonalMemoryManager

class TestPersonalMemoryManager(unittest.TestCase):
    def setUp(self):
        self.test_db = "agent_data/test_memory.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.memory = PersonalMemoryManager(self.test_db)

    def tearDown(self):
        # Force close connection if the manager has one open
        # Since the manager opens connections per method with context managers, 
        # there shouldn't be a persistent one unless we modify the class or test.
        # However, SQLite in WAL mode might keep file locks.
        # Let's try to garbage collect or ensure no pending connections.
        import gc
        del self.memory
        gc.collect()
        
        # Retry removal with small delay
        import time
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


    def test_init_wal_mode(self):
        # Verify WAL mode is set
        with self.memory._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_record_action_and_query(self):
        action_id = self.memory.record_action(
            action_type="test",
            description="Testing memory system",
            method="unittest",
            tags=["test", "unit"]
        )
        self.assertTrue(action_id)
        
        # Query
        results = self.memory.query_memory("Testing")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['data'][3], "Testing memory system") # description

    def test_context_generation(self):
        # Add some data
        # Initial score 0.5. Need > 0.6 to appear in context.
        # Call 3 times: 0.5 -> 0.6 -> 0.7
        self.memory.record_preference("coding", "Python")
        self.memory.record_preference("coding", "Python")
        self.memory.record_preference("coding", "Python")
        
        self.memory.add_important_note("Deadline tomorrow", priority=10)
        
        context = self.memory.get_user_context()
        self.assertIn("Python", context)
        self.assertIn("Deadline tomorrow", context)

if __name__ == '__main__':
    unittest.main()
