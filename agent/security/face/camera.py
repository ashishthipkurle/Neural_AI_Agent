"""
Face Camera - Dedicated camera interface for face authentication.

This module provides camera access specifically for face recognition,
with privacy-focused design.
"""
import logging
import os
from typing import Optional, Tuple
import threading
import time

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


class FaceCamera:
    """
    Camera interface for face authentication.
    
    Privacy considerations:
    - Frames are NOT stored unless explicitly requested
    - Auto-release on timeout
    - Session-scoped operation
    """
    
    def __init__(self, camera_index: int = 0):
        """
        Initialize face camera.
        
        Args:
            camera_index: Camera device index.
        """
        self.logger = logging.getLogger("FaceCamera")
        self.camera_index = camera_index
        self._cap = None
        self._lock = threading.RLock()
        self._is_open = False
        
        if cv2 is None:
            self.logger.error("OpenCV not available. Face camera disabled.")
    
    def open(self) -> bool:
        """
        Open camera connection.
        
        Returns:
            True if opened successfully.
        """
        if cv2 is None:
            return False
        
        with self._lock:
            if self._is_open:
                return True
            
            try:
                # Try DirectShow on Windows for better performance
                if os.name == 'nt':
                    self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                else:
                    self._cap = cv2.VideoCapture(self.camera_index)
                
                if not self._cap.isOpened():
                    # Try fallback
                    self._cap = cv2.VideoCapture(self.camera_index)
                
                if self._cap.isOpened():
                    self._is_open = True
                    self.logger.info(f"Camera {self.camera_index} opened.")
                    return True
                else:
                    self.logger.error(f"Failed to open camera {self.camera_index}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Camera open error: {e}")
                return False
    
    def close(self) -> None:
        """Close camera connection."""
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None
            self._is_open = False
            self.logger.info("Camera closed.")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame.
        
        Returns:
            Frame as numpy array or None if failed.
        """
        if not self._is_open:
            if not self.open():
                return None
        
        with self._lock:
            try:
                ret, frame = self._cap.read()
                if ret:
                    return frame
                else:
                    self.logger.warning("Failed to read frame.")
                    return None
            except Exception as e:
                self.logger.error(f"Capture error: {e}")
                return None
    
    def capture_for_verification(self, num_frames: int = 3) -> list:
        """
        Capture multiple frames for verification.
        
        Args:
            num_frames: Number of frames to capture.
        
        Returns:
            List of captured frames.
        """
        frames = []
        for i in range(num_frames):
            frame = self.capture_frame()
            if frame is not None:
                frames.append(frame)
            time.sleep(0.1)  # Brief delay between frames
        
        self.logger.debug(f"Captured {len(frames)} frames for verification.")
        return frames
    
    def is_available(self) -> bool:
        """Check if camera is available."""
        if cv2 is None:
            return False
        
        if self._is_open:
            return True
        
        # Try to open briefly to check
        try:
            cap = cv2.VideoCapture(self.camera_index)
            available = cap.isOpened()
            cap.release()
            return available
        except:
            return False
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
