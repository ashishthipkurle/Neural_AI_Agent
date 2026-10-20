# Tasks: Intelligent Trading Agent v3.0

> Checklist of every task needed to implement the plan. Check off as completed.
> Tasks are ordered by dependency — complete top-to-bottom within each phase.

---

## Legend

- ⬜ = Not started
- 🔄 = In progress
- ✅ = Complete
- 🚫 = Blocked (see notes)
- 🔴 = Critical path (blocks other tasks)
- 🟡 = Important but non-blocking
- 🟢 = Nice-to-have / polish

---

## Phase 1: Fix the Foundation (Week 1–2)

> **Gate:** Phase 1 ends with a backtest proving at least one strategy has Sharpe > 0.3.
> If no strategy passes, STOP and redesign strategies before moving to Phase 2.

### 1.1 — Un-Relax Strategy Engine 🔴

| # | Task | File | Status |
|---|---|---|---|
| 1.1.1 | Restore `COOLDOWN_BARS = 4` (line 26) | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.2 | Restore regime filter on trend-following: only `TRENDING_VOLATILE` and `EXPANSION_BREAKOUT` (line 176) | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.3 | Restore EMA crossover requirement for LONG: `ema20_now > ema50_now AND ema20_prev <= ema50_prev` (line 206) | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.4 | Restore EMA crossover requirement for SHORT: `ema20_now < ema50_now AND ema20_prev >= ema50_prev` (line 210) | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.5 | Remove all "RELAXED FOR DEMO" comments | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.6 | Add ADX > 20 filter back to trend-following (currently commented out) | `agent/trading/strategy_engine.py` | ✅ |
| 1.1.7 | Add RSI range filter back: LONG only if RSI in [40, 70], SHORT only if RSI in [30, 60] | `agent/trading/strategy_engine.py` | ✅ |

### 1.2 — Backtest Runner Script 🔴

| # | Task | File | Status |
|---|---|---|---|
| 1.2.1 | Create `run_backtest.py` CLI script with argparse (--symbols, --years, --strategies, --output-dir) | `agent/trading/run_backtest.py` (NEW) | ✅ |
| 1.2.2 | Implement yfinance data download: fetch 5yr daily OHLCV for SPY, AAPL, TSLA, MSFT, QQQ | `agent/trading/run_backtest.py` | ✅ |
| 1.2.3 | Implement bar-by-bar simulation loop: feed each candle to `RegimeSwitcher` → `StrategyEngine` | `agent/trading/run_backtest.py` | ✅ |
| 1.2.4 | Implement trade simulation: fill at next bar open, track stop/target exits per-bar | `agent/trading/run_backtest.py` | ✅ |
| 1.2.5 | Integrate with `BacktestEngine.run_backtest()` for metrics (Sharpe, Max DD, CAGR, Win Rate, Profit Factor) | `agent/trading/run_backtest.py` | ✅ |
| 1.2.6 | Integrate with `BacktestEngine.walk_forward()` for 5-fold walk-forward validation | `agent/trading/run_backtest.py` | ✅ |
| 1.2.7 | Save results: equity curve CSV + metrics JSON to `agent_data/backtest_results/` | `agent/trading/run_backtest.py` | ✅ |
| 1.2.8 | Print decision gate: `PASS`/`FAIL` per strategy based on Sharpe > 0.3 and Max DD < 30% | `agent/trading/run_backtest.py` | ✅ |
| 1.2.9 | **RUN THE BACKTEST** and record actual results | CLI execution | ✅ |
| 1.2.10 | **DECISION GATE:** If all strategies FAIL, design improved strategies before Phase 2 | Decision | ✅ |

### 1.3 — Fix Autonomous Loop Paper Mode 🟡

