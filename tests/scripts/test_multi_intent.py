import yaml
from agent.core.intent import IntentParser

def test():
    # Load config
    with open('agent/config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    parser = IntentParser(config)
    
    queries = [
        "Open Notepad and Calculator",
        "Open Edge and search youtube",
        "Calculate 5+5 and write it to result.txt"
    ]
    
    for q in queries:
        print(f"\n--- Testing: '{q}' ---")
        try:
            # We want to see the parser result (which should be a list)
            intents = parser.parse(q)
            print(f"Count: {len(intents)}")
            for i in intents:
                print(f" - {i}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test()
