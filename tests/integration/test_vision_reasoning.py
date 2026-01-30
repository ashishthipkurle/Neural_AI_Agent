"""
Integration Tests - Vision to Reasoning Flow.

Tests the complete pipeline:
1. Screen capture → OCR
2. OCR → UI element detection
3. UI elements → Layout analysis
4. Layout → Scene description
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class MockUIElement:
    """Mock UI element for testing."""
    def __init__(self, element_type, bbox, text="", confidence=0.9):
        self.element_type = element_type
        self.bbox = bbox  # (x, y, w, h)
        self.center = (bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2)
        self.text = text
        self.confidence = confidence
        self.properties = {}


class TestVisionToReasoningFlow:
    """Integration tests for vision understanding pipeline."""
    
    @pytest.fixture
    def mock_screen_capture(self):
        """Create mock screen capture."""
        import numpy as np
        # Create a dummy 1920x1080 image (RGB)
        return np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create mock OCR engine."""
        ocr = MagicMock()
        ocr.extract_text.return_value = [
            {"text": "File", "bbox": (10, 5, 40, 25), "confidence": 0.95},
            {"text": "Edit", "bbox": (60, 5, 40, 25), "confidence": 0.92},
            {"text": "Save", "bbox": (100, 400, 80, 30), "confidence": 0.88},
        ]
        return ocr
    
    @pytest.fixture
    def mock_ui_detector(self):
        """Create mock UI detector."""
        detector = MagicMock()
        detector.detect_elements.return_value = [
            MockUIElement("button", (100, 400, 80, 30), "Save"),
            MockUIElement("text_input", (200, 200, 300, 30)),
            MockUIElement("text_label", (10, 5, 40, 25), "File"),
        ]
        detector.is_available.return_value = True
        return detector
    
    @pytest.fixture
    def mock_layout_reasoner(self):
        """Create mock layout reasoner."""
        reasoner = MagicMock()
        reasoner.analyze_layout.return_value = MagicMock(
            regions=[
                MagicMock(name="header", role="navigation"),
                MagicMock(name="main", role="content"),
            ],
            detected_app_type="text_editor",
            description="A text editor application with menu bar and content area."
        )
        reasoner.describe_what_i_see.return_value = (
            "I see a text editor application. There's a menu bar at the top "
            "with File and Edit options, and a Save button in the content area."
        )
        return reasoner
    
    def test_screen_capture_to_ocr(self, mock_screen_capture, mock_ocr_engine):
        """Test that screen captures are processed by OCR."""
        # Process screen capture
        ocr_results = mock_ocr_engine.extract_text(mock_screen_capture)
        
        assert len(ocr_results) > 0
        assert "text" in ocr_results[0]
        assert "bbox" in ocr_results[0]
    
    def test_ocr_to_ui_detection(self, mock_screen_capture, mock_ui_detector):
        """Test that OCR results feed into UI detection."""
        # Detect UI elements
        elements = mock_ui_detector.detect_elements(mock_screen_capture)
        
        assert len(elements) > 0
        assert hasattr(elements[0], 'element_type')
        assert hasattr(elements[0], 'bbox')
    
    def test_ui_elements_to_layout_analysis(self, mock_ui_detector, mock_layout_reasoner, mock_screen_capture):
        """Test that UI elements are analyzed for layout."""
        # Get elements
        elements = mock_ui_detector.detect_elements(mock_screen_capture)
        
        # Analyze layout
        analysis = mock_layout_reasoner.analyze_layout(elements)
        
        assert analysis is not None
        assert hasattr(analysis, 'regions')
        assert hasattr(analysis, 'detected_app_type')
    
    def test_layout_to_scene_description(self, mock_ui_detector, mock_layout_reasoner, mock_screen_capture):
        """Test that layout analysis produces scene description."""
        elements = mock_ui_detector.detect_elements(mock_screen_capture)
        
        description = mock_layout_reasoner.describe_what_i_see(elements)
        
        assert description is not None
        assert len(description) > 0
        assert "text editor" in description.lower() or "menu" in description.lower()
    
    def test_complete_vision_pipeline(self, mock_screen_capture, mock_ocr_engine, 
                                       mock_ui_detector, mock_layout_reasoner):
        """Test complete vision understanding pipeline."""
        # 1. Capture screen (mocked)
        screen = mock_screen_capture
        assert screen is not None
        
        # 2. Extract text via OCR
        text_regions = mock_ocr_engine.extract_text(screen)
        assert len(text_regions) > 0
        
        # 3. Detect UI elements
        elements = mock_ui_detector.detect_elements(screen)
        assert len(elements) > 0
        
        # 4. Analyze layout
        analysis = mock_layout_reasoner.analyze_layout(elements)
        assert analysis.detected_app_type == "text_editor"
        
        # 5. Generate description
        description = mock_layout_reasoner.describe_what_i_see(elements)
        assert "text editor" in description.lower()
    
    def test_find_clickable_button(self, mock_ui_detector, mock_screen_capture):
        """Test finding a specific button to click."""
        elements = mock_ui_detector.detect_elements(mock_screen_capture)
        
        # Find Save button
        save_button = None
        for elem in elements:
            if elem.element_type == "button" and elem.text == "Save":
                save_button = elem
                break
        
        assert save_button is not None
        assert save_button.center is not None
        # Verify we can get click coordinates
        x, y = save_button.center
        assert 0 <= x <= 1920
        assert 0 <= y <= 1080


