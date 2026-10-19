# Implementation Plan: Intelligent Trading Agent v3.0

> Transform the Neural AI Agent's trading system from a static rule executor into an intelligent, self-improving agent that grows capital — by integrating TradingAgents' multi-agent research framework on top of our existing execution infrastructure.

---

## Executive Summary

**Goal:** An agent that *actually grows money* by combining:
1. **TradingAgents** (multi-agent LLM research — analysts, researchers, risk managers)
2. **Our existing execution engine** (79 files, 16-gate OMS, broker adapters)
3. **A learning loop** that makes the system smarter after every trade
4. **A visual dashboard** so the user sees equity curves, trade journals, and intelligence breakdowns

**Core Insight:** TradingAgents is excellent at *research and analysis* (fundamentals, sentiment, news, technical via LLMs). Our system is excellent at *execution* (OMS, risk compression, broker integration). The plan fuses them: TradingAgents produces the **conviction**, our engine handles the **execution**.

**Timeline:** ~10 weeks across 5 phases

---

## Problems This Plan Solves

| # | Problem (from Critique) | Solution |
|---|---|---|
| 1 | Strategies have no proven edge ("RELAXED FOR DEMO") | Phase 1: Un-relax, backtest with 5yr real data, decision gate |
| 2 | Never backtested with real data | Phase 1: Automated backtest runner script with walk-forward validation |
| 3 | No learning loop — agent doesn't get smarter | Phase 3: Learning Engine records every trade outcome, adapts confidence |
| 4 | No fundamental or sentiment data | Phase 2: TradingAgents integration provides 4 specialist analysts |
| 5 | Confidence engine is circular | Phase 3: Multi-source Confidence Aggregator v2 (technical + sentiment + ML + historical) |
| 6 | No visual dashboard for the user | Phase 4: Equity curve, trade journal, strategy heatmap, intelligence panel |
| 7 | Paper mode bypasses all safety | Phase 1: Fix autonomous loop — paper mode respects market hours and data freshness |
| 8 | ML Predictor is disconnected | Phase 1: Wire as Gate 8.5 in OMS |

---

## Architecture: The Final System

