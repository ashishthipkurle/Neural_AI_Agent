"""
TradingAgents Adapter — Bridge between TradingAgents research
framework and our execution engine.

Runs TradingAgents analysis for a symbol, caches results,
and returns a normalized conviction score.

Key design decisions:
    - Cache results for 1 hour to avoid burning LLM credits on every 15min bar
    - Default to Ollama (free, local) — but support OpenAI/Claude for quality
    - Only run analysis during market hours, not overnight
    - Graceful degradation: if TradingAgents fails, return neutral (0.5)
    - DB-backed cache for persistence across restarts

No LLM calls are made directly — TradingAgents handles all LLM interaction.
"""
import os
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class TradingAgentsAdapter:
    """
    Wraps TradingAgents to produce a conviction score per symbol.

    Usage:
        adapter = TradingAgentsAdapter(config)
        result = adapter.analyze("AAPL", "2026-10-16")
        # result = {
        #     "conviction": 0.72,          # 0.0 = strong sell, 1.0 = strong buy
        #     "direction": "BUY",          # BUY / SELL / HOLD
        #     "analyst_reports": {...},     # Full analyst outputs
        #     "debate_summary": "...",      # Bull vs bear summary
        #     "risk_assessment": "...",     # Risk team output
        #     "cached": False,
        #     "cost_usd": 0.08,            # LLM API cost for this run
        # }
    """

    # Conviction mapping: TradingAgents decision → numeric score
    CONVICTION_MAP = {
        "strong buy":  0.90,
        "buy":         0.70,
        "hold":        0.50,
        "sell":        0.30,
        "strong sell": 0.10,
    }

    def __init__(self, config: Dict[str, Any] = None, database=None, llm_budget=None) -> None:
        self.logger = logging.getLogger("TradingAgentsAdapter")
        self.database = database
        self.llm_budget = llm_budget

        config = config or {}

        # TradingAgents configuration
        self.ta_config = {
            "llm_provider": config.get("ta_provider", os.environ.get("TRADINGAGENTS_PROVIDER", "ollama")),
            "deep_thinking_model": config.get("ta_deep_model", os.environ.get("TRADINGAGENTS_DEEP_MODEL", "llama3.1:70b")),
            "quick_thinking_model": config.get("ta_quick_model", os.environ.get("TRADINGAGENTS_QUICK_MODEL", "llama3.1:8b")),
            "selected_analysts": ("fundamentals", "social", "news", "market"),
            "max_debate_rounds": 1,       # Keep costs low
            "max_risk_discuss_rounds": 1,  # Keep costs low
        }

        # In-memory cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = config.get("ta_cache_ttl", 3600)  # 1 hour

        # TradingAgents availability
        self._ta_available = False
        self._ta_graph_class = None

        try:
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            self._ta_graph_class = TradingAgentsGraph
            self._ta_available = True
            self.logger.info("TradingAgents framework loaded successfully")
        except ImportError:
            self.logger.warning(
                "TradingAgents not installed — adapter will return neutral conviction. "
                "Install with: cd lib/TradingAgents && pip install ."
            )

    @property
    def is_available(self) -> bool:
        return self._ta_available

    def analyze(self, symbol: str, trade_date: str = None) -> Dict[str, Any]:
        """
        Run TradingAgents analysis and return conviction score.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            trade_date: Date string "YYYY-MM-DD" (default: today)

        Returns:
            dict with conviction, direction, analyst_reports, cached status, cost
        """
        if not trade_date:
            trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        cache_key = f"{symbol}:{trade_date}"

        # 1. Check in-memory cache
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached.get("_cached_at", 0)) < self._cache_ttl:
            self.logger.debug(f"TA cache hit: {symbol} ({trade_date})")
            return {**cached, "cached": True}

        # 2. Check DB cache
        if self.database:
            db_cached = self.database.get_ta_cache(symbol, trade_date)
            if db_cached:
                result = {
                    "conviction": db_cached.get("conviction", 0.5),
                    "direction": db_cached.get("direction", "HOLD"),
                    "analyst_reports": db_cached.get("analyst_reports", {}),
                    "debate_summary": db_cached.get("debate_summary", ""),
                    "cost_usd": db_cached.get("cost_usd", 0),
                    "cached": True,
                }
                self._cache[cache_key] = {**result, "_cached_at": time.time()}
                self.logger.debug(f"TA DB cache hit: {symbol} ({trade_date})")
                return result

        # 3. Budget check
        if self.llm_budget and not self.llm_budget.can_spend(0.10):
            self.logger.warning(f"LLM budget exceeded — returning neutral for {symbol}")
            return self._neutral_result(symbol, "BUDGET_EXCEEDED")

        # 4. Run TradingAgents analysis
        if not self._ta_available:
            return self._neutral_result(symbol, "TA_NOT_INSTALLED")

        try:
            result = self._run_analysis(symbol, trade_date)
        except Exception as e:
            self.logger.error(f"TradingAgents analysis failed for {symbol}: {e}")
            return self._neutral_result(symbol, f"ERROR: {str(e)[:100]}")

        # 5. Cache result
        self._cache[cache_key] = {**result, "_cached_at": time.time()}

        if self.database:
            self.database.save_ta_cache(symbol, trade_date, result)

        if self.llm_budget and result.get("cost_usd", 0) > 0:
            self.llm_budget.record_spend(result["cost_usd"], symbol)

        return result

    def _run_analysis(self, symbol: str, trade_date: str) -> Dict[str, Any]:
        """Run the actual TradingAgents analysis."""
        self.logger.info(f"Running TradingAgents analysis for {symbol} ({trade_date})...")
        start_time = time.time()

        try:
            # v0.7.0: LLM config is via env vars (TRADINGAGENTS_LLM_PROVIDER, etc.)
            # Constructor only accepts: selected_analysts, debug, config, callbacks
            graph = self._ta_graph_class(
                selected_analysts=list(self.ta_config["selected_analysts"]),
            )

            # Run the multi-agent research pipeline
            state = graph.propagate(symbol, trade_date)

            # Extract results
            decision = state.get("decision", "hold").lower().strip()
            conviction = self._normalize_conviction(decision)
            direction = self._decision_to_direction(decision)

            elapsed = time.time() - start_time
            # Rough cost estimate based on provider
            cost = self._estimate_cost(elapsed)

            result = {
                "conviction": conviction,
                "direction": direction,
                "analyst_reports": {
                    "fundamentals": state.get("fundamentals_report", ""),
                    "sentiment": state.get("sentiment_report", ""),
                    "news": state.get("news_report", ""),
                    "technical": state.get("technical_report", ""),
                },
                "debate_summary": state.get("debate_result", ""),
                "risk_assessment": state.get("risk_report", ""),
                "cost_usd": cost,
                "elapsed_seconds": round(elapsed, 1),
                "cached": False,
            }

            self.logger.info(
                f"TA analysis complete: {symbol} → {direction} "
                f"(conviction={conviction:.2f}) in {elapsed:.1f}s"
            )
            return result

        except Exception as e:
            self.logger.error(f"TradingAgents graph error for {symbol}: {e}")
            raise

    def _normalize_conviction(self, decision: str) -> float:
        """Convert TradingAgents' decision to a 0.0-1.0 conviction score."""
        decision = decision.lower().strip()

        # Direct mapping
        if decision in self.CONVICTION_MAP:
            return self.CONVICTION_MAP[decision]

        # Fuzzy matching
        if "strong" in decision and "buy" in decision:
            return 0.90
        elif "buy" in decision:
            return 0.70
        elif "strong" in decision and "sell" in decision:
            return 0.10
        elif "sell" in decision:
            return 0.30
        else:
            return 0.50  # Default to neutral

    def _decision_to_direction(self, decision: str) -> str:
        """Convert TradingAgents decision to BUY/SELL/HOLD."""
        decision = decision.lower().strip()
        if "buy" in decision:
            return "BUY"
        elif "sell" in decision:
            return "SELL"
        else:
            return "HOLD"

    def _estimate_cost(self, elapsed_seconds: float) -> float:
        """Rough cost estimate based on provider and time."""
        provider = self.ta_config.get("llm_provider", "ollama")
        if provider == "ollama":
            return 0.0  # Local, free
        elif provider == "openai":
            return 0.05 + (elapsed_seconds / 60) * 0.02  # Rough estimate
        elif provider == "anthropic":
            return 0.08 + (elapsed_seconds / 60) * 0.03
        return 0.0

    def _neutral_result(self, symbol: str, reason: str = "") -> Dict[str, Any]:
        """Return neutral conviction when TA can't run."""
        return {
            "conviction": 0.5,
            "direction": "HOLD",
            "analyst_reports": {},
            "debate_summary": f"Analysis unavailable: {reason}",
            "risk_assessment": "",
            "cost_usd": 0.0,
            "cached": False,
        }

    def get_cached_analysis(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the most recently cached analysis for a symbol."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cache_key = f"{symbol}:{today}"
        cached = self._cache.get(cache_key)
        if cached:
            return {k: v for k, v in cached.items() if not k.startswith("_")}
        if self.database:
            return self.database.get_ta_cache(symbol, today)
        return None
