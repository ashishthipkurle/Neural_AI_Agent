"""
Layout Reasoner - Screen layout understanding.

This module analyzes screen layout and spatial relationships
between UI elements for contextual understanding.

Features:
- DOM-like hierarchy graph export
- Spatial relationship analysis
- Application type detection
- "Where should I click?" reasoning
"""
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .ui_detector import UIElement, UIElementType


@dataclass
class LayoutRegion:
    """Semantic region of the screen."""
    name: str
    bbox: Tuple[int, int, int, int]
    role: str  # header, sidebar, content, footer, etc.
    elements: List[UIElement]


@dataclass
class UINode:
    """DOM-like node for UI hierarchy."""
    id: str
    type: str
    bbox: Tuple[int, int, int, int]
    text: str = ""
    role: str = ""  # button, input, label, container, etc.
    children: List['UINode'] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "type": self.type,
            "bbox": list(self.bbox),
            "text": self.text,
            "role": self.role,
            "children": [c.to_dict() for c in self.children],
            "properties": self.properties
        }


@dataclass
class LayoutAnalysis:
    """Complete layout analysis result."""
    regions: List[LayoutRegion]
    primary_content_area: Optional[Tuple[int, int, int, int]]
    navigation_area: Optional[Tuple[int, int, int, int]]
    element_count: int
    detected_app_type: str  # browser, editor, terminal, etc.
    description: str


@dataclass 
class ClickSuggestion:
    """Suggestion for where to click."""
    element_id: str
    element_type: str
    text: str
    bbox: Tuple[int, int, int, int]
    center: Tuple[int, int]
    confidence: float
    reason: str


