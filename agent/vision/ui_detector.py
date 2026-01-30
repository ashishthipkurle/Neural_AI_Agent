"""
UI Detector - User Interface element detection.

This module detects UI elements (buttons, inputs, etc.)
from screen captures for automation and understanding.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class UIElementType(Enum):
    """Types of UI elements."""
    BUTTON = "button"
    TEXT_INPUT = "text_input"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    ICON = "icon"
    TEXT_LABEL = "text_label"
    IMAGE = "image"
    LINK = "link"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """Detected UI element."""
    element_type: UIElementType
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    center: Tuple[int, int]
    text: str
    confidence: float
    properties: Dict[str, Any]


class UIDetector:
    """
    UI Element detection system.
    
    Features:
    - Button detection
    - Text input detection
    - Element classification
    - Clickable region identification
    
    Uses computer vision techniques:
    - Edge detection
    - Contour analysis
    - Template matching
    """
    
    def __init__(self, ocr_engine=None):
        """
        Initialize UI detector.
        
        Args:
            ocr_engine: OCR engine for text extraction.
        """
        self.logger = logging.getLogger("UIDetector")
        self.ocr_engine = ocr_engine
        self._available = CV2_AVAILABLE
        
        if not self._available:
            self.logger.error("OpenCV not available. UI detection disabled.")
        else:
            self.logger.info("UIDetector initialized.")
    
    def is_available(self) -> bool:
        """Check if UI detection is available."""
        return self._available
    
    def detect_elements(self, image) -> List[UIElement]:
        """
        Detect all UI elements in image.
        
        Args:
            image: Screen capture (numpy array).
        
        Returns:
            List of detected UIElements.
        """
        if not self._available:
            return []
        
        elements = []
        
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Detect buttons (rectangular regions with borders)
            buttons = self._detect_buttons(image, gray)
            elements.extend(buttons)
            
            # Detect text inputs (rectangular regions, usually lighter)
            inputs = self._detect_text_inputs(image, gray)
            elements.extend(inputs)
            
            # Detect text labels using OCR
            if self.ocr_engine and self.ocr_engine.is_available():
                labels = self._detect_text_labels(image)
                elements.extend(labels)
            
        except Exception as e:
            self.logger.error(f"UI detection error: {e}")
        
        self.logger.debug(f"Detected {len(elements)} UI elements.")
        return elements
    
    def _detect_buttons(self, image, gray) -> List[UIElement]:
        """Detect button-like elements."""
        buttons = []
        
        try:
            # Edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(
                edges, 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            for contour in contours:
                # Filter by area
                area = cv2.contourArea(contour)
                if area < 500 or area > 100000:
                    continue
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by aspect ratio (buttons are usually wider than tall)
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.5 or aspect_ratio > 10:
                    continue
                
                # Check if rectangular (button-like)
                approx = cv2.approxPolyDP(
                    contour, 
                    0.02 * cv2.arcLength(contour, True), 
                    True
                )
                
                if len(approx) >= 4:
                    center = (x + w // 2, y + h // 2)
                    
                    buttons.append(UIElement(
                        element_type=UIElementType.BUTTON,
                        bbox=(x, y, w, h),
                        center=center,
                        text="",
                        confidence=0.6,
                        properties={"area": area, "vertices": len(approx)}
                    ))
            
        except Exception as e:
            self.logger.error(f"Button detection error: {e}")
        
        return buttons[:50]  # Limit results
    
    def _detect_text_inputs(self, image, gray) -> List[UIElement]:
        """Detect text input fields."""
        inputs = []
        
        try:
            # Threshold to find light regions (text inputs are usually light)
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(
                thresh, 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Text inputs are typically wide and short
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 3 or aspect_ratio > 30:
                    continue
                
                # Filter by size
                if w < 100 or h < 15 or h > 50:
                    continue
                
                center = (x + w // 2, y + h // 2)
                
                inputs.append(UIElement(
                    element_type=UIElementType.TEXT_INPUT,
                    bbox=(x, y, w, h),
                    center=center,
                    text="",
                    confidence=0.5,
                    properties={"aspect_ratio": aspect_ratio}
                ))
            
        except Exception as e:
            self.logger.error(f"Text input detection error: {e}")
        
        return inputs[:20]
    
    def _detect_text_labels(self, image) -> List[UIElement]:
        """Detect text labels using OCR."""
        labels = []
        
        if not self.ocr_engine:
            return labels
        
        try:
            result = self.ocr_engine.extract_text(image)
            
            for region in result.regions:
                if region.get("confidence", 0) > 0.5:
                    x = region["x"]
                    y = region["y"]
                    w = region["width"]
                    h = region["height"]
                    
                    labels.append(UIElement(
                        element_type=UIElementType.TEXT_LABEL,
                        bbox=(x, y, w, h),
                        center=(x + w // 2, y + h // 2),
                        text=region["text"],
                        confidence=region["confidence"],
                        properties={}
                    ))
            
        except Exception as e:
            self.logger.error(f"Text label detection error: {e}")
        
        return labels
    
    def find_element_by_text(
        self,
        image,
        text: str,
        element_type: UIElementType = None
    ) -> Optional[UIElement]:
        """
        Find UI element by text content.
        
        Args:
            image: Source image.
            text: Text to search for.
            element_type: Optional type filter.
        
        Returns:
            Matching UIElement or None.
        """
        elements = self.detect_elements(image)
        text_lower = text.lower()
        
        for element in elements:
            if element_type and element.element_type != element_type:
                continue
            
            if text_lower in element.text.lower():
                return element
        
        return None
    
    def get_clickable_elements(self, image) -> List[UIElement]:
        """Get all clickable elements."""
        elements = self.detect_elements(image)
        clickable_types = {
            UIElementType.BUTTON,
            UIElementType.LINK,
            UIElementType.CHECKBOX
        }
        return [e for e in elements if e.element_type in clickable_types]
