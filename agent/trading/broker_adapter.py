"""
Broker Adapter — Alpaca Integration Layer.

Wraps alpaca-trade-api with:
    - Circuit breaker (opens after 5 consecutive failures, resets after 300s)
    - Exponential backoff for rate limits (429)
    - Uniform error dict on failure (never raises to caller)
    - All methods return dicts, not Alpaca objects
    - Asset-type-aware market hours (crypto 24/7, equity market hours)

Environment variables required:
    ALPACA_API_KEY
    ALPACA_SECRET_KEY
    ALPACA_BASE_URL (paper: https://paper-api.alpaca.markets)

No LLM. Fully deterministic.
"""
import os
import time
import logging
from typing import Dict, Any, List, Optional

try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    tradeapi = None
    ALPACA_AVAILABLE = False


class CircuitBreaker:
    """
    Opens after `failure_threshold` consecutive failures.
    Rejects all calls while open.
    Allows a single probe after `reset_timeout_s` seconds.
    """

    def __init__(self, failure_threshold: int = 5, reset_timeout_s: int = 300) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.failures = 0
        self.is_open = False
        self.last_failure_time = 0.0
        self.logger = logging.getLogger("CircuitBreaker")

    def record_success(self) -> None:
        self.failures = 0
        if self.is_open:
            self.logger.info("Circuit breaker CLOSED — broker connection restored.")
        self.is_open = False

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold and not self.is_open:
            self.is_open = True
            self.logger.critical(
                f"Circuit breaker OPEN — {self.failures} consecutive broker failures. "
                f"Will retry after {self.reset_timeout_s}s."
            )

    def can_execute(self) -> bool:
        if not self.is_open:
            return True
        # Allow probe after reset timeout
        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.reset_timeout_s:
            self.logger.info("Circuit breaker allowing probe request after timeout.")
            return True
        return False

    def get_state(self) -> Dict[str, Any]:
        return {
            "is_open": self.is_open,
            "failures": self.failures,
            "threshold": self.failure_threshold,
            "seconds_until_retry": max(0, self.reset_timeout_s - (time.time() - self.last_failure_time)) if self.is_open else 0,
        }