```
┌──────────────────────────────────────────────────────────────────┐
│                     ELECTRON DESKTOP APP                         │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ Candlestick  │ │ Equity Curve │ │ Strategy Heatmap      │   │
│  │ Chart        │ │ + Drawdown   │ │ (win rate × regime)   │   │
│  └──────────────┘ └──────────────┘ └───────────────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ Trade        │ │ Intelligence │ │ Risk Gauge            │   │
│  │ Journal      │ │ Panel        │ │ + Mode Timeline       │   │
│  └──────────────┘ └──────────────┘ └───────────────────────┘   │
│                     │ WebSocket + REST                           │
└─────────────────────┼───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│            TRADINGAGENTS RESEARCH LAYER (NEW)                    │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │ Fundamentals│  │ Sentiment   │  │ News Analyst        │    │
│  │ Analyst     │  │ Analyst     │  │ (global events)     │    │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘    │
│         │                │                     │               │
│  ┌──────▼────────────────▼─────────────────────▼──────────┐    │
│  │           RESEARCH MANAGER                              │    │
│  │   Bull Researcher ←debate→ Bear Researcher              │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │         CONVICTION SCORE (0.0 – 1.0)                    │    │
│  │   + direction (BUY / SELL / HOLD)                        │    │
│  │   + analyst reports (for audit trail)                    │    │
│  └────────────────────────┬────────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│              INTELLIGENCE LAYER (NEW)                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ ML Predictor │  │ Learning     │  │ LLM Pre-Trade    │      │
│  │ (GBM model)  │  │ Engine       │  │ Reviewer         │      │
│  └───────┬──────┘  └──────┬───────┘  └───────┬──────────┘      │
│          │                │                   │                  │
│  ┌───────▼────────────────▼───────────────────▼──────────┐      │
│  │        CONFIDENCE AGGREGATOR v2                        │      │
│  │  technical_score    × 0.25                             │      │
│  │  ta_conviction      × 0.30  (from TradingAgents)       │      │
│  │  ml_prediction      × 0.20                             │      │
│  │  historical_edge    × 0.25  (from Learning Engine)     │      │
│  └───────────────────────┬───────────────────────────────┘      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              EXECUTION LAYER (EXISTING, FIXED)                   │
│                                                                  │
│  StrategyEngine (un-relaxed, selective signals)                  │
│       ↓                                                          │
│  Earnings Guard (Gate 3.5 — NEW)                                 │
│       ↓                                                          │
│  ML Alignment Gate (Gate 8.5 — NEW)                              │
│       ↓                                                          │
│  16-Gate OMS → Broker Adapter (Alpaca / Upstox)                  │
│       ↓                                                          │
│  Trade Closes → Learning Engine records outcome                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    PERSISTENCE LAYER                             │
│                                                                  │
│  trading.db:                                                     │
│    existing tables + trade_lessons + strategy_regime_stats        │
│  agent_data/reports/ → Daily HTML reports                        │
│  agent_data/backtest/ → Backtest results + equity curves         │
│  agent_data/ta_reports/ → TradingAgents analyst reports          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Current Asset Inventory

### What We Already Have (Keep & Fix)

| Component | File(s) | State |
|---|---|---|
| 4 Strategies | [`strategy_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/strategy_engine.py) | ⚠️ Relaxed for demo — needs un-relaxing |
| 16-Gate OMS | [`order_manager.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/order_manager.py) | ✅ Solid — keep as-is + add 2 new gates |
| Backtest Engine | [`backtest_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/backtest_engine.py) | ✅ Solid metrics — never been used with real data |
| ML Predictor | [`ml_predictor.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/ml_predictor.py) | ⚠️ Built but disconnected from OMS |
| Risk Engine | [`risk_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/risk_engine.py) | ✅ Solid risk compression state machine |
| Confidence Engine | [`confidence_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/confidence_engine.py) | ⚠️ Circular — needs multi-source rewrite |
| Regime Switcher | [`regime_switcher.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/regime_switcher.py) | ✅ Good — 5 regimes, deterministic |
| Broker Adapters | [`broker_adapter.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/broker_adapter.py), [`upstox_adapter.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/upstox_adapter.py) | ✅ Alpaca + Upstox |
| Trading DB | [`database.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/database.py) | ✅ SQLite WAL mode, proper schema |
| Autonomous Loop | [`autonomous_loop.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/autonomous_loop.py) | ⚠️ Paper mode bypasses safety — needs fix |
| Indicators Engine | [`indicators_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/indicators_engine.py) | ✅ 496-line pure-math indicator library |
| Feature Engine | [`feature_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/feature_engine.py) | ✅ 15-dim feature vector extraction |
| Trading Terminal UI | [`TradingTerminal.tsx`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/components/Dashboard/TradingTerminal.tsx) | ✅ Full UI with candlestick, signals, risk meters |
| Portfolio Dashboard | [`PortfolioDashboard.tsx`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/components/Dashboard/Trading/PortfolioDashboard.tsx) | ✅ Equity, cash, P&L, drawdown cards |
| Trading Chat | [`TradingChat.tsx`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/components/Dashboard/Trading/TradingChat.tsx) | ✅ Copilot chat grounded in engine state |
| Trading Store | [`tradingStore.ts`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/store/tradingStore.ts) | ✅ Zustand store with types |

### What We Build New

| Component | Source | Purpose |
|---|---|---|
| TradingAgents integration | TradingAgents repo | Multi-agent analyst research (fundamentals, sentiment, news, technical) |
| TradingAgents adapter | New | Bridge between TA's conviction output and our OMS |
| Backtest Runner | New | CLI script to run real 5yr backtests |
| Learning Engine | New | Post-trade analysis → parameter adaptation |
| Confidence Aggregator v2 | Rewrite | Multi-source scoring (technical + TA conviction + ML + historical) |
| Earnings Guard | New | Block trades near earnings (Gate 3.5) |
| Sentiment Cache | New | Cache TA sentiment results to avoid repeated LLM calls |
| Trade Journal DB tables | New | Rich per-trade outcome tracking with full context |
| Equity Curve API + Chart | New | `/api/trading/equity-curve` → line chart |
| Strategy Heatmap UI | New | Win rate per strategy × regime matrix |
| Intelligence Panel UI | New | Confidence breakdown visualization |
| Trade Journal UI | New | Sortable, filterable trade history |
| Daily Report Generator | New | HTML summary emailed/telegrammed daily |
| API Server Trading Routes | New | 10+ REST endpoints for frontend |

---

## Phase 1: Fix the Foundation (Week 1–2)

> **Goal:** Un-relax strategies, run real backtests, prove (or disprove) that the strategies have an edge. Fix paper mode. Wire disconnected components.

### 1.1 Un-Relax Strategy Engine

