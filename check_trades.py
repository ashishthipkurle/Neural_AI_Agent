"""Re-create positions from existing filled orders in the database."""
import sqlite3, time
conn = sqlite3.connect("agent_data/trading.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get filled orders
c.execute("SELECT symbol, side, quantity, price, instrument_id, created_at FROM orders WHERE status='FILLED'")
orders = c.fetchall()

now = time.time()
for order in orders:
    print(f"Restoring: {order['symbol']} {order['side']} x{int(order['quantity'])} @ ${order['price']:.2f}")
    c.execute("""
        INSERT OR REPLACE INTO positions
        (instrument_id, symbol, side, quantity, avg_entry_price,
         current_price, unrealized_pnl, realized_pnl, sector,
         opened_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order['instrument_id'], order['symbol'], order['side'],
        order['quantity'], order['price'], order['price'],
        0.0, 0.0, '', order['created_at'], now
    ))

conn.commit()

c.execute("SELECT symbol, side, quantity, avg_entry_price FROM positions")
print("\nPOSITIONS RESTORED:")
for row in c.fetchall():
    print(f"  {row['symbol']} {row['side']} x{int(row['quantity'])} @ ${row['avg_entry_price']:.2f}")

conn.close()
print("Done!")
