"""
Background Retraining & Memory Management Scheduler.

Architecture:
    - Purges stale patterns (>5 years old).
    - Triggers asynchronous background FAISS IndexIVFFlat rebuilds.
    - Monitors numerical drift against a Frozen Baseline Reference.
    - Calls cluster coordinator for hot-swaps.
"""
import logging
import time
from typing import Dict, Any, List, Optional
import math

try:
    from scipy.stats import ks_2samp
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class RetrainingScheduler:
    """
    Manages the lifecycle of FAISS indices and detects statistical decay.
    """

    def __init__(self, max_age_days: int = 1825, drift_p_value_threshold: float = 0.01) -> None:
        self.logger = logging.getLogger("RetrainingScheduler")
        self.max_age_days = max_age_days # ~5 years
        self.drift_p_value_threshold = drift_p_value_threshold # Strict p<0.01
        
        # Frozen Baselines: segment_key -> feature_distributions
        # Dictionary of feature indices -> lists of historical values
        self._frozen_baselines: Dict[str, Dict[int, List[float]]] = {}
        
    def set_frozen_baseline(self, segment_key: str, feature_matrix: List[List[float]]) -> None:
        """
        Locks in the empirical distribution of the exact dataset used to build the greenlit index.
        This prevents 'boiling frog' gradual drift masking.
        """
        if not feature_matrix:
            return
            
        dim = len(feature_matrix[0])
        baseline = {i: [] for i in range(dim)}
        
        # In production, we'd downsample this to ~10,000 points per feature to save RAM
        sample_size = min(len(feature_matrix), 10000)
        step = max(1, len(feature_matrix) // sample_size)
        
        for row in feature_matrix[::step]:
            for i, val in enumerate(row):
                baseline[i].append(val)
                
        self._frozen_baselines[segment_key] = baseline
        self.logger.info(f"Frozen Baseline locked for {segment_key} ({sample_size} vectors x {dim} dims).")

    def detect_drift(self, segment_key: str, recent_feature_matrix: List[List[float]]) -> Dict[str, Any]:
        """
        Calculates numerical drift (Kolmogorov-Smirnov test) against the Frozen Baseline.
        Returns drift severity and boolean trigger for out-of-cycle rebuilds.
        """
        if not recent_feature_matrix:
            return {"drift_detected": False, "reason": "No recent data", "severity": 0.0}
            
        if segment_key not in self._frozen_baselines:
            return {"drift_detected": False, "reason": "No baseline set", "severity": 0.0}

        if not SCIPY_AVAILABLE:
            self.logger.warning("Scipy not installed, cannot run KS test. Assuming no drift.")
            return {"drift_detected": False, "reason": "Missing scipy", "severity": 0.0}

        baseline = self._frozen_baselines[segment_key]
        dim = len(recent_feature_matrix[0])
        
        recent_dist = {i: [] for i in range(dim)}
        for row in recent_feature_matrix:
            for i, val in enumerate(row):
                recent_dist[i].append(val)
                
        features_drifted = 0
        min_p_value = 1.0
        
        for i in range(dim):
            # Two-sample Kolmogorov-Smirnov test
            # H0: The two samples were drawn from the same continuous distribution.
            stat, p_value = ks_2samp(baseline[i], recent_dist[i])
            
            if p_value < min_p_value:
                min_p_value = p_value
                
            # If p-value < threshold, we reject H0 (drift is statistically significant)
            if p_value < self.drift_p_value_threshold:
                features_drifted += 1

        drift_ratio = features_drifted / dim
        severity = drift_ratio * (1.0 - min_p_value)

        # Trigger if more than 25% of features have drifted significantly
        is_drifted = drift_ratio > 0.25 
        
        if is_drifted:
            self.logger.warning(f"DRIFT DETECTED on {segment_key}: {features_drifted}/{dim} features shifted significantly (min p={min_p_value:.4e}).")
            
        return {
            "drift_detected": is_drifted,
            "severity": severity,
            "features_drifted": features_drifted,
            "min_p_value": min_p_value
        }

    def evaluate_rebuild_need(self, segment_key: str, last_build_time_epoch: float, recent_features: List[List[float]]) -> bool:
        """
        Determines if a background rebuild should be triggered asynchronously.
        """
        age_days = (time.time() - last_build_time_epoch) / 86400.0
        
        # Time-based rebuild (e.g., every 30 days) to drop >5y vectors and re-cluster
        if age_days > 30.0:
            self.logger.info(f"Rebuild needed for {segment_key}: Time-based (Age: {age_days:.1f} days)")
            return True
            
        # Drift-based rebuild (out-of-cycle)
        drift_report = self.detect_drift(segment_key, recent_features)
        if drift_report["drift_detected"]:
            self.logger.warning(f"Rebuild forced for {segment_key}: Numerical Drift (Severity: {drift_report['severity']:.2f})")
            return True
            
        return False