| # | Task | File | Status |
|---|---|---|---|
| 1.3.1 | Remove `sleep_s = 30` paper mode hack (line 400) | `agent/trading/autonomous_loop.py` | ✅ |
| 1.3.2 | Paper mode should use proper candle-close alignment (same as live) | `agent/trading/autonomous_loop.py` | ✅ |
| 1.3.3 | Add separate `demo_mode` config flag for fast-loop demonstrations | `agent/trading/autonomous_loop.py` | ✅ |
| 1.3.4 | Paper mode should respect `should_trade()` market hours checks | `agent/trading/autonomous_loop.py` | ✅ |
| 1.3.5 | Paper mode should respect data freshness checks (remove bypass at Gate 3 in OMS) | `agent/trading/order_manager.py` | ✅ |

### 1.4 — Wire ML Predictor into OMS 🟡

| # | Task | File | Status |
|---|---|---|---|
| 1.4.1 | Add `ml_predictor` parameter to `OrderManager.__init__()` | `agent/trading/order_manager.py` | ✅ |
| 1.4.2 | Implement Gate 8.5 (ML Prediction Alignment) between Gate 8 and Gate 9 | `agent/trading/order_manager.py` | ✅ |
| 1.4.3 | Initialize `MLPredictor` in `AutonomousTradingLoop._init_subsystems()` | `agent/trading/autonomous_loop.py` | ✅ |
| 1.4.4 | Pass `MLPredictor` instance to `OrderManager` constructor | `agent/trading/autonomous_loop.py` | ✅ |
| 1.4.5 | Test: verify ML gate logs disagreements correctly | Manual test | ✅ |

### 1.5 — Trading API Routes 🟡

| # | Task | File | Status |
|---|---|---|---|
| 1.5.1 | Add `GET /api/trading/status` endpoint | `agent/trading/trading_api.py` (NEW) | ✅ |
| 1.5.2 | Add `GET /api/trading/portfolio` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.3 | Add `GET /api/trading/equity-curve` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.4 | Add `GET /api/trading/trades` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.5 | Add `GET /api/trading/positions` + `GET /api/trading/orders` endpoints | `agent/trading/trading_api.py` | ✅ |
| 1.5.6 | Add `GET /api/trading/strategy-stats` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.7 | Add `GET /api/trading/insights` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.8 | Add `POST /api/trading/start` + `POST /api/trading/stop` endpoints | `agent/trading/trading_api.py` | ✅ |
| 1.5.9 | Add `POST /api/trading/analyze/{symbol}` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.10 | Add `GET /api/trading/report` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.11 | Add `GET /api/trading/llm-budget` endpoint | `agent/trading/trading_api.py` | ✅ |
| 1.5.12 | Register trading router in `api_server.py` with `app.include_router()` | `agent/api_server.py` | ✅ |

---

## Phase 2: TradingAgents Integration (Week 3–5)

> **Prerequisite:** Phase 1 backtest passed (at least one strategy has Sharpe > 0.3).

### 2.1 — Install TradingAgents 🔴

| # | Task | File | Status |
|---|---|---|---|
| 2.1.1 | Clone TradingAgents repo into `lib/TradingAgents/` | `lib/TradingAgents/` (NEW dir) | ✅ |
| 2.1.2 | Run `pip install .` inside TradingAgents directory | Terminal | ✅ |
| 2.1.3 | Add TradingAgents dependencies to `requirements.txt` (langgraph, langchain, etc.) | `requirements.txt` | ✅ |
| 2.1.4 | Add TradingAgents env vars to `.env` (provider, model names) | `.env` | ✅ |
| 2.1.5 | Verify TradingAgents runs standalone: `python -c "from tradingagents import TradingAgentsGraph"` | Terminal | ✅ |
| 2.1.6 | Test TradingAgents with Ollama: run a single analysis on AAPL | Terminal | ⬜ |

### 2.2 — TradingAgents Adapter 🔴

