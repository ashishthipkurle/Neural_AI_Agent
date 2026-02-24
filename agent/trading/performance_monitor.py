"""
FAISS Performance & Memory Monitor.

Architecture:
    - Tracks RSS (Resident Set Size) memory of the Python process hosting FAISS.
    - Estimates FAISS index memory overhead.
    - Defines absolute `MAX_FAISS_RAM_GB`.
    - Triggers global `Hard Fail-Safe` if the envelope is breached to prevent OS OOM kills.
"""
import os
import psutil
import logging
from typing import Dict, Any

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class PerformanceMonitor:
    """
    Enforces rigid hardware envelopes on the quantitative engine.
    """

    def __init__(self, max_faiss_ram_gb: float = 64.0) -> None:
        self.logger = logging.getLogger("PerformanceMonitor")
        self.max_ram_gb = max_faiss_ram_gb
        self.process = psutil.Process(os.getpid())

    def get_memory_usage_gb(self) -> float:
        """Returns the RSS memory of the current process in Gigabytes."""
        try:
            mem_info = self.process.memory_info()
            return mem_info.rss / (1024 ** 3)
        except Exception as e:
            self.logger.error(f"Failed to read memory usage: {e}")
            return 0.0

    def get_cpu_percent(self) -> float:
        """Returns CPU utilization of the process."""
        try:
            return self.process.cpu_percent(interval=None)
        except Exception:
            return 0.0

    def estimate_index_size_gb(self, num_vectors: int, dimension: int = 15) -> float:
        """
        Rough heuristic for FAISS IndexIVFFlat memory size.
        For IndexFlatIP, each vector is `dimension * 4 bytes`.
        For IVF, add ~10-20% overhead for lists and centroids.
        """
        bytes_per_vec = dimension * 4 * 1.2
        return (num_vectors * bytes_per_vec) / (1024 ** 3)

    def enforce_memory_budget(self) -> Dict[str, Any]:
        """
        Checks current usage against budget.
        Returns state and a boolean `breached` flag.
        """
        current_gb = self.get_memory_usage_gb()
        cpu_pct = self.get_cpu_percent()
        
        breached = current_gb > self.max_ram_gb
        
        if breached:
            self.logger.critical(
                f"MEMORY BUDGET BREACHED! "
                f"Usage: {current_gb:.2f}GB > Budget: {self.max_ram_gb:.2f}GB. "
                f"Initiating Hard Fail-Safe."
            )
            
        return {
            "breached": breached,
            "current_ram_gb": round(current_gb, 2),
            "max_ram_gb": self.max_ram_gb,
            "cpu_percent": round(cpu_pct, 1)
        }
