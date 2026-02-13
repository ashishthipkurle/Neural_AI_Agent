
import unittest
import os
import time
from agent.core.task_manager import PersistentTaskManager

class TestPersistentTaskManager(unittest.TestCase):
    def setUp(self):
        self.test_db = "agent_data/test_tasks.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.tm = PersistentTaskManager(self.test_db)

    def tearDown(self):
        import gc
        del self.tm
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

    def test_init_wal_mode(self):
        with self.tm._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_create_and_manage_task(self):
        # Create
        task_id = self.tm.create_task("Test Task", "coding", priority=9)
        self.assertTrue(task_id)
        
        # Verify status
        status = self.tm.get_task_status(task_id)
        self.assertEqual(status['status'], 'PENDING')
        
        # Execute (simulate start)
        self.tm.execute_task(task_id)
        status = self.tm.get_task_status(task_id)
        self.assertEqual(status['status'], 'RUNNING')
        
        # Checkpoint
        state = {"step": 1, "vars": {"x": 10}}
        self.tm.checkpoint(task_id, state)
        
        # Resume
        resumed_state = self.tm.resume_from_checkpoint(task_id)
        self.assertEqual(resumed_state['vars']['x'], 10)
        
        # Cancel
        self.tm.cancel_task(task_id)
        status = self.tm.get_task_status(task_id)
        self.assertEqual(status['status'], 'FAILED')

    def test_api_compat_methods(self):
        task_id = self.tm.submit_task(
            description="Compat task",
            skill_name="browser",
            params={"url": "https://example.com"},
            priority=4
        )
        self.assertTrue(task_id)

        tasks = self.tm.list_tasks(limit=10)
        self.assertTrue(any(t.get("id") == task_id for t in tasks))

        cancelled = self.tm.cancel_task(task_id)
        self.assertTrue(cancelled)

if __name__ == '__main__':
    unittest.main()
