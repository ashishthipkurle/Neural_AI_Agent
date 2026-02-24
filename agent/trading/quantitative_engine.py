import math
from typing import List, Tuple, Dict, Any

class QuantitativeEngine:
    """
    Statistical analysis core.
    Provides deterministic foundation for probability sizing and risk models.
    """
    
    @staticmethod
    def calculate_z_score(value: float, mean: float, std_dev: float) -> float:
        """Standardize a value to a z-score."""
        if std_dev == 0.0:
            return 0.0
        return (value - mean) / std_dev
        
    @staticmethod
    def calculate_correlation(x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
            
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        
        denominator = math.sqrt(var_x * var_y)
        if denominator == 0:
            return 0.0
            
        return numerator / denominator
        
    @staticmethod
    def calculate_volatility(returns: List[float], annualize_factor: int = 252) -> float:
        """Calculate historical volatility (standard deviation of returns)."""
        if len(returns) < 2:
            return 0.0
            
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(annualize_factor)
