import pyttsx3
import time

def test_audio():
    print("Testing Audio...")
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        print(f"Found {len(voices)} voices.")
        
        engine.say("Hello Ashish, I can speak now.")
        engine.runAndWait()
        print("Audio test complete.")
    except Exception as e:
        print(f"Audio Error: {e}")

if __name__ == "__main__":
    test_audio()
