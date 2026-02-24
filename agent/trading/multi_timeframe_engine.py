import logging
from typing import Dict, List, Any

class MultiTimeframeEngine:
    """
    Fuses signals from multiple timeframes using configurable weights.
    Core concept: Higher timeframes determine trend, lower timeframes determine entry.
    """
    
    def __init__(self, weights: Dict[str, float] = None) -> None:
        self.logger = logging.getLogger("MultiTimeframeEngine")
        # Default time-weighted alignment
        self.weights = weights or {
            "1m": 0.05,
            "5m": 0.15,
            "15m": 0.25,
            "1h": 0.30,
            "4h": 0.15,
            "1d": 0.10
        }
        
    def fuse_signals(self, mt_signals: Dict[str, float]) -> float:
        """
        Fuses multiple timeframe signals (-1.0 to 1.0) into a single score.
        
        Args:
            mt_signals (Dict[str, float]): Dictionary of signals by timeframe.
            
        Returns:
            float: Fused signal from -1.0 to 1.0.
        """
        fused = 0.0
        total_weight = 0.0
        
        for tf, signal in mt_signals.items():
            if tf in self.weights:
                w = self.weights[tf]
                # Ensure signal is bounded
                bounded_signal = max(min(signal, 1.0), -1.0)
                
                fused += bounded_signal * w
                total_weight += w
            else:
                self.logger.warning(f"Timeframe {tf} not found in weights. Ignoring.")
                
        if total_weight == 0:
            return 0.0
            
        normalized_fused = fused / total_weight
        return max(min(normalized_fused, 1.0), -1.0)
