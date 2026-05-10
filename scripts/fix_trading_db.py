"""
Fix trading database: 
1. Seed portfolio_state with initial capital
2. Clear synthetic candle data
3. Backfill real OHLCV data from yfinance
4. Clean up fake signals and trades
"""
import sqlite3
import time
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "agent_data", "trading.db")
INITIAL_CAPITAL = 10000.0

print(f"Fixing trading database at: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Step 1: Fix portfolio_state
print("\n[1/4] Fixing portfolio_state...")
cursor.execute(
    """INSERT OR REPLACE INTO portfolio_state 
    (id, equity, cash, total_exposure, drawdown_pct, peak_equity, 
     risk_mode, open_positions_count, total_trades, winning_trades, total_pnl, updated_at)
    VALUES (1, ?, ?, 0, 0, ?, 'NORMAL', 0, 0, 0, 0, ?)""",
    (INITIAL_CAPITAL, INITIAL_CAPITAL, INITIAL_CAPITAL, time.time())
)
conn.commit()
print(f"  [OK] Portfolio: equity=${INITIAL_CAPITAL}, cash=${INITIAL_CAPITAL}")

# Step 2: Clear synthetic candles
print("\n[2/4] Clearing synthetic candle data...")
cursor.execute("DELETE FROM candles")
conn.commit()
print("  [OK] Candles cleared")

# Step 3: Clear fake signals and trades
print("\n[3/4] Clearing synthetic signals and trades...")
cursor.execute("DELETE FROM signals_archive")
cursor.execute("DELETE FROM trades_history")
cursor.execute("DELETE FROM orders")
cursor.execute("DELETE FROM positions")
conn.commit()
print("  [OK] All synthetic data cleared")

# Step 4: Backfill real OHLCV from yfinance
print("\n[4/4] Backfilling real market data from yfinance...")
try:
    import yfinance as yf
    
    symbols = ["AAPL", "MSFT", "GOOGL"]
    total_candles = 0
    
    for symbol in symbols:
        print(f"  Fetching {symbol}...")
        
        cursor.execute("SELECT id FROM instruments WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            instrument_id = row[0]
        else:
            cursor.execute(
                "INSERT INTO instruments (symbol, exchange, asset_type, active, created_at) VALUES (?, 'US', 'EQUITY', 1, ?)",
                (symbol, time.time())
            )
            instrument_id = cursor.lastrowid
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="60d", interval="15m")
        
        if df.empty:
            print(f"    [WARN] No data for {symbol}")
            continue
        
        count = 0
        for idx, r in df.iterrows():
            ts = idx.timestamp() if hasattr(idx, 'timestamp') else time.time()
            cursor.execute(
                """INSERT OR REPLACE INTO candles 
                (instrument_id, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (instrument_id, "15m", ts,
                 float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                 float(r.get("Volume", 0)))
            )
            count += 1
        
        conn.commit()
        total_candles += count
        last_close = float(df.iloc[-1]["Close"])
        print(f"    [OK] {symbol}: {count} candles (last: ${last_close:.2f})")
    
    print(f"\n  Total: {total_candles} candles")
    
except ImportError:
    print("  [WARN] yfinance not installed. pip install yfinance")
except Exception as e:
    print(f"  [WARN] Backfill error: {e}")

# Verify
print("\n" + "="*50)
print("VERIFICATION")
print("="*50)

cursor.execute("SELECT equity, cash, peak_equity, risk_mode FROM portfolio_state WHERE id=1")
row = cursor.fetchone()
if row:
    print(f"  Portfolio: equity=${row[0]}, cash=${row[1]}, peak=${row[2]}, mode={row[3]}")

cursor.execute("SELECT COUNT(*) FROM candles")
print(f"  Candles: {cursor.fetchone()[0]} rows")

cursor.execute("""
    SELECT i.symbol, MIN(c.close), MAX(c.close), COUNT(*) 
    FROM candles c JOIN instruments i ON c.instrument_id = i.id 
    GROUP BY c.instrument_id
""")
for row in cursor.fetchall():
    print(f"    {row[0]}: ${row[1]:.2f} - ${row[2]:.2f} ({row[3]} bars)")

conn.close()
print("\n[DONE] Database fix complete!")
