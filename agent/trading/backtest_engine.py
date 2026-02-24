"""
Backtesting & Walk-Forward Validation Engine.

Implements:
    - Walk-forward testing with rolling windows
    - Out-of-sample validation
    - Regime-segmented performance statistics
    - Comprehensive performance metrics

Metrics:
    CAGR, Sharpe, Sortino, Max Drawdown, Calmar,
    Ulcer Index, Recovery Factor, Win Rate, Profit Factor

No LLM. Fully deterministic.
"""
import math
import logging
from typing import List, Dict, Any, Optional, Tuple


class BacktestEngine:
    """
    Historical backtesting with walk-forward analysis and regime segmentation.
    """

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.logger = logging.getLogger("BacktestEngine")
        self.risk_free_rate = risk_free_rate

    def run_backtest(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float = 100000.0,
    ) -> Dict[str, Any]:
        """
        Run event-driven backtest on a list of completed trades.

        Args:
            trades: List of trade dicts with keys:
                - pnl_pct: Profit/loss as a decimal (e.g., 0.02 = +2%)
                - regime: Market regime when trade was taken
                - direction: "LONG" or "SHORT"
                - r_achieved: Final R-multiple
            initial_capital: Starting portfolio value

        Returns:
            dict with equity_curve, metrics, regime_breakdown
        """
        if not trades:
            return self._empty_result(initial_capital)

        # ── Build equity curve ─────────────────────────────────
        equity = [initial_capital]
        peak = initial_capital
        max_dd = 0.0
        drawdown_durations = []
        dd_start = None
        returns = []
        regime_trades: Dict[str, List[float]] = {}

        for i, trade in enumerate(trades):
            pnl_pct = trade.get("pnl_pct", 0.0)
            regime = trade.get("regime", "UNKNOWN")
            r = trade.get("r_achieved", 0.0)

            new_equity = equity[-1] * (1 + pnl_pct)
            equity.append(new_equity)
            returns.append(pnl_pct)

            # Track regime performance
            if regime not in regime_trades:
                regime_trades[regime] = []
            regime_trades[regime].append(pnl_pct)

            # Drawdown tracking
            peak = max(peak, new_equity)
            dd = (peak - new_equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

            if dd > 0 and dd_start is None:
                dd_start = i
            elif dd == 0 and dd_start is not None:
                drawdown_durations.append(i - dd_start)
                dd_start = None

        # ── Compute performance metrics ────────────────────────
        metrics = self._compute_metrics(returns, equity, max_dd, initial_capital)

        # ── Regime-segmented stats ─────────────────────────────
        regime_breakdown = {}
        for regime, r_returns in regime_trades.items():
            if r_returns:
                wins = [r for r in r_returns if r > 0]
                losses = [r for r in r_returns if r <= 0]
                regime_breakdown[regime] = {
                    "trade_count": len(r_returns),
                    "win_rate": round(len(wins) / len(r_returns), 4) if r_returns else 0,
                    "avg_return": round(sum(r_returns) / len(r_returns), 6),
                    "total_return": round(sum(r_returns), 6),
                    "best_trade": round(max(r_returns), 6),
                    "worst_trade": round(min(r_returns), 6),
                }

        return {
            "metrics": metrics,
            "regime_breakdown": regime_breakdown,
            "equity_curve": [round(e, 2) for e in equity],
            "total_trades": len(trades),
            "final_equity": round(equity[-1], 2),
            "status": "COMPLETED",
        }

    def walk_forward(
        self,
        trades: List[Dict[str, Any]],
        in_sample_pct: float = 0.70,
        num_folds: int = 5,
        initial_capital: float = 100000.0,
    ) -> Dict[str, Any]:
        """
        Walk-forward validation — train on in-sample, validate on out-of-sample.

        Args:
            trades: Full list of historical trades
            in_sample_pct: Fraction used for in-sample (e.g., 0.70 = 70%)
            num_folds: Number of rolling windows
            initial_capital: Starting capital

        Returns:
            dict with in-sample and out-of-sample metrics per fold
        """
        n = len(trades)
        if n < 20:
            return {"status": "INSUFFICIENT_DATA", "folds": []}

        fold_size = n // num_folds
        folds = []

        for fold in range(num_folds):
            start = fold * fold_size
            end = min(start + fold_size, n)
            fold_trades = trades[start:end]

            split = int(len(fold_trades) * in_sample_pct)
            in_sample = fold_trades[:split]
            out_sample = fold_trades[split:]

            is_result = self.run_backtest(in_sample, initial_capital)
            oos_result = self.run_backtest(out_sample, initial_capital)

            folds.append({
                "fold": fold + 1,
                "in_sample_trades": len(in_sample),
                "out_sample_trades": len(out_sample),
                "in_sample_sharpe": is_result["metrics"].get("sharpe_ratio", 0),
                "out_sample_sharpe": oos_result["metrics"].get("sharpe_ratio", 0),
                "in_sample_return": is_result["metrics"].get("total_return_pct", 0),
                "out_sample_return": oos_result["metrics"].get("total_return_pct", 0),
                "in_sample_max_dd": is_result["metrics"].get("max_drawdown", 0),
                "out_sample_max_dd": oos_result["metrics"].get("max_drawdown", 0),
            })

        # Robustness check: OOS Sharpe should be > 50% of IS Sharpe
        robust_folds = sum(
            1 for f in folds
            if f["in_sample_sharpe"] > 0 and
            f["out_sample_sharpe"] > f["in_sample_sharpe"] * 0.5
        )

        return {
            "folds": folds,
            "num_folds": num_folds,
            "robust_folds": robust_folds,
            "robustness_pct": round(robust_folds / num_folds * 100, 1),
            "status": "ROBUST" if robust_folds >= num_folds * 0.6 else "FRAGILE",
        }

    def _compute_metrics(
        self,
        returns: List[float],
        equity: List[float],
        max_dd: float,
        initial_capital: float,
    ) -> Dict[str, Any]:
        """Compute core performance metrics."""
        n = len(returns)
        if n == 0:
            return {}

        total_return = (equity[-1] - initial_capital) / initial_capital
        avg_return = sum(returns) / n

        # CAGR (assuming 252 trading days per year)
        years = max(n / 252, 0.01)
        cagr = (equity[-1] / initial_capital) ** (1 / years) - 1 if equity[-1] > 0 else -1.0

        # Standard deviation
        variance = sum((r - avg_return) ** 2 for r in returns) / n if n > 1 else 0.0
        std_dev = math.sqrt(variance)
        annualized_std = std_dev * math.sqrt(252)

        # Sharpe Ratio
        sharpe = (cagr - self.risk_free_rate) / annualized_std if annualized_std > 0 else 0.0

        # Sortino Ratio (downside deviation only)
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_std = math.sqrt(downside_var) * math.sqrt(252)
            sortino = (cagr - self.risk_free_rate) / downside_std if downside_std > 0 else 0.0
        else:
            sortino = 0.0

        # Calmar Ratio
        calmar = cagr / max_dd if max_dd > 0 else 0.0

        # Ulcer Index
        drawdowns_sq = []
        peak = equity[0]
        for e in equity:
            peak = max(peak, e)
            dd = (peak - e) / peak if peak > 0 else 0.0
            drawdowns_sq.append(dd ** 2)
        ulcer = math.sqrt(sum(drawdowns_sq) / len(drawdowns_sq)) if drawdowns_sq else 0.0

        # Recovery Factor
        recovery = total_return / max_dd if max_dd > 0 else 0.0

        # Win/Loss stats
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        win_rate = len(wins) / n if n > 0 else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else 0.0

        return {
            "total_return_pct": round(total_return * 100, 2),
            "cagr": round(cagr * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "ulcer_index": round(ulcer * 100, 4),
            "recovery_factor": round(recovery, 3),
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 3),
            "avg_win_pct": round(avg_win * 100, 4),
            "avg_loss_pct": round(avg_loss * 100, 4),
            "total_trades": n,
        }

    def _empty_result(self, capital: float) -> Dict[str, Any]:
        return {
            "metrics": {},
            "regime_breakdown": {},
            "equity_curve": [capital],
            "total_trades": 0,
            "final_equity": capital,
            "status": "NO_TRADES",
        }
