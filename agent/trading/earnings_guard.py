"""
Earnings Calendar Guard — Block Trades Near Earnings.

Prevents new entries within 2 trading days of earnings announcements
to avoid event-driven volatility. Uses yfinance for earnings lookup
with caching to minimize API calls.

Wired into OMS as Gate 3.5 (between Data Freshness and Macro Filter).

No LLM. Fully deterministic.
"""
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone


class EarningsGuard:
    """
    Block new entries within 2 trading days of earnings.
    """

    BLOCK_DAYS = 2  # Trading days before earnings to block entries
    CACHE_TTL = 86400  # 24 hours cache for earnings dates

    def __init__(self) -> None:
        self.logger = logging.getLogger("EarningsGuard")
        self._cache: Dict[str, Dict[str, Any]] = {}

    def check(self, symbol: str) -> Dict[str, Any]:
        """
        Check if it's safe to trade a symbol based on earnings proximity.

        Returns:
            {"safe": True/False, "earnings_date": "2026-10-25", "days_until": 5}
        """
        # Check cache
        cached = self._cache.get(symbol)
        if cached and (time.time() - cached.get("fetched_at", 0)) < self.CACHE_TTL:
            return cached["result"]

        # Fetch earnings date
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar

            if calendar is None or calendar.empty if hasattr(calendar, 'empty') else not calendar:
                result = {"safe": True, "earnings_date": None, "days_until": None}
                self._cache[symbol] = {"result": result, "fetched_at": time.time()}
                return result

            # Get next earnings date
            earnings_date = None
            if isinstance(calendar, dict):
                earnings_date = calendar.get("Earnings Date")
                if isinstance(earnings_date, list) and earnings_date:
                    earnings_date = earnings_date[0]
            elif hasattr(calendar, 'iloc'):
                # DataFrame format
                try:
                    earnings_date = calendar.iloc[0, 0] if len(calendar) > 0 else None
                except Exception:
                    pass

            if earnings_date is None:
                result = {"safe": True, "earnings_date": None, "days_until": None}
                self._cache[symbol] = {"result": result, "fetched_at": time.time()}
                return result

            # Convert to date
            if hasattr(earnings_date, 'date'):
                ed = earnings_date.date() if hasattr(earnings_date, 'date') else earnings_date
            elif isinstance(earnings_date, str):
                ed = datetime.strptime(earnings_date, "%Y-%m-%d").date()
            else:
                ed = earnings_date

            today = datetime.now(timezone.utc).date()
            days_until = (ed - today).days

            safe = days_until > self.BLOCK_DAYS or days_until < 0
            result = {
                "safe": safe,
                "earnings_date": str(ed),
                "days_until": days_until,
            }

            if not safe:
                self.logger.warning(
                    f"EARNINGS GUARD: {symbol} has earnings in {days_until} days "
                    f"({ed}) — BLOCKING new entries"
                )

        except ImportError:
            self.logger.warning("yfinance not available — earnings guard disabled")
            result = {"safe": True, "earnings_date": None, "days_until": None}
        except Exception as e:
            self.logger.warning(f"Earnings check failed for {symbol}: {e}")
            result = {"safe": True, "earnings_date": None, "days_until": None}

        self._cache[symbol] = {"result": result, "fetched_at": time.time()}
        return result

    def is_safe(self, symbol: str) -> bool:
        """Quick boolean check -- safe to trade?"""
        return self.check(symbol).get("safe", True)

    def alert_holdings_near_earnings(
        self, held_symbols: list, telegram_notifier=None
    ) -> list:
        """
        Check all held positions against earnings calendar.
        If any position has earnings within BLOCK_DAYS, send a Telegram alert.

        Args:
            held_symbols: List of symbols currently held
            telegram_notifier: TelegramNotifier instance (must have .send_message())

        Returns:
            List of symbols with upcoming earnings
        """
        at_risk = []
        for symbol in held_symbols:
            result = self.check(symbol)
            if not result.get("safe", True):
                at_risk.append({
                    "symbol": symbol,
                    "earnings_date": result.get("earnings_date"),
                    "days_until": result.get("days_until"),
                })

        if at_risk and telegram_notifier:
            lines = ["EARNINGS ALERT - Positions at risk:"]
            for item in at_risk:
                lines.append(
                    f"  {item['symbol']}: earnings in {item['days_until']}d "
                    f"({item['earnings_date']})"
                )
            lines.append("Consider closing before earnings.")
            try:
                telegram_notifier.send_message("\n".join(lines))
                self.logger.info(
                    f"Earnings alert sent for {len(at_risk)} positions"
                )
            except Exception as e:
                self.logger.error(f"Failed to send earnings alert: {e}")

        return at_risk