**File:** [`strategy_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/strategy_engine.py)

**Changes:**
- Line 26: Restore `COOLDOWN_BARS = 4` (currently 1)
- Line 176: Restore regime filter — only fire in `TRENDING_VOLATILE` and `EXPANSION_BREAKOUT`
- Line 206: Restore EMA crossover requirement (`ema20_prev <= ema50_prev`)
- Line 210: Restore bearish crossover requirement (`ema20_prev >= ema50_prev`)
- Remove all "RELAXED FOR DEMO" comments

### 1.2 Backtest Runner Script

**New file:** `agent/trading/run_backtest.py`

A standalone CLI script that:
1. Downloads 5 years of daily OHLCV data via yfinance for `SPY, AAPL, TSLA, MSFT, QQQ`
2. Iterates bar-by-bar, feeding each candle through `RegimeSwitcher` → `StrategyEngine`
3. Simulates execution: fills at next bar open, stop/target exits tracked per-bar
4. Passes completed trades to `BacktestEngine.run_backtest()` and `BacktestEngine.walk_forward()`
5. Outputs per strategy: Sharpe, Max DD, Win Rate, CAGR, Profit Factor
6. Saves equity curve CSV + metrics JSON to `agent_data/backtest_results/`
7. Prints decision gate: `PASS` if Sharpe > 0.3 and Max DD < 30%, else `FAIL`

**Usage:**
```bash
python -m agent.trading.run_backtest --symbols SPY,AAPL,TSLA --years 5 --strategies all
```

### 1.3 Fix Autonomous Loop Paper Mode

**File:** [`autonomous_loop.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/autonomous_loop.py)

Changes:
- Paper mode still respects `should_trade()` market hours — just simulates order placement
- Remove `sleep_s = 30` hack; use proper candle-close alignment even in paper
- Add `demo_mode` flag (separate from `paper`) that keeps fast loop for live demos only
- Paper mode uses proper data freshness checks (max 900s staleness)

### 1.4 Wire ML Predictor into OMS

**File:** [`order_manager.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/order_manager.py)

Insert Gate 8.5 between Confidence (Gate 8) and Exposure (Gate 9):

```python
# ── Gate 8.5: ML Prediction Alignment ───────────────────
if self.ml_predictor:
    try:
        ohlcv = self.data_feed.get_ohlcv_arrays(symbol, "15m", limit=200) if self.data_feed else None
        if ohlcv and len(ohlcv.get("closes", [])) >= 100:
            prediction = self.ml_predictor.predict(
                ohlcv["closes"], ohlcv["highs"], ohlcv["lows"],
                ohlcv.get("volumes", [])
            )
            if prediction and prediction.get("direction"):
                if prediction["direction"] != ("UP" if direction == "LONG" else "DOWN"):
                    signal["confidence"] *= 0.5
                    signal["ml_conflict"] = True
                    self.logger.info(f"ML disagrees with {direction} on {symbol} — confidence halved")
    except Exception as e:
        self.logger.warning(f"ML gate error (continuing): {e}")
```

**File:** [`autonomous_loop.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/autonomous_loop.py)

Wire `MLPredictor` into `_init_subsystems()` and pass to `OrderManager`.

### 1.5 Trading API Routes

