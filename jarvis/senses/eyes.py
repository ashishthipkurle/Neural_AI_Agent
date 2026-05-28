"""
INDRA Eyes — 60fps screen capture + OpenCV change detection.
Captures continuously; only fires events when meaningful change is detected.
Never calls the vision LLM directly — that is the executor's job.
"""

import threading
import time
import sys
import base64
import io
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CAPTURE_FPS, CHANGE_THRESHOLD
from utils.logger import get_logger

logger = get_logger("Eyes")

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("opencv-python not installed — change detection unavailable")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class Eyes:
    """
    Continuous screen capture at 60fps with OpenCV change detection.
    Fires callbacks only when meaningful screen changes occur.
    """

    def __init__(self):
        self.latest_frame = None      # Always holds the most recent frame (numpy)
        self.prev_frame = None        # Previous frame for diff comparison
        self.change_callbacks = []    # Functions to call on screen change
        self._running = False
        self._thread = None
        self._frame_lock = threading.Lock()

    def start(self):
        """Start the capture loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="indra-eyes"
        )
        self._thread.start()
        logger.info(f"Eyes started ({CAPTURE_FPS}fps target)")

    def stop(self):
        """Stop capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Eyes stopped")

    def on_change(self, callback):
        """Register a callback for screen change events. callback(frame, changed_fraction)."""
        self.change_callbacks.append(callback)

    def get_screenshot_b64(self) -> str:
        """Encode the latest frame as base64 JPEG for the vision LLM."""
        with self._frame_lock:
            frame = self.latest_frame

        if frame is None:
            # Fallback to fresh capture
            from utils.screenshot import capture_screenshot_b64
            return capture_screenshot_b64()

        try:
            # Convert BGRA to RGB
            if HAS_CV2:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            else:
                rgb = frame[:, :, :3]  # Drop alpha, keep BGR

            if HAS_PIL:
                img = Image.fromarray(rgb if not HAS_CV2 else cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB))
                # Send at native resolution — no resize!
                # Vision model coordinates must match actual screen coordinates.
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60)
                buf.seek(0)
                return base64.b64encode(buf.read()).decode("utf-8")
            elif HAS_CV2:
                # Send at native resolution — no resize!
                _, buf = cv2.imencode('.jpg', cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 60])
                return base64.b64encode(buf.tobytes()).decode("utf-8")

        except Exception as e:
            logger.error(f"Frame encoding failed: {e}")

        return ""

    def _capture_loop(self):
        """Main capture loop — runs at target FPS."""
        if not HAS_MSS:
            logger.error("mss not available — Eyes cannot start")
            return

        frame_time = 1.0 / CAPTURE_FPS

        with mss.mss() as sct:
            monitor = sct.monitors[0]

            while self._running:
                t_start = time.perf_counter()

                try:
                    frame = np.array(sct.grab(monitor))
                except Exception as e:
                    logger.debug(f"Screen grab failed: {e}")
                    time.sleep(0.01)
                    continue

                with self._frame_lock:
                    self.latest_frame = frame

                # Change detection
                if self.prev_frame is not None and HAS_CV2 and self.change_callbacks:
                    try:
                        gray_cur = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        gray_prev = cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2GRAY)

                        # Downscale for faster diff (quarter resolution)
                        h, w = gray_cur.shape
                        small_cur = cv2.resize(gray_cur, (w // 4, h // 4))
                        small_prev = cv2.resize(gray_prev, (w // 4, h // 4))

                        diff = cv2.absdiff(small_cur, small_prev)
                        changed_frac = np.count_nonzero(diff > 25) / diff.size

                        if changed_frac > CHANGE_THRESHOLD:
                            for cb in self.change_callbacks:
                                try:
                                    cb(frame, changed_frac)
                                except Exception as e:
                                    logger.debug(f"Change callback error: {e}")
                    except Exception:
                        pass

                self.prev_frame = frame

                # Maintain target FPS
                elapsed = time.perf_counter() - t_start
                sleep_time = max(0, frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
