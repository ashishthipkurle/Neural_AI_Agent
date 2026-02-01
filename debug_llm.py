import sys
from openai import OpenAI

try:
    print("Initializing OpenAI client pointing to Local Ollama...")
    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )
    
    model = "gpt-oss:20b-cloud"
    print(f"Attempting to generate with model: {model}")
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello, are you working?"}],
    )
    
    print("\nSUCCESS!")
    print(f"Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"\nFAILURE: {e}")
    if "401" in str(e):
        print("\nDIAGNOSIS: 401 Unauthorized.")
        print("This normally means the local Ollama instance is not authenticated to use this cloud model,")
        print("OR it expects the client (us) to pass the real API key instead of 'ollama'.")
