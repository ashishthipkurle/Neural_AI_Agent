"""
INDRA Keyboard Control — PyAutoGUI keyboard operations with human-like delays.
"""

import time
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ACTION_DELAY_MIN, ACTION_DELAY_MAX
from utils.logger import get_logger

logger = get_logger("Keyboard")

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    logger.error("pyautogui not installed!")


def _human_delay():
    time.sleep(random.uniform(ACTION_DELAY_MIN, ACTION_DELAY_MAX))


class Keyboard:
    """Keyboard control with human-like typing and hotkey support."""

    def type_text(self, text: str, interval: float = 0.03):
        """Type text with human-like per-character delay."""
        if not HAS_PYAUTOGUI or not text:
            return
        _human_delay()
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
        logger.debug(f"Typed: {text[:40]}...")

    def press(self, key: str):
        """Press a single key (enter, tab, escape, etc.)."""
        if not HAS_PYAUTOGUI:
            return
        _human_delay()
        pyautogui.press(key)
        logger.debug(f"Pressed: {key}")

    def hotkey(self, *keys):
        """Press a key combination (e.g. hotkey('ctrl', 'c'))."""
        if not HAS_PYAUTOGUI:
            return
        _human_delay()
        pyautogui.hotkey(*keys)
        logger.debug(f"Hotkey: {'+'.join(keys)}")

    def key_down(self, key: str):
        """Hold a key down."""
        if HAS_PYAUTOGUI:
            pyautogui.keyDown(key)

    def key_up(self, key: str):
        """Release a key."""
        if HAS_PYAUTOGUI:
            pyautogui.keyUp(key)

    def release_all(self):
        """Release all modifier keys (for emergency stop)."""
        if HAS_PYAUTOGUI:
            for key in ['shift', 'ctrl', 'alt', 'win']:
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass
