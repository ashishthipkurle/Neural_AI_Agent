
import os
import subprocess
import time

def find_browser_path(exe_name):
    # Common paths
    paths = [
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), f"Microsoft\\Edge\\Application\\{exe_name}"),
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), f"Microsoft\\Edge\\Application\\{exe_name}"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), f"Google\\Chrome\\Application\\{exe_name}"),
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), f"Google\\Chrome\\Application\\{exe_name}"),
    ]
    
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def test_launch():
    edge_path = find_browser_path("msedge.exe")
    chrome_path = find_browser_path("chrome.exe")
    
    print(f"Edge Path: {edge_path}")
    print(f"Chrome Path: {chrome_path}")
    
    if edge_path:
        print("Launching Edge directly with Popen...")
        # Direct Popen avoids 'start' command quirks
        subprocess.Popen([edge_path, "https://www.bing.com/search?q=test_direct_popen"])
    
    time.sleep(2)
    
    if chrome_path:
        print("Launching Chrome directly with Popen...")
        subprocess.Popen([chrome_path, "https://www.google.com/search?q=test_direct_popen"])

if __name__ == "__main__":
    test_launch()
