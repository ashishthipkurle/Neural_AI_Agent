"""
Trading Database — SQLite Persistence Layer.

All trading state persists here. Survives restarts, crashes, and power loss.

Tables:
    - instruments: Global tradable universe
    - candles: OHLCV time series (bulk upsert)
    - orders: Full order lifecycle with commission/fee tracking
    - positions: Live position tracking
    - trades_history: Closed trade archive with net P&L
    - portfolio_state: Singleton equity/drawdown snapshot
    - signals_archive: Signal lifecycle history

Architecture:
    - SQLite with WAL mode for concurrent reads
    - All timestamps are UTC epoch seconds
    - No ORM — raw sqlite3 for performance
    - Thread-safe via check_same_thread=False

No LLM. Fully deterministic.
"""
import sqlite3
import time
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class TradingDatabase:
    """
    SQLite-backed persistence for the autonomous trading system.
    """

    def __init__(self, db_path: str = None) -> None:
        self.logger = logging.getLogger("TradingDatabase")

        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent / "agent_data"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "trading.db")

        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=10000")

        self._create_tables()
        self.logger.info(f"TradingDatabase initialized at {self.db_path}")

    # ══════════════════════════════════════════════════════════════
    # TABLE CREATION
    # ══════════════════════════════════════════════════════════════

    def _create_tables(self) -> None:
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.executescript("""
            -- Instruments (global tradable universe)
            CREATE TABLE IF NOT EXISTS instruments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL DEFAULT 'US',
                asset_type TEXT NOT NULL DEFAULT 'EQUITY',
                sector TEXT DEFAULT '',
                liquidity_score REAL DEFAULT 0.0,
                avg_daily_volume REAL DEFAULT 0.0,
                market_cap REAL DEFAULT 0.0,
                volatility_30d REAL DEFAULT 0.0,
                active INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                UNIQUE(symbol, exchange)
            );

            -- Candles (OHLCV time series)
            CREATE TABLE IF NOT EXISTS candles (
                instrument_id INTEGER NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp REAL NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL DEFAULT 0.0,
                PRIMARY KEY (instrument_id, timeframe, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_candles_lookup
                ON candles (instrument_id, timeframe, timestamp DESC);

            -- Orders (full lifecycle with commission tracking)
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                instrument_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL DEFAULT 'MARKET',
                quantity REAL NOT NULL,
                price REAL DEFAULT 0.0,
                stop_price REAL DEFAULT 0.0,
                take_profit_price REAL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'PENDING',
                broker_order_id TEXT DEFAULT '',
                filled_quantity REAL DEFAULT 0.0,
                filled_price REAL DEFAULT 0.0,
                commission REAL DEFAULT 0.0,
                fees REAL DEFAULT 0.0,
                slippage_pct REAL DEFAULT 0.0,
                strategy_name TEXT DEFAULT '',
                signal_id TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders (status);
            CREATE INDEX IF NOT EXISTS idx_orders_symbol
                ON orders (symbol, created_at DESC);

            -- Positions (live position tracking)
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_id INTEGER NOT NULL,
                symbol TEXT NOT NULL UNIQUE,
                side TEXT NOT NULL DEFAULT 'LONG',
                quantity REAL NOT NULL DEFAULT 0.0,
                avg_entry_price REAL NOT NULL DEFAULT 0.0,
                current_price REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                sector TEXT DEFAULT '',
                opened_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            -- Trades History (closed trade archive)
            CREATE TABLE IF NOT EXISTS trades_history (
                trade_id TEXT PRIMARY KEY,
                instrument_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                gross_pnl REAL DEFAULT 0.0,
                pnl_pct REAL DEFAULT 0.0,
                commission_total REAL DEFAULT 0.0,
                net_pnl REAL DEFAULT 0.0,
                net_pnl_pct REAL DEFAULT 0.0,
                r_achieved REAL DEFAULT 0.0,
                regime TEXT DEFAULT '',
                strategy_name TEXT DEFAULT '',
                signal_id TEXT DEFAULT '',
                opened_at REAL NOT NULL,
                closed_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trades_closed
                ON trades_history (closed_at DESC);

            -- Portfolio State (singleton snapshot)
            CREATE TABLE IF NOT EXISTS portfolio_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                equity REAL NOT NULL DEFAULT 0.0,
                cash REAL NOT NULL DEFAULT 0.0,
                total_exposure REAL DEFAULT 0.0,
                drawdown_pct REAL DEFAULT 0.0,
                peak_equity REAL DEFAULT 0.0,
                risk_mode TEXT DEFAULT 'NORMAL',
                open_positions_count INTEGER DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0.0,
                updated_at REAL NOT NULL
            );

            -- Signals Archive (signal lifecycle history)
            CREATE TABLE IF NOT EXISTS signals_archive (
                signal_id TEXT PRIMARY KEY,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL DEFAULT 0.0,
                stop_price REAL DEFAULT 0.0,
                target_price REAL DEFAULT 0.0,
                state TEXT NOT NULL DEFAULT 'GENERATED',
                confidence REAL DEFAULT 0.0,
                strategy_name TEXT DEFAULT '',
                regime TEXT DEFAULT '',
                resolution_reason TEXT DEFAULT '',
                created_at REAL NOT NULL,
                resolved_at REAL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_signals_state
                ON signals_archive (state);
        """)

        self.conn.commit()
        self.logger.debug("All tables created/verified.")

    # ══════════════════════════════════════════════════════════════
    # INSTRUMENTS
    # ══════════════════════════════════════════════════════════════

    def get_or_create_instrument(
        self, symbol: str, exchange: str = "US", asset_type: str = "EQUITY"
    ) -> int:
        """Get instrument_id, creating the record if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM instruments WHERE symbol = ? AND exchange = ?",
            (symbol, exchange),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]

        cursor.execute(
            """INSERT INTO instruments (symbol, exchange, asset_type, created_at)
               VALUES (?, ?, ?, ?)""",
            (symbol, exchange, asset_type, time.time()),
        )
        self.conn.commit()
        instrument_id = cursor.lastrowid
        self.logger.debug(f"Created instrument: {symbol}:{exchange} → id={instrument_id}")
        return instrument_id

    def get_instruments(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all instruments."""
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM instruments WHERE active = 1")
        else:
            cursor.execute("SELECT * FROM instruments")
        return [dict(row) for row in cursor.fetchall()]

    # ══════════════════════════════════════════════════════════════
    # CANDLES
    # ══════════════════════════════════════════════════════════════

    def save_candles(
        self, instrument_id: int, timeframe: str, candles: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert candles. Returns count saved."""
        if not candles:
            return 0

        cursor = self.conn.cursor()
        cursor.executemany(
            """INSERT OR REPLACE INTO candles
               (instrument_id, timeframe, timestamp, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    instrument_id,
                    timeframe,
                    c["timestamp"],
                    c["open"],
                    c["high"],
                    c["low"],
                    c["close"],
                    c.get("volume", 0.0),
                )
                for c in candles
            ],
        )
        self.conn.commit()
        count = len(candles)
        self.logger.debug(f"Saved {count} candles for instrument {instrument_id}/{timeframe}")
        return count

    def get_candles(
        self, instrument_id: int, timeframe: str, limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Get most recent candles, ordered oldest→newest."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM candles
               WHERE instrument_id = ? AND timeframe = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (instrument_id, timeframe, limit),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        rows.reverse()  # oldest first
        return rows

    def get_candle_count(self, instrument_id: int, timeframe: str) -> int:
        """Get total candle count for an instrument/timeframe pair."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM candles WHERE instrument_id = ? AND timeframe = ?",
            (instrument_id, timeframe),
        )
        return cursor.fetchone()["cnt"]

    # ══════════════════════════════════════════════════════════════
    # ORDERS
    # ══════════════════════════════════════════════════════════════

    def save_order(self, order: Dict[str, Any]) -> None:
        """Insert a new order record."""
        now = time.time()
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO orders
               (order_id, instrument_id, symbol, side, order_type, quantity, price,
                stop_price, take_profit_price, status, broker_order_id,
                filled_quantity, filled_price, commission, fees, slippage_pct,
                strategy_name, signal_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order.get("order_id", ""),
                order.get("instrument_id", 0),
                order.get("symbol", ""),
                order.get("side", "BUY"),
                order.get("order_type", "MARKET"),
                order.get("quantity", 0.0),
                order.get("price", 0.0),
                order.get("stop_price", 0.0),
                order.get("take_profit_price", 0.0),
                order.get("status", "PENDING"),
                order.get("broker_order_id", ""),
                order.get("filled_quantity", 0.0),
                order.get("filled_price", 0.0),
                order.get("commission", 0.0),
                order.get("fees", 0.0),
                order.get("slippage_pct", 0.0),
                order.get("strategy_name", ""),
                order.get("signal_id", ""),
                order.get("created_at", now),
                now,
            ),
        )
        self.conn.commit()

    def update_order(self, order_id: str, updates: Dict[str, Any]) -> None:
        """Update specific fields of an order."""
        if not updates:
            return
        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [order_id]
        self.conn.execute(
            f"UPDATE orders SET {set_clause} WHERE order_id = ?", values
        )
        self.conn.commit()

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all orders with status PENDING or PARTIALLY_FILLED."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM orders WHERE status IN ('PENDING', 'PARTIALLY_FILLED') ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_orders_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent orders for a symbol."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM orders WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent orders across all symbols."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ══════════════════════════════════════════════════════════════
    # POSITIONS
    # ══════════════════════════════════════════════════════════════

    def save_position(self, position: Dict[str, Any]) -> None:
        """Upsert a position by symbol."""
        now = time.time()
        self.conn.execute(
            """INSERT OR REPLACE INTO positions
               (instrument_id, symbol, side, quantity, avg_entry_price,
                current_price, unrealized_pnl, realized_pnl, sector,
                opened_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                position.get("instrument_id", 0),
                position["symbol"],
                position.get("side", "LONG"),
                position.get("quantity", 0.0),
                position.get("avg_entry_price", 0.0),
                position.get("current_price", 0.0),
                position.get("unrealized_pnl", 0.0),
                position.get("realized_pnl", 0.0),
                position.get("sector", ""),
                position.get("opened_at", now),
                now,
            ),
        )
        self.conn.commit()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE quantity > 0 ORDER BY opened_at")
        return [dict(row) for row in cursor.fetchall()]

    def remove_position(self, symbol: str) -> None:
        """Remove a closed position."""
        self.conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        self.conn.commit()

    def clear_positions(self) -> None:
        """Clear all positions (used during reconciliation)."""
        self.conn.execute("DELETE FROM positions")
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════
    # TRADES HISTORY
    # ══════════════════════════════════════════════════════════════

    def save_trade(self, trade: Dict[str, Any]) -> None:
        """Record a closed trade with net P&L (after commissions)."""
        self.conn.execute(
            """INSERT OR REPLACE INTO trades_history
               (trade_id, instrument_id, symbol, direction, entry_price, exit_price,
                quantity, gross_pnl, pnl_pct, commission_total, net_pnl, net_pnl_pct,
                r_achieved, regime, strategy_name, signal_id, opened_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade["trade_id"],
                trade.get("instrument_id", 0),
                trade["symbol"],
                trade["direction"],
                trade["entry_price"],
                trade["exit_price"],
                trade["quantity"],
                trade.get("gross_pnl", 0.0),
                trade.get("pnl_pct", 0.0),
                trade.get("commission_total", 0.0),
                trade.get("net_pnl", 0.0),
                trade.get("net_pnl_pct", 0.0),
                trade.get("r_achieved", 0.0),
                trade.get("regime", ""),
                trade.get("strategy_name", ""),
                trade.get("signal_id", ""),
                trade["opened_at"],
                trade["closed_at"],
            ),
        )
        self.conn.commit()

    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent closed trades."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM trades_history ORDER BY closed_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_trade_stats(self) -> Dict[str, Any]:
        """Compute aggregate trade statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM trades_history")
        total = cursor.fetchone()["total"]
        if total == 0:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                    "total_net_pnl": 0.0, "avg_r": 0.0}

        cursor.execute("SELECT COUNT(*) as wins FROM trades_history WHERE net_pnl > 0")
        wins = cursor.fetchone()["wins"]

        cursor.execute("SELECT SUM(net_pnl) as total_pnl FROM trades_history")
        total_pnl = cursor.fetchone()["total_pnl"] or 0.0

        cursor.execute("SELECT AVG(r_achieved) as avg_r FROM trades_history")
        avg_r = cursor.fetchone()["avg_r"] or 0.0

        return {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0.0,
            "total_net_pnl": round(total_pnl, 2),
            "avg_r": round(avg_r, 3),
        }

    # ══════════════════════════════════════════════════════════════
    # PORTFOLIO STATE
    # ══════════════════════════════════════════════════════════════

    def save_portfolio_state(self, state: Dict[str, Any]) -> None:
        """Upsert the singleton portfolio state row."""
        now = time.time()
        self.conn.execute(
            """INSERT OR REPLACE INTO portfolio_state
               (id, equity, cash, total_exposure, drawdown_pct, peak_equity,
                risk_mode, open_positions_count, total_trades, winning_trades,
                total_pnl, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                state.get("equity", 0.0),
                state.get("cash", 0.0),
                state.get("total_exposure", 0.0),
                state.get("drawdown_pct", 0.0),
                state.get("peak_equity", 0.0),
                state.get("risk_mode", "NORMAL"),
                state.get("open_positions_count", 0),
                state.get("total_trades", 0),
                state.get("winning_trades", 0),
                state.get("total_pnl", 0.0),
                now,
            ),
        )
        self.conn.commit()

    def get_portfolio_state(self) -> Optional[Dict[str, Any]]:
        """Get the current portfolio state."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM portfolio_state WHERE id = 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    # ══════════════════════════════════════════════════════════════
    # SIGNALS
    # ══════════════════════════════════════════════════════════════

    def save_signal(self, signal: Dict[str, Any]) -> None:
        """Archive a signal."""
        self.conn.execute(
            """INSERT OR REPLACE INTO signals_archive
               (signal_id, asset, direction, entry_price, stop_price, target_price,
                state, confidence, strategy_name, regime, resolution_reason,
                created_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal["signal_id"],
                signal.get("asset", ""),
                signal.get("direction", ""),
                signal.get("entry_price", 0.0),
                signal.get("stop_price", 0.0),
                signal.get("target_price", 0.0),
                signal.get("state", "GENERATED"),
                signal.get("confidence", 0.0),
                signal.get("strategy_name", ""),
                signal.get("regime", ""),
                signal.get("resolution_reason", ""),
                signal.get("created_at", time.time()),
                signal.get("resolved_at", 0.0),
            ),
        )
        self.conn.commit()

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Get all signals that are not yet CLOSED or RESET."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM signals_archive WHERE state NOT IN ('CLOSED', 'RESET') ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    def resolve_signal(self, signal_id: str, reason: str) -> None:
        """Mark a signal as resolved."""
        self.conn.execute(
            "UPDATE signals_archive SET state = 'CLOSED', resolution_reason = ?, resolved_at = ? WHERE signal_id = ?",
            (reason, time.time(), signal_id),
        )
        self.conn.commit()

    # ══════════════════════════════════════════════════════════════
    # UTILITIES
    # ══════════════════════════════════════════════════════════════

    def test_write(self) -> bool:
        """Pre-flight check: verify database is writable without clobbering existing state."""
        try:
            # Test write using a harmless operation — update the timestamp on existing row
            # If no row exists, insert a placeholder that startup_sequence will overwrite
            existing = self.get_portfolio_state()
            if existing:
                # Just touch the updated_at timestamp
                self.conn.execute(
                    "UPDATE portfolio_state SET updated_at = ? WHERE id = 1",
                    (time.time(),),
                )
            else:
                # No state yet — insert a minimal row (startup_sequence will set real values)
                self.conn.execute(
                    "INSERT OR REPLACE INTO portfolio_state (id, equity, cash, total_exposure, drawdown_pct, peak_equity, risk_mode, open_positions_count, total_trades, winning_trades, total_pnl, updated_at) VALUES (1, 0, 0, 0, 0, 0, 'NORMAL', 0, 0, 0, 0, ?)",
                    (time.time(),),
                )
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Database write test failed: {e}")
            return False

    def get_db_stats(self) -> Dict[str, Any]:
        """Get overview statistics of the database."""
        cursor = self.conn.cursor()
        stats = {}
        for table in ["instruments", "candles", "orders", "positions",
                       "trades_history", "portfolio_state", "signals_archive"]:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            stats[table] = cursor.fetchone()["cnt"]
        return stats

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")