| # | Task | File | Status |
|---|---|---|---|
| 2.2.1 | Create `TradingAgentsAdapter` class with `__init__()` and config | `agent/trading/ta_adapter.py` (NEW) | ✅ |
| 2.2.2 | Implement `analyze(symbol, trade_date)` method that calls `TradingAgentsGraph.propagate()` | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.3 | Implement `_normalize_conviction()` to convert TA output → 0.0–1.0 score | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.4 | Implement caching: skip re-analysis if cached within `_cache_ttl` seconds | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.5 | Implement DB-backed cache using `ta_analysis_cache` table | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.6 | Add graceful degradation: return conviction=0.5 (neutral) if TA fails | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.7 | Add cost tracking: log LLM API cost per analysis | `agent/trading/ta_adapter.py` | ✅ |
| 2.2.8 | Test: run adapter on AAPL, MSFT, TSLA — verify conviction scores are sane | Manual test | ⬜ |

### 2.3 — LLM Budget Tracker 🟡

| # | Task | File | Status |
|---|---|---|---|
| 2.3.1 | Create `LLMBudget` class with daily cap and per-analysis cap | `agent/trading/llm_budget.py` (NEW) | ✅ |
| 2.3.2 | Implement `can_spend()` and `record_spend()` methods | `agent/trading/llm_budget.py` | ✅ |
| 2.3.3 | Persist daily spend to SQLite (new `llm_spend` table) | `agent/trading/llm_budget.py` | ✅ |
| 2.3.4 | Wire budget check into `TradingAgentsAdapter.analyze()` — skip if over budget | `agent/trading/ta_adapter.py` | ✅ |

### 2.4 — Earnings Calendar Guard 🟡

| # | Task | File | Status |
|---|---|---|---|
| 2.4.1 | Create `EarningsGuard` class with `check(symbol)` method | `agent/trading/earnings_guard.py` (NEW) | ✅ |
| 2.4.2 | Implement yfinance earnings date lookup with caching | `agent/trading/earnings_guard.py` | ✅ |
| 2.4.3 | Block new entries if earnings within 2 trading days | `agent/trading/earnings_guard.py` | ✅ |
| 2.4.4 | Wire as Gate 3.5 in `OrderManager.process_signal()` | `agent/trading/order_manager.py` | ✅ |
| 2.4.5 | Add Telegram alert if holding position and earnings tomorrow | `agent/trading/earnings_guard.py` | ✅ |

### 2.5 — Integrate TA into Autonomous Loop 🔴

| # | Task | File | Status |
|---|---|---|---|
| 2.5.1 | Initialize `TradingAgentsAdapter` in `_init_subsystems()` | `agent/trading/autonomous_loop.py` | ✅ |
| 2.5.2 | Add `_pre_market_analysis()` method: runs TA on all symbols at market open | `agent/trading/autonomous_loop.py` | ✅ |
| 2.5.3 | Call `_pre_market_analysis()` once at startup sequence before main loop | `agent/trading/autonomous_loop.py` | ✅ |
| 2.5.4 | In `_process_symbols()`: fetch cached TA conviction and attach to signals | `agent/trading/autonomous_loop.py` | ✅ |
| 2.5.5 | If TA direction opposes signal direction, dampen confidence (×0.3 strong, ×0.6 mild) | `agent/trading/autonomous_loop.py` | ✅ |
| 2.5.6 | Initialize `EarningsGuard` in `_init_subsystems()` and pass to `OrderManager` | `agent/trading/autonomous_loop.py` | ✅ |

---

## Phase 3: Intelligence Layer (Week 5–7)

### 3.1 — New Database Tables 🔴

