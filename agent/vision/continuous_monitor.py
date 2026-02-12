
import threading
import time
import logging
import mss
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional, Tuple
from collections import deque

class ContinuousVisionMonitor:
    """
    Module 3: 24/7 Continuous Vision Monitor
    Background screen analysis and circular buffering.
    """

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Monitor config
        self.capture_interval = self.config.get('vision', {}).get('capture_interval_ms', 1000) / 1000.0
        self.monitor_index = self.config.get('vision', {}).get('monitors', [0])[0]
        
        # State
        self.running = False
        self.thread = None
        self.latest_frame = None
        self.latest_analysis = None
        self.latest_timestamp = 0.0
        
        # Circular buffer for 100 frames (as per spec)
        self.capture_buffer = deque(maxlen=100)
        self.lock = threading.Lock()

    def start_monitoring(self) -> None:
        """Start capture loop in background thread."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        self.logger.info("Continuous Vision Monitor started.")

    def stop_monitoring(self) -> None:
        """Signal stop, join threads."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.logger.info("Continuous Vision Monitor stopped.")

    def _capture_loop(self):
        with mss.mss() as sct:
            while self.running:
                start_time = time.time()
                
                try:
                    # Capture screen
                    monitor = sct.monitors[self.monitor_index + 1] # mss monitors are 1-indexed for specific screens
                    sct_img = sct.grab(monitor)
                    
                    # Convert to PIL/Numpy
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    with self.lock:
                        self.latest_frame = img
                        self.latest_timestamp = time.time()
                        self.capture_buffer.append((self.latest_timestamp, img))
                        
                except Exception as e:
                    self.logger.error(f"Screen capture failed: {e}")
                
                # Sleep to maintain interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.capture_interval - elapsed)
                time.sleep(sleep_time)

    def get_current_view(self) -> Dict[str, Any]:
        """Return: {screenshot: PIL.Image, analysis: str, timestamp: float}"""
        with self.lock:
            return {
                "screenshot": self.latest_frame, # Could be None if starting
                "analysis": self.latest_analysis,
                "timestamp": self.latest_timestamp
            }

    def wait_for_condition(self, condition_description: str, 
                           timeout_sec: float = 60.0) -> bool:
        """
        Wait until AI detects condition. 
        Placeholder: logic would involve calling VisionTools/LLM on latest_frame.
        """
        start = time.time()
        while time.time() - start < timeout_sec:
            # Check condition (stubbed for now)
            # In full impl, this calls self.analyze_frame(self.latest_frame) -> bool
            time.sleep(1)
        return False

    def find_on_screen(self, description: str) -> Optional[tuple]:
        """
        Use AI+OCR to locate element. Return (x, y, w, h) or None.
        Placeholder: returns None or mock for now.
        """
        return None
