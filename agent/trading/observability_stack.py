"""
Observability Stack.

Architecture:
    - Prometheus metrics exporter for FAISS similarity engine.
    - Explicit Service-Level Objective (SLO) definitions.
    - Preemptive alerting triggers when mathematical SLOs are endangered.
"""
import time
import logging
from typing import Dict, Any

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class ObservabilityStack:
    """
    Centralizes all metrics tracking and SLO definitions.
    Instantiates Prometheus exporters if available.
    """

    # ── Explicit SLO Definitions ───────────────────────────────
    SLO_MAX_P99_LATENCY_MS = 100.0
    SLO_MAX_INDEX_STALENESS_HOURS = 24.0
    SLO_MAX_DRIFT_VARIANCE = 0.05
    
    def __init__(self, port: int = 9090) -> None:
        self.logger = logging.getLogger("ObservabilityStack")
        self.port = port
        
        self.metrics_enabled = PROMETHEUS_AVAILABLE
        if self.metrics_enabled:
            self._init_prometheus_metrics()
            try:
                start_http_server(self.port)
                self.logger.info(f"Prometheus metrics exposed on port {self.port}")
            except Exception as e:
                self.logger.error(f"Failed to start Prometheus server: {e}")
                self.metrics_enabled = False
        else:
            self.logger.warning("prometheus_client not installed. Missing observability layer.")

    def _init_prometheus_metrics(self) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
            
        # Counters
        self.query_count = Counter('faiss_queries_total', 'Total similarity queries executed', ['segment'])
        self.signal_count = Counter('signals_emitted_total', 'Total trading signals generated', ['direction', 'regime'])
        
        # Histograms
        self.query_latency = Histogram(
            'faiss_query_latency_ms', 
            'Latency of FAISS similarity queries', 
            ['segment'],
            buckets=[10, 25, 50, 75, 100, 250, 500, 1000]
        )
        
        # Gauges (State)
        self.index_size = Gauge('faiss_index_vectors', 'Number of vectors in FAISS index', ['segment'])
        self.index_age_hours = Gauge('faiss_index_age_hours', 'Age of the active FAISS index', ['segment'])
        self.drift_severity = Gauge('model_drift_severity', 'Statistical drift severity vs Frozen Baseline', ['segment'])
        self.shard_health = Gauge('faiss_shard_health_status', '1 if healthy, 0 if offline', ['node_id'])
        self.memory_usage_gb = Gauge('faiss_memory_usage_gb', 'FAISS RAM footprint', ['node_id'])

    # ── Usage Hooks ──────────────────────────────────────────

    def record_query_latency(self, segment: str, latency_ms: float) -> None:
        """Track query speed against the p99 latency SLO."""
        if self.metrics_enabled:
            self.query_count.labels(segment=segment).inc()
            self.query_latency.labels(segment=segment).observe(latency_ms)
            
        if latency_ms > self.SLO_MAX_P99_LATENCY_MS:
            self.logger.warning(f"SLO VIOLATION: Query latency {latency_ms:.1f}ms exceeds {self.SLO_MAX_P99_LATENCY_MS}ms budget for {segment}.")

    def update_index_stats(self, segment: str, num_vectors: int, age_hours: float, drift: float) -> None:
        """Track index staleness and drift against SLOs."""
        if self.metrics_enabled:
            self.index_size.labels(segment=segment).set(num_vectors)
            self.index_age_hours.labels(segment=segment).set(age_hours)
            self.drift_severity.labels(segment=segment).set(drift)
            
        if age_hours > self.SLO_MAX_INDEX_STALENESS_HOURS:
            self.logger.warning(f"SLO ENDANGERED: Index {segment} age ({age_hours:.1f}h) exceeds target.")
            
        if drift > self.SLO_MAX_DRIFT_VARIANCE:
            self.logger.warning(f"SLO ENDANGERED: Drift {drift:.3f} exceeds bounds for {segment}.")

    def update_node_health(self, node_id: str, is_healthy: bool, mem_gb: float) -> None:
        """Track distributed node health and RAM."""
        if self.metrics_enabled:
            self.shard_health.labels(node_id=node_id).set(1.0 if is_healthy else 0.0)
            self.memory_usage_gb.labels(node_id=node_id).set(mem_gb)

    def record_signal(self, direction: str, regime: str) -> None:
        if self.metrics_enabled:
            self.signal_count.labels(direction=direction, regime=regime).inc()
