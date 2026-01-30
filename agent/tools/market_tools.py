
import logging
from agent.vision.chart_analyzer import ChartAnalyzer
from agent.vision.screen_eye import ScreenEye

class MarketTools:
    """
    Tools for technical market analysis using chart screenshots.
    Wrapper around ChartAnalyzer for the agent's tool system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("MarketTools")
        self.analyzer = ChartAnalyzer()
        self.screen_eye = ScreenEye()

    def analyze_chart(self, path: str) -> str:
        """
        Analyze a stock/index chart screenshot for technical trend assessment.
        
        Args:
            path: Absolute path to the chart image file.
            
        Returns:
            Structured Markdown report of the technical analysis.
        """
        self.logger.info(f"Analyzing chart from file: {path}")
        return self.analyzer.analyze_chart(path)

    def analyze_screen_chart(self) -> str:
        """
        Capture screen and analyze any visible chart for technical trend assessment.
        
        Returns:
            Structured Markdown report of the technical analysis.
        """
        self.logger.info("Capturing screen for chart analysis...")
        
        # Capture screen
        screenshot_path = self.screen_eye.capture()
        if not screenshot_path:
            return "Error: Failed to capture screen for analysis."
            
        self.logger.info(f"Screen captured to: {screenshot_path}. Analyzing...")
        return self.analyzer.analyze_chart(screenshot_path)