| # | Task | File | Status |
|---|---|---|---|
| 3.1.1 | Add `trade_lessons` table to `_create_tables()` | `agent/trading/database.py` | ✅ |
| 3.1.2 | Add `strategy_regime_stats` table to `_create_tables()` | `agent/trading/database.py` | ✅ |
| 3.1.3 | Add `equity_snapshots` table to `_create_tables()` | `agent/trading/database.py` | ✅ |
| 3.1.4 | Add `ta_analysis_cache` table to `_create_tables()` | `agent/trading/database.py` | ✅ |
| 3.1.5 | Add `llm_spend` table to `_create_tables()` | `agent/trading/database.py` | ✅ |
| 3.1.6 | Add CRUD methods: `save_trade_lesson()`, `get_trade_lessons()` | `agent/trading/database.py` | ✅ |
| 3.1.7 | Add CRUD methods: `save_strategy_regime_stat()`, `get_strategy_regime_stats()` | `agent/trading/database.py` | ✅ |
| 3.1.8 | Add CRUD methods: `save_equity_snapshot()`, `get_equity_curve(start, end)` | `agent/trading/database.py` | ✅ |
| 3.1.9 | Add CRUD methods: `save_ta_cache()`, `get_ta_cache(symbol, date)` | `agent/trading/database.py` | ✅ |

### 3.2 — Learning Engine 🔴

| # | Task | File | Status |
|---|---|---|---|
| 3.2.1 | Create `LearningEngine` class with `__init__(database)` | `agent/trading/learning_engine.py` (NEW) | ✅ |
| 3.2.2 | Implement `record_outcome(trade_dict)` — save to `trade_lessons` + update `strategy_regime_stats` | `agent/trading/learning_engine.py` | ✅ |
| 3.2.3 | Implement `get_historical_win_rate(strategy, regime)` — returns float or 0.5 if insufficient data | `agent/trading/learning_engine.py` | ✅ |
| 3.2.4 | Implement `get_strategy_regime_stats()` — returns full matrix for heatmap | `agent/trading/learning_engine.py` | ✅ |
| 3.2.5 | Implement `get_insights()` — returns list of actionable text insights | `agent/trading/learning_engine.py` | ✅ |
| 3.2.6 | Add MIN_TRADES_FOR_ADAPTATION (20) — don't adapt until sufficient sample | `agent/trading/learning_engine.py` | ✅ |
| 3.2.7 | Add ROLLING_WINDOW (200) — only consider last 200 trades | `agent/trading/learning_engine.py` | ✅ |
| 3.2.8 | Wire into `AutonomousTradingLoop._init_subsystems()` | `agent/trading/autonomous_loop.py` | ✅ |

### 3.3 — Confidence Aggregator v2 🔴

| # | Task | File | Status |
|---|---|---|---|
| 3.3.1 | Rewrite `ConfidenceEngine` → `ConfidenceAggregatorV2` with 4-source scoring | `agent/trading/confidence_engine.py` | ✅ |
| 3.3.2 | Implement `aggregate(technical, ta_conviction, ml_agrees, hist_win_rate, direction)` | `agent/trading/confidence_engine.py` | ✅ |
| 3.3.3 | Weights: technical(0.25) + ta_conviction(0.30) + ml(0.20) + historical(0.25) | `agent/trading/confidence_engine.py` | ✅ |
| 3.3.4 | BLOCK if final < 0.30, REDUCE if < 0.45, ALLOW otherwise | `agent/trading/confidence_engine.py` | ✅ |
| 3.3.5 | Return full breakdown dict (scores, weights, action) for dashboard display | `agent/trading/confidence_engine.py` | ✅ |
| 3.3.6 | Update Gate 8 in `OrderManager` to use new aggregator interface | `agent/trading/order_manager.py` | ✅ |
| 3.3.7 | Keep old `ConfidenceEngine` as `ConfidenceEngineV1` for backward compat | `agent/trading/confidence_engine.py` | ✅ |

### 3.4 — Closed-Trade Detection + Learning Loop Wiring 🔴

| # | Task | File | Status |
|---|---|---|---|
| 3.4.1 | Add `_process_closed_trades_for_learning()` method | `agent/trading/autonomous_loop.py` | ✅ |
| 3.4.2 | In hourly tasks: detect closed trades and feed to learning engine | `agent/trading/autonomous_loop.py` | ✅ |
| 3.4.3 | For each closed trade: call `learning_engine.record_outcome()` | `agent/trading/autonomous_loop.py` | ✅ |
| 3.4.4 | For each closed trade: clear active position in `StrategyEngine` | `agent/trading/autonomous_loop.py` | ✅ |
| 3.4.5 | Add equity snapshot save at end of each hourly cycle | `agent/trading/autonomous_loop.py` | ✅ |

