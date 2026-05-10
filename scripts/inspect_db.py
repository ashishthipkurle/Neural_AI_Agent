"""Quick script to inspect trading.db tables and data."""
import sqlite3
import os

for db_path in ['agent_data/trading.db', 'agent/trading.db']:
    full = os.path.join(r'D:\All Projects\My AI Agent', db_path)
    if not os.path.exists(full):
        print(f"\n--- {db_path}: NOT FOUND ---")
        continue
    
    print(f"\n{'='*60}")
    print(f"DATABASE: {db_path} ({os.path.getsize(full)} bytes)")
    print(f"{'='*60}")
    
    conn = sqlite3.connect(full)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Tables: {tables}")
    
    # For each table, show count + sample
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        print(f"\n  [{t}] rows={count}")
        if count > 0:
            cursor.execute(f"SELECT * FROM [{t}] LIMIT 3")
            cols = [d[0] for d in cursor.description]
            print(f"    columns: {cols}")
            for row in cursor.fetchall():
                print(f"    >> {row}")
    
    conn.close()
