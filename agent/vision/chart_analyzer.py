
import logging
import os
import base64
from typing import Dict, Any, Optional
import requests
import json
from agent.vision.screen_eye import ScreenEye

class ChartAnalyzer:
    """
    Industrial Technical Market Analysis Engine.
    
    Analyzes chart screenshots using vision models (via Ollama) and 
    structured technical analysis methodology.
    """
    
    def __init__(self, model_name: str = "llava:13b"):
        self.logger = logging.getLogger("ChartAnalyzer")
        self.model_name = model_name
        self.base_url = "http://localhost:11434"
        self.screen_eye = ScreenEye()
        
        # Check available models and fallback if needed
        self._check_model_availability()

    def _check_model_availability(self):
        """Checks if the preferred model is available, falls back to standard llava if not."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = [m['name'] for m in response.json().get('models', [])]
                if self.model_name not in models:
                    self.logger.warning(f"Preferred model {self.model_name} not found. Checking alternatives.")
                    if "llava:latest" in models:
                        self.model_name = "llava:latest"
                    elif "llava" in models:
                        self.model_name = "llava"
                    # Add other vision models like gemma3 if supported by ollama vision
                    # For now default to what was passed or llava
                    self.logger.info(f"Using vision model: {self.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to check Ollama models: {e}")

    def analyze_chart(self, image_path: str) -> str:
        """
        Analyzes a chart image file and returns a structured technical assessment.
        """
        if not os.path.exists(image_path):
            return "Error: Image file not found."
            
        try:
            # Encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
                
            prompt = self._get_analysis_prompt()
            
            self.logger.info(f"Sending chart to {self.model_name} for analysis...")
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "images": [image_data],
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for strict analysis
                    "num_predict": 1024
                }
            }
            
            response = requests.post(f"{self.base_url}/api/generate", json=payload)
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                return self._format_output(result)
            else:
                return f"Error from Vision Model: {response.text}"
                
        except Exception as e:
            self.logger.error(f"Chart analysis failed: {e}")
            return f"Analysis Failed: {str(e)}"

    def _get_analysis_prompt(self) -> str:
        """Returns a concise, prediction-focused prompt."""
        return """
TASK: Analyze this financial chart and answer the user's question: "Will it go UP or DOWN?"

INSTRUCTIONS:
1. Look for Trend (Higher Highs/Lows = UP, Lower Highs/Lows = DOWN).
2. Look for Support/Resistance levels.
3. BE DECISIVE. Do not give vague "it depends" answers unless impossible to tell.
4. Keep it short and readable.

OUTPUT FORMAT:

# 🔮 PREDICTION: [UP / DOWN / NEUTRAL]

## 💡 RATIONALE
- [Point 1: Trend structure]
- [Point 2: Key levels]
- [Point 3: Candles/Signal]

## ⚠️ KEY LEVEL TO WATCH
[Price Level]
"""

    def _format_output(self, raw_output: str) -> str:
        """Cleans and formats the LLM output if necessary."""
        # The prompt is strict, so we mostly return raw output unless it needs cleanup
        return raw_output.strip()
