
import unittest
from agent.vision.ui_detector import UIElementDetector
from PIL import Image

class TestUIElementDetector(unittest.TestCase):
    def setUp(self):
        # Initialize without OCR/YOLO to avoid heavy load during simple unit test
        # or rely on graceful fallback
        self.detector = UIElementDetector(use_ocr=False)

    def test_init(self):
        self.assertIsNotNone(self.detector)

    def test_detect_returns_list(self):
        # Create dummy image
        img = Image.new('RGB', (100, 100), color='white')
        elements = self.detector.detect_interactive_elements(img)
        self.assertIsInstance(elements, list)

    def test_find_by_text_returns_none_without_ocr(self):
        img = Image.new('RGB', (100, 100), color='white')
        result = self.detector.find_element_by_text(img, "Submit")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
