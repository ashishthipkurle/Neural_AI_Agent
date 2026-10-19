"""
INDRA Error Handler -- Retry logic with 3-strategy escalation and stuck detection.
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAX_RETRIES
from utils.logger import get_logger

logger = get_logger("ErrorHandler")


class ErrorHandler:
    """
    3-strategy escalation for failed actions:
      1. Retry the exact same action (maybe timing issue)
      2. Try via accessibility tree instead of coordinates (or vice versa)  
      3. Re-examine screen with vision LLM for a new approach
    """

    def __init__(self, accessibility, vision_brain, eyes):
        self.accessibility = accessibility
        self.vision_brain = vision_brain
        self.eyes = eyes

    def retry_with_escalation(self, action: dict, execute_fn, attempt: int = 1) -> bool:
        """
        Try up to MAX_RETRIES strategies to complete a failed action.
        
        Args:
            action: The action dict from vision brain
            execute_fn: Function that executes an action dict -> bool
            attempt: Current attempt number
            
        Returns: True if any strategy succeeded.
        """
        if attempt > MAX_RETRIES:
            logger.warning(f"All {MAX_RETRIES} retry strategies exhausted")
            return False

        target = action.get("target", "")
        action_type = action.get("next_action", "")

        logger.info(f"Retry strategy {attempt}/{MAX_RETRIES} for: {action_type} -> {target}")

        # Strategy 1: Simple retry with a short wait (timing issue)
        if attempt == 1:
            logger.info("Strategy 1: Retry after brief wait")
            time.sleep(1.0)
            if execute_fn(action):
                logger.info("Strategy 1 succeeded")
                return True

        # Strategy 2: Try accessibility tree if we used coordinates, or vice versa
        if attempt == 2 and target:
            logger.info("Strategy 2: Try accessibility tree lookup")
            elem = self.accessibility.find_element(name=target)
            if elem and elem.get("rect"):
                alt_action = action.copy()
                alt_action["coordinates"] = [
                    elem["rect"]["center_x"],
                    elem["rect"]["center_y"]
                ]
                if execute_fn(alt_action):
                    logger.info("Strategy 2 succeeded (accessibility)")
                    return True

        # Strategy 3: Re-examine screen for a completely new approach
        if attempt == 3:
            logger.info("Strategy 3: Re-examine screen with vision LLM")
            try:
                screenshot_b64 = self.eyes.get_screenshot_b64()
                if screenshot_b64:
                    new_action = self.vision_brain.decide_async(
                        screenshot_b64,
                        f"Retry: {action_type} on {target}",
                        f"Previous attempt failed. Find an alternative approach."
                    ).result(timeout=15)

                    if new_action.get("next_action") != "wait":
                        if execute_fn(new_action):
                            logger.info("Strategy 3 succeeded (new approach)")
                            return True
            except Exception as e:
                logger.warning(f"Strategy 3 failed: {e}")

        # Recurse to next strategy
        return self.retry_with_escalation(action, execute_fn, attempt + 1)
