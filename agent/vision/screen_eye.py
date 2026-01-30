
import mss
import mss.tools
import os
from datetime import datetime
import logging

class ScreenEye:
    """
    Handles screen capture and basic visual analysis (like OCR if needed).
    """
    def __init__(self, output_dir="logs/vision"):
        self.logger = logging.getLogger("ScreenEye")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.sct = mss.mss()

    def capture(self, monitor_index=1) -> str:
        """
        Captures the screen and saves it to a file.
        Returns the absolute path of the saved image.
        """
        try:
            # Get information of monitor 1
            monitor = self.sct.monitors[monitor_index] if monitor_index < len(self.sct.monitors) else self.sct.monitors[1]
            
            # Grab the data
            sct_img = self.sct.grab(monitor)
            
            # Save to the picture file
            filename = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            output_path = os.path.join(self.output_dir, filename)
            
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
            
            self.logger.info(f"Screen captured: {output_path}")
            return os.path.abspath(output_path)
            
        except Exception as e:
            self.logger.error(f"Failed to capture screen: {e}")
            return ""

    def list_monitors(self):
        return self.sct.monitors