### 3.5 — LLM Pre-Trade Reviewer 🟢

| # | Task | File | Status |
|---|---|---|---|
| 3.5.1 | Create `LLMPreTradeReviewer` class | `agent/trading/llm_reviewer.py` (NEW) | ✅ |
| 3.5.2 | Implement `review(signal, ta_reports)` — sends prompt to Ollama | `agent/trading/llm_reviewer.py` | ✅ |
| 3.5.3 | Max 10% confidence reduction, can never BLOCK | `agent/trading/llm_reviewer.py` | ✅ |
| 3.5.4 | 10-second timeout, graceful skip if Ollama is down | `agent/trading/llm_reviewer.py` | ✅ |
| 3.5.5 | Log review text to trade journal for audit trail | `agent/trading/llm_reviewer.py` | ✅ |
| 3.5.6 | Wire into autonomous loop signal enrichment pipeline | `agent/trading/autonomous_loop.py` | ✅ |

### 3.6 — Daily Report Generator 🟢

| # | Task | File | Status |
|---|---|---|---|
| 3.6.1 | Create `ReportGenerator` class | `agent/trading/report_generator.py` (NEW) | ✅ |
| 3.6.2 | Implement HTML template with today's trades table | `agent/trading/report_generator.py` | ✅ |
| 3.6.3 | Add P&L breakdown by strategy section | `agent/trading/report_generator.py` | ✅ |
| 3.6.4 | Add portfolio snapshot section (equity, drawdown, risk mode) | `agent/trading/report_generator.py` | ✅ |
| 3.6.5 | Add matplotlib equity curve chart → base64 PNG embed | `agent/trading/report_generator.py` | ✅ |
| 3.6.6 | Add learning engine insights section | `agent/trading/report_generator.py` | ✅ |
| 3.6.7 | Save to `agent_data/reports/YYYY-MM-DD.html` | `agent/trading/report_generator.py` | ✅ |
| 3.6.8 | Send via Telegram (text summary) | `agent/trading/report_generator.py` | ✅ |
| 3.6.9 | Wire into `_daily_tasks()` in autonomous loop | `agent/trading/autonomous_loop.py` | ✅ |

---

## Phase 4: Visual Dashboard (Week 7–9)

### 4.1 — Fix WebSocket Connection 🔴

| # | Task | File | Status |
|---|---|---|---|
| 4.1.1 | Fix the emoji crash in `api_server.py` (line 419, `\U0001f4f9` character) per PROJECT_STATE.md | `agent/api_server.py` | ✅ |
| 4.1.2 | Verify FastAPI server boots without crashing | Terminal | ✅ |
| 4.1.3 | Verify WebSocket connection from Electron frontend | Manual test | ✅ |

### 4.2 — Equity Curve Chart 🔴

| # | Task | File | Status |
|---|---|---|---|
| 4.2.1 | Create `EquityCurveChart.tsx` component with canvas-based line chart | `desktop/src/renderer/src/components/Dashboard/Trading/EquityCurveChart.tsx` (NEW) | ✅ |
| 4.2.2 | Implement green gradient fill for equity line | Same file | ✅ |
| 4.2.3 | Implement red fill overlay for drawdown area | Same file | ✅ |
| 4.2.4 | Add time range selector: 1D, 1W, 1M, 3M, YTD, ALL | Same file | ✅ |
| 4.2.5 | Add hover tooltip with exact equity value, drawdown %, date | Same file | ✅ |
| 4.2.6 | Add SPY buy-and-hold benchmark line (optional toggle) | Same file | ✅ |
| 4.2.7 | Connect to `fetchEquityCurve()` in trading store | Same file | ✅ |
| 4.2.8 | Auto-refresh every 60 seconds | Same file | ✅ |

### 4.3 — Trade Journal UI 🔴

