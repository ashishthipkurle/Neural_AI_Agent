"""
INDRA API Bridge — Allows external UIs (like the Neural Trading Terminal)
to send text commands to INDRA as if they were spoken.
Includes WebSocket for real-time state broadcasting (edge lights).
"""

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import json
import asyncio

app = FastAPI(title="INDRA Bridge")

# Allow React frontend (port 5173) to access INDRA API (port 8001)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("IndraAPI")

# Global references to INDRA subsystems
_router = None
_chat_brain = None
_executor = None
_speaker = None
_latency = None
_memory = None
_injection_guard = None

# WebSocket connections for state broadcasting
_ws_connections: list[WebSocket] = []
_current_state = "idle"

def init_bridge(router, chat_brain, executor, speaker, latency, memory, injection_guard):
    """Register INDRA subsystems with the API bridge."""
    global _router, _chat_brain, _executor, _speaker, _latency, _memory, _injection_guard
    _router = router
    _chat_brain = chat_brain
    _executor = executor
    _speaker = speaker
    _latency = latency
    _memory = memory
    _injection_guard = injection_guard
    logger.info("INDRA API Bridge initialized")

def broadcast_state(state: str):
    """Broadcast INDRA state to all connected WebSocket clients."""
    global _current_state
    _current_state = state
    message = json.dumps({"type": "state", "state": state})
    
    dead = []
    for ws in _ws_connections:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(message), _loop)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            _ws_connections.remove(ws)
        except ValueError:
            pass

@app.get("/api/state")
async def get_state():
    """Get current INDRA state."""
    return {"state": _current_state}

@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket):
    """WebSocket endpoint for real-time state updates (edge lights)."""
    await websocket.accept()
    _ws_connections.append(websocket)
    logger.info(f"WebSocket client connected (total: {len(_ws_connections)})")
    
    # Send current state immediately
    await websocket.send_text(json.dumps({"type": "state", "state": _current_state}))
    
    try:
        while True:
            # Keep connection alive, receive pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected (total: {len(_ws_connections)})")

@app.post("/api/command")
async def receive_command(payload: dict, background_tasks: BackgroundTasks):
    """
    Receive a text command from an external UI.
    Routes it exactly like a spoken command.
    """
    text = payload.get("text", "").strip()
    if not text:
        return {"status": "error", "message": "Empty text"}

    logger.info(f"[API INPUT] Received via bridge: '{text}'")

    # Security scan
    if _injection_guard and not _injection_guard.scan(text, source="api"):
        if _speaker:
            _speaker.enqueue("I've detected a prohibited instruction sequence via the API. Ignoring.", priority=True)
        return {"status": "error", "message": "Security block"}

    # Classify intent
    if _router:
        intent_type = _router.classify(text)
    else:
        intent_type = "TYPE1"

    logger.info(f"API Intent classified as: {intent_type}")

    if intent_type in ("TYPE1", "TYPE2"):
        if _chat_brain:
            future = _chat_brain.respond_async(text)
            
            # Extract preferences after completion
            def post_chat_callback(f):
                try:
                    reply = f.result()
                    if _memory:
                        from memory.updater import extract_and_save_preferences
                        extract_and_save_preferences(_memory, text, reply)
                except Exception as e:
                    logger.error(f"Chat callback error: {e}")
                    
            future.add_done_callback(post_chat_callback)
            return {"status": "success", "intent": intent_type, "message": "Conversation started"}

    elif intent_type == "TYPE3":
        if _executor:
            # Run task in background so we can return immediately
            background_tasks.add_task(_executor.run_task, text)
            return {"status": "success", "intent": intent_type, "message": "Computer task started"}

    elif intent_type == "TYPE4":
        if _router and _speaker:
            clarification = _router.get_clarification(text)
            _speaker.enqueue(clarification)
            return {"status": "success", "intent": intent_type, "message": "Ambiguous, asking clarification"}

    return {"status": "error", "message": "Unknown routing error"}

# Store event loop reference for cross-thread broadcasting
_loop = None
_conv_logger = None

def init_conv_logger(conv_logger):
    """Register the conversation logger with the API."""
    global _conv_logger
    _conv_logger = conv_logger

@app.get("/api/indra/conversations")
async def get_indra_conversations():
    """Get all INDRA conversation history."""
    if _conv_logger is None:
        return []
    return _conv_logger.get_all_conversations()

@app.get("/api/indra/conversations/{conv_id}")
async def get_indra_conversation(conv_id: str):
    """Get a specific INDRA conversation with messages."""
    if _conv_logger is None:
        return {"error": "Not initialized"}
    data = _conv_logger.get_conversation(conv_id)
    if data is None:
        return {"error": "Not found"}
    return data

@app.delete("/api/indra/conversations/{conv_id}")
async def delete_indra_conversation(conv_id: str):
    """Delete a INDRA conversation."""
    if _conv_logger is None:
        return {"error": "Not initialized"}
    _conv_logger.delete_conversation(conv_id)
    return {"status": "success"}

def start_api_server_in_thread(port: int = 8001):
    """Start the FastAPI server in a background daemon thread."""
    import threading
    global _loop
    
    def run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error", loop="none")
        
    thread = threading.Thread(target=run, daemon=True, name="indra-api-bridge")
    thread.start()
    return thread

