"""
Structured Vision System — §7 of Production Autonomous Agent Spec.

Vision layer returns structured detection objects, not text.
Pre/post action screenshot comparison via layout_hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("vision.structured")


@dataclass
class DetectedElement:
    """A single detected UI element — §7."""
    type: str          # "button" | "input" | "popup" | "error" | "link" | "text" | "image"
    label: str
    confidence: float  # 0.0–1.0
    bounding_box: Tuple[int, int, int, int]  # (x1, y1, x2, y2)


@dataclass
class VisionResult:
    """Structured vision output — §7.

    No unstructured text. All fields typed.
    """
    detected_elements: List[DetectedElement] = field(default_factory=list)
    layout_hash: str = ""
    error_messages: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    raw_text: str = ""  # OCR-extracted text
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_elements": [
                {
                    "type": e.type,
                    "label": e.label,
                    "confidence": e.confidence,
                    "bounding_box": list(e.bounding_box),
                }
                for e in self.detected_elements
            ],
            "layout_hash": self.layout_hash,
            "error_messages": self.error_messages,
            "screenshot_path": self.screenshot_path,
            "raw_text": self.raw_text[:500],
        }

    def find_element(self, label: str = None, element_type: str = None) -> Optional[DetectedElement]:
        """Find best matching element."""
        candidates = self.detected_elements
        if element_type:
            candidates = [e for e in candidates if e.type == element_type]
        if label:
            label_lower = label.lower()
            candidates = [e for e in candidates if label_lower in e.label.lower()]
        if not candidates:
            return None
        return max(candidates, key=lambda e: e.confidence)


class StructuredVisionSystem:
    """Vision system with structured output — §7.

    Wraps existing VisionSkill to produce DetectedElements
    instead of raw text.
    """

    def __init__(self):
        self._screenshot_dir = os.path.join("agent_data", "screenshots")
        os.makedirs(self._screenshot_dir, exist_ok=True)
        self._last_layout_hash: Optional[str] = None

    def capture_screenshot(self) -> str:
        """Capture screen and return path."""
        try:
            import pyautogui
            filename = f"screen_{int(time.time())}.png"
            path = os.path.join(self._screenshot_dir, filename)
            screenshot = pyautogui.screenshot()
            screenshot.save(path)
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""

    def analyze_screen(self, screenshot_path: str = None) -> VisionResult:
        """Analyze screen and return structured detection objects.

        Uses OCR + heuristics to detect UI elements.
        """
        if not screenshot_path:
            screenshot_path = self.capture_screenshot()

        if not screenshot_path or not os.path.exists(screenshot_path):
            return VisionResult(error_messages=["Screenshot not available"])

        result = VisionResult(
            screenshot_path=screenshot_path,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        # Compute layout hash
        result.layout_hash = self._compute_layout_hash(screenshot_path)

        # OCR text extraction
        raw_text = self._extract_text(screenshot_path)
        result.raw_text = raw_text

        # Detect elements from OCR + image analysis
        result.detected_elements = self._detect_elements(screenshot_path, raw_text)

        # Detect error messages
        result.error_messages = self._detect_errors(raw_text)

        return result

    def verify_action(
        self,
        pre_screenshot: str,
        post_screenshot: str,
        expected_change: str = "",
    ) -> Dict[str, Any]:
        """Compare pre/post screenshots to verify action succeeded — §7.

        Returns:
            {verified: bool, changes: str, hash_changed: bool}
        """
        pre_hash = self._compute_layout_hash(pre_screenshot)
        post_hash = self._compute_layout_hash(post_screenshot)
        hash_changed = pre_hash != post_hash

        pre_text = self._extract_text(pre_screenshot)
        post_text = self._extract_text(post_screenshot)

        # Check if expected change is reflected
        verified = False
        changes = ""

        if hash_changed:
            changes = "Layout changed"
            if expected_change:
                verified = expected_change.lower() in post_text.lower()
            else:
                verified = True  # Layout changed = something happened
        else:
            changes = "No visual change detected"
            if expected_change and expected_change.lower() in post_text.lower():
                verified = True
                changes = "Expected text found (no layout change)"

        return {
            "verified": verified,
            "changes": changes,
            "hash_changed": hash_changed,
            "pre_hash": pre_hash,
            "post_hash": post_hash,
        }

    def _compute_layout_hash(self, image_path: str) -> str:
        """Compute a hash representing the visual layout."""
        try:
            from PIL import Image
            img = Image.open(image_path)
            # Resize to tiny thumbnail for fast hashing
            thumb = img.resize((32, 32)).convert("L")
            pixels = list(thumb.getdata())
            return hashlib.md5(bytes(pixels)).hexdigest()
        except Exception:
            return hashlib.md5(open(image_path, "rb").read()[:4096]).hexdigest()

    def _extract_text(self, image_path: str) -> str:
        """Extract text via OCR."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def _detect_elements(self, image_path: str, text: str) -> List[DetectedElement]:
        """Detect UI elements from screenshot.

        Uses OCR text + basic heuristics.
        For production, this would use a UI element detection model.
        """
        elements = []

        # Heuristic: common button patterns
        button_keywords = ["ok", "cancel", "submit", "save", "close", "next",
                          "back", "send", "confirm", "yes", "no", "apply",
                          "accept", "deny", "allow", "block", "install"]

        lines = text.split("\n")
        y_offset = 0
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                y_offset += 20
                continue

            # Detect buttons
            for kw in button_keywords:
                if kw in line_stripped.lower() and len(line_stripped) < 30:
                    elements.append(DetectedElement(
                        type="button",
                        label=line_stripped,
                        confidence=0.7,
                        bounding_box=(0, y_offset, 200, y_offset + 30),
                    ))

            # Detect error messages
            if any(e in line_stripped.lower() for e in ["error", "failed", "denied", "invalid"]):
                elements.append(DetectedElement(
                    type="error",
                    label=line_stripped,
                    confidence=0.8,
                    bounding_box=(0, y_offset, 800, y_offset + 20),
                ))

            # Detect input fields (heuristic: lines with placeholder-like text)
            if any(p in line_stripped.lower() for p in ["enter", "type", "search", "username", "password", "email"]):
                elements.append(DetectedElement(
                    type="input",
                    label=line_stripped,
                    confidence=0.6,
                    bounding_box=(0, y_offset, 400, y_offset + 30),
                ))

            y_offset += 20

        return elements

    def _detect_errors(self, text: str) -> List[str]:
        """Extract error messages from OCR text."""
        errors = []
        for line in text.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ["error", "failed", "denied", "not found", "exception"]):
                errors.append(line)
        return errors
