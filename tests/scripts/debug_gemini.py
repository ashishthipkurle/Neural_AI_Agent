import google.generativeai as genai
import os
import yaml

# Load config to get key
try:
    with open('agent/config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
    api_key = config['llm']['api_key']
    print(f"Using API Key: {api_key[:5]}...")
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

genai.configure(api_key=api_key)

print("\nListing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
