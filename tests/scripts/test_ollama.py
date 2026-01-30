
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.core.intent import IntentParser

logging.basicConfig(level=logging.INFO)

def test_ollama_parser():
    print("Testing Ollama Intent Parser for Launch App...")
    
    config = {
        "llm": {
            "provider": "ollama",
            "model_name": "phi3:mini",
            "api_key": "ollama"
        }
    }
    
    parser = IntentParser(config)
    
    # Test Launch App
    user_input = "Open Notepad"
    print(f"Sending input: {user_input}")
    
    try:
        intents = parser.parse(user_input)
        print("Intents received:")
        for intent in intents:
            print(intent)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ollama_parser()
