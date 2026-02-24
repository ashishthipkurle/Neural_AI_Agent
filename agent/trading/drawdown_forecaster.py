import logging
import random
from typing import List

class DrawdownForecaster:
    """
    Monte Carlo simulation for portfolio drawdown forecasting.
    Provides statistical boundaries for expected risk over a forward horizon.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("DrawdownForecaster")
        
    def run_monte_carlo(self, historical_returns: List[float], num_simulations: int = 1000, horizon_days: int = 252) -> float:
        """
        Runs Monte Carlo simulations to forecast the 95th percentile max drawdown.
        
        Args:
            historical_returns (List[float]): Array of historical daily returns.
            num_simulations (int): Number of simulated paths.
            horizon_days (int): Forward looking horizon.
            
        Returns:
            float: 95th percentile maximum drawdown (positive float, e.g., 0.15 for 15%).
        """
        if not historical_returns:
            self.logger.warning("No historical returns provided for Monte Carlo.")
            return 0.0
            
        max_drawdowns = []
        
        for _ in range(num_simulations):
            equity = 1.0
            peak = 1.0
            max_dd = 0.0
            
            for _ in range(horizon_days):
                # Simple bootstrapping (sampling with replacement)
                daily_return = random.choice(historical_returns)
                equity *= (1 + daily_return)
                
                if equity > peak:
                    peak = equity
                    
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
                    
            max_drawdowns.append(max_dd)
            
        # Sort to find percentiles
        max_drawdowns.sort()
        
        # 95th percentile worst case
        idx = int(num_simulations * 0.95)
        forecasted_drawdown = max_drawdowns[idx]
        
        self.logger.debug(f"Forecasted 95% worst-case max drawdown: {forecasted_drawdown:.2%}")
        return forecasted_drawdown