**File:** [`api_server.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/api_server.py)

Add these REST endpoints:

| Endpoint | Method | Returns |
|---|---|---|
| `/api/trading/status` | GET | System status, mode, bar counter, market |
| `/api/trading/portfolio` | GET | Equity, cash, drawdown, positions |
| `/api/trading/equity-curve` | GET | Array of `{timestamp, equity}` for charting |
| `/api/trading/trades` | GET | Trade history with P&L |
| `/api/trading/signals/active` | GET | Currently active signals |
| `/api/trading/strategy-stats` | GET | Win rate per strategy × regime |
| `/api/trading/risk` | GET | Current risk mode + triggers |
| `/api/trading/backtest/run` | POST | Trigger a backtest run |
| `/api/trading/backtest/results` | GET | Latest backtest results |
| `/api/trading/journal` | GET | Trade journal with full context |
| `/api/trading/intelligence` | GET | Confidence Aggregator v2 breakdown |
| `/api/trading/ta-report` | GET | Latest TradingAgents analyst reports |

---

## Phase 2: TradingAgents Integration (Week 3–5)

> **Goal:** Integrate TradingAgents' multi-agent analyst framework to provide fundamental, sentiment, news, and technical analysis before every trade decision.

### 2.1 Install TradingAgents as Dependency

```bash
cd "d:\All Projects\My AI Agent"
git clone https://github.com/TauricResearch/TradingAgents.git lib/TradingAgents
cd lib/TradingAgents
pip install .
```

**Add to `requirements.txt`:**
```
# TradingAgents dependencies (installed from lib/TradingAgents)
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0
yfinance>=0.2.40
praw>=7.7.0
feedparser>=6.0.0
```

**Configure `.env`:**
```env
# TradingAgents LLM Provider (pick one)
OPENAI_API_KEY=sk-...
# OR use local Ollama (free):
TRADINGAGENTS_PROVIDER=ollama
TRADINGAGENTS_OLLAMA_BASE_URL=http://localhost:11434
```

### 2.2 TradingAgents Adapter

**New file:** `agent/trading/ta_adapter.py`

This adapter bridges TradingAgents' research output into our trading pipeline:

```python
"""
TradingAgents Adapter — Bridge between TradingAgents research
framework and our execution engine.

Runs TradingAgents analysis for a symbol, caches results,
and returns a normalized conviction score.
"""

class TradingAgentsAdapter:
    """
    Wraps TradingAgents to produce a conviction score per symbol.
    
    Usage:
        adapter = TradingAgentsAdapter(config)
        result = adapter.analyze("AAPL", "2026-10-16")
        # result = {
        #     "conviction": 0.72,          # 0.0 = strong sell, 1.0 = strong buy
        #     "direction": "BUY",           # BUY / SELL / HOLD
        #     "analyst_reports": {...},      # Full analyst outputs
        #     "debate_summary": "...",       # Bull vs bear summary
        #     "risk_assessment": "...",      # Risk team output
        #     "cached": False,
        #     "cost_usd": 0.08,             # LLM API cost for this run
        # }
    """
    
    def __init__(self, config=None):
        # Configure TradingAgents with our preferred settings
        self.ta_config = {
            "llm_provider": config.get("ta_provider", "ollama"),
            "deep_thinking_model": config.get("ta_deep_model", "llama3.1:70b"),
            "quick_thinking_model": config.get("ta_quick_model", "llama3.1:8b"),
            "selected_analysts": ("fundamentals", "social", "news", "market"),
            "max_debate_rounds": 1,       # Keep costs low
            "max_risk_discuss_rounds": 1,  # Keep costs low
        }
        
        # Cache: avoid re-running analysis for same symbol within window
        self._cache = {}  # {(symbol, date): result}
        self._cache_ttl = 3600  # 1 hour cache
    
    def analyze(self, symbol: str, trade_date: str) -> dict:
        """Run TradingAgents analysis and return conviction score."""
        # Check cache first
        # Initialize TradingAgentsGraph
        # Run propagation
        # Parse output into normalized conviction score
        # Cache result
        # Return structured result
    
    def _normalize_conviction(self, ta_output: dict) -> float:
        """Convert TradingAgents' decision to a 0.0-1.0 conviction score."""
        # Map "Strong Buy" → 0.9, "Buy" → 0.7, "Hold" → 0.5, 
        # "Sell" → 0.3, "Strong Sell" → 0.1
```

**Key design decisions:**
- Cache results for 1 hour to avoid burning LLM credits on every 15min bar
- Default to Ollama (free, local) — but support OpenAI/Claude for better quality
- Only run analysis during market hours, not overnight
- Graceful degradation: if TradingAgents fails, return neutral conviction (0.5)

### 2.3 Earnings Calendar Guard

**New file:** `agent/trading/earnings_guard.py`

Inspired by TradingAgents' fundamentals analyst:

```python
class EarningsGuard:
    """Block new entries within 2 trading days of earnings."""
    
    def check(self, symbol: str) -> dict:
        """
        Returns:
            {"safe": True/False, "earnings_date": "2026-10-25", "days_until": 5}
        """
        # Use yfinance.Ticker(symbol).calendar to get next earnings
        # If within 2 trading days → block
        # If holding position and earnings tomorrow → alert
```

Wired into OMS as **Gate 3.5** (between Data Freshness and Macro Filter).

### 2.4 Integrate TA into Autonomous Loop

**File:** [`autonomous_loop.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/autonomous_loop.py)

Update `_process_symbols()`:
```python
# Before strategy evaluation, fetch TradingAgents conviction
ta_result = None
if self.ta_adapter and self._should_run_ta_analysis(symbol):
    ta_result = self.ta_adapter.analyze(symbol, today_str)

# After strategy signals fire, weight them by TA conviction
for signal in signals:
    if ta_result:
        signal["ta_conviction"] = ta_result["conviction"]
        signal["ta_direction"] = ta_result["direction"]
        signal["ta_reports"] = ta_result.get("analyst_reports")
        
        # If TA says HOLD/SELL but strategy says LONG → reduce confidence
        if ta_result["direction"] == "SELL" and signal["direction"] == "LONG":
            signal["confidence"] *= 0.3  # Strong disagreement
        elif ta_result["direction"] == "HOLD" and signal["direction"] == "LONG":
            signal["confidence"] *= 0.6  # Mild caution
```

