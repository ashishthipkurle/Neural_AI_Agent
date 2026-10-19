"""
INDRA Latency Tracker -- Measures and logs per-stage timing.
Warns when targets are exceeded. Helps optimise performance over time.
"""

import time
import contextlib
from utils.logger import get_logger

logger = get_logger("Latency")


class LatencyTracker:
    def __init__(self):
        self.timings = {}

    @contextlib.contextmanager
    def measure(self, stage: str, target_ms: float = None):
        """
        Context manager that measures execution time of a block.
        
        Usage:
            with latency.measure("stt", target_ms=TARGET_STT_MS):
                text = whisper.transcribe(audio)
        """
        start = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.timings[stage] = elapsed_ms

        if target_ms is not None:
            status = "OK" if elapsed_ms <= target_ms else "SLOW"
            logger.info(f"{stage}: {elapsed_ms:.0f}ms (target: {target_ms:.0f}ms) {status}")

            if elapsed_ms > target_ms * 1.5:
                logger.warning(f"{stage} exceeded 1.5x target: {elapsed_ms:.0f}ms")
        else:
            logger.info(f"{stage}: {elapsed_ms:.0f}ms")

    def report_round_trip(self):
        """Call after full voice interaction to log total round-trip."""
        stages = ["wake_word", "stt", "llm", "tts_first_sentence"]
        total = sum(self.timings.get(s, 0) for s in stages)
        present = [s for s in stages if s in self.timings]
        breakdown = ", ".join(f"{s}={self.timings[s]:.0f}ms" for s in present)
        
        from config import TARGET_TOTAL_MS
        status = "OK" if total <= TARGET_TOTAL_MS else "SLOW"
        logger.info(f"Round-trip: {total:.0f}ms (target: {TARGET_TOTAL_MS}ms) {status} [{breakdown}]")
        self.timings = {}

    def get_last(self, stage: str) -> float:
        """Get the last measured time for a stage in ms."""
        return self.timings.get(stage, 0.0)
