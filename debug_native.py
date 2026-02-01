import requests
import json

url = "http://localhost:11434/api/chat"
payload = {
    "model": "gpt-oss:120b-cloud",
    "messages": [
        {
            "role": "user",
            "content": "Hello!"
        }
    ],
    "stream": False
}

print(f"Sending request to {url}...")
try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS! Native API works.")
    else:
        print("FAILURE! Native API also returns error.")

except Exception as e:
    print(f"Error: {e}")