**When to run TradingAgents analysis:**
- Once per symbol per day (expensive LLM calls)
- At market open (9:30 AM ET for US, 9:15 AM IST for India)
- Cache result; reuse for all intraday signals on that symbol
- Skip weekends/holidays

### 2.5 Cost Control for LLM Calls

**New file:** `agent/trading/llm_budget.py`

```python
class LLMBudget:
    """Track and cap LLM API spending."""
    
    MAX_DAILY_USD = 5.00      # Hard daily cap
    MAX_PER_ANALYSIS_USD = 0.50  # Max per symbol analysis
    
    def can_spend(self, estimated_cost: float) -> bool:
        """Check if we're within budget."""
    
    def record_spend(self, actual_cost: float, symbol: str):
        """Record actual LLM cost."""
```

---

## Phase 3: Intelligence Layer (Week 5–7)

> **Goal:** Build the learning loop and multi-source confidence system that makes the agent get smarter over time.

### 3.1 Learning Engine

**New file:** `agent/trading/learning_engine.py`

The core "brain" that makes the agent intelligent:

```python
class LearningEngine:
    """
    Records trade outcomes and builds statistical profiles per
    (strategy × regime × confidence_bucket) combination.
    
    Uses these profiles to predict win probability for future signals,
    creating a self-improving confidence calibration loop.
    """
    
    MIN_TRADES_FOR_ADAPTATION = 20  # Don't adapt until 20+ trades in bucket
    ROLLING_WINDOW = 200            # Only consider last 200 trades
    
    def record_outcome(self, trade: dict):
        """
        Called when a trade closes. Records full context:
        strategy, regime, confidence, sentiment, ML agreement,
        TA conviction, entry/exit prices, P&L, holding period.
        """
    
    def get_historical_win_rate(self, strategy: str, regime: str) -> float:
        """
        Returns win rate for this strategy × regime combination.
        Returns 0.5 (neutral) if insufficient data.
        """
    
    def get_strategy_regime_stats(self) -> dict:
        """
        Returns full matrix for dashboard heatmap:
        {("trend_following", "TRENDING_VOLATILE"): {wins: 12, losses: 5, avg_pnl: 0.02}, ...}
        """
    
    def get_insights(self) -> list:
        """
        Returns actionable insights:
        - "trend_following performs poorly in QUIET regime (28% win rate)"
        - "mean_reversion excels in LOW_VOL_RANGE (72% win rate)"
        """
```

### 3.2 New Database Tables

**File:** [`database.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/database.py)

Add to `_create_tables()`:

```sql
-- Per-trade outcome with full context (for Learning Engine)
CREATE TABLE IF NOT EXISTS trade_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    regime TEXT NOT NULL,
    confidence_bucket TEXT NOT NULL,   -- "HIGH" (>0.7), "MED" (0.5-0.7), "LOW" (<0.5)
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL,
    exit_price REAL,
    pnl_pct REAL,
    pnl_dollars REAL,
    win INTEGER,                       -- 1=win, 0=loss
    sentiment_score REAL,              -- from SentimentEngine (0-1)
    ta_conviction REAL,                -- from TradingAgents (0-1)
    ta_direction TEXT,                 -- BUY/SELL/HOLD
    ml_agreed INTEGER,                 -- 1=agreed, 0=disagreed
    holding_period_bars INTEGER,
    exit_reason TEXT,                   -- STOP_LOSS, TAKE_PROFIT, MANUAL, TIMEOUT
    risk_mode_at_entry TEXT,           -- NORMAL/DEFENSIVE/CRITICAL
    created_at REAL DEFAULT (strftime('%s', 'now'))
);

-- Aggregated stats per strategy × regime (for fast lookup)
CREATE TABLE IF NOT EXISTS strategy_regime_stats (
    strategy TEXT NOT NULL,
    regime TEXT NOT NULL,
    total_trades INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    avg_pnl REAL DEFAULT 0.0,
    avg_confidence REAL DEFAULT 0.0,
    avg_holding_bars REAL DEFAULT 0.0,
    best_pnl REAL DEFAULT 0.0,
    worst_pnl REAL DEFAULT 0.0,
    last_updated REAL,
    PRIMARY KEY (strategy, regime)
);

-- Equity curve snapshots (for charting)
CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    drawdown_pct REAL DEFAULT 0.0,
    open_positions INTEGER DEFAULT 0,
    risk_mode TEXT DEFAULT 'NORMAL',
    created_at REAL DEFAULT (strftime('%s', 'now'))
);

