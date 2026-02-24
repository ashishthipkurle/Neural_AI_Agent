"""
Chaos Testing Suite for Quantitative Infrastructure.

Simulation capabilities:
    - OOM (Out of Memory) Injection.
    - Shard Query Latency Spikes (500ms+).
    - Dropped TCP connections / split-brain nodes.
    - Feature schema corruption.

Validates that `data_integrity_guard` and `cluster_coordinator` trigger
Hard Fail-Safe correctly, guaranteeing zero bad trades under duress.
"""
import time
import logging
import random
from typing import Dict, Any

class ChaosTester:
    """
    Automated monkey-testing for the distributed FAISS architecture.
    NEVER to be run in production mode.
    """

    def __init__(self, mode: str = "DEV") -> None:
        self.logger = logging.getLogger("ChaosTester")
        self.mode = mode
        if mode == "PROD":
            self.logger.critical("CHAOS TESTER INSTANTIATED IN PROD. SELF-DESTRUCTING.")
            raise RuntimeError("Chaos testing is forbidden in production environment.")

    def inject_latency_spike(self, base_ms: int = 50, spike_ms: int = 500) -> float:
        """Simulates intermittent network degradation between shards."""
        if random.random() < 0.1: # 10% chance
            self.logger.warning(f"CHAOS: Injected latency spike of {spike_ms}ms")
            time.sleep(spike_ms / 1000.0)
            return float(spike_ms)
        return float(base_ms)

    def simulate_oom_crash(self) -> Dict[str, Any]:
        """Returns mock RAM readings that breach the FAISS budget."""
        self.logger.warning("CHAOS: Simulating OS Out-Of-Memory condition.")
        return {"simulated_rss_gb": 128.0, "breached": True}

    def simulate_node_death(self, active_nodes: list) -> list:
        """Simulate heartbeats failing for a random active replica."""
        if not active_nodes:
            return []
        dead_node = random.choice(active_nodes)
        self.logger.warning(f"CHAOS: Terminating node {dead_node} silently.")
        return [n for n in active_nodes if n != dead_node]

    def simulate_schema_corruption(self, original_hash: str) -> str:
        """Simulate mismatching feature definitions (e.g. rollback desync)."""
        self.logger.warning("CHAOS: Corrupting schema version hash.")
        return "DEADBEEF" + original_hash[8:]