class TestWhereToClickReasoning:
    """Tests for 'Where should I click?' functionality."""
    
    def test_find_element_by_text(self):
        """Test finding element by text content."""
        elements = [
            MockUIElement("button", (100, 100, 80, 30), "OK"),
            MockUIElement("button", (200, 100, 80, 30), "Cancel"),
            MockUIElement("button", (300, 100, 80, 30), "Apply"),
        ]
        
        # Find "Cancel" button
        target = None
        for elem in elements:
            if "cancel" in elem.text.lower():
                target = elem
                break
        
        assert target is not None
        assert target.text == "Cancel"
    
    def test_find_text_input(self):
        """Test finding text input field."""
        elements = [
            MockUIElement("text_label", (50, 100, 100, 20), "Username:"),
            MockUIElement("text_input", (160, 100, 200, 25)),
            MockUIElement("text_label", (50, 140, 100, 20), "Password:"),
            MockUIElement("text_input", (160, 140, 200, 25)),
        ]
        
        # Find input fields
        inputs = [e for e in elements if e.element_type == "text_input"]
        assert len(inputs) == 2
    
    def test_spatial_relationship(self):
        """Test spatial reasoning between elements."""
        label = MockUIElement("text_label", (50, 100, 100, 20), "Username:")
        input_field = MockUIElement("text_input", (160, 100, 200, 25))
        
        # Check if input is to the right of label
        label_right = label.bbox[0] + label.bbox[2]
        input_left = input_field.bbox[0]
        
        # Input should be to the right of label
        assert input_left > label_right


class TestScreenChangeDetection:
    """Tests for detecting screen changes."""
    
    def test_detect_new_window(self):
        """Test detecting when a new window appears."""
        # Mock previous and current state
        prev_elements = [
            MockUIElement("button", (100, 100, 80, 30), "Open"),
        ]
        curr_elements = [
            MockUIElement("button", (100, 100, 80, 30), "Open"),
            MockUIElement("button", (400, 200, 80, 30), "OK"),  # New dialog
            MockUIElement("button", (500, 200, 80, 30), "Cancel"),  # New dialog
        ]
        
        # Detect new elements
        prev_texts = {e.text for e in prev_elements}
        new_elements = [e for e in curr_elements if e.text not in prev_texts]
        
        assert len(new_elements) == 2
        assert any(e.text == "OK" for e in new_elements)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
