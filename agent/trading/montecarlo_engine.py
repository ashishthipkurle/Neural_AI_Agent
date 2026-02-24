"""
Monte Carlo Robustness Testing Engine.

Bootstrap equity curve simulation using historical return distribution.
10K+ paths with replacement. Outputs confidence intervals for:
    - Max drawdown distribution
    - Terminal equity distribution
    - Ruin probability (probability of hitting a loss threshold)

No LLM. Fully deterministic (given seed).
"""
import math
import random
import logging
from typing import List, Dict, Any, Optional


class MonteCarloEngine:
    """
    Monte Carlo equity curve simulation for strategy robustness testing.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self.logger = logging.getLogger("MonteCarloEngine")
        self.rng = random.Random(seed)

    def simulate(
        self,
        historical_returns: List[float],
        num_simulations: int = 10000,
        horizon_days: int = 252,
        initial_capital: float = 100000.0,
        ruin_threshold: float = 0.50,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation.

        Args:
            historical_returns: List of daily/trade returns (decimals)
            num_simulations: Number of simulated paths
            horizon_days: Duration of each simulation in trading days
            initial_capital: Starting capital
            ruin_threshold: Drawdown level considered "ruin" (0.50 = 50%)

        Returns:
            dict with distributions, percentiles, ruin probability
        """
        if not historical_returns or len(historical_returns) < 10:
            return self._empty_result("INSUFFICIENT_DATA")

        terminal_values = []
        max_drawdowns = []
        ruin_count = 0
        best_path_value = 0.0
        worst_path_value = float('inf')

        for _ in range(num_simulations):
            equity = initial_capital
            peak = initial_capital
            path_max_dd = 0.0
            ruined = False

            for _ in range(horizon_days):
                # Bootstrap: sample with replacement
                ret = self.rng.choice(historical_returns)
                equity *= (1 + ret)

                peak = max(peak, equity)
                dd = (peak - equity) / peak if peak > 0 else 0
                path_max_dd = max(path_max_dd, dd)

                if dd >= ruin_threshold and not ruined:
                    ruined = True

            terminal_values.append(equity)
            max_drawdowns.append(path_max_dd)
            if ruined:
                ruin_count += 1

            best_path_value = max(best_path_value, equity)
            worst_path_value = min(worst_path_value, equity)

        # ── Compute statistics ─────────────────────────────────
        terminal_values.sort()
        max_drawdowns.sort()

        def percentile(data: List[float], pct: float) -> float:
            idx = int(len(data) * pct / 100)
            idx = max(0, min(idx, len(data) - 1))
            return data[idx]

        ruin_probability = ruin_count / num_simulations
        median_terminal = percentile(terminal_values, 50)
        mean_terminal = sum(terminal_values) / len(terminal_values)

        result = {
            "num_simulations": num_simulations,
            "horizon_days": horizon_days,
            "initial_capital": initial_capital,
            "terminal_equity": {
                "mean": round(mean_terminal, 2),
                "median": round(median_terminal, 2),
                "p5": round(percentile(terminal_values, 5), 2),
                "p10": round(percentile(terminal_values, 10), 2),
                "p25": round(percentile(terminal_values, 25), 2),
                "p75": round(percentile(terminal_values, 75), 2),
                "p90": round(percentile(terminal_values, 90), 2),
                "p95": round(percentile(terminal_values, 95), 2),
                "best": round(best_path_value, 2),
                "worst": round(worst_path_value, 2),
            },
            "max_drawdown": {
                "mean": round(sum(max_drawdowns) / len(max_drawdowns) * 100, 2),
                "median": round(percentile(max_drawdowns, 50) * 100, 2),
                "p5": round(percentile(max_drawdowns, 5) * 100, 2),
                "p95": round(percentile(max_drawdowns, 95) * 100, 2),
                "worst": round(max(max_drawdowns) * 100, 2),
            },
            "ruin_probability": round(ruin_probability * 100, 3),
            "ruin_threshold": round(ruin_threshold * 100, 1),
            "profitable_pct": round(
                sum(1 for v in terminal_values if v > initial_capital) / num_simulations * 100, 2
            ),
            "status": "COMPLETED",
        }

        self.logger.info(
            f"Monte Carlo: {num_simulations} paths, "
            f"median_terminal=${median_terminal:.0f}, "
            f"ruin_prob={ruin_probability:.2%}, "
            f"median_maxDD={percentile(max_drawdowns, 50):.2%}"
        )

        return result

    def _empty_result(self, status: str) -> Dict[str, Any]:
        return {
            "num_simulations": 0,
            "terminal_equity": {},
            "max_drawdown": {},
            "ruin_probability": 0,
            "status": status,
        }
