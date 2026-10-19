"""
Learning Engine — Post-Trade Analysis & Adaptive Confidence.

Records every trade outcome and builds statistical profiles per
(strategy × regime × confidence_bucket) combination.

Uses these profiles to predict win probability for future signals,
creating a self-improving confidence calibration loop.

Key features:
    - MIN_TRADES_FOR_ADAPTATION (20): Don't adapt until sufficient sample
    - ROLLING_WINDOW (200): Only consider last 200 trades
    - Per-strategy × regime win rate tracking
    - Actionable insight generation

No LLM. Fully deterministic.
"""
import logging
import time
from typing import Dict, Any, List, Optional


class LearningEngine:
    """
    Records trade outcomes and builds statistical profiles per
    (strategy × regime × confidence_bucket) combination.

    Uses these profiles to predict win probability for future signals,
    creating a self-improving confidence calibration loop.
    """

    MIN_TRADES_FOR_ADAPTATION = 20  # Don't adapt until 20+ trades in bucket
    ROLLING_WINDOW = 200            # Only consider last 200 trades

    def __init__(self, database=None) -> None:
        self.logger = logging.getLogger("LearningEngine")
        self.database = database

        # In-memory cache (refreshed from DB periodically)
        self._stats_cache: Dict[tuple, Dict[str, Any]] = {}
        self._last_refresh = 0
        self._refresh_interval = 300  # 5 minutes

        self.logger.info("LearningEngine initialized")

    # ══════════════════════════════════════════════════════════════
    # RECORD OUTCOMES
    # ══════════════════════════════════════════════════════════════

    def record_outcome(self, trade: Dict[str, Any]) -> None:
        """
        Called when a trade closes. Records full context:
        strategy, regime, confidence, sentiment, ML agreement,
        TA conviction, entry/exit prices, P&L, holding period.
        """
        if not self.database:
            self.logger.warning("No database — cannot record outcome")
            return

        # Determine confidence bucket
        confidence = trade.get("confidence", 0.5)
        if confidence > 0.7:
            bucket = "HIGH"
        elif confidence > 0.5:
            bucket = "MED"
        else:
            bucket = "LOW"

        # Calculate P&L
        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        direction = trade.get("direction", "LONG")
        quantity = trade.get("quantity", 0)

        if direction == "LONG" and entry > 0:
            pnl_pct = (exit_price - entry) / entry
        elif direction == "SHORT" and entry > 0:
            pnl_pct = (entry - exit_price) / entry
        else:
            pnl_pct = trade.get("pnl_pct", 0.0)

        pnl_dollars = pnl_pct * entry * quantity if quantity else trade.get("pnl_dollars", 0.0)

        lesson = {
            "trade_id": trade.get("trade_id", ""),
            "strategy": trade.get("strategy_name", trade.get("strategy", "")),
            "regime": trade.get("regime", "UNKNOWN"),
            "confidence_bucket": bucket,
            "symbol": trade.get("symbol", ""),
            "direction": direction,
            "entry_price": entry,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "pnl_dollars": pnl_dollars,
            "sentiment_score": trade.get("sentiment_score"),
            "ta_conviction": trade.get("ta_conviction"),
            "ta_direction": trade.get("ta_direction"),
            "ml_agreed": 1 if trade.get("ml_agreed") else (0 if trade.get("ml_conflict") else None),
            "holding_period_bars": trade.get("holding_period_bars", trade.get("holding_period")),
            "exit_reason": trade.get("exit_reason", ""),
            "risk_mode_at_entry": trade.get("risk_mode_at_entry", "NORMAL"),
        }

        self.database.save_trade_lesson(lesson)
        self._update_strategy_regime_stats(lesson["strategy"], lesson["regime"])

        win_str = "WIN" if pnl_pct > 0 else "LOSS"
        self.logger.info(
            f"Recorded outcome: {lesson['symbol']} {lesson['strategy']} "
            f"{win_str} {pnl_pct:+.2%} | regime={lesson['regime']}"
        )

    # ══════════════════════════════════════════════════════════════
    # WIN RATE LOOKUPS
    # ══════════════════════════════════════════════════════════════

    def get_historical_win_rate(self, strategy: str, regime: str) -> float:
        """
        Returns win rate for this strategy × regime combination.
        Returns 0.5 (neutral) if insufficient data (< MIN_TRADES_FOR_ADAPTATION).
        """
        self._maybe_refresh_cache()

        key = (strategy, regime)
        if key in self._stats_cache:
            stats = self._stats_cache[key]
            if stats.get("total_trades", 0) >= self.MIN_TRADES_FOR_ADAPTATION:
                wins = stats.get("wins", 0)
                total = stats.get("total_trades", 1)
                return wins / total if total > 0 else 0.5
        return 0.5  # Neutral if insufficient data

    def get_strategy_regime_stats(self) -> Dict[tuple, Dict[str, Any]]:
        """
        Returns full matrix for dashboard heatmap:
        {("trend_following", "TRENDING_VOLATILE"): {wins: 12, losses: 5, avg_pnl: 0.02}, ...}
        """
        self._maybe_refresh_cache()
        return self._stats_cache.copy()

    def get_strategy_regime_stats_list(self) -> List[Dict[str, Any]]:
        """
        Returns strategy × regime stats as a list of dicts (for API responses).
        """
        if not self.database:
            return []
        return self.database.get_strategy_regime_stats()

    # ══════════════════════════════════════════════════════════════
    # INSIGHTS
    # ══════════════════════════════════════════════════════════════

    def get_insights(self) -> List[str]:
        """
        Returns actionable insights based on accumulated trade data:
        - "trend_following performs poorly in QUIET regime (28% win rate)"
        - "mean_reversion excels in LOW_VOL_RANGE (72% win rate)"
        """
        self._maybe_refresh_cache()
        insights = []

        for (strategy, regime), stats in self._stats_cache.items():
            total = stats.get("total_trades", 0)
            if total < self.MIN_TRADES_FOR_ADAPTATION:
                continue

            wins = stats.get("wins", 0)
            win_rate = wins / total if total > 0 else 0

            if win_rate >= 0.65:
                insights.append(
                    f"✅ {strategy} excels in {regime} "
                    f"({win_rate:.0%} win rate over {total} trades)"
                )
            elif win_rate <= 0.35:
                insights.append(
                    f"⚠️ {strategy} performs poorly in {regime} "
                    f"({win_rate:.0%} win rate over {total} trades)"
                )

            avg_pnl = stats.get("avg_pnl", 0)
            if avg_pnl > 0.02:
                insights.append(
                    f"💰 {strategy} in {regime}: avg P&L = {avg_pnl:.2%}"
                )
            elif avg_pnl < -0.02:
                insights.append(
                    f"📉 {strategy} in {regime}: avg P&L = {avg_pnl:.2%} (negative expectancy)"
                )

        if not insights:
            insights.append("📊 Insufficient trade data for insights (need 20+ trades per bucket)")

        return insights

    # ══════════════════════════════════════════════════════════════
    # INTERNAL: STATS UPDATE
    # ══════════════════════════════════════════════════════════════

    def _update_strategy_regime_stats(self, strategy: str, regime: str) -> None:
        """Recompute aggregated stats for a strategy × regime bucket from recent lessons."""
        if not self.database:
            return

        lessons = self.database.get_trade_lessons(
            strategy=strategy, regime=regime, limit=self.ROLLING_WINDOW
        )

        if not lessons:
            return

        total = len(lessons)
        wins = sum(1 for l in lessons if l.get("pnl_pct", 0) > 0)
        losses = total - wins
        pnls = [l.get("pnl_pct", 0) for l in lessons]
        confidences = [l.get("ta_conviction", 0.5) for l in lessons if l.get("ta_conviction") is not None]
        holdings = [l.get("holding_period_bars", 0) for l in lessons if l.get("holding_period_bars") is not None]

        stat = {
            "strategy": strategy,
            "regime": regime,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "avg_pnl": sum(pnls) / total if total else 0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "avg_holding_bars": sum(holdings) / len(holdings) if holdings else 0,
            "best_pnl": max(pnls) if pnls else 0,
            "worst_pnl": min(pnls) if pnls else 0,
        }

        self.database.save_strategy_regime_stat(stat)

        # Update in-memory cache
        self._stats_cache[(strategy, regime)] = stat

    def _maybe_refresh_cache(self) -> None:
        """Refresh the in-memory stats cache from DB if stale."""
        now = time.time()
        if now - self._last_refresh < self._refresh_interval:
            return

        if not self.database:
            return

        try:
            stats_list = self.database.get_strategy_regime_stats()
            self._stats_cache = {}
            for stat in stats_list:
                key = (stat["strategy"], stat["regime"])
                self._stats_cache[key] = stat
            self._last_refresh = now
        except Exception as e:
            self.logger.error(f"Failed to refresh stats cache: {e}")
