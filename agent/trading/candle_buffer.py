from typing import Any, Dict, List, Optional
import collections

class CandleBuffer:
    """
    High-performance, fixed-size ring buffer for streaming OHLCV candle updates.
    Ensures memory stability for high-frequency data feeds.
    """
    
    def __init__(self, max_size: int = 1000) -> None:
        self.buffer = collections.deque(maxlen=max_size)

    def add_candle(self, candle: Dict[str, Any]) -> None:
        """
        Add a new candle or update the most recent one.
        """
        self.buffer.append(candle)
        
    def add_candles(self, candles: List[Dict[str, Any]]) -> None:
        """
        Bulk insert multiple candles.
        """
        self.buffer.extend(candles)
        
    def get_latest(self, n: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieve the latest N candles.
        """
        if n > len(self.buffer):
            n = len(self.buffer)
        return list(collections.deque(self.buffer, maxlen=n))
        
    def clear(self) -> None:
        """
        Clear the candle buffer.
        """
        self.buffer.clear()
        
    def __len__(self) -> int:
        return len(self.buffer)
