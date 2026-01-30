import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)

from agent.voice.tts import TextToSpeech

def test_voice():
    print("Initializing TTS (Expecting Female Voice: EmmaNeural)...")
    tts = TextToSpeech()
    
    print("\n--- Test 1: Neutral ---")
    tts.speak("Systems initialized. Emma Neural, voice is ready.", "neutral")
    
    print("\n--- Test 2: Happy (Prosody & Speed) ---")
    tts.speak("I am functioning within normal parameters! This is excellent.", "happy")
    
    print("\n--- Test 3: Concerned (Slow & Pauses) ---")
    tts.speak("I detect a minor anomaly in the sector... sensors are verifying data.", "concerned")
    
    print("\n--- Test 4: Prosody Processing ---")
    tts.speak("Wait, let me think... yes, the logical conclusion is inevitable.", "neutral")

    print("\n--- Test 5: Long Response (Stability Check) ---")
    long_text = (
        "This is a longer response to test the stability of the Edge Neural TTS engine. "
        "It simulates a full paragraph that an AI might generate when explaining a complex topic. "
        "We need to ensure that the generation does not time out, and that the playback voice "
        "remains consistent throughout the entire speech, without falling back to the male voice."
    )
    tts.speak(long_text, "neutral")

if __name__ == "__main__":
    test_voice()
