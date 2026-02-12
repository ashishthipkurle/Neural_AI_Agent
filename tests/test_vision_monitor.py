
import unittest
import time
import threading
from agent.vision.continuous_monitor import ContinuousVisionMonitor

class TestContinuousVisionMonitor(unittest.TestCase):
    def setUp(self):
        self.config = {
            'vision': {
                'capture_interval_ms': 100, # Fast interval for test
                'monitors': [0]
            }
        }
        self.monitor = ContinuousVisionMonitor(self.config)

    def tearDown(self):
        if self.monitor.running:
            self.monitor.stop_monitoring()
        del self.monitor

    def test_start_stop(self):
        self.monitor.start_monitoring()
        time.sleep(0.5) # Let it capture a few frames
        self.assertTrue(self.monitor.running)
        
        # Check if we got a frame
        view = self.monitor.get_current_view()
        # Takes time to capture first frame, might differ based on machine
        # We just check structure returned
        self.assertIn("screenshot", view)
        self.assertIn("timestamp", view)
        
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.running)

if __name__ == '__main__':
    unittest.main()
