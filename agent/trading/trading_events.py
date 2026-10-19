"""
Trading Event Emitter -- Centralized event bus for real-time
WebSocket notifications from the trading engine.

Events are queued in-memory and consumed by the WS heartbeat loop
in api_server.py. Each event follows the schema:
    { "type": "trading:<event_name>", "timestamp": ..., "data": {...} }

Supported events:
    trading:signal_fired     - New signal generated
    trading:trade_executed   - Order filled
    trading:trade_closed     - Position closed
    trading:risk_mode_change - Risk mode transition
    trading:portfolio_update - Equity snapshot saved
    trading:ta_analysis_complete - TradingAgents finished
    trading:learning_insight - New insight generated
"""
import logging
import time
from collections import deque
from typing import Any, Dict, Optional

logger = logging.getLogger("TradingEvents")


class TradingEventEmitter:
    """Thread-safe event queue for trading WebSocket notifications."""

    # Singleton instance
    _instance: Optional["TradingEventEmitter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._events = deque(maxlen=500)
            cls._instance._initialized = True
        return cls._instance

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Queue an event for broadcast."""
        event = {
            "type": f"trading:{event_type}",
            "timestamp": time.time(),
            "data": data,
        }
        self._events.append(event)
        logger.debug(f"Event queued: {event_type}")

    def drain(self) -> list:
        """Return and clear all pending events."""
        events = list(self._events)
        self._events.clear()
        return events

    def has_events(self) -> bool:
        return len(self._events) > 0

    # ── Convenience Methods ──

    def signal_fired(self, signal: dict) -> None:
        self.emit("signal_fired", {
            "symbol": signal.get("symbol", ""),
            "direction": signal.get("direction", ""),
            "strategy": signal.get("strategy_name", ""),
            "confidence": signal.get("confidence", 0),
            "entry_price": signal.get("entry_price", 0),
        })

    def trade_executed(self, order: dict) -> None:
        self.emit("trade_executed", {
            "symbol": order.get("symbol", ""),
            "side": order.get("side", ""),
            "quantity": order.get("quantity", 0),
            "fill_price": order.get("fill_price", 0),
            "order_id": order.get("order_id", ""),
        })

    def trade_closed(self, trade: dict) -> None:
        self.emit("trade_closed", {
            "symbol": trade.get("symbol", ""),
            "direction": trade.get("direction", ""),
            "net_pnl": trade.get("net_pnl", 0),
            "pnl_pct": trade.get("pnl_pct", 0),
            "exit_reason": trade.get("exit_reason", ""),
        })

    def risk_mode_change(self, old_mode: str, new_mode: str, reason: str = "") -> None:
        self.emit("risk_mode_change", {
            "old_mode": old_mode,
            "new_mode": new_mode,
            "reason": reason,
        })

    def portfolio_update(self, equity: float, drawdown: float) -> None:
        self.emit("portfolio_update", {
            "equity": equity,
            "drawdown_pct": drawdown,
        })

    def ta_analysis_complete(self, symbol: str, conviction: float, direction: str) -> None:
        self.emit("ta_analysis_complete", {
            "symbol": symbol,
            "conviction": conviction,
            "direction": direction,
        })

    def learning_insight(self, insight: str) -> None:
        self.emit("learning_insight", {
            "insight": insight,
        })


# Global singleton
trading_events = TradingEventEmitter()
