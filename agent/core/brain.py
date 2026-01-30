import logging
import json
from typing import Optional, Dict, Any, Protocol
from agent.core.llm_interface import LLMInterface

class Brain:
    """
    The Brain module acts as the cognitive center of the agent.
    It wraps the raw LLM interface and provides semantic capabilities like:
    - Planning (Goal decomposition)
    - Thinking (Chat/Reasoning)
    - Summarization
    """
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger("Brain")
        self.config = config
        
        llm_config = config.get('llm', {})
        self.provider = llm_config.get('provider', 'ollama')
        self.provider = llm_config.get('provider', 'ollama')
        # Use config model name, or default to standard phi3:mini which user has installed
        self.model_name = llm_config.get('model_name', 'phi3:mini')
        self.api_key = llm_config.get('api_key', 'ollama')
        
        self.logger.info(f"Initializing Brain with {self.provider}/{self.model_name}")
        self.llm = LLMInterface(self.api_key, self.model_name, self.provider)

    async def think(self, context: str, prompt: str) -> str:
        """
        General reasoning/chat capability.
        """
        # Use System Prompt from Config if available, otherwise default
        persona = self.config.get('system_prompt', "You are a helpful, local AI assistant.")
        system_prompt = f"{persona}\nCONTEXT: {context}"
        return self.llm.chat(system_prompt, prompt)

    async def plan(self, goal: str) -> Dict[str, Any]:
        """
        Decomposes a user goal into a structured plan/intent.
        """
        system_context = """
        You are an autonomous AI agent running locally on the user's PC.
        Your job is to parse the User's goal into a JSON structure of actions.
        Available tools: chat, open_app, search_web, write_code, system_control.
        """
        return self.llm.parse_intent(goal, system_context)
        
    def is_alive(self) -> bool:
        return self.llm.client is not None or self.llm.model is not None
