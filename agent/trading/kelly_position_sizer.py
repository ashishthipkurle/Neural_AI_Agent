import logging

class KellyPositionSizer:
    """
    Kelly Criterion position sizing algorithm.
    Calculates the optimal fraction of capital to risk 
    given probability of winning and reward/risk ratio.
    """
    
    def __init__(self, kelly_fraction: float = 0.5, max_position_size: float = 0.2) -> None:
        self.logger = logging.getLogger("KellySizer")
        # Fractional Kelly (e.g., 0.5 for Half-Kelly) is standard for risk reduction
        self.kelly_fraction = kelly_fraction 
        # Hard limit on maximum portfolio allocation per trade
        self.max_position_size = max_position_size
        
    def calculate_size(self, win_probability: float, win_loss_ratio: float) -> float:
        """
        Calculate suggested position size.
        
        Formula: f* = p - (q / b)
        Where:
            p = probability of win
            q = probability of loss (1 - p)
            b = proportion of the wager gained on a win (win/loss ratio)
            
        Args:
            win_probability (float): 0.0 to 1.0
            win_loss_ratio (float): Ratio of average win to average loss.
            
        Returns:
            float: Safe position size as a fraction of total capital (0.0 to max_position_size).
        """
        if win_probability <= 0 or win_loss_ratio <= 0:
            return 0.0
            
        q = 1.0 - win_probability
        
        # Unadjusted Kelly fraction
        f_star = win_probability - (q / win_loss_ratio)
        
        if f_star <= 0:
            # Edge is negative, do not trade
            self.logger.debug("Negative Kelly edge. Suggested size: 0.0")
            return 0.0
            
        # Apply fractional Kelly for volatility reduction
        adjusted_size = f_star * self.kelly_fraction
        
        # Apply absolute risk limits
        final_size = min(adjusted_size, self.max_position_size)
        
        self.logger.debug(f"f*: {f_star:.4f}, Adjusted: {adjusted_size:.4f}, Final: {final_size:.4f}")
        return final_size
