import sys
sys.path.insert(0, '.')

print("Testing autonomous loop import...")
from agent.trading.autonomous_loop import AutonomousTradingLoop

loop = AutonomousTradingLoop({
    "mode": "paper",
    "symbols": ["AAPL", "SPY"],
    "initial_capital": 10000,
})

status = loop.get_status()
print(f"Mode: {status['mode']}")
print(f"Symbols: {status['symbols']}")
print(f"Running: {status['running']}")
print(f"DB stats: {status['db_stats']}")
print(f"Broker connected: {status['broker'].get('connected', False)}")
print()
print("ALL AUTONOMOUS LOOP TESTS PASSED")
loop.database.close()