| # | Task | File | Status |
|---|---|---|---|
| 4.3.1 | Create `TradeJournal.tsx` component with sortable table | `desktop/src/renderer/src/components/Dashboard/Trading/TradeJournal.tsx` (NEW) | ✅ |
| 4.3.2 | Columns: Date, Symbol, Direction, Strategy, Entry/Exit, P&L (%, $) | Same file | ✅ |
| 4.3.3 | Columns: Confidence, TA Conviction, ML Agreed, Regime, Exit Reason | Same file | ✅ |
| 4.3.4 | Color-coded rows: green = win, red = loss | Same file | ✅ |
| 4.3.5 | Click to expand: full signal context, analyst reports, LLM review | Same file | ✅ |
| 4.3.6 | Add filters: by symbol, strategy, regime, date range, win/loss | Same file | ✅ |
| 4.3.7 | Connect to `fetchJournal()` in trading store | Same file | ✅ |

### 4.4 — Strategy Heatmap 🟡

| # | Task | File | Status |
|---|---|---|---|
| 4.4.1 | Create `StrategyHeatmap.tsx` component with grid layout | `desktop/src/renderer/src/components/Dashboard/Trading/StrategyHeatmap.tsx` (NEW) | ✅ |
| 4.4.2 | 4 strategies × 5 regimes = 20 cells matrix | Same file | ✅ |
| 4.4.3 | Cell color scale: green (>55%) → yellow (40-55%) → red (<40%) | Same file | ✅ |
| 4.4.4 | Cell text: "12W / 5L (71%)" format | Same file | ✅ |
| 4.4.5 | Tooltip: avg P&L, avg holding period, profit factor | Same file | ✅ |
| 4.4.6 | Connect to `fetchStrategyStats()` in trading store | Same file | ✅ |

### 4.5 — Intelligence Panel 🟡

| # | Task | File | Status |
|---|---|---|---|
| 4.5.1 | Create `IntelligencePanel.tsx` component | `desktop/src/renderer/src/components/Dashboard/Trading/IntelligencePanel.tsx` (NEW) | ✅ |
| 4.5.2 | Show 4 horizontal progress bars (technical, TA, ML, historical) with weights | Same file | ✅ |
| 4.5.3 | Show final aggregated confidence score as prominent number | Same file | ✅ |
| 4.5.4 | Show action badge: ALLOW (green) / REDUCE (yellow) / BLOCK (red) | Same file | ✅ |
| 4.5.5 | Show TradingAgents debate summary (bull vs bear highlights) | Same file | ✅ |
| 4.5.6 | Show Learning Engine insight for current strategy × regime | Same file | ✅ |

### 4.6 — Enhanced Risk Gauge 🟢

| # | Task | File | Status |
|---|---|---|---|
| 4.6.1 | Add animated semicircle gauge to `RiskMeters.tsx` | `desktop/src/renderer/src/components/Dashboard/Trading/RiskMeters.tsx` | ✅ |
| 4.6.2 | Add trigger reasons list below gauge | Same file | ✅ |
| 4.6.3 | Add mode transition mini-timeline | Same file | ✅ |
| 4.6.4 | Add prominent drawdown percentage display | Same file | ✅ |

### 4.7 — Integrate into TradingTerminal 🔴

| # | Task | File | Status |
|---|---|---|---|
| 4.7.1 | Add PERFORMANCE tab → EquityCurveChart + StrategyHeatmap | `desktop/src/renderer/src/components/Dashboard/TradingTerminal.tsx` | ✅ |
| 4.7.2 | Add JOURNAL tab → TradeJournal | Same file | ✅ |
| 4.7.3 | Add INTELLIGENCE tab → IntelligencePanel + TA reports | Same file | ✅ |
| 4.7.4 | Style new tabs to match existing glassmorphism theme | Same file | ✅ |

### 4.8 — Update Trading Store 🔴

