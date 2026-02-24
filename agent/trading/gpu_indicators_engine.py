import logging
from typing import List, Tuple, Any

class GPUIndicatorsEngine:
    """
    GPU-accelerated indicators via CuPy with automatic fallback to NumPy.
    Used for processing massive historical datasets during backtesting or 
    multi-asset real-time scanning.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("GPUIndicatorsEngine")
        self.use_gpu = False
        try:
            import cupy as cp # type: ignore
            self.xp = cp
            self.use_gpu = True
            self.logger.info("CuPy detected. GPU acceleration enabled.")
        except ImportError:
            import numpy as np
            self.xp = np
            self.logger.warning("CuPy not found. Falling back to NumPy (CPU).")
            
    def calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate SMA using hardware acceleration."""
        data = self.xp.array(prices)
        if len(data) < period:
            return 0.0
        return float(self.xp.mean(data[-period:]))
        
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA using hardware acceleration."""
        if len(prices) < period:
            return 0.0
            
        data = self.xp.array(prices)
        multiplier = 2.0 / (period + 1.0)
        
        # Hardware acceleration is best for bulk EMA, but for a single latest point 
        # we still iterate or use a compiled kernel if this were fully optimized.
        # This is a simplified fallback for demonstration.
        ema = float(self.xp.mean(data[:period]))
        
        # In a real CuPy implementation, we'd use cupy.convolve or custom kernels for EMA
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
            
        return ema
        
    def batch_calculate_returns(self, prices: List[float]) -> Any:
        """
        Calculate log returns for a batch of prices.
        Returns are an array using the appropriate backend (CuPy/NumPy).
        """
        if len(prices) < 2:
            return self.xp.array([])
            
        data = self.xp.array(prices)
        return self.xp.log(data[1:] / data[:-1])
