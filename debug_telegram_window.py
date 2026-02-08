
import win32gui
import win32process
import psutil

def get_process_name_by_pid(pid):
    try:
        return psutil.Process(pid).name()
    except:
        return "?"

def callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            # Get process ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = get_process_name_by_pid(pid)
            
            # Print ALL visible windows to debug
            print(f"HWND: {hwnd} | Title: '{title}' | PID: {pid} ({proc_name})")

print("Listing all visible windows...")
win32gui.EnumWindows(callback, None)
print("Done.")
