"""
Autonomous Trading Loop — 24/7 Main Orchestrator.

Wires ALL engines together into a single, self-running trading system.
Candle-close-aligned scheduling (fires at :00, :15, :30, :45).

Startup: pre-flight → backtest validation → sync → pattern load → go.
Loop: fetch → regime → strategies → OMS 16-gate → sync → reconcile.
Shutdown: save state → save patterns → notify → exit.

No LLM. Fully deterministic.
"""
import os
import time
import logging
import logging.handlers
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from agent.trading.trading_events import trading_events as _trading_events
except ImportError:
    _trading_events = None


class AutonomousTradingLoop:
    """
    24/7 autonomous trading orchestrator.
    """

    DEFAULT_CONFIG = {
        "mode": "paper",
        "market": "USA", # "USA" or "IND"
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ"],
        "usa_symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ"],
        "ind_symbols": ["NIFTY 50", "RELIANCE", "TCS", "HDFCBANK", "INFY", "SBIN"],
        "timeframes": ["15m"],
        "max_positions": 3,
        "max_risk_per_trade": 0.02,
        "max_portfolio_exposure": 0.25,
        "initial_capital": 10000,
        "strategies_enabled": ["trend_following", "mean_reversion", "breakout", "faiss_pattern"],
        "demo_mode": False,  # Fast loop for live demos only (separate from paper mode)
    }

    def __init__(self, config: Dict[str, Any] = None) -> None:
        self.logger = logging.getLogger("AutonomousLoop")
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self._shutdown = False
        self._thread: Optional[threading.Thread] = None
        self._bar_counter = 0  # Global bar counter for anti-whipsaw

        # ── Setup file logging ──────────────────────────────────
        self._setup_file_logging()

        # ── Initialize all subsystems ───────────────────────────
        self._init_subsystems()

        self.logger.info(f"AutonomousTradingLoop initialized | Mode: {self.config['mode']} | Market: {self.config['market']}")

    def set_market(self, market: str) -> None:
        """Switch the active market and symbol list."""
        market = market.upper()
        if market not in ["USA", "IND"]:
            return
        
        self.config["market"] = market
        self.config["symbols"] = self.config[f"{market.lower()}_symbols"]
        self.logger.info(f"Market switched to {market}. Tracking {len(self.config['symbols'])} symbols.")
        
        # Sync market context to data feed for proper routing
        if hasattr(self, 'data_feed'):
            self.data_feed.set_active_market(market)
        
        # Trigger an immediate background backfill for the new symbols so the UI loads quickly
        if hasattr(self, 'data_feed'):
            import threading
            def bg_backfill():
                for sym in self.config["symbols"]:
                    self.data_feed.backfill_historical(sym, self.config["timeframes"][0], days=30)
            threading.Thread(target=bg_backfill, daemon=True).start()

    def _setup_file_logging(self) -> None:
        """Persistent rotating file log (50MB × 5 backups)."""
        log_dir = Path(__file__).resolve().parent.parent.parent / "agent_data"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "trading.log"

        handler = logging.handlers.RotatingFileHandler(
            str(log_file), maxBytes=50_000_000, backupCount=5, encoding="utf-8"
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logging.getLogger("").addHandler(handler)

    def _init_subsystems(self) -> None:
        """Initialize all trading subsystems with graceful fallbacks."""

        # Phase 1: Database
        from agent.trading.database import TradingDatabase
        self.database = TradingDatabase()

        # Phase 2: Broker + Data
        from agent.trading.broker_adapter import BrokerAdapter
        self.broker = BrokerAdapter()

        # Phase 2b: Upstox Adapter (Indian Market)
        self.upstox = None
        try:
            from agent.trading.upstox_adapter import UpstoxAdapter
            self.upstox = UpstoxAdapter()
            if self.upstox.is_connected:
                self.logger.info("UpstoxAdapter connected — Indian market data available")
            else:
                self.logger.info(
                    f"UpstoxAdapter initialized — awaiting OAuth login. "
                    f"Visit: {self.upstox.get_login_url()}"
                )
        except Exception as e:
            self.logger.warning(f"UpstoxAdapter init failed (Indian data unavailable): {e}")

        from agent.trading.market_data_feed import MarketDataFeed
        self.data_feed = MarketDataFeed(
            broker_adapter=self.broker,
            database=self.database,
            upstox_adapter=self.upstox,
        )
        # Sync market context
        self.data_feed.set_active_market(self.config.get("market", "USA"))

        # Existing engines (all imports are safe — they exist)
        from agent.trading.indicators_engine import IndicatorsEngine
        from agent.trading.regime_switcher import RegimeSwitcher
        from agent.trading.kill_switch import KillSwitch
        from agent.trading.macro_filter import MacroFilter
        from agent.trading.risk_engine import RiskEngine
        from agent.trading.compliance_layer import ComplianceLayer
        from agent.trading.confidence_engine import ConfidenceEngine
        from agent.trading.exposure_engine import ExposureEngine
        from agent.trading.slippage_engine import SlippageEngine
        from agent.trading.sizing_engine import SizingEngine
        from agent.trading.capital_allocator import CapitalAllocator
        from agent.trading.capital_preservation import CapitalPreservation
        from agent.trading.lifecycle_engine import LifecycleEngine

        self.indicators = IndicatorsEngine()
        self.regime_switcher = RegimeSwitcher()
        self.kill_switch = KillSwitch()
        self.macro_filter = MacroFilter()
        self.risk_engine = RiskEngine()
        self.compliance = ComplianceLayer()
        self.confidence_engine = ConfidenceEngine()
        self.exposure_engine = ExposureEngine()
        self.slippage_engine = SlippageEngine()
        self.sizing_engine = SizingEngine()
        self.capital_allocator = CapitalAllocator()
        self.capital_preservation = CapitalPreservation()
        self.lifecycle_engine = LifecycleEngine(
            event_emitter=lambda event: self.logger.debug(f"Lifecycle event: {event.get('event_type', '?')}")
        )

        # Optional engines (may fail to import)
        self.feature_engine = None
        self.similarity_engine = None
        self.pattern_store = None
        self.probability_engine = None
        self.mtf_fusion = None
        self.bias_engine = None
        self.performance_monitor = None
        self.universe_manager = None
        self.screener = None
        self.ml_predictor = None
        self.learning_engine = None
        self.earnings_guard = None
        self.ta_adapter = None
        self.llm_budget = None
        self.llm_reviewer = None
        self.report_generator = None

        try:
            from agent.trading.feature_engine import FeatureEngine
            self.feature_engine = FeatureEngine()
        except Exception:
            pass

        try:
            from agent.trading.similarity_engine import SimilarityEngine
            self.similarity_engine = SimilarityEngine()
        except Exception:
            pass

        try:
            from agent.trading.pattern_store import PatternStore
            self.pattern_store = PatternStore()
        except Exception:
            pass

        try:
            from agent.trading.probability_engine import ProbabilityEngine
            self.probability_engine = ProbabilityEngine()
        except Exception:
            pass

        try:
            from agent.trading.performance_monitor import PerformanceMonitor
            self.performance_monitor = PerformanceMonitor(max_faiss_ram_gb=8.0)
        except Exception:
            pass

        try:
            from agent.trading.universe_manager import UniverseManager
            self.universe_manager = UniverseManager()
        except Exception:
            pass

        try:
            from agent.trading.screener_engine import ScreenerEngine
            self.screener = ScreenerEngine()
        except Exception:
            pass

        try:
            from agent.trading.ml_predictor import MLPredictor
            self.ml_predictor = MLPredictor()
            self.logger.info("MLPredictor initialized")
        except Exception as e:
            self.logger.warning(f"MLPredictor init failed (continuing without ML): {e}")

        try:
            from agent.trading.learning_engine import LearningEngine
            self.learning_engine = LearningEngine(database=self.database)
            self.logger.info("LearningEngine initialized")
        except Exception as e:
            self.logger.warning(f"LearningEngine init failed: {e}")

        try:
            from agent.trading.earnings_guard import EarningsGuard
            self.earnings_guard = EarningsGuard()
            self.logger.info("EarningsGuard initialized")
        except Exception as e:
            self.logger.warning(f"EarningsGuard init failed: {e}")

        try:
            from agent.trading.llm_budget import LLMBudget
            self.llm_budget = LLMBudget(database=self.database)
            self.logger.info("LLMBudget initialized")
        except Exception as e:
            self.logger.warning(f"LLMBudget init failed: {e}")

        try:
            from agent.trading.ta_adapter import TradingAgentsAdapter
            self.ta_adapter = TradingAgentsAdapter(
                config=self.config, database=self.database, llm_budget=self.llm_budget
            )
            self.logger.info("TradingAgentsAdapter initialized")
        except Exception as e:
            self.logger.warning(f"TradingAgentsAdapter init failed: {e}")

        try:
            from agent.trading.llm_reviewer import LLMPreTradeReviewer
            self.llm_reviewer = LLMPreTradeReviewer()
            self.logger.info("LLMPreTradeReviewer initialized")
        except Exception as e:
            self.logger.warning(f"LLMPreTradeReviewer init failed: {e}")

        try:
            from agent.trading.report_generator import ReportGenerator
            self.report_generator = ReportGenerator(
                database=self.database, learning_engine=self.learning_engine
            )
            self.logger.info("ReportGenerator initialized")
        except Exception as e:
            self.logger.warning(f"ReportGenerator init failed: {e}")

        # Phase 3: Strategy Engine
        from agent.trading.strategy_engine import StrategyEngine
        self.strategy_engine = StrategyEngine(
            indicators_engine=self.indicators,
            regime_switcher=self.regime_switcher,
            feature_engine=self.feature_engine,
            similarity_engine=self.similarity_engine,
            pattern_store=self.pattern_store,
            probability_engine=self.probability_engine,
        )

        # Phase 4: Telegram + Pattern Builder
        from agent.trading.telegram_trading import TelegramTradingNotifier
        self.telegram = TelegramTradingNotifier(
            database=self.database,
            kill_switch=self.kill_switch,
        )

        from agent.trading.pattern_builder import PatternDatabaseBuilder
        self.pattern_builder = PatternDatabaseBuilder(
            market_data_feed=self.data_feed,
            feature_engine=self.feature_engine,
            pattern_store=self.pattern_store,
            similarity_engine=self.similarity_engine,
            regime_switcher=self.regime_switcher,
            indicators_engine=self.indicators,
        )

        # Phase 3: Order Manager (needs everything above)
        from agent.trading.order_manager import OrderManager
        self.order_manager = OrderManager(
            broker_adapter=self.broker,
            database=self.database,
            market_data_feed=self.data_feed,
            kill_switch=self.kill_switch,
            macro_filter=self.macro_filter,
            risk_engine=self.risk_engine,
            compliance_layer=self.compliance,
            confidence_engine=self.confidence_engine,
            exposure_engine=self.exposure_engine,
            slippage_engine=self.slippage_engine,
            sizing_engine=self.sizing_engine,
            capital_allocator=self.capital_allocator,
            capital_preservation=self.capital_preservation,
            lifecycle_engine=self.lifecycle_engine,
            strategy_engine=self.strategy_engine,
            telegram_notifier=self.telegram,
            ml_predictor=self.ml_predictor,
            earnings_guard=self.earnings_guard,
        )

        # Wire order manager back into telegram
        self.telegram.order_manager = self.order_manager

    # ══════════════════════════════════════════════════════════════
    # PRE-FLIGHT CHECKS
    # ══════════════════════════════════════════════════════════════

    def _preflight_checks(self) -> bool:
        """Validate all systems before starting to trade."""
        self.logger.info("Running pre-flight checks...")
        checks = {}

        # 1. Database writable
        checks["database"] = self.database.test_write()

        # 2. Broker reachable
        acct = self.broker.get_account()
        checks["broker"] = not acct.get("error", True) if isinstance(acct, dict) else False

        # 3. Telegram reachable
        checks["telegram"] = self.telegram.send_test()

        # 4. Sufficient buying power
        if checks["broker"]:
            checks["buying_power"] = acct.get("buying_power", 0) > 100
        else:
            checks["buying_power"] = False

        # 5. Memory OK
        if self.performance_monitor:
            mem = self.performance_monitor.enforce_memory_budget()
            checks["memory"] = not mem.get("breached", False)
        else:
            checks["memory"] = True

        # Log results
        failed = [k for k, v in checks.items() if not v]
        passed = [k for k, v in checks.items() if v]

        self.logger.info(f"Pre-flight PASSED: {passed}")
        if failed:
            self.logger.error(f"Pre-flight FAILED: {failed}")
            self.telegram.send_error(f"Pre-flight FAILED: {failed}")
            return False

        self.logger.info("All pre-flight checks passed ✅")
        return True

    # ══════════════════════════════════════════════════════════════
    # STARTUP
    # ══════════════════════════════════════════════════════════════

    def start(self) -> None:
        """Start the autonomous trading loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            self.logger.warning("Trading loop already running")
            return

        self._shutdown = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="TradingLoop")
        self._thread.start()
        self.logger.info("Autonomous trading loop started")

    def _run(self) -> None:
        """Main execution — startup sequence then infinite loop."""
        try:
            self._startup_sequence()
            self._main_loop()
        except Exception as e:
            self.logger.critical(f"Trading loop crashed: {e}", exc_info=True)
            self.telegram.send_error(f"CRASH: {str(e)}")
        finally:
            self._shutdown_sequence()

    def _startup_sequence(self) -> None:
        """Initialize state before entering the main loop."""
        self.logger.info("═══ STARTUP SEQUENCE ═══")

        # 1. Load portfolio state
        state = self.database.get_portfolio_state()
        if not state or state.get("equity", 0) == 0:
            self.database.save_portfolio_state({
                "equity": self.config["initial_capital"],
                "cash": self.config["initial_capital"],
                "peak_equity": self.config["initial_capital"],
                "risk_mode": "NORMAL",
            })
            self.logger.info(f"Initialized portfolio: ${self.config['initial_capital']}")

        # 2. Sync + reconcile positions
        self.order_manager.sync_positions()
        recon = self.order_manager.reconcile_positions()
        self.logger.info(f"Reconciliation: {recon}")

        # 3. Register symbols in universe
        if self.universe_manager:
            for sym in self.config["symbols"]:
                asset_type = "CRYPTO" if "/" in sym else "EQUITY"
                self.universe_manager.add_instrument(
                    symbol=sym, exchange="US", asset_type=asset_type
                )

        # 4. Resume active signals
        active_signals = self.database.get_active_signals()
        for sig in active_signals:
            self.strategy_engine.register_active_position(sig["asset"], sig["direction"])
        self.logger.info(f"Resumed {len(active_signals)} active signals")

        # 5. Pre-flight checks
        if not self._preflight_checks():
            self.logger.warning("Pre-flight failed — continuing in degraded mode")

        # 6. Send startup notification
        state = self.database.get_portfolio_state()
        equity = state.get("equity", self.config["initial_capital"]) if state else self.config["initial_capital"]
        self.telegram.send_startup(self.config["mode"], equity)

        self.logger.info("=== STARTUP COMPLETE ===")

        # 7. Pre-market analysis (runs TradingAgents on all symbols if available)
        self._pre_market_analysis()

    # ══════════════════════════════════════════════════════════════
    # PRE-MARKET ANALYSIS
    # ══════════════════════════════════════════════════════════════

    def _pre_market_analysis(self) -> None:
        """
        Run TradingAgents analysis on all monitored symbols at startup.

        This provides initial conviction scores that are cached for the day.
        If TA adapter is not available (TradingAgents not installed), this
        is a no-op and signals will use default neutral conviction.
        """
        if not self.ta_adapter:
            self.logger.info("Pre-market analysis: TA adapter not available, skipping")
            return

        symbols = self.config.get("symbols", [])
        self.logger.info(f"Pre-market analysis: analyzing {len(symbols)} symbols via TradingAgents...")

        for symbol in symbols:
            try:
                result = self.ta_adapter.analyze(symbol)
                if result:
                    conviction = result.get("conviction", 0.5)
                    direction = result.get("direction", "HOLD")
                    self.logger.info(
                        f"  {symbol}: conviction={conviction:.2f} direction={direction}"
                    )
                    if _trading_events:
                        _trading_events.ta_analysis_complete(symbol, conviction, direction)
            except Exception as e:
                self.logger.warning(f"  {symbol}: TA analysis failed: {e}")

        self.logger.info("Pre-market analysis complete")

    # ══════════════════════════════════════════════════════════════
    # MAIN LOOP (candle-close-aligned)
    # ══════════════════════════════════════════════════════════════

    def _main_loop(self) -> None:
        """
        Infinite trading loop, aligned to candle close times.
        """
        self.logger.info("Entering main trading loop...")

        while not self._shutdown:
            try:
                # Sleep until next candle close
                sleep_s = self.data_feed.seconds_until_next_candle_close("15m")
                # Demo mode: fast loop (30s) for live demonstrations only
                if self.config.get("demo_mode"):
                    sleep_s = 30
                else:
                    # Both paper and live use proper candle-close alignment
                    sleep_s = max(sleep_s, 5)  # Minimum 5 seconds
                    sleep_s = min(sleep_s, 900)  # Maximum 15 minutes

                self.logger.debug(f"Sleeping {sleep_s}s until next candle close")

                # Interruptible sleep
                for _ in range(sleep_s):
                    if self._shutdown:
                        return
                    time.sleep(1)

                # Memory guard
                if self.performance_monitor:
                    mem = self.performance_monitor.enforce_memory_budget()
                    if mem.get("breached"):
                        self.order_manager.emergency_close_all("MEMORY_LIMIT_BREACH")
                        self.logger.critical("Memory budget breached — halting")
                        return

                # Increment bar counter
                self._bar_counter += 1

                # Process each symbol
                self._process_symbols()

                # Sync positions with broker
                self.order_manager.sync_positions()

                # Periodic reconciliation (every 5th cycle)
                if self._bar_counter % 5 == 0:
                    self.order_manager.reconcile_positions()

                # Periodic tasks
                if self._bar_counter % 4 == 0:  # Every hour (4 × 15min)
                    self._hourly_tasks()

                if self._is_daily_close():
                    self._daily_tasks()

            except Exception as e:
                self.logger.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(30)  # Backoff on error

    def _process_symbols(self) -> None:
        """Evaluate all symbols through the strategy+OMS pipeline."""
        for symbol in self.config["symbols"]:
            try:
                # Asset type detection
                asset_type = "CRYPTO" if "/" in symbol else "EQUITY"

                # Market hours check (paper mode bypasses market hours)
                if not self.data_feed.should_trade(symbol, asset_type, mode=self.config.get("mode", "paper")):
                    continue

                # Data freshness check
                # First try to get fresh bars
                bars = self.data_feed.get_latest_bars(symbol, "15m", limit=200)
                if not bars or len(bars) < 50:
                    continue

                # Build OHLCV arrays
                ohlcv = self.data_feed.get_ohlcv_arrays(symbol, "15m", limit=200)
                if not ohlcv.get("closes") or len(ohlcv["closes"]) < 50:
                    continue

                # Detect regime
                regime = "QUIET"
                try:
                    regime = self.regime_switcher.detect_regime(
                        highs=ohlcv["highs"],
                        lows=ohlcv["lows"],
                        closes=ohlcv["closes"],
                    )
                except Exception:
                    pass

                # Evaluate strategies
                signals = self.strategy_engine.evaluate_all_strategies(
                    symbol=symbol,
                    ohlcv=ohlcv,
                    regime=regime,
                    current_bar_index=self._bar_counter,
                    strategies_enabled=self.config["strategies_enabled"],
                )

                # Process signals through 16-gate OMS
                for signal in signals:
                    # Enrich signal with multi-source data
                    signal = self._enrich_signal(signal, symbol, regime)

                    result = self.order_manager.process_signal(signal)
                    if result.get("status") == "EXECUTED":
                        self.logger.info(f"Trade executed: {symbol} {signal['direction']}")
                        if _trading_events:
                            _trading_events.signal_fired(signal)
                            _trading_events.trade_executed(result)

            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {e}")

    def _hourly_tasks(self) -> None:
        """Tasks that run every hour."""
        try:
            # Incremental pattern update
            for sym in self.config["symbols"][:3]:
                self.pattern_builder.update_incremental(sym, "15m")
        except Exception as e:
            self.logger.error(f"Hourly pattern update error: {e}")

        # Equity snapshot for charting
        try:
            state = self.database.get_portfolio_state()
            if state and self.database:
                self.database.save_equity_snapshot({
                    "timestamp": time.time(),
                    "equity": state.get("equity", 0),
                    "cash": state.get("cash", 0),
                    "drawdown_pct": state.get("drawdown_pct", 0),
                    "open_positions": state.get("open_positions_count", 0),
                    "risk_mode": state.get("risk_mode", "NORMAL"),
                })
        except Exception as e:
            self.logger.error(f"Equity snapshot error: {e}")

        # Process closed trades through learning engine
        try:
            self._process_closed_trades_for_learning()
        except Exception as e:
            self.logger.error(f"Learning engine update error: {e}")

    def _daily_tasks(self) -> None:
        """Tasks that run at market close."""
        try:
            state = self.database.get_portfolio_state()
            stats = self.database.get_trade_stats()
            if state and stats:
                self.telegram.send_daily_summary(state, stats)
        except Exception as e:
            self.logger.error(f"Daily summary error: {e}")

        # Generate daily HTML report
        try:
            if self.report_generator:
                filepath = self.report_generator.generate_daily_report()
                if filepath:
                    self.logger.info(f"Daily report saved: {filepath}")
                    # Send text summary via telegram
                    summary = self.report_generator.get_report_summary_text()
                    self.telegram.send_message(summary)
        except Exception as e:
            self.logger.error(f"Daily report error: {e}")

        # Log learning insights
        try:
            if self.learning_engine:
                insights = self.learning_engine.get_insights()
                for insight in insights[:5]:
                    self.logger.info(f"Learning insight: {insight}")
        except Exception as e:
            self.logger.error(f"Learning insights error: {e}")

        # Log LLM budget status
        try:
            if self.llm_budget:
                budget = self.llm_budget.get_budget_status()
                self.logger.info(f"LLM budget: spent=${budget['daily_spent']:.4f}, remaining=${budget['daily_remaining']:.4f}")
        except Exception as e:
            self.logger.error(f"Budget status error: {e}")

        # Check holdings near earnings and send Telegram alert
        try:
            if self.earnings_guard:
                positions = self.database.get_positions()
                held = [p.get("symbol", "") for p in positions if p.get("symbol")]
                if held:
                    at_risk = self.earnings_guard.alert_holdings_near_earnings(
                        held, self.telegram
                    )
                    if at_risk:
                        self.logger.warning(
                            f"Earnings alert: {len(at_risk)} positions near earnings"
                        )
        except Exception as e:
            self.logger.error(f"Earnings alert error: {e}")

    def _is_daily_close(self) -> bool:
        """Check if it's near US market close (4 PM ET)."""
        try:
            now = datetime.now(timezone.utc)
            # US market close is ~20:00 UTC (4 PM ET during EDT)
            return now.hour == 20 and now.minute < 15
        except Exception:
            return False

    # ══════════════════════════════════════════════════════════════
    # SHUTDOWN
    # ══════════════════════════════════════════════════════════════

    def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        self.logger.info("Stop requested...")
        self._shutdown = True
        if self._thread:
            self._thread.join(timeout=30)
            self.logger.info("Trading loop stopped")

    def _shutdown_sequence(self) -> None:
        """Save all state and notify."""
        self.logger.info("═══ SHUTDOWN SEQUENCE ═══")
        try:
            self.order_manager.sync_positions()
            self.database.save_portfolio_state(
                self.database.get_portfolio_state() or {}
            )
            self.telegram.send_shutdown()
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")
        self.logger.info("═══ SHUTDOWN COMPLETE ═══")

    # ══════════════════════════════════════════════════════════════
    # STATUS
    # ══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        status = {
            "running": self._thread.is_alive() if self._thread else False,
            "shutdown_requested": self._shutdown,
            "mode": self.config["mode"],
            "bar_counter": self._bar_counter,
            "symbols": self.config["symbols"],
            "strategies": self.config["strategies_enabled"],
            "broker": self.broker.get_status() if self.broker else {},
            "portfolio": self.database.get_portfolio_state() if self.database else {},
            "db_stats": self.database.get_db_stats() if self.database else {},
        }

        # Add new engine statuses
        if self.llm_budget:
            status["llm_budget"] = self.llm_budget.get_budget_status()
        if self.learning_engine:
            status["learning_insights"] = self.learning_engine.get_insights()[:3]
        if self.ta_adapter:
            status["ta_available"] = self.ta_adapter.is_available

        return status

    # ══════════════════════════════════════════════════════════════
    # SIGNAL ENRICHMENT
    # ══════════════════════════════════════════════════════════════

    def _enrich_signal(self, signal: Dict[str, Any], symbol: str, regime: str) -> Dict[str, Any]:
        """
        Enrich a raw strategy signal with:
        1. TradingAgents conviction score
        2. Learning Engine historical win rate
        3. LLM Pre-Trade Reviewer advisory
        """
        direction = signal.get("direction", "LONG")
        strategy = signal.get("strategy_name", "")

        # 1. TradingAgents conviction
        if self.ta_adapter and self.ta_adapter.is_available:
            try:
                ta_result = self.ta_adapter.analyze(symbol)
                signal["ta_conviction"] = ta_result.get("conviction", 0.5)
                signal["ta_direction"] = ta_result.get("direction", "HOLD")
            except Exception as e:
                self.logger.debug(f"TA enrichment failed: {e}")

        # 2. Historical win rate from Learning Engine
        if self.learning_engine:
            try:
                win_rate = self.learning_engine.get_historical_win_rate(strategy, regime)
                signal["historical_win_rate"] = win_rate
            except Exception as e:
                self.logger.debug(f"Learning engine lookup failed: {e}")

        # 3. LLM Pre-Trade Reviewer (advisory only)
        if self.llm_reviewer:
            try:
                review = self.llm_reviewer.review(
                    signal,
                    ta_reports=self.ta_adapter.get_cached_analysis(symbol) if self.ta_adapter else None
                )
                if not review.get("skipped") and review.get("adjustment", 0) != 0:
                    old_conf = signal.get("confidence", 0.5)
                    signal["confidence"] = max(0, old_conf + review["adjustment"])
                    signal["llm_review"] = review.get("review_text", "")
                    self.logger.info(
                        f"LLM reviewer adjusted confidence: {old_conf:.2f} → {signal['confidence']:.2f}"
                    )
            except Exception as e:
                self.logger.debug(f"LLM review failed: {e}")

        return signal

    def _process_closed_trades_for_learning(self) -> None:
        """Check for recently closed trades and feed them to the learning engine."""
        if not self.learning_engine or not self.database:
            return

        trades = self.database.get_trade_history(limit=10)
        already_learned = set()

        # Get existing lessons to avoid duplicates
        existing_lessons = self.database.get_trade_lessons(limit=100)
        for lesson in existing_lessons:
            already_learned.add(lesson.get("trade_id", ""))

        for trade in trades:
            trade_id = trade.get("trade_id", "")
            if trade_id and trade_id not in already_learned:
                try:
                    self.learning_engine.record_outcome(trade)
                    # Clear active position in StrategyEngine so new signals can fire
                    symbol = trade.get("symbol", "")
                    if symbol and self.strategy_engine:
                        self.strategy_engine.clear_active_position(symbol)
                    if _trading_events:
                        _trading_events.trade_closed(trade)
                except Exception as e:
                    self.logger.error(f"Failed to record outcome for {trade_id}: {e}")
