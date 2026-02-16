"""
Vision Skill - Screen understanding and visual analysis.

Provides:
- Screenshot capture
- OCR text extraction
- UI element detection
- Error/popup reading
- Visual comparisons
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import base64

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class VisionSkill(BaseSkill):
    """
    Vision and screen understanding skill.
    
    Actions:
    - screenshot: Capture screen or region
    - ocr: Extract text from image/screen
    - detect_elements: Find UI elements
    - analyze: Describe what's on screen
    - find_text: Find location of text on screen
    - compare: Compare two images
    - read_popup: Read error/notification popup
    """
    
    SCREENSHOTS_DIR = Path("agent/data/screenshots")
    
    def __init__(self):
        super().__init__()
        self._ocr_engine = None
        self._detector = None
    
    @property
    def name(self) -> str:
        return "vision"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="vision",
            version="1.0.0",
            description="Screen understanding, OCR, and visual analysis",
            actions=[
                "screenshot", "ocr", "detect_elements", "analyze",
                "find_text", "compare", "read_popup"
            ],
            requires=["pillow", "pytesseract"],
            permissions=["screen"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize vision components."""
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Try to load OCR
        try:
            import pytesseract
            self._ocr_engine = pytesseract
            self.logger.info("Vision skill: OCR (pytesseract) loaded.")
        except ImportError:
            try:
                import easyocr
                self._ocr_engine = easyocr.Reader(['en'])
                self.logger.info("Vision skill: OCR (easyocr) loaded.")
            except:
                self.logger.warning("No OCR engine available.")
        
        # Try to load detector from existing vision tools
        try:
            from agent.tools.vision_tools import VisionTools
            self._detector = VisionTools()
            self.logger.info("Vision skill: Detector loaded.")
        except Exception as e:
            self.logger.warning(f"Detector not available: {e}")
        
        super().on_load()
    
    def on_unload(self) -> None:
        """Cleanup vision resources."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        high_patterns = [
            "screenshot", "capture screen", "take picture",
            "what's on", "what is on", "read screen",
            "ocr", "extract text", "find text",
            "detect", "analyze image", "look at"
        ]
        
        for pattern in high_patterns:
            if pattern in intent_lower:
                return 0.85
        
        if any(x in intent_lower for x in ["see", "look", "visual", "screen"]):
            return 0.6
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a vision action."""
        
        handlers = {
            "screenshot": self._action_screenshot,
            "ocr": self._action_ocr,
            "detect_elements": self._action_detect_elements,
            "analyze": self._action_analyze,
            "find_text": self._action_find_text,
            "compare": self._action_compare,
            "read_popup": self._action_read_popup,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Vision action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_screenshot(self, params: Dict, context: Dict) -> SkillResult:
        """Capture screenshot of the current screen."""
        path = params.get("path", self.SCREENSHOTS_DIR / f"screen_{int(time.time())}.png")
        region = params.get("region")  # (x, y, width, height)
        settle_delay = params.get("settle_delay", 2)  # seconds to wait for render

        try:
            import pyautogui

            # Brief delay to let any recently-opened page fully render
            if settle_delay and settle_delay > 0:
                time.sleep(settle_delay)

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            Path(path).parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(str(path))
            
            return SkillResult(
                success=True,
                data={"path": str(path)},
                message=f"Screenshot saved to {path}"
            )
        except Exception as e:
            return SkillResult(success=False, error=f"Screenshot failed: {e}")
    
    def _action_ocr(self, params: Dict, context: Dict) -> SkillResult:
        """Extract text from image or screen."""
        image_path = params.get("path")
        capture_screen = params.get("capture_screen", True)
        
        if not self._ocr_engine:
            return SkillResult(success=False, error="OCR engine not available")
        
        try:
            from PIL import Image
            
            # Get image
            if image_path:
                image = Image.open(image_path)
            elif capture_screen:
                import pyautogui
                image = pyautogui.screenshot()
            else:
                return SkillResult(success=False, error="Image path or capture_screen required")
            
            # Perform OCR
            if hasattr(self._ocr_engine, 'image_to_string'):  # pytesseract
                text = self._ocr_engine.image_to_string(image)
            else:  # easyocr
                import numpy as np
                result = self._ocr_engine.readtext(np.array(image))
                text = ' '.join([item[1] for item in result])
            
            return SkillResult(
                success=True,
                data={"text": text},
                message=f"Extracted {len(text)} characters"
            )
        except Exception as e:
            return SkillResult(success=False, error=f"OCR failed: {e}")
    
    def _action_detect_elements(self, params: Dict, context: Dict) -> SkillResult:
        """Detect UI elements on screen."""
        if not self._detector:
            return SkillResult(success=False, error="Detector not available")
        
        try:
            # Use existing vision tools
            elements = self._detector.detect_elements()
            return SkillResult(
                success=True,
                data={"elements": elements},
                message=f"Detected {len(elements)} elements"
            )
        except Exception as e:
            return SkillResult(success=False, error=f"Detection failed: {e}")
    
    def _action_analyze(self, params: Dict, context: Dict) -> SkillResult:
        """Analyze what's on screen using LLM vision."""
        question = params.get("question", "What do you see on the screen?")
        
        try:
            import pyautogui
            from PIL import Image
            import io
            
            # Capture screen
            screenshot = pyautogui.screenshot()
            
            # Convert to base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Use LLM with vision (if available)
            try:
                from agent.core.llm.local_runtime import LocalLLMRuntime
                llm = LocalLLMRuntime()
                
                analysis = llm.generate(
                    prompt=question,
                    images=[img_base64]
                )
                
                return SkillResult(
                    success=True,
                    data={"analysis": analysis.text},
                    message=analysis.text[:200] + "..."
                )
            except Exception as e:
                # Fallback to OCR description
                if self._ocr_engine:
                    text = self._action_ocr({"capture_screen": True}, {})
                    return SkillResult(
                        success=True,
                        data={"analysis": f"[OCR Fallback] Screen text: {text.data.get('text', '')[:500]}"},
                        message="Used OCR fallback for analysis"
                    )
                return SkillResult(success=False, error=f"Vision analysis not available: {e}")
                
        except Exception as e:
            return SkillResult(success=False, error=f"Analysis failed: {e}")
    
    def _action_find_text(self, params: Dict, context: Dict) -> SkillResult:
        """Find location of text on screen."""
        target_text = params.get("text", "")
        
        if not target_text:
            return SkillResult(success=False, error="Text to find required")
        
        if not self._ocr_engine:
            return SkillResult(success=False, error="OCR engine not available")
        
        try:
            import pyautogui
            from PIL import Image
            
            screenshot = pyautogui.screenshot()
            
            # Use pytesseract with bounding boxes
            if hasattr(self._ocr_engine, 'image_to_data'):
                import pandas as pd
                data = self._ocr_engine.image_to_data(screenshot, output_type=self._ocr_engine.Output.DICT)
                
                matches = []
                for i, text in enumerate(data['text']):
                    if text and target_text.lower() in text.lower():
                        matches.append({
                            "text": text,
                            "x": data['left'][i],
                            "y": data['top'][i],
                            "width": data['width'][i],
                            "height": data['height'][i],
                            "confidence": data['conf'][i]
                        })
                
                return SkillResult(
                    success=True,
                    data={"matches": matches},
                    message=f"Found {len(matches)} matches for '{target_text}'"
                )
            else:
                return SkillResult(success=False, error="Detailed OCR not available")
                
        except Exception as e:
            return SkillResult(success=False, error=f"Find text failed: {e}")
    
    def _action_compare(self, params: Dict, context: Dict) -> SkillResult:
        """Compare two images."""
        image1_path = params.get("image1")
        image2_path = params.get("image2")
        
        if not image1_path or not image2_path:
            return SkillResult(success=False, error="Two image paths required")
        
        try:
            from PIL import Image
            import imagehash
            
            img1 = Image.open(image1_path)
            img2 = Image.open(image2_path)
            
            hash1 = imagehash.average_hash(img1)
            hash2 = imagehash.average_hash(img2)
            
            difference = hash1 - hash2
            similarity = max(0, 100 - (difference * 100 / 64))
            
            return SkillResult(
                success=True,
                data={"similarity": similarity, "difference": difference},
                message=f"Images are {similarity:.1f}% similar"
            )
        except ImportError:
            return SkillResult(success=False, error="imagehash not installed")
        except Exception as e:
            return SkillResult(success=False, error=f"Compare failed: {e}")
    
    def _action_read_popup(self, params: Dict, context: Dict) -> SkillResult:
        """Read error or notification popup."""
        # Common popup patterns to look for
        popup_keywords = ["error", "warning", "notification", "alert", "dialog"]
        
        # Capture and OCR
        ocr_result = self._action_ocr({"capture_screen": True}, {})
        
        if not ocr_result.success:
            return ocr_result
        
        text = ocr_result.data.get("text", "")
        
        # Look for popup-like text patterns
        lines = text.split('\n')
        popup_content = []
        
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in popup_keywords):
                popup_content.append(line)
        
        return SkillResult(
            success=True,
            data={"popup_text": popup_content, "full_text": text},
            message=f"Found {len(popup_content)} potential popup lines"
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check vision skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._ocr_engine:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview vision action."""
        previews = {
            "screenshot": f"Would capture screen to: {params.get('path', 'default location')}",
            "ocr": f"Would extract text from: {params.get('path', 'screen')}",
            "analyze": f"Would analyze screen for: {params.get('question', 'general analysis')}",
            "find_text": f"Would search screen for: {params.get('text', 'unknown')}",
        }
        
        return previews.get(action, f"Would execute vision.{action}")
