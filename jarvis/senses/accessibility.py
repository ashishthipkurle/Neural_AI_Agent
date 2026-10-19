"""
INDRA Accessibility Layer -- Windows UI Automation live layer.
PRIMARY way INDRA finds UI elements. Vision LLM is the fallback, not this.
"""

import threading
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("A11y")

try:
    import pywinauto
    from pywinauto import Desktop
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False
    logger.warning("pywinauto not installed -- accessibility layer unavailable")


class AccessibilityLayer:
    """
    Reads the Windows UI Automation accessibility tree continuously.
    Provides a real-time, structured map of every interactive element on screen.
    """

    def __init__(self):
        self.desktop = None
        self._element_cache = []
        self._cache_timestamp = 0
        self.CACHE_TTL = 0.5  # Refresh cache every 500ms

        if HAS_PYWINAUTO:
            try:
                self.desktop = Desktop(backend="uia")
                logger.info("Accessibility layer initialized (UIA backend)")
            except Exception as e:
                logger.error(f"Accessibility init failed: {e}")

    def get_all_elements(self) -> list[dict]:
        """
        Returns list of interactive elements on screen.
        Each element: {name, control_type, rect, enabled, visible}
        Cached for CACHE_TTL seconds to avoid thrashing.
        """
        if not self.desktop:
            return []

        now = time.time()
        if (now - self._cache_timestamp) < self.CACHE_TTL and self._element_cache:
            return self._element_cache

        elements = []
        try:
            # Get the foreground window's elements
            windows = self.desktop.windows()
            for win in windows[:5]:  # Limit to top 5 windows
                try:
                    descendants = win.descendants()
                    for elem in descendants[:200]:  # Limit per window
                        try:
                            info = {
                                "name": elem.window_text() or "",
                                "control_type": elem.element_info.control_type or "",
                                "rect": None,
                                "enabled": elem.is_enabled(),
                                "visible": elem.is_visible(),
                            }
                            try:
                                r = elem.rectangle()
                                info["rect"] = {
                                    "left": r.left, "top": r.top,
                                    "right": r.right, "bottom": r.bottom,
                                    "center_x": (r.left + r.right) // 2,
                                    "center_y": (r.top + r.bottom) // 2
                                }
                            except Exception:
                                pass

                            if info["name"] or info["control_type"]:
                                elements.append(info)
                        except Exception:
                            continue
                except Exception:
                    continue

            self._element_cache = elements
            self._cache_timestamp = now

        except Exception as e:
            logger.debug(f"Element scan error: {e}")

        return elements

    def find_element(self, name: str = None, control_type: str = None) -> dict | None:
        """
        Search elements by name (fuzzy match) or control_type.
        Returns element dict with .rect for coordinates, or None.
        """
        elements = self.get_all_elements()

        for elem in elements:
            if not elem.get("visible") or not elem.get("enabled"):
                continue

            name_match = False
            type_match = False

            if name:
                elem_name = (elem.get("name") or "").lower()
                name_lower = name.lower()
                # Fuzzy: check if search term is contained in element name or vice versa
                name_match = name_lower in elem_name or elem_name in name_lower

            if control_type:
                type_match = (elem.get("control_type") or "").lower() == control_type.lower()

            if name and control_type:
                if name_match and type_match:
                    return elem
            elif name and name_match:
                return elem
            elif control_type and type_match:
                return elem

        return None

    def click_element_by_name(self, name: str) -> bool:
        """Find element by name, click its center. Returns success."""
        elem = self.find_element(name=name)
        if not elem or not elem.get("rect"):
            return False

        try:
            import pyautogui
            rect = elem["rect"]
            pyautogui.click(rect["center_x"], rect["center_y"])
            logger.info(f"Clicked '{name}' at ({rect['center_x']}, {rect['center_y']})")
            return True
        except Exception as e:
            logger.warning(f"Click failed for '{name}': {e}")
            return False

    def get_focused_app(self) -> str:
        """Returns name of currently focused application."""
        if not self.desktop:
            return "Unknown"
        try:
            windows = self.desktop.windows()
            for w in windows:
                try:
                    if w.has_focus():
                        return w.window_text() or "Unknown"
                except Exception:
                    continue
        except Exception:
            pass
        return "Unknown"

    def get_window_list(self) -> list[str]:
        """Returns names of all open windows."""
        if not self.desktop:
            return []
        try:
            return [w.window_text() for w in self.desktop.windows() if w.window_text()]
        except Exception:
            return []

    def start(self):
        """Pre-warm the cache (called from main.py startup)."""
        if self.desktop:
            threading.Thread(target=self.get_all_elements, daemon=True).start()
            logger.info("Accessibility layer cache warming started")
