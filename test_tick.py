import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# os.environ["DIAGNOSTIC"] = "1"

from agent.trading.realtime_engine import RealtimeEngine

engine = RealtimeEngine()

def mock_query(*args, **kwargs):
    return [
        {"future_return": 0.05, "max_drawdown": 0.02, "max_runup": 0.06, "r_multiple": 2.5, "regime_label": "R1", "similarity_score": 0.95, "pattern_age_days": 10},
        {"future_return": 0.04, "max_drawdown": 0.03, "max_runup": 0.05, "r_multiple": 1.5, "regime_label": "R1", "similarity_score": 0.90, "pattern_age_days": 20},
        {"future_return": 0.06, "max_drawdown": 0.01, "max_runup": 0.07, "r_multiple": 3.0, "regime_label": "R1", "similarity_score": 0.85, "pattern_age_days": 30}
    ]
engine.similarity_engine.query = mock_query

print("--- SENDING CANDLE CLOSE TICK ---")

current_time_ms = int(time.time() * 1000)

res = engine.tick(
    instrument_id=1,
    closes=[50000.0 + i for i in range(50)],
    highs=[50100.0 + i for i in range(50)],
    lows=[49900.0 + i for i in range(50)],
    volumes=[100.0] * 50,
    current_regime="R1",
    regime_volatility_bucket="V_M",
    candle_timestamp_ms=current_time_ms,
    is_candle_close=True
)

print("\n--- RESULT ---")
print(res)
