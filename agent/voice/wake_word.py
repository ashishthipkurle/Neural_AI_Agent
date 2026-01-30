
import logging
import json
import sys
import queue
import time

try:
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
except ImportError:
    sd = None
    Model = None
    KaldiRecognizer = None

class WakeWordEngine:
    def __init__(self, model_path="voice_models/vosk-model-small-en-us-0.15", wake_words=None):
        self.logger = logging.getLogger("WakeWordEngine")
        self.wake_words = wake_words or ["hey jarvis", "hey nova"]
        self.q = queue.Queue()
        self.running = False
        self.model = None # Init to None to avoid AttributeError
        
        if not Model:
            self.logger.error("Vosk/SoundDevice not installed. Wake Word will not function.")
            return

        try:
            self.logger.info(f"Loading Vosk Model from {model_path}...")
            # Note: User must provide the model path or we use default
            self.model = Model(model_path)
            self.logger.info("Vosk Model loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load Vosk model: {e}")
            self.model = None

    def _callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status, file=sys.stderr)
        self.q.put(bytes(indata))

    def wait_for_wake_word(self, on_partial=None, is_muted_callback=None, should_pause_callback=None):
        """
        Blocking method that listens until a wake word is detected.
        
        Args:
            on_partial: Optional callback for real-time partial results.
            is_muted_callback: Optional function returning bool (True if muted).
        """
        if not self.model or not sd:
            self.logger.error("Wake Word engine not available.")
            return None

        self.running = True
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                   channels=1, callback=self._callback):
                self.logger.info("Listening for Wake Word...")
                rec = KaldiRecognizer(self.model, 16000)
                
                while self.running:
                    # Check pause state (e.g. agent is speaking/busy)
                    if should_pause_callback and should_pause_callback():
                        # Drain queue to discard audio captured while busy
                        while not self.q.empty():
                            self.q.get()
                        time.sleep(0.1) # Prevent CPU spin
                        continue

                    # Check mute state inside the loop
                    if is_muted_callback and is_muted_callback():
                        # Clear any buffered audio effectively ignoring input
                        while not self.q.empty():
                            self.q.get()
                        time.sleep(0.1)
                        continue

                    data = self.q.get()
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get('text', '').lower()
                        if text:
                            # Log everything for debug tuning
                            self.logger.info(f"VOSK HEARD: '{text}'")
                            
                        if any(ww in text for ww in self.wake_words):
                            self.logger.info(f"Wake Word Detected: {text}")
                            return text
                    else:
                        # Partial result
                        if on_partial:
                            partial = json.loads(rec.PartialResult())
                            partial_text = partial.get('partial', '')
                            if partial_text:
                                on_partial(partial_text)
                        
        except Exception as e:
            self.logger.error(f"Error during wake word listening: {e}")
            return None
            
    def stop(self):
        self.running = False
