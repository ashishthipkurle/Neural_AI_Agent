"""
Correlation Engine.

Architecture:
    - Maintains rolling 30d Pearson correlation matrix of daily returns.
    - Groups highly correlated instruments (r > 0.75) into risk clusters.
    - Limits aggregate exposure to any single cluster to prevent concentration.
"""
import logging
from typing import Dict, List, Set, Any
import math

class CorrelationEngine:
    """
    Prevents deploying signal capital into clustered correlated assets.
    """

    def __init__(self, high_correlation_threshold: float = 0.75) -> None:
        self.logger = logging.getLogger("CorrelationEngine")
        self.threshold = high_correlation_threshold
        
        # instrument_id -> Dict[instrument_id, correlation_coefficient]
        self._correlation_matrix: Dict[int, Dict[int, float]] = {}
        
        # List of sets, where each set is a cluster of highly correlated instrument_ids
        self._risk_clusters: List[Set[int]] = []

    def update_matrix(self, returns_by_instrument: Dict[int, List[float]]) -> None:
        """
        Calculates Pearson correlation matrix.
        Expected: daily returns over rolling 30d window for each active instrument.
        """
        ids = list(returns_by_instrument.keys())
        n = len(ids)
        if n < 2:
            return
            
        # Rebuild matrix
        self._correlation_matrix = {iid: {} for iid in ids}
        
        for i in range(n):
            for j in range(i+1, n):
                id1, id2 = ids[i], ids[j]
                r = self._pearson(returns_by_instrument[id1], returns_by_instrument[id2])
                self._correlation_matrix[id1][id2] = r
                self._correlation_matrix[id2][id1] = r
                
        self._detect_clusters()

    def _detect_clusters(self) -> None:
        """Group instruments with > threshold correlation into clusters."""
        visited = set()
        clusters = []
        
        for id1, corrs in self._correlation_matrix.items():
            if id1 in visited:
                continue
                
            current_cluster = {id1}
            visited.add(id1)
            
            for id2, r in corrs.items():
                if r > self.threshold:
                    current_cluster.add(id2)
                    visited.add(id2)
                    
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
                
        self._risk_clusters = clusters
        self.logger.info(f"Rebuilt correlation matrix. Detected {len(clusters)} high-risk clusters (r > {self.threshold}).")

    def get_cluster_for_instrument(self, instrument_id: int) -> Set[int]:
        """Return the cluster set containing this instrument, if any."""
        for cluster in self._risk_clusters:
            if instrument_id in cluster:
                return cluster
        return {instrument_id} # Trivial cluster of itself

    def enforce_cluster_exposure_limit(
        self, 
        instrument_id: int, 
        proposed_size: float, 
        current_exposures: Dict[int, float], 
        max_cluster_capital: float
    ) -> float:
        """
        Caps the proposed trade size so the entire cluster's aggregate gross
        exposure doesn't exceed the max allowed capital.
        """
        cluster = self.get_cluster_for_instrument(instrument_id)
        
        current_cluster_exposure = sum(abs(current_exposures.get(iid, 0.0)) for iid in cluster)
        
        available_room = max_cluster_capital - current_cluster_exposure
        if available_room <= 0:
            self.logger.warning(f"Cluster exposure limit reached for {instrument_id}. Blocking trade.")
            return 0.0
            
        accepted_size = min(abs(proposed_size), available_room)
        return math.copysign(accepted_size, proposed_size)

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
            
        x, y = x[-n:], y[-n:]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
        den_x = sum((a - mean_x)**2 for a in x)
        den_y = sum((b - mean_y)**2 for b in y)
        
        if den_x == 0 or den_y == 0:
            return 0.0
            
        return num / math.sqrt(den_x * den_y)
