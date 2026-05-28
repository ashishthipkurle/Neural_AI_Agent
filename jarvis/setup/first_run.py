"""
INDRA First Run Setup — Onboarding Q&A on first launch.
Seeds the identity DB if it's empty.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.store import MemoryStore
from utils.logger import get_logger

logger = get_logger("Setup")

FLAG_FILE = Path(__file__).parent.parent / ".indra_initialized"


def is_first_run(memory: MemoryStore) -> bool:
    """Check if this is the very first time INDRA is running."""
    if FLAG_FILE.exists():
        return False
    # Double check memory just in case flag was deleted
    return memory.is_empty()


def run_onboarding(speaker, memory: MemoryStore, ears):
    """
    Run the one-time onboarding conversation.
    Ask questions ONE AT A TIME via voice, wait for spoken answer.
    """
    logger.info("Starting first-run onboarding sequence")
    
    from config import USER_NAME
    
    intro = (
        f"Good to meet you, {USER_NAME}. Before we begin, I have a few quick "
        f"questions so I can serve you properly."
    )
    speaker.enqueue(intro)
    
    # Wait for intro to finish playing
    while speaker.queue_size > 0 or speaker.is_speaking:
        time.sleep(0.5)
        
    questions = [
        "What do you mainly use your computer for — work, coding, content creation, or something else?",
        "What time do you usually start your day?",
        "Which apps do you use most often?",
        "Is there anything you'd like me to always remember about how you prefer to work?"
    ]
    
    for q in questions:
        speaker.enqueue(q)
        
        # Wait for INDRA to finish asking
        while speaker.queue_size > 0 or speaker.is_speaking:
            time.sleep(0.5)
            
        logger.info(f"Onboarding asked: {q}")
        
        # Wait for Ashish to answer
        answer = ""
        retries = 0
        while not answer and retries < 3:
            answer = ears.listen_once()
            if not answer:
                speaker.enqueue("I didn't quite catch that. Could you repeat?")
                while speaker.is_speaking: time.sleep(0.5)
                retries += 1
                
        if answer:
            logger.info(f"Onboarding answer: {answer}")
            # Store in permanent identity memory
            fact = f"Question: {q} | Answer: {answer}"
            memory.save_identity(fact)
        else:
            logger.warning("Onboarding skipped a question due to no audio")
            
    outro = "Perfect. I have everything I need. Let's get started."
    speaker.enqueue(outro)
    
    # Set flag so this never runs again
    FLAG_FILE.touch()
    logger.info("Onboarding complete. Flag file created.")
