"""
Trading API Routes — REST endpoints for the trading system.

All routes are under /api/trading/* prefix.

Endpoints:
    GET  /api/trading/status          — System status
    GET  /api/trading/portfolio        — Portfolio state
    GET  /api/trading/positions        — Open positions
    GET  /api/trading/orders           — Recent orders
    GET  /api/trading/trades           — Trade history
    GET  /api/trading/equity-curve     — Equity curve data
    GET  /api/trading/strategy-stats   — Strategy × regime stats
    GET  /api/trading/insights         — Learning engine insights
    GET  /api/trading/llm-budget       — LLM budget status
    POST /api/trading/start            — Start trading loop
    POST /api/trading/stop             — Stop trading loop
    POST /api/trading/analyze/{symbol} — Run TradingAgents analysis
    GET  /api/trading/report           — Generate daily report
"""
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("TradingAPI")

# The trading loop instance — set by the main api_server at startup
_trading_loop = None
_trading_lock = threading.Lock()


def set_trading_loop(loop):
    """Called by api_server to inject the autonomous loop instance."""
    global _trading_loop
    _trading_loop = loop


def _get_loop():
    """Get the trading loop, raise 503 if not initialized."""
    if _trading_loop is None:
        raise HTTPException(status_code=503, detail="Trading system not initialized")
    return _trading_loop


# ══════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/trading", tags=["Trading"])


# ── Request Models ────────────────────────────────────────────

class StartRequest(BaseModel):
    mode: str = "paper"
    symbols: list = []
    initial_capital: float = 10000.0


class AnalyzeRequest(BaseModel):
    symbol: str


# ── System Status ─────────────────────────────────────────────

@router.get("/status")
async def get_trading_status():
    """Get comprehensive trading system status."""
    loop = _get_loop()
    return loop.get_status()


# ── Portfolio ─────────────────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio():
    """Get current portfolio state."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    state = db.get_portfolio_state()
    stats = db.get_trade_stats()

    return {
        "portfolio": state or {},
        "trade_stats": stats or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Positions ─────────────────────────────────────────────────

@router.get("/positions")
async def get_positions():
    """Get all open positions."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"positions": db.get_positions()}


# ── Orders ────────────────────────────────────────────────────

@router.get("/orders")
async def get_orders(limit: int = 50):
    """Get recent orders."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"orders": db.get_recent_orders(limit=limit)}


@router.get("/orders/open")
async def get_open_orders():
    """Get pending/partially filled orders."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"orders": db.get_open_orders()}


# ── Trade History ─────────────────────────────────────────────

@router.get("/trades")
async def get_trades(limit: int = 100):
    """Get closed trade history."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"trades": db.get_trade_history(limit=limit)}


# ── Equity Curve ──────────────────────────────────────────────

@router.get("/equity-curve")
async def get_equity_curve(limit: int = 500):
    """Get equity curve data points for charting."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"data": db.get_equity_curve(limit=limit)}


# ── Strategy Stats ────────────────────────────────────────────

@router.get("/strategy-stats")
async def get_strategy_stats():
    """Get strategy × regime aggregated statistics (for heatmap)."""
    loop = _get_loop()
    if loop.learning_engine:
        stats = loop.learning_engine.get_strategy_regime_stats_list()
    elif loop.database:
        stats = loop.database.get_strategy_regime_stats()
    else:
        stats = []
    return {"stats": stats}


# ── Learning Insights ─────────────────────────────────────────

@router.get("/insights")
async def get_insights():
    """Get learning engine actionable insights."""
    loop = _get_loop()
    if not loop.learning_engine:
        return {"insights": ["Learning engine not initialized"]}
    return {"insights": loop.learning_engine.get_insights()}


# ── LLM Budget ────────────────────────────────────────────────

@router.get("/llm-budget")
async def get_llm_budget():
    """Get LLM budget status."""
    loop = _get_loop()
    if not loop.llm_budget:
        return {"budget": {"daily_limit": 0, "daily_spent": 0, "daily_remaining": 0}}
    return {"budget": loop.llm_budget.get_budget_status()}


# ── Start / Stop ──────────────────────────────────────────────

@router.post("/start")
async def start_trading(request: StartRequest):
    """Start the autonomous trading loop."""
    loop = _get_loop()

    with _trading_lock:
        if loop._thread and loop._thread.is_alive():
            raise HTTPException(status_code=409, detail="Trading loop already running")

        # Update config
        if request.symbols:
            loop.config["symbols"] = request.symbols
        loop.config["mode"] = request.mode
        loop.config["initial_capital"] = request.initial_capital

        loop.start()

    return {
        "status": "started",
        "mode": request.mode,
        "symbols": loop.config["symbols"],
    }


