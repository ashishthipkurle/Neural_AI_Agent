"""
Backtest Runner -- CLI script for running real 5-year backtests.

Downloads historical OHLCV data via yfinance, iterates bar-by-bar
through RegimeSwitcher -> StrategyEngine, simulates execution with
fills at next-bar open, and produces comprehensive performance metrics.

Usage:
    python -m agent.trading.run_backtest --symbols SPY,AAPL,TSLA --years 5 --strategies all
    python -m agent.trading.run_backtest --symbols SPY --years 3 --strategies trend_following
"""
import argparse
import json
import csv
import time
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Ensure agent package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent.trading.indicators_engine import IndicatorsEngine
from agent.trading.regime_switcher import RegimeSwitcher
from agent.trading.strategy_engine import StrategyEngine
from agent.trading.backtest_engine import BacktestEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("BacktestRunner")


# ══════════════════════════════════════════════════════════════
# DATA DOWNLOAD
# ══════════════════════════════════════════════════════════════

def download_data(symbol: str, years: int) -> Optional[Dict[str, List[float]]]:
    """Download daily OHLCV data via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    logger.info(f"Downloading {symbol} from {start_date.date()} to {end_date.date()}")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date, interval="1d")

    if df is None or len(df) < 100:
        logger.error(f"Insufficient data for {symbol}: got {len(df) if df is not None else 0} bars")
        return None

    ohlcv = {
        "timestamps": [t.timestamp() for t in df.index],
        "opens": df["Open"].tolist(),
        "highs": df["High"].tolist(),
        "lows": df["Low"].tolist(),
        "closes": df["Close"].tolist(),
        "volumes": df["Volume"].tolist(),
    }

    logger.info(f"Downloaded {len(df)} daily bars for {symbol}")
    return ohlcv


# ══════════════════════════════════════════════════════════════
# BAR-BY-BAR SIMULATION
# ══════════════════════════════════════════════════════════════

class TradeSimulator:
    """
    Simulates trade execution: fills at next bar open, tracks
    stop-loss and take-profit exits per bar.
    """

    def __init__(self) -> None:
        self.open_trades: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

    def process_signal(self, signal: Dict[str, Any], next_bar_open: float, bar_index: int) -> None:
        """Open a new trade at the next bar's open price."""
        direction = signal["direction"]
        entry_price = next_bar_open  # Fill at next bar open (realistic)
        stop_price = signal["stop_price"]
        target_price = signal["target_price"]

        # Adjust stop/target relative to actual fill price vs signal entry
        price_diff = entry_price - signal["entry_price"]
        stop_price += price_diff
        target_price += price_diff

        trade = {
            "trade_id": f"BT_{bar_index}_{signal['strategy_name']}",
            "symbol": signal["symbol"],
            "strategy_name": signal["strategy_name"],
            "direction": direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "regime": signal.get("regime", "UNKNOWN"),
            "confidence": signal.get("confidence", 0.0),
            "entry_bar": bar_index,
            "exit_price": None,
            "exit_reason": None,
            "exit_bar": None,
        }
        self.open_trades.append(trade)

    def check_exits(self, high: float, low: float, close: float, bar_index: int) -> None:
        """Check if any open trades hit stop-loss or take-profit this bar."""
        still_open = []
        for trade in self.open_trades:
            exited = False

            if trade["direction"] == "LONG":
                # Stop-loss hit
                if low <= trade["stop_price"]:
                    trade["exit_price"] = trade["stop_price"]
                    trade["exit_reason"] = "STOP_LOSS"
                    exited = True
                # Take-profit hit
                elif high >= trade["target_price"]:
                    trade["exit_price"] = trade["target_price"]
                    trade["exit_reason"] = "TAKE_PROFIT"
                    exited = True
            else:  # SHORT
                # Stop-loss hit (price goes up)
                if high >= trade["stop_price"]:
                    trade["exit_price"] = trade["stop_price"]
                    trade["exit_reason"] = "STOP_LOSS"
                    exited = True
                # Take-profit hit (price goes down)
                elif low <= trade["target_price"]:
                    trade["exit_price"] = trade["target_price"]
                    trade["exit_reason"] = "TAKE_PROFIT"
                    exited = True

            # Timeout: close at current price after 20 bars
            if not exited and (bar_index - trade["entry_bar"]) >= 20:
                trade["exit_price"] = close
                trade["exit_reason"] = "TIMEOUT"
                exited = True

            if exited:
                trade["exit_bar"] = bar_index
                trade["holding_period"] = bar_index - trade["entry_bar"]

                # Calculate P&L
                if trade["direction"] == "LONG":
                    trade["pnl_pct"] = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]
                else:
                    trade["pnl_pct"] = (trade["entry_price"] - trade["exit_price"]) / trade["entry_price"]

                # R-multiple
                risk = abs(trade["entry_price"] - trade["stop_price"])
                if risk > 0:
                    reward = trade["pnl_pct"] * trade["entry_price"]
                    trade["r_achieved"] = reward / risk
                else:
                    trade["r_achieved"] = 0.0

                self.closed_trades.append(trade)
            else:
                still_open.append(trade)

        self.open_trades = still_open

    def close_remaining(self, close: float, bar_index: int) -> None:
        """Close all remaining open trades at end of backtest."""
        for trade in self.open_trades:
            trade["exit_price"] = close
            trade["exit_reason"] = "END_OF_DATA"
            trade["exit_bar"] = bar_index
            trade["holding_period"] = bar_index - trade["entry_bar"]

            if trade["direction"] == "LONG":
                trade["pnl_pct"] = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]
            else:
                trade["pnl_pct"] = (trade["entry_price"] - trade["exit_price"]) / trade["entry_price"]

            risk = abs(trade["entry_price"] - trade["stop_price"])
            if risk > 0:
                reward = trade["pnl_pct"] * trade["entry_price"]
                trade["r_achieved"] = reward / risk
            else:
                trade["r_achieved"] = 0.0

            self.closed_trades.append(trade)
        self.open_trades = []


