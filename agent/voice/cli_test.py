"""
Voice Pipeline CLI Test
Tests the full wake -> STT -> TTS echo pipeline.
"""
import logging
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    try:
        from agent.voice.session import VoiceSession
    except ImportError:
        print("Please run this script from the project root: python -m agent.voice.cli_test")
        sys.exit(1)

    print("=== Neural AI Agent: Voice Pipeline Test ===")
    print("Initializing components (this may take a moment to load models)...")
    
    def on_event(event):
        print(f"\n[EVENT] {event['type']} | State: {event['state']} | RMS: {event['level']:.2f}")
        if event['transcript']:
            print(f"        Transcript: {event['transcript']}")
            
    try:
        session = VoiceSession(broadcast_callback=on_event, device="cuda")
        print("\nInitialization complete.")
        print("Say 'Hey Neural' or 'Hello Neural' to wake.")
        print("Say 'stop', 'cancel' or 'nevermind' to exit listening.")
        print("Press Ctrl+C to quit the test entirely.\n")
        
        session.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping voice session...")
        session.stop()
        print("Exited cleanly.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