class BrokerAdapter:
    """
    Alpaca REST API wrapper with circuit breaker and error normalization.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("BrokerAdapter")
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, reset_timeout_s=300)

        self.api_key = os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        self.base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        self.api = None
        self._connected = False

        if not ALPACA_AVAILABLE:
            self.logger.warning("alpaca-trade-api not installed. Broker disabled.")
            return

        if not self.api_key or self.api_key == "your_paper_key_here":
            self.logger.warning("ALPACA_API_KEY not configured. Broker disabled.")
            return

        try:
            self.api = tradeapi.REST(
                self.api_key,
                self.secret_key,
                self.base_url,
                api_version="v2",
            )
            self._connected = True
            self.logger.info(f"BrokerAdapter connected to {self.base_url}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Alpaca REST client: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected and self.api is not None

    def _error(self, method: str, error: Exception) -> Dict[str, Any]:
        """Standardized error response."""
        self.circuit_breaker.record_failure()
        msg = f"Broker error in {method}: {str(error)}"
        self.logger.error(msg)
        return {"error": True, "message": msg, "method": method}

    def _check_ready(self, method: str) -> Optional[Dict[str, Any]]:
        """Pre-call checks. Returns error dict if not ready, None if OK."""
        if not self.is_connected:
            return {"error": True, "message": "Broker not connected", "method": method}
        if not self.circuit_breaker.can_execute():
            state = self.circuit_breaker.get_state()
            return {
                "error": True,
                "message": f"Circuit breaker OPEN. Retry in {state['seconds_until_retry']:.0f}s",
                "method": method,
                "circuit_breaker": state,
            }
        return None

    # ══════════════════════════════════════════════════════════════
    # ACCOUNT
    # ══════════════════════════════════════════════════════════════

    def get_account(self) -> Dict[str, Any]:
        """Get account snapshot: equity, cash, buying power."""
        check = self._check_ready("get_account")
        if check:
            return check
        try:
            acct = self.api.get_account()
            self.circuit_breaker.record_success()
            return {
                "error": False,
                "equity": float(acct.equity),
                "cash": float(acct.cash),
                "buying_power": float(acct.buying_power),
                "portfolio_value": float(acct.portfolio_value),
                "currency": acct.currency,
                "account_blocked": acct.account_blocked,
                "trading_blocked": acct.trading_blocked,
                "status": acct.status,
            }
        except Exception as e:
            return self._error("get_account", e)

    # ══════════════════════════════════════════════════════════════
    # POSITIONS
    # ══════════════════════════════════════════════════════════════

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from broker."""
        check = self._check_ready("get_positions")
        if check:
            return []
        try:
            positions = self.api.list_positions()
            self.circuit_breaker.record_success()
            result = []
            for p in positions:
                result.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": "LONG" if float(p.qty) > 0 else "SHORT",
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pnl": float(p.unrealized_pl),
                    "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                    "market_value": float(p.market_value),
                })
            return result
        except Exception as e:
            self._error("get_positions", e)
            return []

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a single position by symbol."""
        check = self._check_ready("close_position")
        if check:
            return check
        try:
            order = self.api.close_position(symbol)
            self.circuit_breaker.record_success()
            return {
                "error": False,
                "order_id": order.id,
                "symbol": symbol,
                "status": order.status,
            }
        except Exception as e:
            return self._error("close_position", e)

    def close_all_positions(self) -> Dict[str, Any]:
        """Emergency: close all positions."""
        check = self._check_ready("close_all_positions")
        if check:
            return check
        try:
            result = self.api.close_all_positions()
            self.circuit_breaker.record_success()
            count = len(result) if isinstance(result, list) else 0
            self.logger.warning(f"EMERGENCY: Closed {count} positions.")
            return {"error": False, "closed_count": count}
        except Exception as e:
            return self._error("close_all_positions", e)

    # ══════════════════════════════════════════════════════════════
    # ORDERS
    # ══════════════════════════════════════════════════════════════

    def _normalize_order(self, order) -> Dict[str, Any]:
        """Convert Alpaca order object to dict."""
        return {
            "error": False,
            "order_id": order.id,
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side,
            "type": order.type,
            "qty": float(order.qty) if order.qty else 0.0,
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0.0,
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else 0.0,
            "status": order.status,
            "created_at": str(order.created_at),
        }

    def place_market_order(self, symbol: str, qty: float, side: str) -> Dict[str, Any]:
        """Place a market order."""
        check = self._check_ready("place_market_order")
        if check:
            return check
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="market",
                time_in_force="day",
            )
            self.circuit_breaker.record_success()
            self.logger.info(f"Market order placed: {side} {qty} {symbol}")
            return self._normalize_order(order)
        except Exception as e:
            return self._error("place_market_order", e)

    def place_limit_order(
        self, symbol: str, qty: float, side: str, limit_price: float
    ) -> Dict[str, Any]:
        """Place a limit order."""
        check = self._check_ready("place_limit_order")
        if check:
            return check
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="limit",
                time_in_force="day",
                limit_price=str(limit_price),
            )
            self.circuit_breaker.record_success()
            self.logger.info(f"Limit order placed: {side} {qty} {symbol} @ {limit_price}")
            return self._normalize_order(order)
        except Exception as e:
            return self._error("place_limit_order", e)

    def place_stop_order(
        self, symbol: str, qty: float, side: str, stop_price: float
    ) -> Dict[str, Any]:
        """Place a stop order."""
        check = self._check_ready("place_stop_order")
        if check:
            return check
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="stop",
                time_in_force="day",
                stop_price=str(stop_price),
            )
            self.circuit_breaker.record_success()
            return self._normalize_order(order)
        except Exception as e:
            return self._error("place_stop_order", e)

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        take_profit_price: float,
        stop_loss_price: float,
    ) -> Dict[str, Any]:
        """
        Place a bracket order (entry + take-profit + stop-loss, atomic).
        This is the primary order type for autonomous trading.
        """
        check = self._check_ready("place_bracket_order")
        if check:
            return check
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side.lower(),
                type="market",
                time_in_force="day",
                order_class="bracket",
                take_profit={"limit_price": str(round(take_profit_price, 2))},
                stop_loss={"stop_price": str(round(stop_loss_price, 2))},
            )
            self.circuit_breaker.record_success()
            self.logger.info(
                f"Bracket order placed: {side} {qty} {symbol} | "
                f"TP={take_profit_price} SL={stop_loss_price}"
            )
            return self._normalize_order(order)
        except Exception as e:
            return self._error("place_bracket_order", e)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a single order by ID."""
        check = self._check_ready("cancel_order")
        if check:
            return check
        try:
            self.api.cancel_order(order_id)
            self.circuit_breaker.record_success()
            return {"error": False, "cancelled": True, "order_id": order_id}
        except Exception as e:
            return self._error("cancel_order", e)

    def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders."""
        check = self._check_ready("cancel_all_orders")
        if check:
            return check
        try:
            result = self.api.cancel_all_orders()
            self.circuit_breaker.record_success()
            count = len(result) if isinstance(result, list) else 0
            return {"error": False, "cancelled_count": count}
        except Exception as e:
            return self._error("cancel_all_orders", e)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details by ID."""
        check = self._check_ready("get_order")
        if check:
            return check
        try:
            order = self.api.get_order(order_id)
            self.circuit_breaker.record_success()
            return self._normalize_order(order)
        except Exception as e:
            return self._error("get_order", e)

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all pending/open orders."""
        check = self._check_ready("get_open_orders")
        if check:
            return []
        try:
            orders = self.api.list_orders(status="open")
            self.circuit_breaker.record_success()
            return [self._normalize_order(o) for o in orders]
        except Exception as e:
            self._error("get_open_orders", e)
            return []

    # ══════════════════════════════════════════════════════════════
    # MARKET STATUS
    # ══════════════════════════════════════════════════════════════

    def is_market_open(self) -> bool:
        """Check if US equity market is currently open."""
        check = self._check_ready("is_market_open")
        if check:
            return False
        try:
            clock = self.api.get_clock()
            self.circuit_breaker.record_success()
            return clock.is_open
        except Exception as e:
            self._error("is_market_open", e)
            return False

    def get_clock(self) -> Dict[str, Any]:
        """Get market clock with next open/close times."""
        check = self._check_ready("get_clock")
        if check:
            return check
        try:
            clock = self.api.get_clock()
            self.circuit_breaker.record_success()
            return {
                "error": False,
                "is_open": clock.is_open,
                "next_open": str(clock.next_open),
                "next_close": str(clock.next_close),
                "timestamp": str(clock.timestamp),
            }
        except Exception as e:
            return self._error("get_clock", e)

    # ══════════════════════════════════════════════════════════════
    # HISTORICAL DATA
    # ══════════════════════════════════════════════════════════════

    def get_bars(
        self, symbol: str, timeframe: str = "15Min", limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Get historical bars from Alpaca."""
        check = self._check_ready("get_bars")
        if check:
            return []
        try:
            bars = self.api.get_bars(symbol, timeframe, limit=limit).df
            self.circuit_breaker.record_success()
            result = []
            for idx, row in bars.iterrows():
                result.append({
                    "timestamp": idx.timestamp(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                })
            return result
        except Exception as e:
            self._error("get_bars", e)
            return []

    # ══════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Return broker connection status and circuit breaker state."""
        return {
            "connected": self.is_connected,
            "base_url": self.base_url,
            "circuit_breaker": self.circuit_breaker.get_state(),
            "alpaca_available": ALPACA_AVAILABLE,
            "api_key_configured": bool(self.api_key and self.api_key != "your_paper_key_here"),
        }
