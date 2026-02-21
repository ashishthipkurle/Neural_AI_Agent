# update_ltm.py
"""
This script updates the Long-Term Memory (LTM) with a sample entry using the authorized pathway.
"""

def main():
    # Define the key, value, and category for the LTM entry
    key = "sample_entry"
    value = {
        "message": "Hello from LTM update script",
        "timestamp": "2026-02-17T12:00:00"
    }
    category = "general"

    # Perform the LTM store operation via the authorized tool
    result = ltm_tool(
        action="store",
        key=key,
        value=value,
        category=category
    )
    print("LTM store result:", result)

if __name__ == "__main__":
    main()
