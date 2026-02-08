import sys
import logging
import json
import queue

try:
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
except ImportError:
    sd = None
    Model = None
    KaldiRecognizer = None

class SpeechToText:
    def __init__(self, model_path="voice_models/vosk-model-small-en-us-0.15"):
        self.logger = logging.getLogger("STT")
        self.model_path = model_path
        self.q = queue.Queue()
        self.model = None
        
        if not Model:
            self.logger.error("Vosk/SoundDevice not installed. STT will not function.")
            return

        try:
            # We assume the same model is used for Wake Word and STT for simplicity, 
            # or a larger model for STT. For now, sharing the path.
            self.model = Model(model_path)
            self.logger.info(f"STT Model loaded from {model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load STT model: {e}")

    def _callback(self, indata, frames, time, status):
        """Callback for sounddevice stream."""
        if status:
            print(status, file=sys.stderr) # type: ignore
        self.q.put(bytes(indata))

    def listen(self, timeout=10, on_partial=None):
        """
        Listens for a command. Returns text string.
        
        Args:
            timeout: Maximum listen time.
            on_partial: Optional callback for real-time partial results.
        """
        if not self.model or not sd:
            self.logger.error("STT engine not available.")
            return ""

        self.logger.info("Listening for command...")
        
        # Clear queue
        with self.q.mutex:
            self.q.queue.clear()
            
        text = ""
        
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                   channels=1, callback=self._callback):
                
                rec = KaldiRecognizer(self.model, 16000)
                
                import time
                start_time = time.time()
                
                while (time.time() - start_time) < timeout:
                    try:
                        data = self.q.get(timeout=0.1)
                        if rec.AcceptWaveform(data):
                            result = json.loads(rec.Result())
                            res_text = result.get('text', '')
                            if res_text:
                                text = res_text
                                # Final result received
                                break
                        else:
                            # Handle partial results
                            if on_partial:
                                partial = json.loads(rec.PartialResult())
                                partial_text = partial.get('partial', '')
                                if partial_text:
                                    on_partial(partial_text)
                                    
                    except queue.Empty:
                        continue
                        
                if not text:
                    # check final partial
                    partial = json.loads(rec.PartialResult())
                    text = partial.get('partial', '')

                self.logger.info(f"Heard: {text}")
                return text

        except Exception as e:
            self.logger.error(f"STT Error: {e}")
            return ""

# Alias for compatibility
SpeechRecognizer = SpeechToText
