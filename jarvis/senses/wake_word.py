"""
INDRA Wake Word Detector — "Hey INDRA" always-on local detection.

Uses a dual-strategy approach:
  1. Primary: Continuous speech-to-text with faster-whisper, checking for "hey indra"
     in the transcript. This allows ANY custom wake phrase without retraining.
  2. Fallback: Simple energy-based voice activity detection if Whisper unavailable.

The detector runs in a daemon thread with low CPU overhead using VAD-gated
transcription — audio is only sent to Whisper when voice activity is detected.
"""

import threading
import time
import numpy as np
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import WAKE_WORD, WAKE_WORD_SENSITIVITY, CONVERSATION_TIMEOUT
from utils.logger import get_logger

logger = get_logger("WakeWord")

# ── PyAudio ──
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.error("pyaudio not installed — wake word detection unavailable")

# ── faster-whisper (for keyword-in-transcript wake word) ──
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
    logger.info("faster-whisper loaded for wake word detection")
except ImportError:
    HAS_WHISPER = False
    logger.warning("faster-whisper not installed — using energy-only fallback")

# ── webrtcvad (for voice activity detection gating) ──
try:
    import webrtcvad
    HAS_VAD = True
except ImportError:
    HAS_VAD = False
    logger.info("webrtcvad not installed — using energy-based VAD")


SAMPLE_RATE = 16000
# 2-second rolling buffer for wake word detection
WAKE_BUFFER_SECONDS = 2
WAKE_BUFFER_SAMPLES = SAMPLE_RATE * WAKE_BUFFER_SECONDS
# VAD frame size: 30ms (480 samples at 16kHz)
VAD_FRAME_MS = 30
VAD_FRAME_SAMPLES = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)
# How many VAD frames of speech trigger a transcription check
VAD_SPEECH_FRAMES_THRESHOLD = 6  # ~180ms of speech
# Cooldown between transcription attempts (to avoid hammering CPU)
TRANSCRIPTION_COOLDOWN = 0.8


