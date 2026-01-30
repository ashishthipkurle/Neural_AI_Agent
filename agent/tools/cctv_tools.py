import cv2
import time
import logging
import os
from datetime import datetime
from agent.vision.camera_stream import CameraStream

class CCTVTools:
    """
    Tools for monitoring video feeds using the robust CameraStream with Object Detection.
    """
    def __init__(self):
        self.logger = logging.getLogger("CCTVTools")
        self.stream = None

    def start_surveillance(self, source: str = "0") -> str:
        """
        Starts the CCTV surveillance window with Object Detection and Face Recognition.
        Opens a native window on the host machine.
        """
        try:
            # Parse source
            video_source = int(source) if source.isdigit() else source
            
            # Initialize Stream if not exists or if source changed
            if self.stream:
                self.stream.stop()
            
            self.stream = CameraStream(source=video_source)
            self.stream.start()
            
            return f"Surveillance started on Camera {source}. Look for the 'CCTV Surveillance' window."
        except Exception as e:
            self.logger.error(f"Failed to start surveillance: {e}")
            return f"Error starting surveillance: {e}"

    def stop_surveillance(self) -> str:
        """Stops the CCTV stream."""
        if self.stream:
            self.stream.stop()
            self.stream = None
            return "Surveillance stopped."
        return "No active surveillance to stop."

