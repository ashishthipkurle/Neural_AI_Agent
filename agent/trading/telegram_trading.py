"""
Telegram Trading Interface — Alerts + Kill Switch.

Outbound: trade alerts, risk warnings, daily summaries, errors.
Inbound: /kill, /status, /pause, /resume, /positions, /pnl, /health.

All user-facing times converted from UTC to IST.
Uses existing Telegram bot infrastructure from agent/skills/telegram/skill.py.

No LLM. Fully deterministic.
"""
import time
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    HAS_PYTZ = True
except ImportError:
    IST = None
    HAS_PYTZ = False

try:
    from telegram import Bot
    HAS_TELEGRAM = True
except ImportError:
    Bot = None
    HAS_TELEGRAM = False


class TelegramTradingNotifier:
    """
    Trading-specific Telegram notifications and command handling.
    """

    def __init__(self, order_manager=None, database=None, kill_switch=None) -> None:
        self.logger = logging.getLogger("TelegramTrading")
        self.order_manager = order_manager
        self.database = database
        self.kill_switch = kill_switch

        self.token = os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

        self.bot = None
        if HAS_TELEGRAM and self.token:
            try:
                self.bot = Bot(token=self.token)
            except Exception as e:
                self.logger.error(f"Failed to init Telegram bot: {e}")

    # ══════════════════════════════════════════════════════════════
    # OUTBOUND ALERTS
    # ══════════════════════════════════════════════════════════════

    def send_trade_alert(
        self, signal: Dict[str, Any], quantity: int = 0, order_id: str = ""
    ) -> bool:
        """Send trade entry alert."""
        direction = signal.get("direction", "?")
        symbol = signal.get("symbol", "?")
        entry = signal.get("entry_price", 0)
        stop = signal.get("stop_price", 0)
        target = signal.get("target_price", 0)
        strategy = signal.get("strategy_name", "?")
        emoji = "🟢" if direction == "LONG" else "🔴"

        msg = (
            f"{emoji} {direction} {symbol} @ ${entry:.2f}\n"
            f"Stop: ${stop:.2f} | Target: ${target:.2f}\n"
            f"Size: {quantity} shares | Strategy: {strategy}\n"
            f"Time: {self._now_ist()}"
        )
        return self._send(msg)

    def send_close_alert(
        self, symbol: str, pnl_pct: float, net_pnl: float, r_achieved: float,
        regime: str = "", strategy: str = ""
    ) -> bool:
        """Send trade close alert."""
        emoji = "✅" if net_pnl > 0 else "❌"
        msg = (
            f"{emoji} CLOSED {symbol} {pnl_pct:+.1f}% (${net_pnl:+.2f})\n"
            f"R: {r_achieved:.1f} | Regime: {regime} | Strategy: {strategy}\n"
            f"Time: {self._now_ist()}"
        )
        return self._send(msg)

    def send_risk_alert(self, message: str) -> bool:
        """Send risk/warning alert."""
        return self._send(f"⚠️ {message}\nTime: {self._now_ist()}")

    def send_daily_summary(self, portfolio_state: Dict, trade_stats: Dict) -> bool:
        """Send end-of-day trading summary."""
        equity = portfolio_state.get("equity", 0)
        dd = portfolio_state.get("drawdown_pct", 0)
        mode = portfolio_state.get("risk_mode", "NORMAL")
        positions = portfolio_state.get("open_positions_count", 0)

        total = trade_stats.get("total", 0)
        wins = trade_stats.get("wins", 0)
        wr = trade_stats.get("win_rate", 0)
        net_pnl = trade_stats.get("total_net_pnl", 0)
        avg_r = trade_stats.get("avg_r", 0)

        msg = (
            f"📊 Daily Summary ({self._now_ist()})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Equity: ${equity:,.2f}\n"
            f"Total Net P&L: ${net_pnl:+,.2f}\n"
            f"Trades: {total} | Wins: {wins} | WR: {wr:.1f}%\n"
            f"Avg R: {avg_r:.2f}\n"
            f"Drawdown: {dd:.1%} | Mode: {mode}\n"
            f"Open Positions: {positions}/3"
        )
        return self._send(msg)

    def send_error(self, message: str) -> bool:
        """Send error notification."""
        return self._send(f"🔴 ERROR: {message}\nTime: {self._now_ist()}")

    def send_startup(self, mode: str, equity: float) -> bool:
        """Send startup notification."""
        return self._send(
            f"🤖 Trading System Online\n"
            f"Mode: {mode.upper()} | Equity: ${equity:,.2f}\n"
            f"Time: {self._now_ist()}"
        )

    def send_shutdown(self) -> bool:
        """Send shutdown notification."""
        return self._send(f"🤖 Trading System Offline\nTime: {self._now_ist()}")

    def send_test(self) -> bool:
        """Pre-flight test: verify Telegram is reachable."""
        return self._send("🔧 Pre-flight test — Telegram OK")

    # ══════════════════════════════════════════════════════════════
    # INBOUND COMMAND HANDLER
    # ══════════════════════════════════════════════════════════════

    def handle_trading_command(self, command: str) -> str:
        """
        Process trading commands from Telegram.
        Returns response text to send back.
        """
        cmd = command.strip().lower().lstrip("/")

        if cmd == "kill":
            return self._cmd_kill()
        elif cmd == "status":
            return self._cmd_status()
        elif cmd == "pause":
            return self._cmd_pause()
        elif cmd == "resume":
            return self._cmd_resume()
        elif cmd == "positions":
            return self._cmd_positions()
        elif cmd == "pnl":
            return self._cmd_pnl()
        elif cmd == "health":
            return self._cmd_health()
        else:
            return ""  # Not a trading command

    def is_trading_command(self, text: str) -> bool:
        """Check if text is a trading command."""
        cmd = text.strip().lower().lstrip("/")
        return cmd in ("kill", "status", "pause", "resume", "positions", "pnl", "health")

    def _cmd_kill(self) -> str:
        if self.order_manager:
            result = self.order_manager.emergency_close_all("TELEGRAM_KILL_COMMAND")
            return f"🔴 KILL SWITCH ACTIVATED\nClosed {result.get('closed', 0)} positions\nTrading halted."
        return "⚠️ Order manager not connected."

    def _cmd_status(self) -> str:
        if not self.database:
            return "⚠️ Database not connected."
        state = self.database.get_portfolio_state()
        if not state:
            return "No portfolio state available."
        return (
            f"📊 Portfolio Status\n"
            f"Equity: ${state.get('equity', 0):,.2f}\n"
            f"Cash: ${state.get('cash', 0):,.2f}\n"
            f"Drawdown: {state.get('drawdown_pct', 0):.1%}\n"
            f"Mode: {state.get('risk_mode', 'UNKNOWN')}\n"
            f"Positions: {state.get('open_positions_count', 0)}/3"
        )

    def _cmd_pause(self) -> str:
        if self.order_manager:
            self.order_manager.pause()
            return "⏸️ Trading PAUSED. No new signals will be processed."
        return "⚠️ Order manager not connected."

    def _cmd_resume(self) -> str:
        if self.order_manager:
            self.order_manager.resume()
            if self.kill_switch:
                self.kill_switch.manual_reset("I_ACKNOWLEDGE_RISK_AND_RESET")
            return "▶️ Trading RESUMED. Kill switch reset."
        return "⚠️ Order manager not connected."

    def _cmd_positions(self) -> str:
        if not self.database:
            return "⚠️ Database not connected."
        positions = self.database.get_positions()
        if not positions:
            return "No open positions."
        lines = ["📋 Open Positions:"]
        for p in positions:
            pnl = p.get("unrealized_pnl", 0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(
                f"{emoji} {p['symbol']} {p['side']} | "
                f"Qty: {p['quantity']} | Entry: ${p['avg_entry_price']:.2f} | "
                f"P&L: ${pnl:+.2f}"
            )
        return "\n".join(lines)

    def _cmd_pnl(self) -> str:
        if not self.database:
            return "⚠️ Database not connected."
        stats = self.database.get_trade_stats()
        return (
            f"💰 P&L Summary\n"
            f"Total Trades: {stats['total']}\n"
            f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
            f"Win Rate: {stats['win_rate']:.1f}%\n"
            f"Net P&L: ${stats['total_net_pnl']:+,.2f}\n"
            f"Avg R: {stats['avg_r']:.2f}"
        )

    def _cmd_health(self) -> str:
        return "🔧 System health check — use pre-flight from autonomous loop."

    # ══════════════════════════════════════════════════════════════
    # UTILITIES
    # ══════════════════════════════════════════════════════════════

    def _send(self, message: str) -> bool:
        """Send a message to the configured Telegram chat."""
        if not self.bot or not self.chat_id:
            self.logger.debug(f"Telegram not configured. Message: {message}")
            return False
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, can't use run()
                asyncio.ensure_future(
                    self.bot.send_message(chat_id=self.chat_id, text=message)
                )
            else:
                loop.run_until_complete(
                    self.bot.send_message(chat_id=self.chat_id, text=message)
                )
            return True
        except Exception:
            try:
                import asyncio
                asyncio.run(
                    self.bot.send_message(chat_id=self.chat_id, text=message)
                )
                return True
            except Exception as e:
                self.logger.error(f"Telegram send failed: {e}")
                return False

    @staticmethod
    def _now_ist() -> str:
        """Get current time as IST string."""
        now_utc = datetime.now(timezone.utc)
        if HAS_PYTZ and IST:
            now_ist = now_utc.astimezone(IST)
            return now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
        return now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
