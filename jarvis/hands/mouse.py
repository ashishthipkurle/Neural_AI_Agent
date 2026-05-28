"""
INDRA Mouse Control — PyAutoGUI mouse operations with human-like delays.
"""

import time
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ACTION_DELAY_MIN, ACTION_DELAY_MAX
from utils.logger import get_logger

logger = get_logger("Mouse")

try:
    import pyautogui
    pyautogui.FAILSAFE = True    # Move mouse to corner to abort
    pyautogui.PAUSE = 0.05       # Small pause between actions
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    logger.error("pyautogui not installed!")


def _human_delay():
    """Add a small random delay to mimic human behavior."""
    time.sleep(random.uniform(ACTION_DELAY_MIN, ACTION_DELAY_MAX))


class Mouse:
    """Mouse control with human-like timing."""

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        """Click at coordinates."""
        if not HAS_PYAUTOGUI:
            return
        _human_delay()
        pyautogui.click(x, y, button=button, clicks=clicks)
        logger.debug(f"Click ({button}) at ({x}, {y})")

    def double_click(self, x: int, y: int):
        """Double-click at coordinates."""
        self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int):
        """Right-click at coordinates."""
        self.click(x, y, button="right")

    def move(self, x: int, y: int, duration: float = 0.3):
        """Move mouse to coordinates with smooth animation."""
        if not HAS_PYAUTOGUI:
            return
        pyautogui.moveTo(x, y, duration=duration)
        logger.debug(f"Move to ({x}, {y})")

    def scroll(self, direction: str = "down", amount: int = 3):
        """Scroll up or down."""
        if not HAS_PYAUTOGUI:
            return
        _human_delay()
        clicks = amount if direction == "up" else -amount
        pyautogui.scroll(clicks)
        logger.debug(f"Scroll {direction} x{amount}")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """Drag from (x1,y1) to (x2,y2)."""
        if not HAS_PYAUTOGUI:
            return
        _human_delay()
        pyautogui.moveTo(x1, y1, duration=0.1)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
        logger.debug(f"Drag ({x1},{y1}) → ({x2},{y2})")

    def get_position(self) -> tuple[int, int]:
        """Get current mouse position."""
        if HAS_PYAUTOGUI:
            pos = pyautogui.position()
            return (pos.x, pos.y)
        return (0, 0)

    def release_all(self):
        """Release mouse buttons (for emergency stop)."""
        if HAS_PYAUTOGUI:
            pyautogui.mouseUp()