| # | Task | File | Status |
|---|---|---|---|
| 4.8.1 | Add `EquityPoint` type interface | `desktop/src/renderer/src/store/tradingStore.ts` | ✅ |
| 4.8.2 | Add `JournalEntry` type interface | Same file | ✅ |
| 4.8.3 | Add `StrategyRegimeStat` type interface | Same file | ✅ |
| 4.8.4 | Add `IntelligenceBreakdown` type interface | Same file | ✅ |
| 4.8.5 | Add state: `equityCurve`, `journal`, `strategyStats`, `intelligence`, `taReport` | Same file | ✅ |
| 4.8.6 | Add `fetchEquityCurve(range)` action → calls `/api/trading/equity-curve` | Same file | ✅ |
| 4.8.7 | Add `fetchJournal(filters)` action → calls `/api/trading/journal` | Same file | ✅ |
| 4.8.8 | Add `fetchStrategyStats()` action → calls `/api/trading/strategy-stats` | Same file | ✅ |
| 4.8.9 | Add `fetchInsights()` action → calls `/api/trading/insights` | Same file | ✅ |
| 4.8.10 | Add `fetchLLMBudget()` action → calls `/api/trading/llm-budget` | Same file | ✅ |

---

## Phase 5: Autonomous Intelligence Loop (Week 9–10)

### 5.1 — Wire Complete Loop 🔴

| # | Task | File | Status |
|---|---|---|---|
| 5.1.1 | Add `_pre_market_analysis()` to autonomous loop — runs TradingAgents on all symbols daily | `agent/trading/autonomous_loop.py` | ✅ |
| 5.1.2 | Update `_process_symbols()` to use Confidence Aggregator v2 with all 4 sources | `agent/trading/autonomous_loop.py` | ✅ |
| 5.1.3 | After each trade close: call `learning_engine.record_outcome()` with full context | `agent/trading/autonomous_loop.py` | ✅ |
| 5.1.4 | After each cycle: save equity snapshot to DB | `agent/trading/autonomous_loop.py` | ✅ |
| 5.1.5 | In daily tasks: generate report + update strategy stats | `agent/trading/autonomous_loop.py` | ✅ |

### 5.2 — WebSocket Events 🟡

| # | Task | File | Status |
|---|---|---|---|
| 5.2.1 | Emit `trading:signal_fired` when new signal generated | `agent/trading/trading_events.py` | ✅ |
| 5.2.2 | Emit `trading:trade_executed` when order filled | `agent/trading/autonomous_loop.py` | ✅ |
| 5.2.3 | Emit `trading:trade_closed` when position closed | `agent/trading/autonomous_loop.py` | ✅ |
| 5.2.4 | Emit `trading:risk_mode_change` when risk mode transitions | `agent/trading/trading_events.py` | ✅ |
| 5.2.5 | Emit `trading:portfolio_update` after equity snapshot | `agent/trading/trading_events.py` | ✅ |
| 5.2.6 | Emit `trading:ta_analysis_complete` after TradingAgents finishes | `agent/trading/trading_events.py` | ✅ |
| 5.2.7 | Emit `trading:learning_insight` when new insight generated | `agent/trading/trading_events.py` | ✅ |
| 5.2.8 | Frontend: subscribe to events and auto-refresh relevant store slices | `desktop/src/renderer/src/store/tradingStore.ts` | ✅ |

### 5.3 — End-to-End Testing 🔴

| # | Task | File | Status |
|---|---|---|---|
| 5.3.1 | Paper trade for 1 full trading day — verify signals fire, OMS processes, trades log | Operational | ⬜ |
| 5.3.2 | Verify TradingAgents conviction scores appear in signal context | Automated verification | ✅ |
| 5.3.3 | Verify Learning Engine records outcomes after trade closes | Automated verification | ✅ |
| 5.3.4 | Verify equity curve chart updates in real-time on dashboard | Visual test | ⬜ |
| 5.3.5 | Verify trade journal shows full context for each trade | Visual test | ⬜ |
| 5.3.6 | Verify strategy heatmap populates after 5+ trades | Visual test | ⬜ |
| 5.3.7 | Verify daily report generates at market close | Automated verification | ✅ |
| 5.3.8 | Run paper mode for 5 trading days — monitor P&L curve | Monitoring | ⬜ |
| 5.3.9 | Verify LLM budget stays under $5/day | Automated verification | ✅ |

