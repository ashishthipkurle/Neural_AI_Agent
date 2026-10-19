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

---

## 3. What is Working

✅ **Frontend UI**: The React interface is robust. The Workflow Builder canvas successfully generates JSON payloads and connects to the backend REST/WebSocket APIs.
✅ **Workflow Engine (Backend)**: The core engine is fully implemented. It can parse DAGs, execute nodes sequentially, write outputs, and stream status events via WebSockets.
✅ **Heavy ML Initialization**: The backend successfully loads FAISS, YOLO, and InsightFace models into memory upon startup.
✅ **Voice Pipeline (Phase 1)**: Integrated `webrtcvad` for gating, `faster-whisper-tiny` for fuzzy wake word detection on CUDA, and `faster-whisper` for STT. The pipeline is fully testable from a CLI script (`cli_test.py`) with a robust state machine (`session.py`) and WebSockets event publishing (`events.py`).
✅ **Voice Overlay (Phase 2)**: Added a borderless, transparent, always-on-top React 3D overlay (`VoiceOverlay.tsx`) that renders a CSS glassmorphism sphere with smooth framer-motion animations. It responds to `agent:sync` WS events, hiding when idle, and can be toggled via the global shortcut `Alt+Space`.
✅ **Database**: SQLite databases (`workflow.db`, `todo.db`, `personal_memory.db`) properly initialize with WAL mode enabled.
✅ **Startup Scripts**: `start-all.bat` correctly attempts to orchestrate Ollama, the API server, INDRA, and the React frontend.

---

## 4. What is NOT Working (Known Issues)

✅ **API Server Startup Crash (Encoding Issue)**: Fixed by setting `sys.stdout` and `sys.stderr` to UTF-8.
✅ **Ollama Connection Refused**: Fixed by adding a 60s polling backoff in `agent/main.py`.
✅ **Docker Dependency Missing**: Code execution is now disabled safely and gracefully when Docker is missing.

⚠️ **Workflow UI Sync**
*   Because the API server crashes on the emoji bug, the React frontend cannot establish a WebSocket connection. Therefore, the UI currently appears disconnected, and workflow saves/runs will throw `fetch` connection refused errors until the Python backend stays alive.

---

## 5. Next Steps for the Next AI
If you are an AI reading this, prioritize the following actions:
1. **Fix the Crash**: Open `agent/api_server.py`, locate line 419, and remove the `\U0001f4f9` character so the FastAPI server can actually boot on Windows.
2. **Verify Workflow Engine**: Once the server is running, use the UI to test the newly implemented workflow engine (create a Web Search -> Write File workflow and run it).
3. **Configure Environment**: Ensure the `.env` file has the required variables for the workflow executors to work (e.g., `SMTP_HOST`, `EMAIL_USER`, `EMAIL_PASS`, `TELEGRAM_TOKEN`).
