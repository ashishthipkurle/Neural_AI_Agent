"""
INDRA Vision Brain -- Vision LLM for screen understanding.
Runs in its own thread pool, completely isolated from ChatBrain.
"""

import threading
import time
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import VISION_MODEL, VISION_COOLDOWN
from utils.logger import get_logger

logger = get_logger("VisionBrain")

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    logger.error("ollama SDK not installed!")


class VisionBrain:
    """
    Vision LLM for screen understanding and action planning.
    Separate thread pool -- NEVER shares threads with ChatBrain.
    """

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision_brain")
        self._last_call_time = 0
        self._lock = threading.Lock()

    def decide_async(self, screenshot_b64: str, task: str, current_step: str):
        """Submit a vision decision as a non-blocking future."""
        return self.executor.submit(self._decide, screenshot_b64, task, current_step)

    def _decide(self, screenshot_b64: str, task: str, current_step: str) -> dict:
        """
        Analyse a screenshot and return the next action to take.
        
        Returns dict with:
          screen_state, previous_step_complete, next_action, target,
          value, coordinates, confidence, narration
        """
        if not HAS_OLLAMA:
            return self._fallback_action("Vision LLM unavailable")

        # Enforce cooldown to prevent spamming
        with self._lock:
            time_since_last = time.time() - self._last_call_time
            if time_since_last < VISION_COOLDOWN:
                time.sleep(VISION_COOLDOWN - time_since_last)

        # Get actual screen resolution
        try:
            import pyautogui
            screen_w, screen_h = pyautogui.size()
        except Exception:
            screen_w, screen_h = 1920, 1080

        prompt = f"""You are INDRA, controlling a Windows 11 computer for sir (Ashish).
Current task: {task}
Current step: {current_step}

Screen resolution: {screen_w}x{screen_h} pixels. This screenshot is at native resolution.
All coordinates must be actual screen pixel positions.

Decide the single next action. Respond ONLY with valid JSON:
{{
  "screen_state": "brief description of what is visible",
  "previous_step_complete": true,
  "next_action": "click|type|scroll|navigate|wait|hotkey|done",
  "target": "exact visible text label",
  "value": "text to type, URL, hotkey like ctrl+a, or null",
  "coordinates": [x, y],
  "confidence": 0.85,
  "narration": "brief internal note"
}}

Rules:
- coordinates = [x, y] actual pixel position on {screen_w}x{screen_h} screen
- x must be 0 to {screen_w}, y must be 0 to {screen_h}
- For click: provide both target AND coordinates
- Return "done" when the full task is complete
- Only valid JSON, nothing else."""

        t_start = time.perf_counter()

        try:
            response = ollama.chat(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [screenshot_b64]
                }]
            )

            self._last_call_time = time.time()
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"Vision decision in {elapsed_ms:.0f}ms")

            raw = response.get("message", {}).get("content", "")
            return self._parse_response(raw)

        except Exception as e:
            logger.error(f"Vision LLM error: {e}")
            return self._fallback_action(str(e))

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM response, stripping markdown fences if present."""
        clean = raw.strip()

        # Strip markdown code fences
        if clean.startswith("```"):
            lines = clean.split("\n")
            # Remove first and last lines if they're fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines).strip()

        try:
            parsed = json.loads(clean)
            # Validate required fields
            if "next_action" not in parsed:
                parsed["next_action"] = "wait"
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse vision response: {e}")
            logger.debug(f"Raw response: {raw[:200]}")
            return self._fallback_action("Could not parse vision response")

    def _fallback_action(self, reason: str) -> dict:
        """Return a safe fallback action when vision fails."""
        return {
            "screen_state": f"Vision error: {reason}",
            "previous_step_complete": False,
            "next_action": "wait",
            "target": None,
            "value": "1.0",
            "coordinates": None,
            "confidence": 0.0,
            "narration": f"Having trouble seeing the screen. {reason}"
        }
