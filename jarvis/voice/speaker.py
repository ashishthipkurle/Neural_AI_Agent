"""
INDRA Speaker — Async non-blocking narration queue.
Executor pushes narration lines here while simultaneously continuing to execute steps.
INDRA speaks and acts at the same time.
"""

import queue
import threading
import io
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("Speaker")

try:
    import pygame
    pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
    HAS_PYGAME = True
    logger.info("Pygame mixer initialized (24kHz, 16-bit, mono)")
except Exception as e:
    HAS_PYGAME = False
    logger.warning(f"Pygame mixer unavailable: {e}")


class Speaker:
    """
    Async audio playback queue. Non-blocking — callers enqueue text and
    return immediately. A daemon thread consumes the queue and plays audio.
    """

    def __init__(self, tts):
        """
        Args:
            tts: A voice.tts.TTS instance for text-to-speech conversion.
        """
        self.tts = tts
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._current_playing = False
        self._thread = None

    def enqueue(self, text: str, priority: bool = False):
        """
        Add text to speech queue. NON-BLOCKING — returns immediately.
        
        Args:
            text: Text to speak
            priority: If True, jumps to front of queue (e.g. error messages)
        """
        if not text or not text.strip():
            return

        if priority:
            # Insert at front of queue AND increment the unfinished counter
            with self._queue.mutex:
                self._queue.queue.insert(0, text)
                self._queue.unfinished_tasks += 1
                self._queue.not_empty.notify()
        else:
            self._queue.put(text)

        logger.debug(f"Queued {'(priority) ' if priority else ''}speech: {text[:60]}...")

    def _playback_worker(self):
        """Runs in daemon thread. Consumes queue and plays audio sequentially."""
        logger.info("Speaker playback worker started")
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.1)
                self._current_playing = True

                try:
                    audio_bytes = self.tts.synthesise(text)
                    if audio_bytes:
                        self._play_audio(audio_bytes)
                    else:
                        logger.warning(f"TTS returned empty audio for: {text[:40]}...")
                except Exception as e:
                    logger.error(f"TTS/playback error: {e}")

                self._current_playing = False
                try:
                    self._queue.task_done()
                except ValueError:
                    pass  # Ignore if task_done called too many times

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Speaker worker error: {e}")
                self._current_playing = False

        logger.info("Speaker playback worker stopped")

    def _play_audio(self, audio_bytes: bytes):
        """Play audio bytes through pygame mixer."""
        if not HAS_PYGAME or not audio_bytes:
            return

        try:
            buf = io.BytesIO(audio_bytes)
            pygame.mixer.music.load(buf)
            pygame.mixer.music.play()

            # Wait for playback to finish, but check stop event
            while pygame.mixer.music.get_busy():
                if self._stop_event.is_set():
                    pygame.mixer.music.stop()
                    return
                time.sleep(0.05)

        except Exception as e:
            logger.error(f"Audio playback error: {e}")

    def stop_immediately(self):
        """Called by F9 emergency stop. Clears queue AND stops current playback."""
        # Clear the queue
        with self._queue.mutex:
            self._queue.queue.clear()

        # Stop current audio
        if HAS_PYGAME:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

        self._current_playing = False
        logger.info("Speaker: emergency stop — queue cleared, audio stopped")

    def start(self):
        """Start the playback worker thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._playback_worker,
            daemon=True,
            name="indra-speaker"
        )
        self._thread.start()
        logger.info("Speaker started")

    def stop(self):
        """Graceful shutdown."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Speaker stopped")

    @property
    def is_speaking(self) -> bool:
        """Check if audio is currently playing."""
        return self._current_playing

    @property
    def queue_size(self) -> int:
        """Number of items waiting in the queue."""
        return self._queue.qsize()
