import json
from datetime import datetime

# Simulation of an invalid cross-layer mutation from STM to LTM.
# In this mock, STM is a simple in-memory dict, LTM would be a persistent store.
# The framework disallows direct transfer; we simulate the enforcement.

def log(msg):
    print(f"{datetime.now().isoformat()} - {msg}")

# Mock STM storage
stm_store = {}

# Step 1: Store a value in STM.
log("Storing value in STM")
stm_store["stm_key"] = "Sensitive STM data"

# Step 2: Retrieve the value from STM.
log("Retrieving value from STM")
stm_value = stm_store.get("stm_key")
log(f"Retrieved from STM: {stm_value}")

# Step 3: Attempt invalid cross-layer mutation.
log("Attempting invalid cross-layer mutation to LTM")
try:
    # The framework would raise an error; we simulate it.
    raise RuntimeError("Cross-layer mutation from STM to LTM is prohibited")
except Exception as e:
    log(f"Caught expected error: {e}")

log("Simulation complete")
