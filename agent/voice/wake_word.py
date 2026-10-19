"""
Wake Word Engine

VAD-gated faster-whisper-tiny with fuzzy match on 'hey neural'/'hello neural'.
"""
import logging
import time
import io
import wave
import numpy as np

try:
    import webrtcvad
except ImportError:
    webrtcvad = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

logger = logging.getLogger("WakeWord")

class WakeWordEngine:
    def __init__(self, wake_words=None, device="cuda"):
        self.wake_words = wake_words or ["hey neural", "hello neural"]
        self.device = device
        
        if webrtcvad:
            self.vad = webrtcvad.Vad(2)  # Aggressiveness 0-3
        else:
            self.vad = None
            logger.warning("webrtcvad not installed. Wake Word will be less efficient.")
        
        if not WhisperModel:
            logger.error("faster-whisper not installed. Wake Word will not function.")
            self.model = None
            return

        logger.info(f"Loading faster-whisper (tiny.en) on {device} for wake word...")
        self.model = WhisperModel("tiny.en", device=device, compute_type="float16" if device=="cuda" else "int8")
        logger.info("faster-whisper wake word model loaded.")

    def fuzzy_match(self, text):
        t = text.lower().replace(".", "").replace(",", "").replace("!", "").replace("?", "").strip()
        if not t:
            return False
            
        for ww in self.wake_words:
            if ww in t:
                return True
        # Basic fuzzy logic for Whisper mishears
        if "hey" in t and "neural" in t: return True
        if "hello" in t and "neural" in t: return True
        if "hey" in t and "nero" in t: return True
        if "new roll" in t: return True
        if "hey ne" in t: return True
        return False

    def listen_for_wake_word(self, audio_stream, should_pause_callback=None):
        if not self.model or not self.vad:
            return None

        audio_stream.start()
        audio_stream.clear_buffer()

        frame_duration_ms = 30
        sample_rate = 16000
        frame_size = int(sample_rate * (frame_duration_ms / 1000.0) * 2) # bytes (16-bit)

        buffer = b''
        speech_frames = []
        is_speaking = False
        silence_counter = 0
        silence_threshold = 20 # approx 0.6s of silence
        
        # Pre-roll buffer to catch the beginning of words
        pre_roll = []
        pre_roll_max = 10 # 300ms

        logger.info("Listening for Wake Word...")

        while True:
            if should_pause_callback and should_pause_callback():
                audio_stream.clear_buffer()
                time.sleep(0.1)
                buffer = b''
                speech_frames = []
                is_speaking = False
                continue
                
            block = audio_stream.get_audio_block(timeout=0.1)
            if block is None:
                continue

            buffer += block
            
            while len(buffer) >= frame_size:
                frame = buffer[:frame_size]
                buffer = buffer[frame_size:]
                
                try:
                    is_speech = self.vad.is_speech(frame, sample_rate)
                except Exception:
                    is_speech = False
                    
                if is_speech:
                    silence_counter = 0
                    if not is_speaking:
                        is_speaking = True
                        speech_frames.extend(pre_roll)
                    if is_speaking:
                        speech_frames.append(frame)
                else:
                    if is_speaking:
                        speech_frames.append(frame)
                        silence_counter += 1
                        if silence_counter > silence_threshold:
                            # End of utterance, transcribe
                            audio_data = b''.join(speech_frames)
                            
                            is_speaking = False
                            speech_frames = []
                            silence_counter = 0
                            pre_roll = []
                            
                            # Transcribe if long enough
                            if len(audio_data) > sample_rate * 2 * 0.4: # at least 0.4 seconds
                                text = self._transcribe(audio_data)
                                if text:
                                    if self.fuzzy_match(text):
                                        logger.info(f"Wake Word Detected: {text}")
                                        return text
                    else:
                        pre_roll.append(frame)
                        if len(pre_roll) > pre_roll_max:
                            pre_roll.pop(0)
                                    
    def _transcribe(self, audio_bytes):
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
            
        wav_io.seek(0)
        
        try:
            segments, info = self.model.transcribe(wav_io, beam_size=1)
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
