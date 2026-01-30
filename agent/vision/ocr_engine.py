"""
OCR Engine - Optical Character Recognition.

This module provides text extraction from screen captures
using Tesseract OCR or alternative engines.
"""
import logging
import os
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

try:
    import pytesseract
    from PIL import Image
    import numpy as np
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


@dataclass
class OCRResult:
    """Result of OCR operation."""
    text: str
    confidence: float
    regions: List[Dict[str, Any]]
    language: str


@dataclass
class TextRegion:
    """Detected text region."""
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float


class OCREngine:
    """
    Optical Character Recognition engine.
    
    Features:
    - Full-page text extraction
    - Region-based extraction
    - Confidence scoring
    - Multiple language support
    
    Privacy:
    - All processing is local
    - No data sent externally
    """
    
    def __init__(self, tesseract_path: str = None, language: str = "eng"):
        """
        Initialize OCR engine.
        
        Args:
            tesseract_path: Path to tesseract executable.
            language: OCR language code.
        """
        self.logger = logging.getLogger("OCREngine")
        self.language = language
        self._available = False
        
        if not TESSERACT_AVAILABLE:
            self.logger.error("pytesseract not installed. OCR disabled.")
            return
        
        # Set tesseract path if provided
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            # Try common Windows paths
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
        
        # Verify installation
        try:
            pytesseract.get_tesseract_version()
            self._available = True
            self.logger.info("OCR Engine initialized (Tesseract)")
        except Exception as e:
            self.logger.error(f"Tesseract not available: {e}")
    
    def is_available(self) -> bool:
        """Check if OCR is available."""
        return self._available
    
    def extract_text(self, image) -> OCRResult:
        """
        Extract all text from image.
        
        Args:
            image: PIL Image or numpy array.
        
        Returns:
            OCRResult with extracted text.
        """
        if not self._available:
            return OCRResult(
                text="OCR not available",
                confidence=0.0,
                regions=[],
                language=self.language
            )
        
        try:
            # Convert numpy array to PIL if needed
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            
            # Extract text
            text = pytesseract.image_to_string(image, lang=self.language)
            
            # Get confidence data
            data = pytesseract.image_to_data(
                image, 
                lang=self.language,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [
                int(c) for c in data['conf'] 
                if str(c).isdigit() and int(c) > 0
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract regions
            regions = self._extract_regions(data)
            
            return OCRResult(
                text=text.strip(),
                confidence=avg_confidence / 100.0,
                regions=regions,
                language=self.language
            )
            
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return OCRResult(
                text=f"Error: {e}",
                confidence=0.0,
                regions=[],
                language=self.language
            )
    
    def _extract_regions(self, ocr_data: Dict) -> List[Dict[str, Any]]:
        """Extract text regions from OCR data."""
        regions = []
        n_boxes = len(ocr_data['text'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = ocr_data['conf'][i]
            
            if text and str(conf).isdigit() and int(conf) > 30:
                regions.append({
                    "text": text,
                    "x": ocr_data['left'][i],
                    "y": ocr_data['top'][i],
                    "width": ocr_data['width'][i],
                    "height": ocr_data['height'][i],
                    "confidence": int(conf) / 100.0,
                    "level": ocr_data['level'][i]
                })
        
        return regions
    
    def extract_from_region(
        self,
        image,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> str:
        """
        Extract text from specific region.
        
        Args:
            image: Source image.
            x, y, width, height: Region coordinates.
        
        Returns:
            Extracted text.
        """
        if not self._available:
            return ""
        
        try:
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            
            # Crop region
            region = image.crop((x, y, x + width, y + height))
            
            # Extract text
            text = pytesseract.image_to_string(region, lang=self.language)
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Region OCR failed: {e}")
            return ""
    
    def find_text(self, image, search_text: str) -> List[TextRegion]:
        """
        Find specific text in image.
        
        Args:
            image: Source image.
            search_text: Text to find.
        
        Returns:
            List of TextRegion matches.
        """
        result = self.extract_text(image)
        search_lower = search_text.lower()
        
        matches = []
        for region in result.regions:
            if search_lower in region["text"].lower():
                matches.append(TextRegion(
                    text=region["text"],
                    bbox=(
                        region["x"],
                        region["y"],
                        region["width"],
                        region["height"]
                    ),
                    confidence=region["confidence"]
                ))
        
        return matches
    
    def set_language(self, language: str) -> None:
        """Set OCR language."""
        self.language = language
        self.logger.info(f"OCR language set to: {language}")
