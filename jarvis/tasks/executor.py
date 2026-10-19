"""
INDRA Executor -- The core SEE->THINK->ACT loop.
Narrates via speaker.enqueue() (non-blocking) while continuing to execute.
INDRA speaks and acts simultaneously.
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tasks.error_handler import ErrorHandler
from utils.logger import get_logger

logger = get_logger("Executor")


class Executor:
    """Core computer control loop. Executes tasks step-by-step."""

    def __init__(self, eyes, accessibility, vision_brain, mouse, keyboard, browser, speaker):
        self.eyes = eyes
        self.accessibility = accessibility
        self.vision_brain = vision_brain
        self.mouse = mouse
        self.keyboard = keyboard
        self.browser = browser
        self.speaker = speaker
        self.error_handler = ErrorHandler(accessibility, vision_brain, eyes)
        self._running = False

    def run_task(self, task_description: str):
        """Execute a computer task end-to-end."""
        self._running = True
        logger.info(f"Starting task: {task_description}")

        # Only speak ONCE at start -- then stay silent until done
        self.speaker.enqueue("On it, sir.")

        step_count = 0
        max_steps = 50  # Safety limit

        try:
            while self._running and step_count < max_steps:
                step_count += 1
                logger.info(f"--- Step {step_count} ---")

                # 1. Get current screen state
                logger.info(f"[Step {step_count}] Capturing screenshot...")
                screenshot_b64 = self.eyes.get_screenshot_b64()
                if not screenshot_b64:
                    logger.error(f"[Step {step_count}] Screenshot capture failed!")
                    time.sleep(1.0)
                    continue

                # 2. Ask vision brain what to do
                logger.info(f"[Step {step_count}] Asking vision brain...")
                try:
                    action_future = self.vision_brain.decide_async(
                        screenshot_b64, task_description, f"Step {step_count}"
                    )
                    action = action_future.result(timeout=45)
                except Exception as e:
                    logger.error(f"[Step {step_count}] Vision decision error: {e}")
                    self.speaker.enqueue("Having trouble with the screen, sir.", priority=True)
                    break

                logger.info(f"[Step {step_count}] Vision returned: action={action.get('next_action')}, "
                           f"target={action.get('target')}, coords={action.get('coordinates')}")

                # 3. Log narration silently -- NEVER speak during execution
                narration = action.get("narration")
                if narration:
                    logger.info(f"[Vision] {narration}")

                # 4. Check if done
                next_action = action.get("next_action")
                if next_action == "done":
                    self.speaker.enqueue("That's done, sir.")
                    logger.info(f"Task completed in {step_count} steps.")
                    break

                # 5. Execute action
                logger.info(f"[Step {step_count}] Executing action...")
                success = self._execute_action(action)
                logger.info(f"[Step {step_count}] Action result: {'SUCCESS' if success else 'FAILED'}")

                # 6. Verify and retry if needed
                if not success:
                    logger.info(f"[Step {step_count}] Trying error recovery...")
                    success = self.error_handler.retry_with_escalation(
                        action, self._execute_action, attempt=1
                    )
                    logger.info(f"[Step {step_count}] Recovery result: {'SUCCESS' if success else 'FAILED'}")

                # 7. If still failing, stop
                if not success:
                    self.speaker.enqueue("I'm stuck, sir. Want me to try differently?", priority=True)
                    logger.warning(f"Task stalled at step {step_count}")
                    self._running = False
                    break

                # Small pause between steps for UI to settle
                logger.info(f"[Step {step_count}] Complete. Waiting 1.5s for UI...")
                time.sleep(1.5)

        except Exception as e:
            logger.error(f"[EXECUTOR CRASH] Task failed with exception: {e}", exc_info=True)
            self.speaker.enqueue("Something went wrong, sir. The task has stopped.", priority=True)

        if step_count >= max_steps:
            self.speaker.enqueue("Reached the step limit, sir. Stopping.")
            logger.warning("Max steps reached")

        logger.info(f"Executor finished after {step_count} steps.")
        self._running = False

    def _clamp_coords(self, coords: list) -> list:
        """
        Clamp coordinates to screen bounds. No scaling needed since 
        screenshots are now sent at native resolution.
        """
        if not coords or len(coords) != 2:
            return coords
        try:
            import pyautogui
            screen_w, screen_h = pyautogui.size()
            x = max(0, min(int(coords[0]), screen_w - 1))
            y = max(0, min(int(coords[1]), screen_h - 1))
            if x != int(coords[0]) or y != int(coords[1]):
                logger.warning(f"[Coords] Clamped ({coords[0]}, {coords[1]}) -> ({x}, {y}) [screen: {screen_w}x{screen_h}]")
            return [x, y]
        except Exception:
            return [int(coords[0]), int(coords[1])]

    def _execute_action(self, action: dict) -> bool:
        """Execute a single action dict from the vision brain."""
        target = action.get("target")
        value = action.get("value")
        raw_coords = action.get("coordinates")
        action_type = action.get("next_action")

        # Clamp coordinates to screen bounds (safety)
        coords = self._clamp_coords(raw_coords) if raw_coords else None

        logger.info(f"[Execute] {action_type} | target='{target}' | value='{value}' | coords={coords}")

        try:
            # -- CLICK --
            if action_type == "click":
                # Try accessibility tree first (most reliable)
                if target:
                    if self.accessibility.click_element_by_name(target):
                        logger.info(f"[Execute] [OK] Clicked via accessibility: '{target}'")
                        return True
                    else:
                        logger.info(f"[Execute] Accessibility miss for '{target}', trying coords")
                
                # Fall back to scaled coordinates
                if coords and len(coords) == 2:
                    self.mouse.click(coords[0], coords[1])
                    logger.info(f"[Execute] [OK] Clicked at ({coords[0]}, {coords[1]})")
                    return True
                logger.warning(f"[Execute] [FAIL] Click failed -- no coords and no accessibility match")
                return False

            # -- DOUBLE CLICK --
            elif action_type == "double_click":
                if coords and len(coords) == 2:
                    self.mouse.double_click(coords[0], coords[1])
                    return True
                return False

            # -- RIGHT CLICK --
            elif action_type == "right_click":
                if coords and len(coords) == 2:
                    self.mouse.right_click(coords[0], coords[1])
                    return True
                return False

            # -- TYPE --
            elif action_type == "type":
                if not value:
                    return False
                self.keyboard.type_text(str(value))
                return True

            # -- SCROLL --
            elif action_type == "scroll":
                amount = 3
                try:
                    if value:
                        amount = int(value)
                except Exception:
                    pass
                self.mouse.scroll("down" if amount > 0 else "up", abs(amount))
                return True

            # -- NAVIGATE --
            elif action_type == "navigate":
                if not value:
                    return False
                self.browser.open_url(str(value))
                return True

            # -- HOTKEY --
            elif action_type == "hotkey":
                if not value:
                    return False
                keys = str(value).lower().split("+")
                self.keyboard.hotkey(*keys)
                return True

            # -- WAIT --
            elif action_type == "wait":
                duration = 1.0
                try:
                    if value:
                        duration = float(value)
                except Exception:
                    pass
                time.sleep(duration)
                return True

            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    def stop(self):
        """Called by F9 emergency stop."""
        self._running = False
        logger.warning("Executor stopped via emergency interrupt")

