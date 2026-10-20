# Neural AI Agent - Project State & Architecture

This document provides a comprehensive overview of the Neural AI Agent project. It is designed to be fed into an AI assistant to immediately provide context on the architecture, current implementation state, what is working, and what is currently broken.

---

## 1. Project Overview
**Neural AI Agent** is a complex, local-first AI assistant built as an Electron desktop application powered by a Python backend. It features deep OS integration, autonomous workflow automation (n8n-style), visual/facial recognition, memory (RAG), and local LLM execution via Ollama.

### Core Stack
*   **Frontend**: React, TypeScript, Vite, TailwindCSS.
*   **Desktop Container**: Electron (with IPC bridges to system and agent).
*   **Backend**: Python, FastAPI (`uvicorn` on port 8000), SQLite.
*   **Background Services**: INDRA background service (`jarvis/main.py` on port 8001).
*   **AI/ML Stack**: 
    *   **LLM**: Ollama (running locally on port 11434).
    *   **Vision/Faces**: InsightFace (`buffalo_l`), YOLOv8 (`yolov8n.pt`).
    *   **Memory/RAG**: `sentence-transformers` (`all-MiniLM-L6-v2`), FAISS vector database.

---

## 2. Architecture & Subsystems

### 2.1 Electron Desktop App (`desktop/`)
*   **Main Process**: Handles window creation, OS-level tray, and IPC handlers (`desktop/src/main/`).
*   **Renderer**: The React UI (`desktop/src/renderer/`). Contains a dashboard, an interactive 3D AI Globe (Three.js), chat interfaces, and a visual **Workflow Builder**.

### 2.2 Python API Server (`agent/`)
*   **Entry Point**: `agent/api_server.py`. Runs a FastAPI app exposing REST endpoints (`/api/chat`, `/api/workflow`) and a WebSocket endpoint for real-time bidirectional communication.
*   **Core Agent (`agent/main.py`)**: The `NeuralAgent` class orchestrates the tools, memory, and LLM processing.
*   **Tool Router**: Over 20+ specialized tools (file system, web search, mouse/keyboard control, screen capture, chart analysis).

### 2.3 Workflow Automation Engine (`agent/workflow/`)
*Recently implemented to replace a frontend-only mockup.*
*   **Engine (`workflow_engine.py`)**: Executes DAGs (Directed Acyclic Graphs) using Kahn's topological sort. Passes outputs from one node as inputs to the next.
*   **Store (`workflow_store.py`)**: SQLite (`workflow.db`) persistence for saved workflows, run history logs, and cron schedules.
*   **Executors (`workflow_executors.py`)**: Real functional Python handlers for visual nodes (IMAP/SMTP email, File I/O, Web Search, Beautifulsoup Scraping, Agent Routing, Telegram/System Notifications).
*   **Scheduler (`workflow_scheduler.py`)**: An `asyncio` loop running in the FastAPI lifespan that parses Cron strings and fires workflows automatically.

### 2.3 Intelligent Trading System (`agent/trading/`)
*Full autonomous trading system — 89 files, 121/122 tasks complete.*
*   **Strategies**: 4 strategies (Trend Following, Mean Reversion, Breakout, FAISS Pattern Matching) in `strategy_engine.py`.
*   **Order Management**: 16-gate OMS (`order_manager.py`) with risk filters, ML gate, earnings guard, confidence aggregation.
*   **Autonomous Loop** (`autonomous_loop.py`): Pre-market TA analysis → signal generation → OMS → position management → learning loop → daily reports.
*   **TradingAgents Integration** (`ta_adapter.py`): Multi-agent AI debate system via `lib/TradingAgents/` with conviction scoring, caching, and graceful Ollama fallback.
*   **Intelligence Layer**: 4-source confidence aggregator (`confidence_engine.py`), post-trade learning engine (`learning_engine.py`), LLM budget tracker (`llm_budget.py`), earnings guard (`earnings_guard.py`).
*   **ML Pipeline**: Feature engine (15-dim vectors), FAISS similarity search, gradient boosted ML predictor, regime-aware strategy adaptation.
*   **Dashboard Components** (React/TSX): Equity curve chart, trade journal, strategy heatmap, intelligence panel, risk meters — all wired to 18 REST endpoints + WebSocket event bus.
*   **Paper Trading**: `python -m agent.trading.start_paper --symbols SPY,QQQ,AAPL --capital 25000`

---

## 3. What is Working

✅ **Frontend UI**: The React interface is robust. The Workflow Builder canvas successfully generates JSON payloads and connects to the backend REST/WebSocket APIs.
✅ **Workflow Engine (Backend)**: The core engine is fully implemented. It can parse DAGs, execute nodes sequentially, write outputs, and stream status events via WebSockets.
✅ **Heavy ML Initialization**: The backend successfully loads FAISS, YOLO, and InsightFace models into memory upon startup.
✅ **Voice Pipeline (Phase 1)**: Integrated `webrtcvad` for gating, `faster-whisper-tiny` for fuzzy wake word detection on CUDA, and `faster-whisper` for STT. The pipeline is fully testable from a CLI script (`cli_test.py`) with a robust state machine (`session.py`) and WebSockets event publishing (`events.py`).
✅ **Voice Overlay (Phase 2)**: Added a borderless, transparent, always-on-top React 3D overlay (`VoiceOverlay.tsx`) that renders a CSS glassmorphism sphere with smooth framer-motion animations. It responds to `agent:sync` WS events, hiding when idle, and can be toggled via the global shortcut `Alt+Space`.
✅ **Database**: SQLite databases (`workflow.db`, `todo.db`, `personal_memory.db`, `trading.db`) properly initialize with WAL mode enabled.
✅ **Startup Scripts**: `start-all.bat` correctly attempts to orchestrate Ollama, the API server, INDRA, and the React frontend.
✅ **Trading System (13/13 subsystems verified)**: Database, Strategy Engine, Confidence Aggregator V2, Learning Engine, Earnings Guard, LLM Budget, TA Adapter, Report Generator, LLM Reviewer, Event Emitter, Trading API (18 routes), Feature Engine, Autonomous Loop — all pass automated verification.

---

## 4. What is NOT Working (Known Issues)

✅ **API Server Startup Crash (Encoding Issue)**: Fixed by setting `sys.stdout` and `sys.stderr` to UTF-8.
✅ **Ollama Connection Refused**: Fixed by adding a 60s polling backoff in `agent/main.py`.
✅ **Docker Dependency Missing**: Code execution is now disabled safely and gracefully when Docker is missing.

⚠️ **Ollama Not Running**: TradingAgents requires Ollama for multi-agent AI debate analysis. The system gracefully degrades to conviction=0.5 (neutral) when Ollama is offline, but full TA analysis requires starting Ollama first.

⚠️ **Visual Dashboard Tests Pending**: Equity curve chart, trade journal, strategy heatmap, and intelligence panel need visual verification during a live paper trading session.

---

## 5. Next Steps
1. **Start Ollama**: Run `ollama serve` to enable TradingAgents multi-agent debate analysis.
2. **Paper Trade**: Run `python -m agent.trading.start_paper --symbols SPY,QQQ,AAPL --capital 25000` during US market hours.
3. **Verify Dashboard**: Open `http://localhost:8000`, navigate to Trading Terminal, and verify all tabs (PERFORMANCE, JOURNAL, INTELLIGENCE) update in real-time.
4. **30-Day Run**: After verifying a single day, run paper trading for 30 consecutive trading days and compute final Sharpe/MaxDD/return.
5. **Go-Live Decision**: Compare paper P&L to backtest expectations and decide whether to proceed to live trading (Alpaca).