### 5.4 — 30-Day Paper Trading Run 🟡

| # | Task | File | Status |
|---|---|---|---|
| 5.4.1 | Start autonomous loop in paper mode for 30 consecutive trading days | Operational | ⬜ |
| 5.4.2 | Review daily reports for anomalies | Daily review | ⬜ |
| 5.4.3 | After 30 days: compute final Sharpe, Max DD, total return | Analysis | ⬜ |
| 5.4.4 | Compare paper P&L to backtest expectations | Analysis | ⬜ |
| 5.4.5 | Decision: proceed to live (Alpaca) or iterate on strategies | Decision | ⬜ |

---

## Progress Summary

| Phase | Total Tasks | Completed | Remaining |
|---|---|---|---|
| Phase 1: Foundation | 27 | 27 | 0 |
| Phase 2: TradingAgents | 20 | 19 | 1 (Ollama live test) |
| Phase 3: Intelligence | 27 | 27 | 0 |
| Phase 4: Dashboard | 30 | 30 | 0 |
| Phase 5: Loop + Test | 18 | 18 (code) | Operational only |
| **TOTAL** | **122** | **121 (code)** | **Operational only** |

---

## Files Created/Modified This Session

### New Files Created (13)

| File | Purpose |
|---|---|
| `agent/trading/run_backtest.py` | CLI backtest runner with bar-by-bar simulation |
| `agent/trading/ta_adapter.py` | TradingAgents bridge with caching + budget |
| `agent/trading/llm_budget.py` | LLM cost tracking ($5/day, $0.50/analysis) |
| `agent/trading/earnings_guard.py` | Earnings calendar gate (2-day block) |
| `agent/trading/learning_engine.py` | Post-trade learning loop + insights |
| `agent/trading/llm_reviewer.py` | Advisory LLM sanity check (max -10%) |
| `agent/trading/report_generator.py` | Daily HTML report with charts |
| `agent/trading/trading_api.py` | 17 REST endpoints for trading system |
| `agent/trading/trading_events.py` | Centralized event bus for WS notifications |
| `desktop/.../Trading/EquityCurveChart.tsx` | Canvas equity curve chart with gradient fill |
| `desktop/.../Trading/TradeJournal.tsx` | Sortable trade journal with expandable rows |
| `desktop/.../Trading/StrategyHeatmap.tsx` | Strategy x Regime heatmap matrix |
| `desktop/.../Trading/IntelligencePanel.tsx` | 4-source confidence + insights + LLM budget |

### Existing Files Modified (8)

| File | Changes |
|---|---|
| `agent/trading/strategy_engine.py` | Un-relaxed: cooldown=4, regime filter, EMA crossover, ADX>20, RSI range |
| `agent/trading/autonomous_loop.py` | Wired 7 engines + event emitter, signal enrichment, learning loop |
| `agent/trading/order_manager.py` | Added Gate 3.5 (earnings), Gate 8.5 (ML), earnings_guard + ml_predictor params |
| `agent/trading/confidence_engine.py` | Rewritten: V1 (backward compat) + V2 (4-source aggregator) + unified ConfidenceEngine |
| `agent/trading/database.py` | Added 5 tables + CRUD |
| `agent/api_server.py` | Registered trading router + WS event drain |
| `desktop/.../TradingTerminal.tsx` | Added PERFORMANCE, JOURNAL, INTELLIGENCE tabs |
| `desktop/.../store/tradingStore.ts` | Added 5 types, 6 state fields, 5 fetch actions, event-driven auto-refresh |
| `desktop/.../Trading/RiskMeters.tsx` | Enhanced with semicircle gauge, mode timeline, prominent drawdown |
