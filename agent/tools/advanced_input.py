
import time
import random
import logging
import math
import threading
from typing import Tuple, Optional, Any

# Try imports
try:
    import pyautogui
    import numpy as np
    from scipy import interpolate
except ImportError:
    pyautogui = None
    np = None
    interpolate = None

class HumanLikeInputController:
    """
    Module 4: Advanced Human-Like Input Controller
    Bezier mouse movement, human typing, and error simulation.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        if pyautogui:
            pyautogui.FAILSAFE = True
            self.screen_width, self.screen_height = pyautogui.size()
        else:
            self.logger.warning("PyAutoGUI not found. Input control disabled.")
            self.screen_width, self.screen_height = 1920, 1080

    def move_mouse_human(self, target_x: int, target_y: int, 
                         duration_range: Tuple[float, float] = (0.5, 1.5)) -> None:
        """
        Bezier curve movement with variable speed and overshoot.
        """
        if not (pyautogui and np and interpolate):
            self.logger.warning("Dependencies missing for human mouse movement.")
            return

        start_x, start_y = pyautogui.position()
        
        # Calculate random control points for Bezier curve
        # Two control points for cubic bezier
        dist = math.hypot(target_x - start_x, target_y - start_y)
        
        # Random perturbation
        control1_x = start_x + (target_x - start_x) * 0.3 + random.uniform(-100, 100)
        control1_y = start_y + (target_y - start_y) * 0.3 + random.uniform(-100, 100)
        
        control2_x = start_x + (target_x - start_x) * 0.7 + random.uniform(-100, 100)
        control2_y = start_y + (target_y - start_y) * 0.7 + random.uniform(-100, 100)
        
        # Overshoot target slightly (simulating human error correction)
        overshoot_dist = min(dist * 0.05, 15.0) # Max 15px overshoot
        angle = math.atan2(target_y - start_y, target_x - start_x)
        overshoot_x = target_x + math.cos(angle) * overshoot_dist
        overshoot_y = target_y + math.sin(angle) * overshoot_dist
        
        # Create curve points
        # Points: Start -> C1 -> C2 -> Overshoot -> Target
        # We simplify to 4 points for the main movement, then a separate small correction
        
        points = np.array([
            [start_x, start_y],
            [control1_x, control1_y],
            [control2_x, control2_y],
            [overshoot_x, overshoot_y]
        ])
        
        # Generate B-spline
        try:
            ctr = np.array(points)
            x = ctr[:,0]
            y = ctr[:,1]
            t = np.linspace(0, 1, ctr.shape[0])
            
            # Cubic spline interpolation
            tck, u = interpolate.splprep([x, y], k=3, s=0)
            u_fine = np.linspace(0, 1, num=50) # 50 steps
            out = interpolate.splev(u_fine, tck)
            path = list(zip(out[0], out[1]))
            
        except Exception as e:
            self.logger.error(f"Spline generation failed: {e}. Fallback to linear.")
            pyautogui.moveTo(target_x, target_y, duration=random.uniform(*duration_range))
            return

        # Execute movement
        duration = random.uniform(*duration_range)
        step_delay = duration / len(path)
        
        for px, py in path:
            pyautogui.moveTo(px, py)
            # Add micro-pauses occasionally
            if random.random() < 0.05:
                time.sleep(random.uniform(0.01, 0.05))
            else:
                pass # pyautogui calls usually have small overhead

        # Correction movement (overshoot back to target)
        if overshoot_dist > 2:
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.moveTo(target_x, target_y, duration=random.uniform(0.1, 0.2))

    def click_human(self, x: int, y: int, button: str = 'left') -> None:
        """Move with human-like path, random delay, click."""
        if not pyautogui:
            return
            
        self.move_mouse_human(x, y)
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.click(button=button)

    def type_text_human(self, text: str, 
                        wpm_range: Tuple[int, int] = (80, 120),
                        error_rate: float = 0.02) -> None:
        """
        Human typing with variable speed, errors, and corrections.
        """
        if not pyautogui:
            return

        for char in text:
            # Calculate delay based on WPM
            wpm = random.uniform(*wpm_range)
            # Characters per minute = WPM * 5
            cpm = wpm * 5
            delay = 60.0 / cpm
            
            # Add randomness to delay
            delay = delay * random.uniform(0.7, 1.3)
            
            # Simulate error
            if random.random() < error_rate:
                # Type wrong char
                wrong_char = chr(ord(char) + 1) # simple wrong char
                pyautogui.write(wrong_char)
                time.sleep(random.uniform(0.1, 0.3))
                pyautogui.press('backspace')
                time.sleep(random.uniform(0.05, 0.2))
            
            pyautogui.write(char)
            time.sleep(delay)
            
            # Pauses between words
            if char == ' ':
                time.sleep(random.uniform(0.05, 0.15))

    def scroll_human(self, clicks: int, direction: str = 'down') -> None:
        """Variable scroll amounts with random pauses"""
        if not pyautogui:
            return
            
        amount = clicks * (-1 if direction == 'down' else 1) * 100
        pyautogui.scroll(amount)
        time.sleep(random.uniform(0.2, 0.8))

    def drag_human(self, start_x: int, start_y: int, 
                   end_x: int, end_y: int) -> None:
        """Human-like drag path"""
        if not pyautogui:
            return
            
        pyautogui.moveTo(start_x, start_y)
        time.sleep(0.3)
        pyautogui.mouseDown()
        self.move_mouse_human(end_x, end_y)
        time.sleep(0.2)
        pyautogui.mouseUp()

    def find_and_click(self, element_description: str, 
                       vision_monitor: Any) -> bool:
        """Find element with vision, click with human movement. Retry 3x"""
        # Placeholder for integration loop
        # 1. Get view from monitor
        # 2. Call UI detector
        # 3. If found, click
        self.logger.info(f"Looking for '{element_description}' to click...")
        return False
