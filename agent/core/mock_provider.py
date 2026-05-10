import json
from typing import List, Dict, Any, Optional

class MockProvider:
    """Mock LLM Provider for deterministic testing."""
    
    def __init__(self, predefined_responses: List[Dict[str, Any]]):
        self.responses = predefined_responses
        self.call_history: List[Dict[str, Any]] = []
        self.current_index = 0
        
    def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Simulate an LLM generation."""
        self.call_history.append({
            "messages": messages,
            "tools": tools
        })
        
        if self.current_index >= len(self.responses):
            return {
                "role": "assistant",
                "content": "Mock provider exhausted predefined responses."
            }
            
        response = self.responses[self.current_index]
        self.current_index += 1
        
        # Simulate usage stats
        return {
            "message": response,
            "usage": {
                "input_tokens": 150,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0
            }
        }
