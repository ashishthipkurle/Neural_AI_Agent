"""
Trading Module — Autonomous Algorithmic Trading System.
Institutional-grade quantitative trading with 16-gate safety pipeline.

Capabilities:
- 4 algorithmic strategies (Trend, Mean Reversion, Breakout, FAISS Pattern)
- 16-gate order management with all safety engines integrated
- Real-time Alpaca broker integration with circuit breaker
- SQLite persistence across restarts
- Telegram monitoring and kill switch

Strict constraints:
- NEVER guarantee profits
- All trading involves risk of loss
- Paper trading for 30+ days before live
"""

__version__ = "2.0.0"