-- TradingAgents analysis cache
CREATE TABLE IF NOT EXISTS ta_analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    conviction REAL,
    direction TEXT,
    analyst_reports TEXT,            -- JSON blob
    debate_summary TEXT,
    cost_usd REAL DEFAULT 0.0,
    created_at REAL DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, analysis_date)
);
```

### 3.3 Confidence Aggregator v2

**Rewrite:** [`confidence_engine.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/confidence_engine.py)

Replace circular confidence with multi-source aggregation:

```python
class ConfidenceAggregatorV2:
    """
    Multi-source confidence scoring. Four independent signals vote
    on each trade, breaking the circular dependency of v1.
    
    Sources:
        1. Technical (from strategy signal) — 0.25 weight
        2. TradingAgents conviction          — 0.30 weight  
        3. ML Predictor agreement            — 0.20 weight
        4. Historical win rate               — 0.25 weight
    """
    
    WEIGHTS = {
        "technical":  0.25,
        "ta_conviction": 0.30,
        "ml_model":   0.20,
        "historical": 0.25,
    }
    
    BLOCK_THRESHOLD = 0.30
    REDUCE_THRESHOLD = 0.45
    
    def aggregate(self, technical_confidence, ta_conviction,
                  ml_agrees, historical_win_rate, direction):
        scores = {
            "technical": technical_confidence,
            "ta_conviction": ta_conviction if direction == "LONG" else (1.0 - ta_conviction),
            "ml_model": 0.8 if ml_agrees else 0.2,
            "historical": historical_win_rate,
        }
        
        final = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        
        if final < self.BLOCK_THRESHOLD:
            action = "BLOCK"
        elif final < self.REDUCE_THRESHOLD:
            action = "REDUCE"
        else:
            action = "ALLOW"
        
        return {
            "confidence": round(final, 4),
            "action": action,
            "scores": scores,
            "weights": self.WEIGHTS,
        }
```

### 3.4 LLM Pre-Trade Reviewer

**New file:** `agent/trading/llm_reviewer.py`

Optional, advisory-only gate using local Ollama:

```python
class LLMPreTradeReviewer:
    """
    Sends a 1-paragraph trade summary to Ollama for a sanity check.
    Advisory only: can reduce confidence by max 10%, can never BLOCK.
    Graceful degradation: if Ollama is down, skip silently.
    """
    
    MAX_CONFIDENCE_REDUCTION = 0.10  # Can only nudge, not veto
    TIMEOUT_SECONDS = 10             # Don't wait forever
    
    def review(self, signal: dict, ta_reports: dict = None) -> dict:
        prompt = f"""You are a risk-aware trading reviewer. 
        Signal: {signal['direction']} {signal['symbol']} @ {signal['entry_price']}
        Strategy: {signal['strategy_name']}, Regime: {signal['regime']}
        Confidence: {signal['confidence']:.2f}
        TradingAgents says: {ta_reports.get('direction', 'N/A') if ta_reports else 'N/A'}
        
        In 2 sentences: Is this a reasonable trade? Any red flags?"""
        
        # Call Ollama → parse response → return adjustment
```

### 3.5 Daily Report Generator

**New file:** `agent/trading/report_generator.py`

