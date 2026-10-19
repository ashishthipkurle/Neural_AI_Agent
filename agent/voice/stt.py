"""
Speech-To-Text Engine

Uses faster-whisper with VAD-based end-of-speech detection.
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

logger = logging.getLogger("STT")

class SpeechToText:
    def __init__(self, model_size="base.en", device="cuda"):
        self.device = device
        
        if webrtcvad:
            self.vad = webrtcvad.Vad(1)  # Less aggressive for main speech
        else:
            self.vad = None
            logger.warning("webrtcvad not installed. STT will rely purely on timeout.")
        
        if not WhisperModel:
            logger.error("faster-whisper not installed. STT will not function.")
            self.model = None
            return

        logger.info(f"Loading faster-whisper ({model_size}) on {device} for STT...")
        self.model = WhisperModel(model_size, device=device, compute_type="float16" if device=="cuda" else "int8")
        logger.info("STT model loaded.")

    def listen(self, audio_stream, timeout=15):
        """
        Listens for a command and transcribes it.
        Ends on VAD silence threshold or timeout.
        """
        if not self.model or not self.vad:
            return ""

        audio_stream.start()
        audio_stream.clear_buffer()

        frame_duration_ms = 30
        sample_rate = 16000
        frame_size = int(sample_rate * (frame_duration_ms / 1000.0) * 2) # bytes

        buffer = b''
        speech_frames = []
        is_speaking = False
        silence_counter = 0
        silence_threshold = int(1.5 * 1000 / frame_duration_ms) # 1.5s of silence marks end
        
        pre_roll = []
        pre_roll_max = 15

        logger.info("Listening for command...")
        start_time = time.time()

        while (time.time() - start_time) < timeout:
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
                            return self._transcribe(b''.join(speech_frames))
                    else:
                        pre_roll.append(frame)
                        if len(pre_roll) > pre_roll_max:
                            pre_roll.pop(0)
                            
        # If we hit timeout but captured some speech, transcribe it
        if speech_frames:
            return self._transcribe(b''.join(speech_frames))
            
        return ""
                                    
    def _transcribe(self, audio_bytes):
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
            
        wav_io.seek(0)
        
        try:
            segments, info = self.model.transcribe(wav_io, beam_size=5, vad_filter=True)
            text = " ".join([segment.text for segment in segments])
            res = text.strip()
            if res:
                logger.info(f"Heard: {res}")
            return res
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