class LayoutReasoner:
    """
    Screen layout reasoning system.
    
    Features:
    - Spatial relationship analysis
    - Semantic region detection
    - Application type detection
    - Natural language description generation
    - DOM-like hierarchy export
    - Click target suggestions
    
    Understands:
    - Header/footer/sidebar patterns
    - Content hierarchy
    - Groupings and clusters
    """
    
    # Common screen regions
    REGION_TYPES = {
        "header": {"y_max_percent": 0.15, "role": "Navigation/branding"},
        "footer": {"y_min_percent": 0.85, "role": "Status/controls"},
        "left_sidebar": {"x_max_percent": 0.25, "role": "Navigation/tools"},
        "right_sidebar": {"x_min_percent": 0.75, "role": "Details/properties"},
        "content": {"role": "Main content area"}
    }
    
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        """
        Initialize layout reasoner.
        
        Args:
            screen_width: Screen width in pixels.
            screen_height: Screen height in pixels.
        """
        self.logger = logging.getLogger("LayoutReasoner")
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._node_counter = 0
        self.logger.info("LayoutReasoner initialized.")
    
    def analyze_layout(self, elements: List[UIElement]) -> LayoutAnalysis:
        """
        Analyze screen layout from detected elements.
        
        Args:
            elements: List of detected UI elements.
        
        Returns:
            LayoutAnalysis with regions and description.
        """
        regions = self._detect_regions(elements)
        primary_content = self._find_primary_content(regions)
        navigation = self._find_navigation_area(regions)
        app_type = self._detect_app_type(elements, regions)
        description = self._generate_description(elements, regions, app_type)
        
        return LayoutAnalysis(
            regions=regions,
            primary_content_area=primary_content,
            navigation_area=navigation,
            element_count=len(elements),
            detected_app_type=app_type,
            description=description
        )
    
    # ==================== DOM EXPORT ====================
    
    def to_dom_tree(self, elements: List[UIElement]) -> UINode:
        """
        Convert UI elements to DOM-like tree structure.
        
        Args:
            elements: List of detected UI elements.
        
        Returns:
            Root UINode containing all elements as tree.
        """
        self._node_counter = 0
        
        # Create root node
        root = UINode(
            id="root",
            type="screen",
            bbox=(0, 0, self.screen_width, self.screen_height),
            role="document"
        )
        
        # Analyze layout to get regions
        regions = self._detect_regions(elements)
        
        # Create region nodes as children of root
        for region in regions:
            region_node = UINode(
                id=f"region_{region.name}",
                type="region",
                bbox=region.bbox,
                role=region.role,
                text=region.name
            )
            
            # Add elements as children of region
            for elem in region.elements:
                elem_node = self._element_to_node(elem)
                region_node.children.append(elem_node)
            
            root.children.append(region_node)
        
        return root
    
    def _element_to_node(self, element: UIElement) -> UINode:
        """Convert UIElement to UINode."""
        self._node_counter += 1
        
        return UINode(
            id=f"elem_{self._node_counter}",
            type=element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type),
            bbox=element.bbox,
            text=element.text or "",
            role=self._infer_role(element),
            properties={
                "confidence": getattr(element, 'confidence', 0.9),
                "clickable": self._is_clickable(element)
            }
        )
    
    def _infer_role(self, element: UIElement) -> str:
        """Infer ARIA-like role from element type."""
        role_map = {
            UIElementType.BUTTON: "button",
            UIElementType.TEXT_INPUT: "textbox",
            UIElementType.TEXT_LABEL: "label",
            UIElementType.CHECKBOX: "checkbox",
            UIElementType.DROPDOWN: "combobox",
            UIElementType.LINK: "link",
            UIElementType.IMAGE: "img",
            UIElementType.ICON: "img",
        }
        return role_map.get(element.element_type, "generic")
    
    def _is_clickable(self, element: UIElement) -> bool:
        """Check if element is likely clickable."""
        clickable_types = {
            UIElementType.BUTTON,
            UIElementType.LINK,
            UIElementType.CHECKBOX,
            UIElementType.DROPDOWN,
            UIElementType.ICON
        }
        return element.element_type in clickable_types
    
    def export_as_json(self, elements: List[UIElement]) -> str:
        """
        Export layout as JSON string (DOM-like structure).
        
        Args:
            elements: List of detected UI elements.
        
        Returns:
            JSON string of DOM tree.
        """
        tree = self.to_dom_tree(elements)
        return json.dumps(tree.to_dict(), indent=2)
    
    def export_as_dict(self, elements: List[UIElement]) -> Dict[str, Any]:
        """Export layout as dictionary."""
        tree = self.to_dom_tree(elements)
        return tree.to_dict()
    
    # ==================== CLICK SUGGESTIONS ====================
    
    def answer_where_to_click(
        self, 
        elements: List[UIElement],
        target_description: str
    ) -> List[ClickSuggestion]:
        """
        Answer "Where should I click?" for a given action.
        
        Args:
            elements: List of detected UI elements.
            target_description: What the user wants to click (e.g., "save button", "submit")
        
        Returns:
            List of ClickSuggestions ranked by confidence.
        """
        suggestions = []
        target_lower = target_description.lower()
        
        for i, element in enumerate(elements):
            # Skip non-clickable elements unless specifically requested
            if not self._is_clickable(element) and "text" not in target_lower:
                continue
            
            confidence = 0.0
            reason = ""
            
            elem_text = (element.text or "").lower()
            elem_type = element.element_type
            
            # Text match scoring
            if elem_text:
                if target_lower in elem_text:
                    confidence = 0.9
                    reason = f"Text contains '{target_description}'"
                elif any(word in elem_text for word in target_lower.split()):
                    confidence = 0.7
                    reason = f"Text partially matches"
            
            # Type match scoring
            if "button" in target_lower and elem_type == UIElementType.BUTTON:
                confidence = max(confidence, 0.6)
                reason = reason or "Element is a button"
            elif "input" in target_lower and elem_type == UIElementType.TEXT_INPUT:
                confidence = max(confidence, 0.6)
                reason = reason or "Element is a text input"
            elif "link" in target_lower and elem_type == UIElementType.LINK:
                confidence = max(confidence, 0.6)
                reason = reason or "Element is a link"
            
            # Common action keywords
            action_matches = {
                "save": ["save", "apply", "confirm"],
                "cancel": ["cancel", "close", "x"],
                "submit": ["submit", "send", "ok", "done"],
                "search": ["search", "find", "🔍"],
                "menu": ["menu", "☰", "≡"],
                "settings": ["settings", "config", "⚙", "options"],
            }
            
            for action, keywords in action_matches.items():
                if action in target_lower:
                    if any(kw in elem_text for kw in keywords):
                        confidence = max(confidence, 0.85)
                        reason = f"Matches '{action}' action"
            
            if confidence > 0.3:
                x, y, w, h = element.bbox
                suggestions.append(ClickSuggestion(
                    element_id=f"elem_{i}",
                    element_type=str(elem_type.value if hasattr(elem_type, 'value') else elem_type),
                    text=element.text or "",
                    bbox=element.bbox,
                    center=(x + w // 2, y + h // 2),
                    confidence=confidence,
                    reason=reason
                ))
        
        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return suggestions[:5]  # Return top 5
    
    def find_element_by_text(
        self, 
        elements: List[UIElement], 
        text: str
    ) -> Optional[UIElement]:
        """Find element containing specific text."""
        text_lower = text.lower()
        for elem in elements:
            if elem.text and text_lower in elem.text.lower():
                return elem
        return None
    
    def find_clickable_elements(self, elements: List[UIElement]) -> List[UIElement]:
        """Get all clickable elements."""
        return [e for e in elements if self._is_clickable(e)]
    
    # ==================== EXISTING METHODS ====================
    
    def _detect_regions(self, elements: List[UIElement]) -> List[LayoutRegion]:
        """Detect semantic regions based on element positions."""
        regions = []
        
        # Group elements by vertical position
        header_elements = []
        footer_elements = []
        left_sidebar_elements = []
        right_sidebar_elements = []
        content_elements = []
        
        header_threshold = self.screen_height * 0.15
        footer_threshold = self.screen_height * 0.85
        left_threshold = self.screen_width * 0.25
        right_threshold = self.screen_width * 0.75
        
        for element in elements:
            x, y, w, h = element.bbox
            center_y = y + h / 2
            center_x = x + w / 2
            
            if center_y < header_threshold:
                header_elements.append(element)
            elif center_y > footer_threshold:
                footer_elements.append(element)
            elif center_x < left_threshold:
                left_sidebar_elements.append(element)
            elif center_x > right_threshold:
                right_sidebar_elements.append(element)
            else:
                content_elements.append(element)
        
        # Create regions for non-empty groups
        if header_elements:
            bbox = self._compute_bounding_box(header_elements)
            regions.append(LayoutRegion(
                name="header",
                bbox=bbox,
                role="header",
                elements=header_elements
            ))
        
        if footer_elements:
            bbox = self._compute_bounding_box(footer_elements)
            regions.append(LayoutRegion(
                name="footer",
                bbox=bbox,
                role="footer",
                elements=footer_elements
            ))
        
        if left_sidebar_elements:
            bbox = self._compute_bounding_box(left_sidebar_elements)
            regions.append(LayoutRegion(
                name="left_sidebar",
                bbox=bbox,
                role="sidebar",
                elements=left_sidebar_elements
            ))
        
        if right_sidebar_elements:
            bbox = self._compute_bounding_box(right_sidebar_elements)
            regions.append(LayoutRegion(
                name="right_sidebar",
                bbox=bbox,
                role="sidebar",
                elements=right_sidebar_elements
            ))
        
        if content_elements:
            bbox = self._compute_bounding_box(content_elements)
            regions.append(LayoutRegion(
                name="content",
                bbox=bbox,
                role="content",
                elements=content_elements
            ))
        
        return regions
    
    def _compute_bounding_box(
        self, 
        elements: List[UIElement]
    ) -> Tuple[int, int, int, int]:
        """Compute bounding box encompassing all elements."""
        if not elements:
            return (0, 0, 0, 0)
        
        min_x = min(e.bbox[0] for e in elements)
        min_y = min(e.bbox[1] for e in elements)
        max_x = max(e.bbox[0] + e.bbox[2] for e in elements)
        max_y = max(e.bbox[1] + e.bbox[3] for e in elements)
        
        return (min_x, min_y, max_x - min_x, max_y - min_y)
    
    def _find_primary_content(
        self, 
        regions: List[LayoutRegion]
    ) -> Optional[Tuple[int, int, int, int]]:
        """Find the primary content area."""
        for region in regions:
            if region.role == "content":
                return region.bbox
        return None
    
    def _find_navigation_area(
        self, 
        regions: List[LayoutRegion]
    ) -> Optional[Tuple[int, int, int, int]]:
        """Find navigation area (header or sidebar)."""
        for region in regions:
            if region.role in ["header", "sidebar"]:
                return region.bbox
        return None
    
    def _detect_app_type(
        self, 
        elements: List[UIElement],
        regions: List[LayoutRegion]
    ) -> str:
        """Detect application type from layout and elements."""
        # Collect all text from elements
        all_text = " ".join(e.text.lower() for e in elements if e.text)
        
        # Check for browser indicators
        browser_keywords = ["http", "www", "search", "bookmark", "tab"]
        if any(kw in all_text for kw in browser_keywords):
            return "browser"
        
        # Check for code editor indicators
        editor_keywords = ["def ", "function", "class ", "import", "const "]
        if any(kw in all_text for kw in editor_keywords):
            return "code_editor"
        
        # Check for terminal indicators
        terminal_keywords = ["$", ">>>", "c:\\", "~$"]
        if any(kw in all_text for kw in terminal_keywords):
            return "terminal"
        
        # Check for document editor
        doc_keywords = ["file", "edit", "view", "format", "tools"]
        if sum(1 for kw in doc_keywords if kw in all_text) >= 3:
            return "document_editor"
        
        return "unknown"
    
    def _generate_description(
        self,
        elements: List[UIElement],
        regions: List[LayoutRegion],
        app_type: str
    ) -> str:
        """Generate natural language description of the screen."""
        parts = []
        
        # App type
        app_descriptions = {
            "browser": "a web browser",
            "code_editor": "a code editor",
            "terminal": "a terminal/command prompt",
            "document_editor": "a document editor",
            "unknown": "an application"
        }
        parts.append(f"I'm looking at {app_descriptions.get(app_type, 'an application')}.")
        
        # Regions
        region_names = [r.name for r in regions]
        if region_names:
            parts.append(f"The layout has: {', '.join(region_names)}.")
        
        # Element summary
        buttons = sum(1 for e in elements if e.element_type == UIElementType.BUTTON)
        inputs = sum(1 for e in elements if e.element_type == UIElementType.TEXT_INPUT)
        labels = sum(1 for e in elements if e.element_type == UIElementType.TEXT_LABEL)
        
        element_desc = []
        if buttons:
            element_desc.append(f"{buttons} buttons")
        if inputs:
            element_desc.append(f"{inputs} text inputs")
        if labels:
            element_desc.append(f"{labels} text labels")
        
        if element_desc:
            parts.append(f"I can see {', '.join(element_desc)}.")
        
        # Notable text
        texts = [e.text for e in elements if e.text and len(e.text) > 3][:5]
        if texts:
            parts.append(f"Some visible text: {', '.join(texts[:3])}...")
        
        return " ".join(parts)
    
    def describe_what_i_see(
        self, 
        elements: List[UIElement]
    ) -> str:
        """Generate 'What am I looking at?' response."""
        analysis = self.analyze_layout(elements)
        return analysis.description