@router.post("/stop")
async def stop_trading():
    """Stop the autonomous trading loop gracefully."""
    loop = _get_loop()

    with _trading_lock:
        if not loop._thread or not loop._thread.is_alive():
            raise HTTPException(status_code=409, detail="Trading loop not running")
        loop.stop()

    return {"status": "stopped"}


# ── TradingAgents Analysis ────────────────────────────────────

@router.post("/analyze/{symbol}")
async def analyze_symbol(symbol: str):
    """Run TradingAgents multi-agent research for a symbol."""
    loop = _get_loop()
    if not loop.ta_adapter:
        raise HTTPException(status_code=503, detail="TradingAgents adapter not initialized")

    result = loop.ta_adapter.analyze(symbol.upper())
    return {"analysis": result}


@router.get("/analyze/{symbol}/cached")
async def get_cached_analysis(symbol: str):
    """Get cached TradingAgents analysis (no new LLM call)."""
    loop = _get_loop()
    if not loop.ta_adapter:
        raise HTTPException(status_code=503, detail="TradingAgents adapter not initialized")

    cached = loop.ta_adapter.get_cached_analysis(symbol.upper())
    if not cached:
        raise HTTPException(status_code=404, detail=f"No cached analysis for {symbol}")
    return {"analysis": cached}


# ── Daily Report ──────────────────────────────────────────────

@router.get("/report")
async def generate_report(date: str = None):
    """Generate and return path to daily HTML report."""
    loop = _get_loop()
    if not loop.report_generator:
        raise HTTPException(status_code=503, detail="Report generator not initialized")

    filepath = loop.report_generator.generate_daily_report(date)
    if not filepath:
        raise HTTPException(status_code=500, detail="Report generation failed")

    summary = loop.report_generator.get_report_summary_text(date)
    return {"filepath": filepath, "summary": summary}


# ── DB Stats ──────────────────────────────────────────────────

@router.get("/db-stats")
async def get_db_stats():
    """Get database table row counts."""
    loop = _get_loop()
    db = loop.database
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return {"stats": db.get_db_stats()}


# ── SPY Benchmark ─────────────────────────────────────────────

@router.get("/benchmark")
async def get_benchmark(symbol: str = "SPY", limit: int = 500):
    """
    Get buy-and-hold benchmark prices for comparison with equity curve.

    Returns normalized price series for the given symbol (default: SPY).
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist.empty:
            return {"data": [], "symbol": symbol}

        data = []
        for ts, row in hist.iterrows():
            data.append({
                "timestamp": int(ts.timestamp()),
                "value": float(row["Close"]),
            })

        # Limit to most recent N points
        if len(data) > limit:
            data = data[-limit:]

        return {"data": data, "symbol": symbol}
    except ImportError:
        raise HTTPException(status_code=503, detail="yfinance not installed")
    except Exception as e:
        logger.error(f"Benchmark fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── TradingAgents Debate Summary ──────────────────────────────

@router.get("/debate-summary/{symbol}")
async def get_debate_summary(symbol: str):
    """
    Return the latest TradingAgents analysis for a symbol,
    including bull vs bear debate highlights.
    """
    loop = _get_loop()
    db = loop.database

    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Check TA analysis cache
    try:
        cached = db.get_ta_analysis_cache(symbol)
        if cached:
            return {
                "symbol": symbol,
                "conviction": cached.get("conviction", 0.5),
                "direction": cached.get("direction", "HOLD"),
                "debate_summary": cached.get("debate_summary", "No debate data available"),
                "risk_assessment": cached.get("risk_assessment", ""),
                "analyst_reports": cached.get("analyst_reports", {}),
                "cached_at": cached.get("cached_at", ""),
                "cost_usd": cached.get("cost_usd", 0),
            }
    except Exception as e:
        logger.warning(f"Failed to get TA cache for {symbol}: {e}")

    return {
        "symbol": symbol,
        "conviction": 0.5,
        "direction": "HOLD",
        "debate_summary": "No TradingAgents analysis available. Run pre-market analysis first.",
        "risk_assessment": "",
        "analyst_reports": {},
        "cached_at": None,
        "cost_usd": 0,
    }
