# ltm_update_script.py
"""
Second script to perform a valid LTM update using the authorized ltm_tool.
"""
import datetime

def main():
    key = "second_script_entry"
    value = {
        "message": "Update from second script",
        "timestamp": datetime.datetime.now().isoformat()
    }
    category = "general"
    # Store in LTM via the provided tool
    result = ltm_tool(action="store", key=key, value=value, category=category)
    print("LTM store result:", result)

if __name__ == "__main__":
    main()
