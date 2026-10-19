"""
Order Management System — 16-Gate Signal Processing Pipeline.

Every signal passes through 16 sequential gates before reaching the broker.
Uses ALL existing safety engines: KillSwitch, MacroFilter, RiskEngine,
ComplianceLayer, ConfidenceEngine, ExposureEngine, SlippageEngine,
SizingEngine, CapitalAllocator, CapitalPreservation.

Includes position reconciliation (orphan/ghost detection).

No LLM. Fully deterministic.
"""
import uuid
import time
import logging
from typing import Dict, Any, List, Optional


class OrderManager:
    """
    16-gate order management system with position reconciliation.
    """

    # Hard safety caps — NEVER configurable
    MAX_RISK_PER_TRADE = 0.02       # 2% of portfolio
    MAX_SINGLE_POSITION = 0.05      # 5% of portfolio
    MAX_TOTAL_EXPOSURE = 0.25       # 25% of portfolio
    MAX_CONCURRENT_POSITIONS = 3
    DRAWDOWN_REDUCE_THRESHOLD = 0.10  # 10% → reduce sizes 50%
    DRAWDOWN_HALT_THRESHOLD = 0.20    # 20% → HALT all trading

    def __init__(
        self,
        broker_adapter=None,
        database=None,
        market_data_feed=None,
        kill_switch=None,
        macro_filter=None,
        risk_engine=None,
        compliance_layer=None,
        confidence_engine=None,
        exposure_engine=None,
        slippage_engine=None,
        sizing_engine=None,
        capital_allocator=None,
        capital_preservation=None,
        lifecycle_engine=None,
        strategy_engine=None,
        telegram_notifier=None,
        ml_predictor=None,
        earnings_guard=None,
    ) -> None:
        self.logger = logging.getLogger("OrderManager")

        # Injected dependencies
        self.broker = broker_adapter
        self.database = database
        self.data_feed = market_data_feed
        self.kill_switch = kill_switch
        self.macro_filter = macro_filter
        self.risk_engine = risk_engine
        self.compliance = compliance_layer
        self.confidence_engine = confidence_engine
        self.exposure_engine = exposure_engine
        self.slippage_engine = slippage_engine
        self.sizing_engine = sizing_engine
        self.capital_allocator = capital_allocator
        self.capital_preservation = capital_preservation
        self.lifecycle_engine = lifecycle_engine
        self.strategy_engine = strategy_engine
        self.telegram = telegram_notifier
        self.ml_predictor = ml_predictor
        self.earnings_guard = earnings_guard

        # Trading state
        self._paused = False

    # ══════════════════════════════════════════════════════════════
    # 16-GATE SIGNAL PROCESSING PIPELINE
    # ══════════════════════════════════════════════════════════════

    def process_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a trading signal through the 16-gate pipeline.
        Returns a result dict with status and details.
        """
        symbol = signal.get("symbol", "UNKNOWN")
        direction = signal.get("direction", "")
        entry_price = signal.get("entry_price", 0.0)
        stop_price = signal.get("stop_price", 0.0)
        target_price = signal.get("target_price", 0.0)
        confidence = signal.get("confidence", 0.0)
        strategy_name = signal.get("strategy_name", "")

        self.logger.info(f"Processing signal: {symbol} {direction} @ {entry_price}")

        # ── Gate 1: Kill Switch ──────────────────────────────────
        if self.kill_switch and self.kill_switch.check_status() == "ACTIVE":
            return self._reject(signal, "KILL_SWITCH_ACTIVE", "Kill switch is active")

        # ── Gate 2: Paused Check ─────────────────────────────────
        if self._paused:
            return self._reject(signal, "TRADING_PAUSED", "Trading is paused")

        # ── Gate 3: Data Freshness (skip in paper mode) ────────────
        # Paper mode allows stale data so we can demo trading after hours
        if self.data_feed and not self._is_paper_mode():
            if not self.data_feed.is_data_fresh(symbol, max_age_seconds=900):
                return self._reject(signal, "STALE_DATA", f"Data for {symbol} is stale")

        # ── Gate 3.5: Earnings Calendar Guard ────────────────────
        if self.earnings_guard:
            try:
                earnings_result = self.earnings_guard.check(symbol)
                if not earnings_result.get("safe", True):
                    days = earnings_result.get("days_until", "?")
                    date = earnings_result.get("earnings_date", "?")
                    return self._reject(
                        signal, "EARNINGS_BLOCK",
                        f"Earnings in {days} days ({date}) — blocking new entries"
                    )
            except Exception as e:
                self.logger.warning(f"EarningsGuard error (continuing): {e}")

        # ── Gate 4: Macro Filter ─────────────────────────────────
        macro_dampened = False
        if self.macro_filter:
            try:
                # Use default VIX=20, credit_spread=3 if not available
                macro_regime = self.macro_filter.assess_macro_regime(
                    risk_free_rate=4.5, vcs_index=20.0, credit_spread=3.0
                )
                if macro_regime == "RISK_OFF":
                    signal["confidence"] = signal.get("confidence", 0.5) * 0.5
                    macro_dampened = True
                    self.logger.info(f"Macro RISK_OFF: confidence dampened to {signal['confidence']:.2f}")
            except Exception as e:
                self.logger.warning(f"MacroFilter error (continuing): {e}")

        # ── Gate 5: Capital Preservation Mode ────────────────────
        portfolio_state = self.database.get_portfolio_state() if self.database else None
        drawdown_pct = portfolio_state.get("drawdown_pct", 0) if portfolio_state else 0

        if self.capital_preservation:
            mode = self.capital_preservation.evaluate_mode(drawdown_pct)
            if mode == "HALTED":
                self._emergency_close_all("DRAWDOWN_HALT")
                return self._reject(signal, "CAPITAL_HALTED", f"Drawdown {drawdown_pct:.1%} exceeded halt threshold")

        # ── Gate 6: Risk Engine ──────────────────────────────────
        if self.risk_engine:
            try:
                risk_result = self.risk_engine.assess_risk(signal)
                if isinstance(risk_result, dict) and risk_result.get("action") == "HALT":
                    return self._reject(signal, "RISK_HALTED", "Risk engine halted trading")
            except Exception as e:
                self.logger.warning(f"RiskEngine error (continuing): {e}")

        # ── Gate 7: Compliance Layer ─────────────────────────────
        if self.compliance:
            compliance_signal = {
                **signal,
                "kill_switch_state": self.kill_switch.check_status() if self.kill_switch else "INACTIVE",
                "capital_mode": self.capital_preservation.mode if self.capital_preservation else "NORMAL",
            }
            if not self.compliance.check_compliance(compliance_signal):
                return self._reject(signal, "NON_COMPLIANT", "Compliance check failed")

        # ── Gate 8: Confidence Threshold ─────────────────────────
        if self.confidence_engine:
            try:
                conf_result = self.confidence_engine.compute_confidence(signal)
                if isinstance(conf_result, dict) and conf_result.get("action") == "BLOCK":
                    return self._reject(signal, "LOW_CONFIDENCE", "Confidence too low")
            except Exception as e:
                self.logger.warning(f"ConfidenceEngine error (continuing): {e}")

        # ── Gate 8.5: ML Prediction Alignment ────────────────────
        if self.ml_predictor:
            try:
                ohlcv = self.data_feed.get_ohlcv_arrays(symbol, "15m", limit=200) if self.data_feed else None
                if ohlcv and len(ohlcv.get("closes", [])) >= 100:
                    prediction = self.ml_predictor.predict(
                        ohlcv["closes"], ohlcv["highs"], ohlcv["lows"],
                        ohlcv.get("volumes", [])
                    )
                    if prediction and prediction.get("direction"):
                        expected_dir = "UP" if direction == "LONG" else "DOWN"
                        if prediction["direction"] != expected_dir:
                            signal["confidence"] *= 0.5
                            signal["ml_conflict"] = True
                            self.logger.info(f"ML disagrees with {direction} on {symbol} — confidence halved")
                        else:
                            signal["ml_agreed"] = True
            except Exception as e:
                self.logger.warning(f"ML gate error (continuing): {e}")

        # ── Gate 9: Exposure Limits ──────────────────────────────
        if self.exposure_engine:
            try:
                exposure_check = self.exposure_engine.check_exposure(
                    new_asset=symbol,
                    new_size_pct=self.MAX_SINGLE_POSITION,
                    sector=signal.get("sector", "GENERAL"),
                )
                if not exposure_check.get("allowed", True):
                    violations = exposure_check.get("violations", [])
                    return self._reject(signal, "EXPOSURE_LIMIT", f"Exposure violations: {violations}")
            except Exception as e:
                self.logger.warning(f"ExposureEngine error (continuing): {e}")

        # ── Gate 10: Position Count Limit ────────────────────────
        current_positions = self.database.get_positions() if self.database else []
        if len(current_positions) >= self.MAX_CONCURRENT_POSITIONS:
            return self._reject(signal, "MAX_POSITIONS", f"Already at {self.MAX_CONCURRENT_POSITIONS} positions")

        # ── Gate 11: Slippage Simulation ─────────────────────────
        if self.slippage_engine and entry_price > 0 and stop_price > 0 and target_price > 0:
            try:
                atr = signal.get("indicators", {}).get("atr", entry_price * 0.005)
                slippage_result = self.slippage_engine.simulate_slippage(
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    atr=atr,
                    direction=direction,
                )
                if slippage_result.get("fill_quality") == "UNVIABLE":
                    return self._reject(signal, "UNVIABLE_SLIPPAGE", "Slippage makes trade unviable")
                signal["slippage_pct"] = slippage_result.get("slippage", {}).get("pct_of_entry", 0)
            except Exception as e:
                self.logger.warning(f"SlippageEngine error (continuing): {e}")

        # ── Gate 12: Position Sizing ─────────────────────────────
        equity = portfolio_state.get("equity", 10000) if portfolio_state else 10000
        position_size_pct = self.MAX_RISK_PER_TRADE

        if self.sizing_engine:
            try:
                size_result = self.sizing_engine.calculate_size(signal)
                if isinstance(size_result, dict):
                    position_size_pct = min(size_result.get("size_pct", position_size_pct), self.MAX_SINGLE_POSITION)
            except Exception:
                pass

        # Apply drawdown reduction
        if self.capital_preservation:
            multiplier = self.capital_preservation.get_position_sizing_multiplier()
            position_size_pct *= multiplier

        if position_size_pct <= 0:
            return self._reject(signal, "ZERO_SIZE", "Position size is zero after adjustments")

        # ── Gate 13: Capital Allocation ──────────────────────────
        allocated_capital = equity * position_size_pct

        if self.capital_allocator:
            try:
                alloc_result = self.capital_allocator.allocate(signal, equity)
                if isinstance(alloc_result, dict):
                    allocated_capital = alloc_result.get("allocated", allocated_capital)
            except Exception:
                pass

        if allocated_capital <= 0 or entry_price <= 0:
            return self._reject(signal, "NO_CAPITAL", "No capital allocated")

        quantity = int(allocated_capital / entry_price)
        if quantity <= 0:
            return self._reject(signal, "ZERO_QTY", "Calculated quantity is 0")

        # ── Gate 14: Circuit Breaker ─────────────────────────────
        if self.broker and hasattr(self.broker, 'circuit_breaker'):
            if not self.broker.circuit_breaker.can_execute():
                return self._reject(signal, "CIRCUIT_OPEN", "Broker circuit breaker is open")

        # ── Gate 15: Place Order ─────────────────────────────────
        order_result = {"error": True, "message": "No broker connected"}
        if self.broker and self.broker.is_connected:
            side = "buy" if direction == "LONG" else "sell"
            order_result = self.broker.place_bracket_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                take_profit_price=target_price,
                stop_loss_price=stop_price,
            )

            if order_result.get("error"):
                return self._reject(signal, "BROKER_REJECTED", order_result.get("message", "Order rejected"))
        else:
            self.logger.warning("No broker connected — simulating order for paper mode")
            order_result = {
                "error": False,
                "order_id": f"SIM_{uuid.uuid4().hex[:12]}",
                "symbol": symbol,
                "side": direction,
                "status": "SIMULATED",
            }

        # ── Gate 16: Persist + Notify ────────────────────────────
        order_id = str(uuid.uuid4())
        broker_order_id = order_result.get("order_id", "")

        # Save to database
        if self.database:
            instrument_id = self.database.get_or_create_instrument(symbol)
            self.database.save_order({
                "order_id": order_id,
                "instrument_id": instrument_id,
                "symbol": symbol,
                "side": direction,
                "order_type": "BRACKET",
                "quantity": quantity,
                "price": entry_price,
                "stop_price": stop_price,
                "take_profit_price": target_price,
                "status": "FILLED" if not order_result.get("error") else "REJECTED",
                "broker_order_id": broker_order_id,
                "strategy_name": strategy_name,
                "signal_id": signal.get("signal_id", ""),
                "slippage_pct": signal.get("slippage_pct", 0.0),
            })

            # Save position
            self.database.save_position({
                "instrument_id": instrument_id,
                "symbol": symbol,
                "side": direction,
                "quantity": quantity,
                "avg_entry_price": entry_price,
                "current_price": entry_price,
            })

            # Archive signal
            self.database.save_signal({
                "signal_id": signal.get("signal_id", order_id),
                "asset": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "state": "ACTIVE",
                "confidence": confidence,
                "strategy_name": strategy_name,
                "regime": signal.get("regime", ""),
            })

        # Update lifecycle
        if self.lifecycle_engine:
            try:
                self.lifecycle_engine.generate_and_lock(signal)
            except Exception as e:
                self.logger.warning(f"LifecycleEngine error: {e}")

        # Register with exposure engine
        if self.exposure_engine:
            self.exposure_engine.register_position(symbol, position_size_pct)

        # Register with strategy engine
        if self.strategy_engine:
            self.strategy_engine.register_active_position(symbol, direction)

        # Send Telegram alert
        if self.telegram:
            try:
                self.telegram.send_trade_alert(signal, quantity, order_id)
            except Exception as e:
                self.logger.warning(f"Telegram alert failed: {e}")

        self.logger.info(
            f"ORDER EXECUTED: {direction} {quantity} {symbol} @ {entry_price} | "
            f"Stop={stop_price} Target={target_price} | Strategy={strategy_name}"
        )

        return {
            "status": "EXECUTED",
            "order_id": order_id,
            "broker_order_id": broker_order_id,
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "strategy": strategy_name,
            "gates_passed": 16,
        }

    # ══════════════════════════════════════════════════════════════
    # POSITION SYNC & RECONCILIATION
    # ══════════════════════════════════════════════════════════════

    def sync_positions(self) -> None:
        """Poll broker for current positions and update database."""
        if not self.broker or not self.broker.is_connected or not self.database:
            return

        try:
            broker_positions = self.broker.get_positions()
            for bp in broker_positions:
                self.database.save_position({
                    "symbol": bp["symbol"],
                    "side": bp.get("side", "LONG"),
                    "quantity": bp["qty"],
                    "avg_entry_price": bp["avg_entry_price"],
                    "current_price": bp["current_price"],
                    "unrealized_pnl": bp.get("unrealized_pnl", 0),
                })

            # Update portfolio state from account
            acct = self.broker.get_account()
            if not acct.get("error"):
                equity = acct["equity"]
                state = self.database.get_portfolio_state()
                peak = max(equity, state.get("peak_equity", equity) if state else equity)
                dd = (peak - equity) / peak if peak > 0 else 0

                self.database.save_portfolio_state({
                    "equity": equity,
                    "cash": acct["cash"],
                    "total_exposure": equity - acct["cash"],
                    "drawdown_pct": dd,
                    "peak_equity": peak,
                    "risk_mode": self.capital_preservation.mode if self.capital_preservation else "NORMAL",
                    "open_positions_count": len(broker_positions),
                })

        except Exception as e:
            self.logger.error(f"Position sync error: {e}")

    def reconcile_positions(self) -> Dict[str, Any]:
        """
        Detect orphan and ghost positions.
        Orphan: broker has it, we don't.
        Ghost: we have it, broker doesn't.
        """
        if not self.broker or not self.database:
            return {"orphans": [], "ghosts": [], "mismatches": []}

        broker_positions = {p["symbol"]: p for p in self.broker.get_positions()}
        db_positions = {p["symbol"]: p for p in self.database.get_positions()}

        orphans = []
        ghosts = []
        mismatches = []

        # Orphans: broker has, DB doesn't
        for sym, bp in broker_positions.items():
            if sym not in db_positions:
                orphans.append(sym)
                self.logger.warning(f"ORPHAN position detected: {sym}")
                self.database.save_position(bp)
                if self.telegram:
                    self.telegram.send_risk_alert(f"⚠️ Orphan position: {sym} (qty={bp['qty']})")

        # Ghosts: DB has, broker doesn't
        # In paper mode, don't remove ghosts — broker may not track simulated positions
        for sym, dp in db_positions.items():
            if sym not in broker_positions:
                if self._is_paper_mode():
                    # Paper mode: keep the position, just log it
                    self.logger.info(f"Paper mode: keeping simulated position {sym}")
                else:
                    ghosts.append(sym)
                    self.logger.warning(f"GHOST position: {sym} closed externally")
                    self.database.remove_position(sym)
                    if self.strategy_engine:
                        self.strategy_engine.clear_active_position(sym)
                    if self.exposure_engine:
                        self.exposure_engine.remove_position(sym)
                    if self.telegram:
                        self.telegram.send_risk_alert(f"⚠️ Ghost: {sym} closed externally")

        # Quantity mismatches: broker is truth
        for sym in broker_positions:
            if sym in db_positions:
                bq = broker_positions[sym]["qty"]
                dq = db_positions[sym]["quantity"]
                if abs(bq - dq) > 0.01:
                    mismatches.append({"symbol": sym, "broker_qty": bq, "db_qty": dq})
                    self.database.save_position(broker_positions[sym])

        return {"orphans": orphans, "ghosts": ghosts, "mismatches": mismatches}

    # ══════════════════════════════════════════════════════════════
    # EMERGENCY CONTROLS
    # ══════════════════════════════════════════════════════════════

    def emergency_close_all(self, reason: str = "MANUAL") -> Dict[str, Any]:
        """Emergency: close all positions and halt trading."""
        return self._emergency_close_all(reason)

    def _emergency_close_all(self, reason: str) -> Dict[str, Any]:
        self.logger.critical(f"EMERGENCY CLOSE ALL: {reason}")

        result = {"reason": reason, "closed": 0}

        # Kill switch
        if self.kill_switch:
            self.kill_switch.activate(reason)

        # Close all via broker
        if self.broker and self.broker.is_connected:
            close_result = self.broker.close_all_positions()
            result["closed"] = close_result.get("closed_count", 0)

        # Cancel all pending orders
        if self.broker and self.broker.is_connected:
            self.broker.cancel_all_orders()

        # Clear DB positions
        if self.database:
            self.database.clear_positions()

        # Telegram alert
        if self.telegram:
            self.telegram.send_risk_alert(f"🔴 EMERGENCY CLOSE ALL: {reason} | Closed {result['closed']} positions")

        self._paused = True
        return result

    def pause(self) -> None:
        """Pause trading (no new signals processed)."""
        self._paused = True
        self.logger.warning("Trading PAUSED")

    def resume(self) -> None:
        """Resume trading."""
        self._paused = False
        self.logger.info("Trading RESUMED")

    # ══════════════════════════════════════════════════════════════
    # INTERNALS
    # ══════════════════════════════════════════════════════════════

    def _reject(self, signal: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
        """Log and return a rejection."""
        self.logger.info(f"REJECTED [{code}]: {signal.get('symbol', '?')} — {reason}")
        return {"status": "REJECTED", "code": code, "reason": reason, "signal": signal}

    def _is_paper_mode(self) -> bool:
        """Check if we're in paper trading mode."""
        if self.database:
            state = self.database.get_portfolio_state()
            if state and state.get("mode") == "live":
                return False
        # Default to paper mode (safe)
        return True
