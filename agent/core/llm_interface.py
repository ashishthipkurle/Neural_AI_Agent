import logging
import json
import os
from openai import OpenAI

class LLMInterface:
    """
    Interface for interacting with Large Language Models (Gemini or OpenAI).
    """
    def __init__(self, api_key: str, model_name: str, provider: str = "openai"):
        self.logger = logging.getLogger("LLMInterface")
        self.provider = provider
        self.model_name = model_name
        self.client = None
        self.model = None
        
        if not api_key or "YOUR_" in api_key:
            if provider != "ollama": # Ollama doesn't strictly need a key, but we pass one
                self.logger.warning("No valid API Key provided. LLM will not function.")
                return

        try:
            if provider == "openai":
                self.client = OpenAI(api_key=api_key)
                self.logger.info(f"Initialized OpenAI: {model_name}")
            elif provider == "ollama":
                self.client = OpenAI(
                    base_url="http://localhost:11434/v1",
                    api_key="ollama" 
                )
                self.logger.info(f"Initialized Ollama: {model_name}")
            else:
                self.logger.error(f"Unknown provider: {provider}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM: {e}")

    def parse_intent(self, user_input: str, system_context: str) -> dict:
        """
        Uses the LLM to parse user input into a JSON intent.
        """
        if not self.client and not self.model:
             return {"error": "LLM not initialized"}

        prompt = f"""
        USER INPUT: "{user_input}"

        You must respond with a valid JSON object.
        Structure:
        {{
            "actions": [
                {{
                    "action": "tool_name",
                    "reasoning": "short explanation",
                    "parameters": {{ "arg": "value" }}
                }}
            ]
        }}
        
        Example:
        {{ "actions": [ {{ "action": "chat_tool", "reasoning": "User asked a question", "parameters": {{ "message": "The capital of France is Paris." }} }} ] }}

        If no tool matches, return empty actions list.
        Do NOT wrap the output in markdown code blocks. Just valid JSON.
        """

        try:
            text = ""
            if (self.provider == "openai" or self.provider == "ollama") and self.client:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                text = response.choices[0].message.content
            
            elif self.provider == "gemini" and self.model:
                full_prompt = system_context + "\n" + prompt
                response = self.model.generate_content(full_prompt)
                text = response.text.replace("```json", "").replace("```", "").strip()

            if not text:
                return {"error": "Empty response from LLM"}

            return json.loads(text)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                self.logger.warning("Gemini Rate Limit Exceeded.")
                return {"error": "rate_limit", "message": "My API quota is exceeded. Please wait a moment."}
                
            self.logger.error(f"LLM Generation Error: {e}")
            return {"error": str(e)}

    def chat(self, system_prompt: str, user_input: str) -> str:
        """
        Simple chat completion returning a string.
        """
        if not self.client and not self.model:
             return "Error: LLM not initialized"

        try:
            if (self.provider == "openai" or self.provider == "ollama") and self.client:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ]
                )
                return response.choices[0].message.content
            
            elif self.provider == "gemini" and self.model:
                full_prompt = system_prompt + "\n\nUser: " + user_input
                response = self.model.generate_content(full_prompt)
                return response.text
                
            return "Error: Unknown provider configured."
            
        except Exception as e:
            self.logger.error(f"LLM Chat Error: {e}")
            return f"I encountered an error thinking about that: {e}"