class WakeWordDetector:
    """
    Always-on wake word detector. Runs in daemon thread.
    When "Hey INDRA" is detected, calls the on_wake_callback.

    If INDRA is mid-conversation (within CONVERSATION_TIMEOUT seconds),
    the wake word requirement is skipped — Ashish can speak freely.

    Detection strategy:
      - Continuously capture audio in 30ms VAD frames
      - When voice activity is detected (enough consecutive speech frames),
        transcribe the rolling 2-second buffer using faster-whisper (tiny model)
      - Check if the transcription contains the wake phrase
      - If match → trigger callback
    """

    def __init__(self, on_wake_callback):
        """
        Args:
            on_wake_callback: Function to call when wake word detected.
        """
        self.on_wake = on_wake_callback
        self._running = False
        self._thread = None
        self._last_interaction_time = 0

        # Wake phrase variants for fuzzy matching
        self._wake_phrases = self._build_wake_phrases(WAKE_WORD)

        # VAD
        self._vad = None
        if HAS_VAD:
            try:
                self._vad = webrtcvad.Vad(2)  # Aggressiveness 2 (moderate)
                logger.info("WebRTC VAD initialized (aggressiveness=2)")
            except Exception as e:
                logger.warning(f"VAD init failed: {e}")

        # Whisper model (tiny for speed — only needs to recognize a short phrase)
        self._whisper_model = None
        if HAS_WHISPER:
            try:
                self._whisper_model = WhisperModel(
                    "tiny",
                    device="cpu",
                    compute_type="int8"
                )
                logger.info("Whisper 'tiny' model loaded for wake word detection")
            except Exception as e:
                logger.warning(f"Failed to load Whisper model: {e}")

    def _build_wake_phrases(self, wake_word: str) -> list:
        """
        Build a list of acceptable wake phrase variants for fuzzy matching.
        This handles common Whisper mishearings of 'indra'.
        """
        base = wake_word.lower().strip()
        phrases = [base]

        # Common Whisper mishearings / phonetic variants
        if "indra" in base:
            phrases.extend([
                "hey indra",
                "he indra",
                "hey indro",
                "hey indre",
                "hey indri",
                "hey andra",
                "hey endra",
                "hey hindra",
                "a indra",
                "heyindra",
                "hay indra",
                "hey in dra",
                "hey india",    # common mishearing
                "hey intra",    # common mishearing
                "hey indras",
                "hey indrah",
            ])

        # Also allow just "indra" spoken alone
        phrases.append("indra")

        # Deduplicate
        return list(set(phrases))

    def start(self):
        """Start detection in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="indra-wakeword"
        )
        self._thread.start()
        logger.info(f"Wake word detector started (phrase: '{WAKE_WORD}')")

    def stop(self):
        """Stop detection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Wake word detector stopped")

    def mark_interaction(self):
        """Mark that an interaction just happened (resets conversation timeout)."""
        self._last_interaction_time = time.time()

    def is_in_conversation(self) -> bool:
        """Check if we're within the conversation timeout window."""
        return (time.time() - self._last_interaction_time) < CONVERSATION_TIMEOUT

    def _detection_loop(self):
        """Main detection loop running in daemon thread."""
        if not HAS_PYAUDIO:
            logger.error("Cannot start wake word detection — pyaudio unavailable")
            return

        audio = pyaudio.PyAudio()

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=VAD_FRAME_SAMPLES
            )
        except Exception as e:
            logger.error(f"Failed to open microphone for wake word: {e}")
            audio.terminate()
            return

        logger.info("Listening for wake word...")

        # Rolling audio buffer (2 seconds)
        audio_buffer = np.zeros(WAKE_BUFFER_SAMPLES, dtype=np.int16)
        speech_frame_count = 0
        last_transcription_time = 0

        try:
            while self._running:
                try:
                    raw = stream.read(VAD_FRAME_SAMPLES, exception_on_overflow=False)
                except Exception:
                    time.sleep(0.01)
                    continue

                frame = np.frombuffer(raw, dtype=np.int16)

                # Roll the buffer and append new frame
                audio_buffer = np.roll(audio_buffer, -len(frame))
                audio_buffer[-len(frame):] = frame

                # Check for voice activity
                is_speech = False

                if self._vad:
                    try:
                        is_speech = self._vad.is_speech(raw, SAMPLE_RATE)
                    except Exception:
                        # Fallback to energy
                        energy = np.sqrt(np.mean(frame.astype(float) ** 2))
                        is_speech = energy > 1500
                else:
                    energy = np.sqrt(np.mean(frame.astype(float) ** 2))
                    is_speech = energy > 1500

                if is_speech:
                    speech_frame_count += 1
                else:
                    # Decay speech counter (allow brief pauses)
                    speech_frame_count = max(0, speech_frame_count - 1)

                # When enough speech frames accumulated, try transcription
                now = time.time()
                if (speech_frame_count >= VAD_SPEECH_FRAMES_THRESHOLD
                        and (now - last_transcription_time) > TRANSCRIPTION_COOLDOWN):

                    speech_frame_count = 0
                    last_transcription_time = now

                    if self._whisper_model:
                        detected = self._check_wake_whisper(audio_buffer)
                    else:
                        # No Whisper — just use energy spike as wake trigger
                        detected = True
                        logger.debug("No Whisper model — energy-triggered wake")

                    if detected:
                        self._handle_wake()
                        # Clear buffer after detection to prevent re-triggers
                        audio_buffer = np.zeros(WAKE_BUFFER_SAMPLES, dtype=np.int16)
                        speech_frame_count = 0
                        time.sleep(0.5)  # Debounce

        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    def _check_wake_whisper(self, audio_buffer: np.ndarray) -> bool:
        """
        Transcribe the audio buffer with Whisper tiny and check
        if the transcript contains the wake phrase.
        """
        try:
            # Convert int16 to float32 normalized [-1, 1]
            audio_float = audio_buffer.astype(np.float32) / 32768.0

            segments, info = self._whisper_model.transcribe(
                audio_float,
                beam_size=1,
                language="en",
                vad_filter=False,
                without_timestamps=True,
            )

            transcript = ""
            for seg in segments:
                transcript += seg.text

            transcript = transcript.lower().strip()

            if not transcript:
                return False

            # Check against all wake phrase variants
            for phrase in self._wake_phrases:
                if phrase in transcript:
                    logger.info(
                        f"Wake word detected! Transcript: '{transcript}' "
                        f"matched phrase: '{phrase}'"
                    )
                    return True

            # Log near-misses for debugging (if transcript is short enough to be a wake attempt)
            if len(transcript) < 30:
                logger.debug(f"Wake check (no match): '{transcript}'")

            return False

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return False

    def _handle_wake(self):
        """Handle wake word detection."""
        logger.info("Wake word activated — starting listening")
        self.mark_interaction()

        # Play confirmation chime (short beep)
        try:
            self._play_chime()
        except Exception as e:
            logger.debug(f"Chime failed (non-critical): {e}")

        # Call the callback
        if self.on_wake:
            try:
                self.on_wake()
            except Exception as e:
                logger.error(f"Wake callback error: {e}")

    def _play_chime(self):
        """Play a short confirmation sound."""
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=1)

            # Generate a short beep tone (880Hz, 150ms)
            duration = 0.15
            sample_rate = 24000
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            # Soft sine wave with fade-in/out
            tone = np.sin(2 * np.pi * 880 * t) * 0.3
            fade_samples = int(0.02 * sample_rate)
            tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
            tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)

            pcm = (tone * 32767).astype(np.int16)
            import wave
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())
            buf.seek(0)

            pygame.mixer.music.load(buf)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.01)

        except Exception as e:
            logger.debug(f"Chime generation failed: {e}")