# ══════════════════════════════════════════════════════════════
# MAIN BACKTEST RUNNER
# ══════════════════════════════════════════════════════════════

def run_backtest_for_symbol(
    symbol: str,
    ohlcv: Dict[str, List[float]],
    strategies_enabled: List[str],
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """
    Run bar-by-bar backtest for a single symbol.

    Iterates through each bar, feeds data to RegimeSwitcher -> StrategyEngine,
    simulates trade execution, and returns metrics.
    """
    indicators = IndicatorsEngine()
    regime_switcher = RegimeSwitcher()
    strategy_engine = StrategyEngine(
        indicators_engine=indicators,
        regime_switcher=regime_switcher,
    )
    backtest_engine = BacktestEngine()
    simulator = TradeSimulator()

    closes = ohlcv["closes"]
    highs = ohlcv["highs"]
    lows = ohlcv["lows"]
    opens = ohlcv["opens"]
    volumes = ohlcv["volumes"]
    n_bars = len(closes)

    # Need at least 51 bars of lookback before we can start evaluating
    lookback = 60
    if n_bars < lookback + 10:
        return {"symbol": symbol, "status": "INSUFFICIENT_DATA", "metrics": {}}

    logger.info(f"Running backtest for {symbol}: {n_bars} bars, strategies={strategies_enabled}")

    # Per-strategy results
    strategy_results = {}

    for strategy_name in strategies_enabled:
        strategy_engine_copy = StrategyEngine(
            indicators_engine=indicators,
            regime_switcher=regime_switcher,
        )
        sim = TradeSimulator()

        for i in range(lookback, n_bars):
            # Build rolling OHLCV window (last 200 bars or all available)
            start_idx = max(0, i - 200)
            window_ohlcv = {
                "opens": opens[start_idx:i + 1],
                "highs": highs[start_idx:i + 1],
                "lows": lows[start_idx:i + 1],
                "closes": closes[start_idx:i + 1],
                "volumes": volumes[start_idx:i + 1],
            }

            # Check exits on current bar first
            sim.check_exits(highs[i], lows[i], closes[i], i)

            # Detect regime
            try:
                regime = regime_switcher.detect_regime(
                    highs=window_ohlcv["highs"],
                    lows=window_ohlcv["lows"],
                    closes=window_ohlcv["closes"],
                )
            except Exception:
                regime = "QUIET"

            # Evaluate strategy (limit to 1 open trade per strategy)
            if len(sim.open_trades) == 0:
                signal = strategy_engine_copy.evaluate_strategy(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    ohlcv=window_ohlcv,
                    regime=regime,
                    current_bar_index=i,
                )

                # If signal fired and we have a next bar, fill at next bar open
                if signal and i + 1 < n_bars:
                    sim.process_signal(signal, opens[i + 1], i + 1)

        # Close remaining trades
        if sim.open_trades:
            sim.close_remaining(closes[-1], n_bars - 1)

        trades = sim.closed_trades

        # Run through BacktestEngine for metrics
        result = backtest_engine.run_backtest(trades, initial_capital)

        # Walk-forward validation
        wf_result = backtest_engine.walk_forward(trades, num_folds=5)

        strategy_results[strategy_name] = {
            "trades": len(trades),
            "metrics": result.get("metrics", {}),
            "regime_breakdown": result.get("regime_breakdown", {}),
            "equity_curve": result.get("equity_curve", [initial_capital]),
            "walk_forward": wf_result,
        }

        # Print per-strategy summary
        metrics = result.get("metrics", {})
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = metrics.get("max_drawdown", 0)
        win_rate = metrics.get("win_rate", 0)
        cagr = metrics.get("cagr", 0)
        profit_factor = metrics.get("profit_factor", 0)

        # Decision gate
        passed = sharpe > 0.3 and max_dd < 30
        status = "[PASS]" if passed else "[FAIL]"

        logger.info(
            f"  {strategy_name:20s} | Trades: {len(trades):4d} | "
            f"Sharpe: {sharpe:6.3f} | MaxDD: {max_dd:5.1f}% | "
            f"WinRate: {win_rate:5.1f}% | CAGR: {cagr:6.2f}% | "
            f"PF: {profit_factor:5.3f} | {status}"
        )

    return {
        "symbol": symbol,
        "status": "COMPLETED",
        "strategies": strategy_results,
    }


# ══════════════════════════════════════════════════════════════
# SAVE RESULTS
# ══════════════════════════════════════════════════════════════

def save_results(results: Dict[str, Any], output_dir: str) -> None:
    """Save backtest results to output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for symbol, result in results.items():
        if result.get("status") != "COMPLETED":
            continue

        # Save metrics JSON
        metrics_file = out_path / f"{symbol}_metrics_{timestamp}.json"
        metrics_data = {
            "symbol": symbol,
            "timestamp": timestamp,
            "strategies": {},
        }
        for strat_name, strat_result in result.get("strategies", {}).items():
            metrics_data["strategies"][strat_name] = {
                "trades": strat_result["trades"],
                "metrics": strat_result["metrics"],
                "regime_breakdown": strat_result["regime_breakdown"],
                "walk_forward": strat_result.get("walk_forward", {}),
            }

        with open(metrics_file, "w") as f:
            json.dump(metrics_data, f, indent=2)
        logger.info(f"Saved metrics: {metrics_file}")

        # Save equity curves as CSV
        for strat_name, strat_result in result.get("strategies", {}).items():
            curve = strat_result.get("equity_curve", [])
            if curve:
                csv_file = out_path / f"{symbol}_{strat_name}_equity_{timestamp}.csv"
                with open(csv_file, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["bar_index", "equity"])
                    for idx, eq in enumerate(curve):
                        writer.writerow([idx, eq])
                logger.info(f"Saved equity curve: {csv_file}")


# ══════════════════════════════════════════════════════════════
# DECISION GATE
# ══════════════════════════════════════════════════════════════

def print_decision_gate(results: Dict[str, Any]) -> bool:
    """Print final PASS/FAIL decision gate and return overall status."""
    print("\n" + "=" * 80)
    print("DECISION GATE: Backtest Results Summary")
    print("=" * 80)
    print(f"  Criteria: Sharpe > 0.3 AND Max Drawdown < 30%")
    print("-" * 80)

    any_passed = False

    for symbol, result in results.items():
        if result.get("status") != "COMPLETED":
            print(f"  {symbol}: SKIPPED (insufficient data)")
            continue

        for strat_name, strat_result in result.get("strategies", {}).items():
            metrics = strat_result.get("metrics", {})
            sharpe = metrics.get("sharpe_ratio", 0)
            max_dd = metrics.get("max_drawdown", 0)
            win_rate = metrics.get("win_rate", 0)
            cagr = metrics.get("cagr", 0)
            profit_factor = metrics.get("profit_factor", 0)
            trades = strat_result.get("trades", 0)
            wf = strat_result.get("walk_forward", {})
            wf_status = wf.get("status", "N/A")

            passed = sharpe > 0.3 and max_dd < 30
            if passed:
                any_passed = True

            status = "[PASS]" if passed else "[FAIL]"
            print(
                f"  {symbol:6s} | {strat_name:20s} | "
                f"Sharpe={sharpe:6.3f} | DD={max_dd:5.1f}% | "
                f"WR={win_rate:5.1f}% | CAGR={cagr:6.2f}% | "
                f"PF={profit_factor:5.3f} | Trades={trades:4d} | "
                f"WF={wf_status:8s} | {status}"
            )

    print("-" * 80)
    if any_passed:
        print("  OVERALL: [PASS] -- At least one strategy has Sharpe > 0.3 and MaxDD < 30%")
        print("  -> Proceed to Phase 2: TradingAgents Integration")
    else:
        print("  OVERALL: [FAIL] -- No strategy meets minimum criteria")
        print("  -> STOP: Redesign strategies before proceeding to Phase 2")
    print("=" * 80 + "\n")

    return any_passed


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Run backtests against 5-year historical data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m agent.trading.run_backtest --symbols SPY,AAPL,TSLA --years 5 --strategies all
    python -m agent.trading.run_backtest --symbols SPY --years 3 --strategies trend_following,breakout
    python -m agent.trading.run_backtest --symbols MSFT --years 5 --capital 50000
        """,
    )
    parser.add_argument(
        "--symbols", type=str, default="SPY,AAPL,TSLA,MSFT,QQQ",
        help="Comma-separated list of symbols to backtest (default: SPY,AAPL,TSLA,MSFT,QQQ)",
    )
    parser.add_argument(
        "--years", type=int, default=5,
        help="Number of years of historical data (default: 5)",
    )
    parser.add_argument(
        "--strategies", type=str, default="all",
        help="Comma-separated list of strategies, or 'all' (default: all)",
    )
    parser.add_argument(
        "--capital", type=float, default=100000.0,
        help="Initial capital for backtest (default: 100000)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory for results (default: agent_data/backtest_results/)",
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    # Parse strategies
    all_strategies = ["trend_following", "mean_reversion", "breakout", "faiss_pattern"]
    if args.strategies.lower() == "all":
        strategies = all_strategies
    else:
        strategies = [s.strip() for s in args.strategies.split(",")]
        for s in strategies:
            if s not in all_strategies:
                logger.error(f"Unknown strategy: {s}. Available: {all_strategies}")
                sys.exit(1)

    # Output directory
    output_dir = args.output_dir
    if not output_dir:
        output_dir = str(Path(__file__).resolve().parent.parent.parent / "agent_data" / "backtest_results")

    print("\n" + "=" * 80)
    print("BACKTEST RUNNER -- Intelligent Trading Agent v3.0")
    print("=" * 80)
    print(f"  Symbols:    {symbols}")
    print(f"  Years:      {args.years}")
    print(f"  Strategies: {strategies}")
    print(f"  Capital:    ${args.capital:,.0f}")
    print(f"  Output:     {output_dir}")
    print("=" * 80 + "\n")

    # Download data and run backtests
    results = {}
    for symbol in symbols:
        ohlcv = download_data(symbol, args.years)
        if not ohlcv:
            results[symbol] = {"status": "NO_DATA"}
            continue

        result = run_backtest_for_symbol(
            symbol=symbol,
            ohlcv=ohlcv,
            strategies_enabled=strategies,
            initial_capital=args.capital,
        )
        results[symbol] = result

    # Save results
    save_results(results, output_dir)

    # Decision gate
    passed = print_decision_gate(results)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
