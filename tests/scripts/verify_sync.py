import asyncio
import websockets
import json
import requests

async def test_sync():
    print("--- Diagnostic Report ---")
    
    # 1. Check REST API
    try:
        resp = requests.get("http://127.0.0.1:8000/api/status")
        print(f"[API] Status: {resp.status_code}")
        print(f"[API] Data: {resp.json()}")
    except Exception as e:
        print(f"[API] Error: {e}")

    # 2. Check WebSocket
    try:
        uri = "ws://127.0.0.1:8000/api/ws"
        async with websockets.connect(uri) as websocket:
            print("[WS] Connection Successful")
            
            # Send a trigger message
            requests.post("http://127.0.0.1:8000/api/chat", json={"message": "hello diagnostic test"})
            print("[WS] Triggered chat message")
            
            # Wait for response event
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                event = json.loads(msg)
                print(f"[WS] Event Received: {event['type']} from {event['role']}")
                print(f"[WS] Text: {event['text']}")
            except asyncio.TimeoutError:
                print("[WS] Timeout - no event received")
    except Exception as e:
        print(f"[WS] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_sync())
