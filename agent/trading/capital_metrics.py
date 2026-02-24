"""
Capital Efficiency Metrics Engine.

Calculates strict deterministic institutional metrics:
    - Sharpe Ratio
    - Sortino Ratio
    - Information Ratio
    - Maximum Drawdown
    - Turnover
    - Capital Efficiency (Return / Unit Risk)

No LLMs used. Purely mathematical.
"""
import math
import logging
from typing import List, Dict, Any


class CapitalMetrics:
    """
    Computes rigorous portfolio performance benchmarks.
    All inputs should be arrays of period returns (e.g. daily or per-trade).
    """

    def __init__(self, risk_free_rate_annual: float = 0.04, periods_per_year: int = 252) -> None:
        self.logger = logging.getLogger("CapitalMetrics")
        self.rf_annual = risk_free_rate_annual
        self.periods = periods_per_year
        self.rf_periodic = (1.0 + self.rf_annual) ** (1.0 / self.periods) - 1.0

    def compute_all_metrics(
        self, 
        portfolio_returns: List[float], 
        benchmark_returns: List[float], 
        portfolio_values: List[float],
        total_traded_volume: float
    ) -> Dict[str, float]:
        """Calculates all compliance-grade metrics."""
        
        if len(portfolio_returns) < 2:
            return {}

        metrics = {
            "sharpe_ratio": self.calculate_sharpe(portfolio_returns),
            "sortino_ratio": self.calculate_sortino(portfolio_returns),
            "max_drawdown": self.calculate_max_drawdown(portfolio_values),
            "turnover_ratio": self.calculate_turnover(total_traded_volume, portfolio_values[-1] if portfolio_values else 1.0)
        }

        if benchmark_returns and len(benchmark_returns) == len(portfolio_returns):
            metrics["information_ratio"] = self.calculate_information_ratio(portfolio_returns, benchmark_returns)

        # Capital Efficiency = Annualized Return / Max Drawdown (Calmar variant)
        ann_ret = self._annualize_return(portfolio_returns)
        mdd = metrics["max_drawdown"]
        metrics["capital_efficiency_calmar"] = ann_ret / mdd if mdd > 0 else 0.0

        return metrics

    def calculate_sharpe(self, returns: List[float]) -> float:
        """Sharpe Ratio: (Mean Return - Rf) / StdDev(Returns)"""
        n = len(returns)
        if n < 2: return 0.0
        
        excess_returns = [r - self.rf_periodic for r in returns]
        mean_er = sum(excess_returns) / n
        
        variance = sum((r - mean_er) ** 2 for r in excess_returns) / (n - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0: return 0.0
        
        daily_sharpe = mean_er / std_dev
        return daily_sharpe * math.sqrt(self.periods)

    def calculate_sortino(self, returns: List[float]) -> float:
        """Sortino Ratio: (Mean Return - Target) / DownsideDeviation(Returns)"""
        n = len(returns)
        if n < 2: return 0.0
        
        excess_returns = [r - self.rf_periodic for r in returns]
        mean_er = sum(excess_returns) / n
        
        downside_sq = [r ** 2 for r in excess_returns if r < 0]
        if not downside_sq: return 0.0 # No downside risk
        
        downside_variance = sum(downside_sq) / n
        downside_dev = math.sqrt(downside_variance)
        
        daily_sortino = mean_er / downside_dev
        return daily_sortino * math.sqrt(self.periods)

    def calculate_information_ratio(self, returns: List[float], benchmark: List[float]) -> float:
        """Information Ratio: (Mean Active Return) / Tracking Error"""
        n = len(returns)
        if n < 2 or len(benchmark) != n: return 0.0
        
        active_returns = [r - b for r, b in zip(returns, benchmark)]
        mean_ar = sum(active_returns) / n
        
        variance = sum((ar - mean_ar)**2 for ar in active_returns) / (n - 1)
        tracking_error = math.sqrt(variance)
        
        if tracking_error == 0: return 0.0
        
        daily_ir = mean_ar / tracking_error
        return daily_ir * math.sqrt(self.periods)

    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Peak-to-Trough maximum drawdown percentage."""
        if not equity_curve: return 0.0
        
        max_seen = equity_curve[0]
        max_dd = 0.0
        
        for val in equity_curve:
            if val > max_seen:
                max_seen = val
            
            dd = (max_seen - val) / max_seen if max_seen > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                
        return max_dd

    def calculate_turnover(self, total_volume_traded: float, avg_portfolio_value: float) -> float:
        """Portfolio Turnover: Min(Purchases, Sales) / Avg Net Assets. Using volume as proxy."""
        if avg_portfolio_value <= 0: return 0.0
        return (total_volume_traded / 2.0) / avg_portfolio_value

    def _annualize_return(self, returns: List[float]) -> float:
        if not returns: return 0.0
        # Compounded return
        comp_ret = 1.0
        for r in returns:
            comp_ret *= (1.0 + r)
        
        # Annualize based on length
        years = len(returns) / self.periods
        if years == 0: return 0.0
        return comp_ret ** (1.0 / years) - 1.0
