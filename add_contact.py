import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from agent.memory.personal_memory import PersonalMemoryManager

def add_contact():
    # Initialize manager pointing to the correct DB path
    # Assuming run from project root
    db_path = "agent_data/personal_memory.db"
    
    print(f"Connecting to memory at {db_path}...")
    pm = PersonalMemoryManager(db_path)
    
    # Check if exists
    existing = pm.get_relationship("friend")
    if existing:
        print(f"Update existing 'friend' contact: {existing.get('phone_number')} -> +919860084406")
    
    # Upsert
    pm.record_relationship(
        name="friend",
        relationship_type="friend",
        phone_number="+919860084406",
        context="User provided contact via chat.",
        important_info={"nickname": "Ashish"}
    )
    print("Successfully added/updated 'friend' in memory.")

if __name__ == "__main__":
    add_contact()