Generates HTML daily summary (inspired by TradingAgents' report system):
- Today's trades (entries + exits) with P&L
- Portfolio snapshot: equity, drawdown, risk mode
- Strategy performance breakdown
- Learning engine insights
- TradingAgents analyst highlights
- Embedded equity curve chart (matplotlib → base64 PNG)

Output: `agent_data/reports/YYYY-MM-DD.html` + Telegram notification

---

## Phase 4: Visual Dashboard (Week 7–9)

> **Goal:** The user sees everything — equity curves, trade journals, strategy performance, intelligence breakdowns — in the existing Electron trading terminal.

### 4.1 Equity Curve Chart

**New file:** `desktop/src/renderer/src/components/Dashboard/Trading/EquityCurveChart.tsx`

- Line chart: portfolio equity over time (gradient green area fill)
- Drawdown overlay: red fill below the peak line
- Benchmark line: SPY buy-and-hold for comparison
- Time range selector: 1D, 1W, 1M, 3M, YTD, ALL
- Hover tooltip with exact equity, drawdown %, date
- Data from `/api/trading/equity-curve`
- Auto-refresh every 60 seconds via trading store

### 4.2 Trade Journal Component

**New file:** `desktop/src/renderer/src/components/Dashboard/Trading/TradeJournal.tsx`

Sortable, filterable table:

| Column | Description |
|---|---|
| Date | Entry date |
| Symbol | Ticker |
| Direction | LONG / SHORT with color |
| Strategy | Which strategy fired |
| Entry / Exit | Prices |
| P&L (%) | Color-coded green/red |
| P&L ($) | Dollar amount |
| Confidence | Aggregated v2 score |
| TA Conviction | TradingAgents score |
| ML Agreed? | ✓ / ✗ |
| Regime | Market regime at entry |
| Exit Reason | STOP_LOSS / TAKE_PROFIT / MANUAL |

Click row to expand: full analyst reports, LLM review, signal context.

### 4.3 Strategy Heatmap

**New file:** `desktop/src/renderer/src/components/Dashboard/Trading/StrategyHeatmap.tsx`

Matrix visualization: 4 strategies × 5 regimes = 20 cells.
- Cell color: green (>55% win) → yellow (40-55%) → red (<40%)
- Cell text: "12W / 5L (71%)" — wins, losses, win rate
- Tooltip: avg P&L, avg holding period, profit factor
- Data from Learning Engine's `strategy_regime_stats` table

### 4.4 Intelligence Panel

**New file:** `desktop/src/renderer/src/components/Dashboard/Trading/IntelligencePanel.tsx`

For the currently selected signal/trade, shows:
- **Confidence Breakdown**: 4 horizontal bars (technical, TA conviction, ML, historical)
- **TradingAgents Summary**: Bull vs Bear debate highlights
- **ML Prediction**: Direction + confidence + feature importance
- **Learning Insight**: "This strategy × regime has 68% win rate over 45 trades"

### 4.5 Enhanced Risk Gauge

**Update:** [`RiskMeters.tsx`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/components/Dashboard/Trading/RiskMeters.tsx)

Add:
- Animated semicircle gauge (NORMAL → DEFENSIVE → CRITICAL → HALTED)
- Trigger reasons list
- Mode transition timeline (mini sparkline)
- Current drawdown as prominent number

### 4.6 Integrate into TradingTerminal

**Update:** [`TradingTerminal.tsx`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/components/Dashboard/TradingTerminal.tsx)

Add new tabs to existing tab system:
- **PERFORMANCE** tab → EquityCurveChart + StrategyHeatmap
- **JOURNAL** tab → TradeJournal
- **INTELLIGENCE** tab → IntelligencePanel + TA reports

### 4.7 Update Trading Store

**Update:** [`tradingStore.ts`](file:///d:/All%20Projects/My%20AI%20Agent/desktop/src/renderer/src/store/tradingStore.ts)

Add new state + fetchers:

```typescript
// New types
interface EquityPoint { timestamp: number; equity: number; drawdown_pct: number; }
interface JournalEntry { /* ... full trade context ... */ }
interface StrategyRegimeStat { strategy: string; regime: string; wins: number; losses: number; avg_pnl: number; }
interface IntelligenceBreakdown { technical: number; ta_conviction: number; ml_model: number; historical: number; }

// New state
equityCurve: EquityPoint[];
journal: JournalEntry[];
strategyStats: StrategyRegimeStat[];
intelligence: IntelligenceBreakdown | null;
taReport: any | null;

// New actions
fetchEquityCurve(range: string): Promise<void>;
fetchJournal(filters: object): Promise<void>;
fetchStrategyStats(): Promise<void>;
fetchIntelligence(signalId: string): Promise<void>;
fetchTAReport(symbol: string): Promise<void>;
```

---

## Phase 5: Autonomous Intelligence Loop (Week 9–10)

> **Goal:** Wire everything into a self-improving system that runs 24/7.

### 5.1 Updated Autonomous Loop Flow

```
06:00 UTC — Pre-market prep
    │
    ├── For each symbol: run TradingAgents analysis (cached 24hr)
    │     → Fundamentals, Sentiment, News, Technical analysts
    │     → Bull vs Bear debate
    │     → Conviction score + direction
    │
    ├── Check earnings calendar → mark blocked symbols
    │
    └── Train/retrain ML predictor if 50+ new bars since last train
    
09:30 ET — Market opens (main loop starts)
    │
    ▼  Every candle close (15min):
    │
    ├── Fetch fresh OHLCV data
    ├── Detect regime (RegimeSwitcher)
    ├── Evaluate strategies (un-relaxed, selective)
    │
    ├── For each signal:
    │     ├── Get TA conviction (from morning cache)
    │     ├── Get ML prediction alignment
    │     ├── Get historical win rate (from Learning Engine)
    │     ├── Confidence Aggregator v2 scores all sources
    │     │     technical(0.25) + TA(0.30) + ML(0.20) + history(0.25)
    │     ├── Optional LLM review (advisory, logged)
    │     └── 16-Gate OMS processes signal
    │
    ├── Sync positions with broker
    ├── Detect closed trades → Learning Engine records outcome
    ├── Snapshot equity curve point → DB
    └── Emit WebSocket events → Dashboard updates
    
16:00 ET — Market closes
    │
    ├── Generate daily HTML report
    ├── Send Telegram summary
    ├── Learning Engine computes daily insights
    └── Update strategy × regime stats
```

### 5.2 Closed-Trade Detection

**Update:** [`order_manager.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/order_manager.py)

Add method to detect when positions close (stop-loss hit, take-profit hit):

```python
def detect_closed_trades(self) -> list:
    """Compare current positions with last known positions.
    Returns list of closed trades with full context."""
```

### 5.3 WebSocket Events

**Update:** [`api_server.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/api_server.py)

Real-time events emitted to frontend:
- `trading:signal_fired` — New signal generated (with confidence breakdown)
- `trading:trade_executed` — Order filled at broker
- `trading:trade_closed` — Position closed (with P&L)
- `trading:risk_mode_change` — Risk mode transition
- `trading:portfolio_update` — Equity snapshot
- `trading:ta_analysis_complete` — TradingAgents finished analyzing a symbol
- `trading:learning_insight` — New learning engine insight

### 5.4 Equity Curve Snapshots

**Update:** [`autonomous_loop.py`](file:///d:/All%20Projects/My%20AI%20Agent/agent/trading/autonomous_loop.py)

Every cycle, save equity snapshot:
```python
if self.database:
    state = self.database.get_portfolio_state()
    self.database.save_equity_snapshot({
        "equity": state.get("equity", 0),
        "cash": state.get("cash", 0),
        "drawdown_pct": state.get("drawdown_pct", 0),
        "open_positions": len(self.database.get_positions()),
        "risk_mode": self.risk_engine.current_mode,
    })
```

---

## Dependencies & Configuration

### New Python Dependencies

Add to [`requirements.txt`](file:///d:/All%20Projects/My%20AI%20Agent/requirements.txt):

```
# TradingAgents integration
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0

# Sentiment & data
praw>=7.7.0
feedparser>=6.0.0

# ML & visualization
scikit-learn>=1.3.0
matplotlib>=3.7.0
numpy>=1.24.0

# Already have: yfinance, alpaca-trade-api, faiss
```

### Environment Variables

Add to `.env`:
```env
# TradingAgents LLM (choose one)
TRADINGAGENTS_PROVIDER=ollama          # ollama | openai | anthropic
TRADINGAGENTS_DEEP_MODEL=llama3.1:70b  # For research manager, debate
TRADINGAGENTS_QUICK_MODEL=llama3.1:8b  # For analysts
# OPENAI_API_KEY=sk-...               # If using OpenAI

# LLM Budget
LLM_DAILY_BUDGET_USD=5.00
LLM_PER_ANALYSIS_MAX_USD=0.50

# Reddit (for sentiment)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Strategies have no edge after un-relaxing | Medium | High | Phase 1 backtest is the decision gate. If Sharpe < 0.3, redesign strategies before Phase 2. |
| TradingAgents is too slow (multi-minute LLM calls) | Medium | Medium | Run once per day pre-market, cache 24hr. Don't block intraday signals. |
| LLM costs spiral | Low | Medium | Hard $5/day cap. Ollama default (free). Budget tracker with alerts. |
| TradingAgents hallucinations | Medium | Low | 30% weight only. Can nudge but never override. Logged for audit. |
| Learning engine overfits to recent data | Medium | Medium | Rolling 200-trade window. Min 20 trades per bucket before adapting. |
| Frontend WebSocket still broken | High | Medium | Fix WS connection first (known issue in PROJECT_STATE.md line 61). |
| ML Predictor undertrained | Low | Low | Graceful degradation — if not trained, returns neutral. |

---

## Success Criteria

| Metric | Target | Phase | Measured By |
|---|---|---|---|
| Backtest Sharpe (best strategy, 5yr SPY) | > 0.5 | 1 | `run_backtest.py` output |
| Walk-forward robustness | > 60% folds pass | 1 | Walk-forward report |
| TradingAgents runs on all 7 symbols | < 5 min total | 2 | Timing logs |
| LLM daily cost | < $5/day | 2 | Budget tracker |
| Confidence uses 4 independent sources | All active | 3 | Log inspection |
| Learning engine has 50+ trades | Populated | 5 | DB query on `trade_lessons` |
| Dashboard shows live equity curve | Working | 4 | Visual inspection |
| Trade journal shows full context | All columns populated | 4 | UI test |
| Strategy heatmap renders correctly | 20 cells with data | 4 | Visual inspection |
| Paper trading 30-day return | Positive | 5 | Equity curve |
| Daily HTML report generates | Automated | 3 | `agent_data/reports/` check |
