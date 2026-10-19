"""
Audio Stream Capture

Captures 16 kHz mono microphone audio using sounddevice.
Provides a ring buffer and computes RMS level for the UI sphere.
"""
import logging
import queue
import math
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = logging.getLogger("AudioStream")

class AudioStream:
    def __init__(self, sample_rate=16000, block_size=8000):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.q = queue.Queue()
        self.running = False
        self.stream = None
        self.current_rms = 0.0

    def _callback(self, indata, frames, time, status):
        if status:
            logger.debug(f"Stream status: {status}")
        
        # Calculate RMS level
        if frames > 0:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            rms = math.sqrt(np.mean(np.square(audio_data.astype(np.float32))))
            # Normalize RMS to 0.0 - 1.0 (max int16 is 32767)
            self.current_rms = min(rms / 32767.0, 1.0)
        
        self.q.put(bytes(indata))

    def start(self):
        if not sd:
            logger.error("sounddevice not installed. Audio capture will not function.")
            return False

        if self.running:
            return True

        try:
            self.stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype='int16',
                channels=1,
                callback=self._callback
            )
            self.stream.start()
            self.running = True
            logger.info("Audio stream started.")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.running = False
            return False

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        logger.info("Audio stream stopped.")

    def get_audio_block(self, timeout=None):
        """Get the next block of audio data from the queue."""
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_buffer(self):
        """Clear all pending audio data in the queue."""
        with self.q.mutex:
            self.q.queue.clear()

    def get_rms(self):
        """Get current audio level."""
        return self.current_rms
