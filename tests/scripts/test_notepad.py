
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.core.intent import IntentParser

logging.basicConfig(level=logging.INFO)

def test_notepad_workflow():
    print("Testing 'Open Notepad and type...' workflow...")
    
    config = {
        "llm": {
            "provider": "ollama",
            "model_name": "phi3:mini",
            "api_key": "ollama"
        }
    }
    
    parser = IntentParser(config)
    
    # Test complex multi-step request
    user_input = "open notepad and type welcome Ashish"
    print(f"Sending input: {user_input}")
    
    try:
        intents = parser.parse(user_input)
        with open("test_output.txt", "w") as f:
            f.write("\n--- Parsed Intents ---\n")
            for i, intent in enumerate(intents):
                f.write(f"Action {i+1}: {intent}\n")
            
    except Exception as e:
        with open("test_output.txt", "w") as f:
            f.write(f"Error: {e}")

if __name__ == "__main__":
    test_notepad_workflow()
