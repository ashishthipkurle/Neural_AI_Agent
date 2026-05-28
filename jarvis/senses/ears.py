"""
INDRA Ears — Microphone input → VAD → faster-whisper → text.
Captures speech from the microphone, uses Voice Activity Detection to find
speech boundaries, then transcribes using faster-whisper.
"""

import threading
import time
import io
import wave
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import WHISPER_MODEL, WHISPER_LANGUAGE, TARGET_STT_MS
from utils.logger import get_logger

logger = get_logger("Ears")

# ── PyAudio ──
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.error("pyaudio not installed — microphone unavailable")

# ── WebRTC VAD ──
try:
    import webrtcvad
    HAS_VAD = True
except ImportError:
    HAS_VAD = False
    logger.warning("webrtcvad not installed — using energy-based VAD fallback")

# ── faster-whisper ──
try:
    from faster_whisper import WhisperModel
    _whisper_model = WhisperModel(
        WHISPER_MODEL,
        device="cpu",
        compute_type="int8"
    )
    HAS_WHISPER = True
    logger.info(f"faster-whisper loaded (model: {WHISPER_MODEL})")
except ImportError:
    HAS_WHISPER = False
    logger.error("faster-whisper not installed — speech-to-text unavailable")
except Exception as e:
    HAS_WHISPER = False
    logger.error(f"Whisper init failed: {e}")

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30  # VAD frame size: 10, 20, or 30 ms
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # samples per chunk
FORMAT = pyaudio.paInt16 if HAS_PYAUDIO else None

# VAD settings
SPEECH_PAD_MS = 300  # padding after speech ends before cutting
MIN_SPEECH_MS = 250  # minimum speech duration to consider valid
MAX_SPEECH_S = 15    # maximum recording duration in seconds
SILENCE_THRESHOLD_MS = 1000  # silence duration to end recording


class Ears:
    """
    Microphone listener with VAD-based speech detection and Whisper transcription.
    """

    def __init__(self):
        self._audio = None
        if HAS_PYAUDIO:
            self._audio = pyaudio.PyAudio()
        
        if HAS_VAD:
            self._vad = webrtcvad.Vad(2)  # aggressiveness 0-3 (2 = balanced, filters background noise)
        else:
            self._vad = None

    def listen_once(self) -> str:
        """
        Listen for a single utterance from the microphone.
        Uses VAD to detect start/end of speech, then transcribes with Whisper.
        
        Returns: Transcribed text, or empty string if nothing detected.
        """
        if not HAS_PYAUDIO or not HAS_WHISPER:
            logger.error("Audio/Whisper not available")
            return ""

        audio_data = self._record_utterance()
        if not audio_data:
            return ""

        return self._transcribe(audio_data)

    def _record_utterance(self) -> bytes | None:
        """Record audio from mic until speech ends (detected by VAD)."""
        try:
            stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
        except Exception as e:
            logger.error(f"Failed to open microphone: {e}")
            return None

        logger.debug("Listening for speech...")

        frames = []
        speech_started = False
        silence_chunks = 0
        max_chunks = int(MAX_SPEECH_S * 1000 / CHUNK_DURATION_MS)
        silence_limit = int(SILENCE_THRESHOLD_MS / CHUNK_DURATION_MS)

        try:
            for _ in range(max_chunks):
                try:
                    chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                except Exception:
                    continue

                is_speech = self._is_speech(chunk)

                if is_speech:
                    speech_started = True
                    silence_chunks = 0
                    frames.append(chunk)
                elif speech_started:
                    silence_chunks += 1
                    frames.append(chunk)  # Include some silence padding
                    if silence_chunks >= silence_limit:
                        break  # End of utterance
        finally:
            stream.stop_stream()
            stream.close()

        if not speech_started or not frames:
            logger.debug("No speech detected")
            return None

        # Check minimum duration
        duration_ms = len(frames) * CHUNK_DURATION_MS
        if duration_ms < MIN_SPEECH_MS:
            logger.debug(f"Speech too short ({duration_ms}ms), ignoring")
            return None

        logger.debug(f"Captured {duration_ms}ms of speech ({len(frames)} chunks)")
        return b"".join(frames)

    def _is_speech(self, chunk: bytes) -> bool:
        """Detect if an audio chunk contains speech."""
        if self._vad:
            try:
                return self._vad.is_speech(chunk, SAMPLE_RATE)
            except Exception:
                pass

        # Fallback: energy-based detection
        audio_array = np.frombuffer(chunk, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_array.astype(float) ** 2))
        return energy > 300  # RMS threshold (lowered from 500 to catch quieter speech)

    def _amplify_audio(self, audio_bytes: bytes, gain: float = 2.0) -> bytes:
        """Boost quiet audio before sending to Whisper."""
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_array *= gain
        # Clip to prevent overflow
        audio_array = np.clip(audio_array, -32768, 32767)
        return audio_array.astype(np.int16).tobytes()

    def _transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes using faster-whisper."""
        if not HAS_WHISPER:
            return ""

        t_start = time.perf_counter()

        # Convert raw PCM to WAV for whisper
        # First amplify quiet audio
        amplified = self._amplify_audio(audio_bytes, gain=2.0)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(amplified)
        wav_buf.seek(0)

        try:
            segments, info = _whisper_model.transcribe(
                wav_buf,
                language=WHISPER_LANGUAGE,  # None = auto-detect
                beam_size=1,               # Faster with beam_size=1
                vad_filter=True,           # Built-in VAD for cleaner results
                word_timestamps=False
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()

            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.info(
                f"STT: '{text[:60]}...' in {elapsed_ms:.0f}ms "
                f"(target: {TARGET_STT_MS}ms, lang: {info.language})"
            )

            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def cleanup(self):
        """Release audio resources."""
        if self._audio:
            self._audio.terminate()
            logger.info("Audio resources released")
