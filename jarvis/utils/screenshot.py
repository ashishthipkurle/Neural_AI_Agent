"""
INDRA Screenshot Utility — Captures screen, encodes base64 for vision LLM.
"""

import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("Screenshot")

try:
    import mss
    import numpy as np
    from PIL import Image
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    logger.warning("mss/Pillow not installed — screenshots unavailable")


def capture_screenshot_b64(quality: int = 70, max_width: int = 1280) -> str:
    """
    Capture the primary monitor and return as base64-encoded JPEG.
    
    Args:
        quality: JPEG quality (0-100). Lower = smaller, faster LLM processing.
        max_width: Resize to this width if larger (preserves aspect ratio).
    
    Returns: Base64 string of JPEG image.
    """
    if not HAS_MSS:
        return ""

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Primary monitor (full virtual screen)
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Resize if too large
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Encode as JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")

    except Exception as e:
        logger.error(f"Screenshot capture failed: {e}")
        return ""


def capture_screenshot_np():
    """Capture screen as numpy array (BGR). Used by Eyes for change detection."""
    if not HAS_MSS:
        return None
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            return np.array(screenshot)
    except Exception as e:
        logger.error(f"Screenshot numpy capture failed: {e}")
        return None
