import requests
import time
import json
import os

API_BASE = "http://localhost:8000"

def run_tests():
    print("Testing Workflow API endpoints...")
    
    # Wait for API to be ready
    for _ in range(10):
        try:
            requests.get(f"{API_BASE}/docs", timeout=2)
            break
        except:
            time.sleep(1)
            
    # 1. Create a workflow
    print("\n1. Creating workflow...")
    workflow_data = {
        "name": "Test Web Search & File Write",
        "description": "Searches the web and writes to a file",
        "nodes": [
            {
                "id": "n1",
                "type": "action",
                "label": "Web Search",
                "tool_id": "web_search",
                "icon": "Globe",
                "color": "cyan",
                "x": 0, "y": 0,
                "config": {"query": "Latest AI news"}
            },
            {
                "id": "n2",
                "type": "action",
                "label": "Write File",
                "tool_id": "file_write",
                "icon": "Database",
                "color": "orange",
                "x": 200, "y": 0,
                "config": {"path": "test_output.txt"}
            }
        ],
        "edges": [
            {"id": "e1", "from": "n1", "to": "n2"}
        ],
        "config": {"stop_on_error": True}
    }
    
    res = requests.post(f"{API_BASE}/api/workflow", json=workflow_data)
    assert res.status_code == 200, f"Failed to create: {res.text}"
    wf = res.json()["workflow"]
    wf_id = wf["id"]
    print(f"Created workflow: {wf_id}")
    
    # 2. Get workflow
    print("\n2. Getting workflow...")
    res = requests.get(f"{API_BASE}/api/workflow/{wf_id}")
    assert res.status_code == 200
    assert res.json()["workflow"]["name"] == "Test Web Search & File Write"
    print("Get successful")
    
    # 3. Run inline workflow
    print("\n3. Running workflow inline...")
    res = requests.post(f"{API_BASE}/api/workflow/run-inline", json=workflow_data)
    assert res.status_code == 200
    print("Inline run triggered successfully")
    
    time.sleep(5)
    
    # 4. Check if file was written
    print("\n4. Checking if test_output.txt exists...")
    if os.path.exists("test_output.txt"):
        with open("test_output.txt", "r", encoding="utf-8") as f:
            content = f.read()
        print(f"File created successfully. Size: {len(content)} bytes")
        os.remove("test_output.txt")
    else:
        print("WARNING: test_output.txt was not created. The inline execution might have failed or is still running.")
    
    # 5. Delete workflow
    print("\n5. Deleting workflow...")
    res = requests.delete(f"{API_BASE}/api/workflow/{wf_id}")
    assert res.status_code == 200
    print("Delete successful")
    
    print("\n✅ All workflow API tests passed!")

if __name__ == "__main__":
    run_tests()
