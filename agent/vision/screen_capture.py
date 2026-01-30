import os
import datetime
from PIL import ImageGrab

class ScreenCapture:
    def __init__(self, output_dir="captures"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                pass

    def capture(self) -> str:
        """Capture the screen and save to a file."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            # Capture full screen
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            
            return os.path.abspath(filepath)
        except Exception as e:
            raise Exception(f"Failed to capture screen: {e}")
