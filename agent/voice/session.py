"""
Voice Session State Machine

States: IDLE -> LISTENING -> THINKING -> ACTING -> SPEAKING -> IDLE
Provides a 6s follow-up window.
"""
import logging
import threading
import time
from .events import VoiceEvents
from .audio_stream import AudioStream
from .wake_word import WakeWordEngine
from .stt import SpeechToText
from .tts import TextToSpeech

logger = logging.getLogger("VoiceSession")

class VoiceSession:
    def __init__(self, broadcast_callback=None, device="cuda"):
        self.events = VoiceEvents(broadcast_callback)
        self.audio = AudioStream()
        self.wake_word = WakeWordEngine(device=device)
        self.stt = SpeechToText(device=device)
        self.tts = TextToSpeech()
        self.state = "IDLE"
        self.running = False
        self.thread = None
        
        # Follow-up window tracking
        self.last_interaction_time = 0
        self.follow_up_window = 6.0
        self.on_command_callback = None
        
    def set_state(self, new_state, transcript="", message="", task_id="", step=""):
        if self.state != new_state:
            logger.info(f"State transition: {self.state} -> {new_state}")
        self.state = new_state
        self.events.publish(state=new_state, level=self.audio.get_rms(), 
                            transcript=transcript, message=message, 
                            task_id=task_id, step=step)
        
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        self.audio.stop()
        if self.thread:
            self.thread.join(timeout=2)
            
    def cancel_current_action(self):
        logger.info("Canceling current action...")
        self.set_state("IDLE")

    def _loop(self):
        self.set_state("IDLE")
        while self.running:
            if self.state == "IDLE":
                # Check if in follow-up window
                if time.time() - self.last_interaction_time < self.follow_up_window:
                    self.set_state("LISTENING")
                    continue
                    
                # Wait for wake word
                ww = self.wake_word.listen_for_wake_word(
                    self.audio, 
                    should_pause_callback=lambda: self.state not in ["IDLE"]
                )
                if ww:
                    self.set_state("LISTENING", transcript=ww)
            
            elif self.state == "LISTENING":
                command = self.stt.listen(self.audio, timeout=10)
                if command:
                    cmd_lower = command.lower().strip()
                    if cmd_lower in ["stop", "cancel", "nevermind", "never mind", "stop listening"]:
                        self.set_state("IDLE")
                        continue
                    
                    self.set_state("THINKING", transcript=command)
                    if self.on_command_callback:
                        self.on_command_callback(command)
                    else:
                        self.handle_command_mock(command)
                else:
                    self.set_state("IDLE")
                    
            elif self.state in ["THINKING", "ACTING", "SPEAKING"]:
                # State managed by external callbacks, just sleep here
                time.sleep(0.1)

    def handle_command_mock(self, command):
        """Mock handler for CLI testing."""
        time.sleep(1) # Thinking...
        self.set_state("SPEAKING")
        self.tts.speak(f"Echoing: {command}")
        self.last_interaction_time = time.time()
        self.set_state("IDLE")
        
    async def speak(self, text, suppress_sync=False):
        """External call to speak text and return to idle/listening."""
        self.set_state("SPEAKING")
        self.tts.speak(text)
        self.last_interaction_time = time.time()
        self.set_state("IDLE")

    def set_busy(self, is_busy: bool):
        if is_busy:
            self.set_state("ACTING")
        else:
            self.set_state("IDLE")

    async def acknowledge(self):
        self.set_state("THINKING")
        # Could play a short tone, for now just state change
        await __import__("asyncio").sleep(0.1)
