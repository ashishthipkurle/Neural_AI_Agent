"""
FastAPI Server for Web UI Integration

This server bridges the React web interface to the NeuralAgent,
enabling full tool execution (open apps, browser, etc.) from the web UI.

Run with: python -m agent.api_server
Or: uvicorn agent.api_server:app --reload --port 8000
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime
import uuid

# Set API mode BEFORE importing agent - this enables auto-approval for actions
os.environ['AGENT_API_MODE'] = 'true'

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("AgentAPI")

# Global agent instance
agent = None

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast event to all clients following mandatory schema."""
        if not self.active_connections:
            return
            
        # Ensure timestamp is present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
            
        payload = json.dumps(message)
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

async def broadcast_event(event_type: str, role: str, text: str, task_id: str = None, partial: bool = False):
    """Helper to broadcast event according to mandatory model."""
    event = {
        "type": event_type,
        "role": role,
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": task_id,
        "partial": partial
    }
    await manager.broadcast(event)

class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str
    action_taken: Optional[str] = None

class StatusResponse(BaseModel):
    status: str
    initialized: bool
    locked: bool
    state: str

class Conversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

class Message(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str

class LoadContextRequest(BaseModel):
    conversation_id: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup."""
    global agent
    logger.info("🚀 Starting NeuralAgent API Server...")
    
    try:
        from agent.main import NeuralAgent
        agent = NeuralAgent()
        
        # Inject WebSocket broadcaster into agent/voice_manager
        # Ensure it's thread-safe as it's called from VoiceManager's worker threads
        loop = asyncio.get_running_loop()
        def sync_broadcast(event_type, role, text, task_id=None, partial=False):
            coro = broadcast_event(event_type, role, text, task_id, partial)
            loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))

        agent.sync_broadcast = sync_broadcast
        agent.initialize()
        
        # Hook into VoiceManager if available
        if agent._voice_manager:
            agent._voice_manager.on_stt = lambda text: sync_broadcast("stt", "user", text)
            agent._voice_manager.on_partial = lambda text: sync_broadcast("stt", "user", text, partial=True)
            agent._voice_manager.on_status = lambda text, role="system": sync_broadcast("status", role, text)
            
            # Start background voice loop
            async def handle_wake():
                logger.info("🎙 Wake word detected!")
                # Broadcast wake event so frontend clears partial STT messages
                await broadcast_event("wake", "system", "Wake word detected")
                await agent._voice_manager.greet()
                
            async def handle_voice_input(text):
                logger.info(f"🎙 Voice Input detected: {text}")
                
                # Yield to event loop to allow 'stt' broadcast (sent by VoiceManager.on_stt) to flush to UI
                await asyncio.sleep(0.05)
                
                # Explicitly broadcast processing status (ensures "Processing..." indicator appears)
                await broadcast_event("status", "system", "Processing...")
                
                await agent.process_input(text)
            
            asyncio.create_task(agent._voice_manager.start_voice_loop(
                on_wake=handle_wake, 
                on_input=handle_voice_input
            ))
            logger.info("🎙 Background voice interaction loop started")
            
        logger.info("✅ Agent initialized with Voice-Chat Bridge")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
        agent = None
    
    yield
    
    # Cleanup
    if agent:
        try:
            agent.shutdown()
        except:
            pass
    logger.info("👋 Agent API Server shutdown")

# Create FastAPI app
app = FastAPI(
    title="NeuralAgent API",
    description="Web API for the Humanoid Local AI Agent",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Register video stream router
try:
    from agent.video_stream import router as video_router
    app.include_router(video_router, prefix="/api")
    logger.info("📹 Video stream endpoint registered at /api/video_feed")
except Exception as e:
    logger.warning(f"⚠ Video stream not available: {e}")

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get agent status."""
    if agent is None:
        return StatusResponse(
            status="offline",
            initialized=False,
            locked=False,
            state="not_initialized"
        )
    
    return StatusResponse(
        status="online",
        initialized=agent._initialized,
        locked=agent._lock_controller.is_locked if agent._lock_controller else False,
        state=agent._state_machine.current_state.name if agent._state_machine else "unknown"
    )


class MuteRequest(BaseModel):
    muted: bool


@app.post("/api/mute")
async def toggle_mute(request: MuteRequest):
    """Toggle microphone mute state."""
    if agent is None or agent._voice_manager is None:
        raise HTTPException(status_code=503, detail="Agent or voice manager not initialized")
    
    agent._voice_manager.set_muted(request.muted)
    logger.info(f"🎤 Microphone mute toggled: {'MUTED' if request.muted else 'ACTIVE'}")
    
    return {"muted": request.muted, "status": "success"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process user input through the full agent pipeline.
    
    This handles:
    - Intent parsing (open notepad, search web, etc.)
    - Tool execution (launch apps, browser automation)
    - LLM fallback for general conversation
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    logger.info(f"📥 Received: {request.message}")
    if request.image:
        img_len = len(request.image)
        preview = request.image[:30] + "..." + request.image[-30:] if img_len > 60 else request.image
        logger.info(f"📷 Received image attachment! Length: {img_len} chars")
        logger.info(f"📷 Header/Preview: {preview}")
    
    try:
        # NUCLEAR OPTION: Hard Bypass for Surveillance Commands
        msg_lower = request.message.lower()
        if any(k in msg_lower for k in ["cctv", "surveillance", "start scan", "activate camera"]):
            if "start" in msg_lower or "activate" in msg_lower or "surveillance" in msg_lower:
                logger.info("🚀 HARD BYPASS: Activating Surveillance Web Stream!")
                # Don't launch subprocess - the web UI will stream via /api/video_feed
                return ChatResponse(
                    response="Surveillance activated! View the live feed in the Surveillance panel (CAM-01) on the right side of your screen.",
                    status="success",
                    action_taken="start_surveillance"
                )
            elif "stop" in msg_lower or "close" in msg_lower:
                logger.info("🛑 HARD BYPASS: Stopping Surveillance!")
                return ChatResponse(
                    response="Surveillance deactivated.",
                    status="success",
                    action_taken="stop_surveillance"
                )

        # Process through the full agent pipeline (Normal Path)
        response = await agent.process_input(request.message, image_data=request.image)
        
        logger.info(f"📤 Response: {response[:100]}...")
        
        return ChatResponse(
            response=response,
            status="success",
            action_taken=None  # Could be enhanced to report what tool was used
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing input: {e}")
        return ChatResponse(
            response=f"I encountered an error: {str(e)}",
            status="error",
            action_taken=None
        )

# ==========================================
# CHAT HISTORY ENDPOINTS
# ==========================================

@app.get("/api/conversations", response_model=List[Conversation])
async def get_conversations():
    """Get list of recent conversations."""
    if agent is None or agent._history_manager is None:
        return []
    
    return agent._history_manager.get_conversations()

@app.post("/api/conversations", response_model=Conversation)
async def create_conversation():
    """Create a new conversation."""
    if agent is None or agent._history_manager is None:
        raise HTTPException(status_code=503, detail="Agent history not initialized")
    
    conv_id = agent._history_manager.create_conversation("New Session")
    # Also switch context immediately
    await agent.load_context(conv_id)
    
    return agent._history_manager.get_conversation(conv_id)

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    if agent is None or agent._history_manager is None:
        raise HTTPException(status_code=503, detail="Agent history not initialized")
        
    agent._history_manager.delete_conversation(conversation_id)
    return {"status": "success"}

@app.post("/api/conversations/load")
async def load_conversation(request: LoadContextRequest):
    """Load context for a specific conversation."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
        
    success = await agent.load_context(request.conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Return messages so frontend can update UI
    messages = agent._history_manager.get_messages(request.conversation_id)
    return {"status": "success", "messages": messages}

@app.get("/api/conversations/{conversation_id}/messages", response_model=List[Message])
async def get_messages(conversation_id: str):
    """Get messages for a conversation without switching context."""
    if agent is None or agent._history_manager is None:
        return []
        
    return agent._history_manager.get_messages(conversation_id)

# ==========================================


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "agent_ready": agent is not None}


@app.post("/api/code", response_model=ChatResponse)
async def generate_code(request: ChatRequest):
    """
    Generate code using the specialized coding model (deepseek-coder).
    This endpoint is optimized for code generation tasks.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    logger.info(f"💻 Code generation request: {request.message[:100]}...")
    
    try:
        # Coding model for better code generation
        coding_model = "deepseek-coder:6.7b"
        logger.info(f"🤖 Using model: {coding_model}")
        
        # Direct call to Ollama with coding model
        # Timeout set to 600s (10 min) for slow CPU-based generation
        import httpx
        async with httpx.AsyncClient(timeout=600.0) as client:
            logger.info("📡 Sending request to Ollama (this may take 2-5 minutes on CPU)...")
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": coding_model,
                    "prompt": request.message,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,  # Lower for more precise code
                        "num_predict": 2048,  # More tokens for complete code
                    }
                }
            )
            
            logger.info(f"📡 Ollama response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                code_response = data.get("response", "")
                logger.info(f"✅ Code generated successfully ({len(code_response)} chars)")
                return ChatResponse(
                    response=code_response,
                    status="success",
                    action_taken="code_generation"
                )
            else:
                error_text = response.text
                logger.error(f"❌ Ollama error: {error_text}")
                raise Exception(f"Ollama returned status {response.status_code}: {error_text}")
                
    except httpx.TimeoutException:
        logger.error("⏱️ Request timed out")
        return ChatResponse(
            response="Code generation timed out. The model is taking too long to respond.",
            status="error",
            action_taken=None
        )
    except Exception as e:
        import traceback
        logger.error(f"❌ Code generation error: {e}")
        logger.error(traceback.format_exc())
        return ChatResponse(
            response=f"Code generation failed: {str(e) or 'Unknown error'}. Make sure Ollama is running and deepseek-coder:6.7b is installed.",
            status="error",
            action_taken=None
        )


class SaveFileRequest(BaseModel):
    path: str
    content: str
    directory: Optional[str] = None  # Custom directory to save to


@app.post("/api/save-file")
async def save_file(request: SaveFileRequest):
    """
    Save a generated file to disk.
    Files are saved to the specified directory or default generated folder.
    """
    import os
    
    # Use provided directory or default to generated folder
    if request.directory and os.path.isdir(request.directory):
        base_dir = request.directory
    else:
        base_dir = "D:\\All Projects\\My AI Agent\\generated"
    
    # Ensure the directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Get just the filename from the path
    filename = os.path.basename(request.path)
    full_path = os.path.join(base_dir, filename)
    
    logger.info(f"📁 Saving file: {full_path}")
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        logger.info(f"✅ File saved: {full_path}")
        return {"success": True, "path": full_path}
    except Exception as e:
        logger.error(f"❌ Failed to save file: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/list-files")
async def list_files(directory: str = "D:\\All Projects\\My AI Agent\\generated"):
    """
    List files in a directory.
    Used by the Code Editor to show files in the explorer.
    """
    import os
    
    try:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            return {"files": [], "directory": directory}
        
        files = []
        for entry in os.scandir(directory):
            files.append({
                "name": entry.name,
                "path": entry.path,
                "isDirectory": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0
            })
        
        # Sort: folders first, then files
        files.sort(key=lambda x: (not x["isDirectory"], x["name"].lower()))
        
        logger.info(f"📁 Listed {len(files)} files in {directory}")
        return {"files": files, "directory": directory}
    except Exception as e:
        logger.error(f"❌ Failed to list files: {e}")
        return {"files": [], "error": str(e)}


@app.get("/api/read-file")
async def read_file(path: str):
    """
    Read file contents.
    """
    import os
    
    try:
        if not os.path.exists(path):
            return {"content": "", "error": "File not found"}
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return {"content": content, "path": path}
    except Exception as e:
        return {"content": "", "error": str(e)}


class TerminalRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    shell: Optional[str] = "powershell"  # 'powershell' or 'cmd'


class TerminalResponse(BaseModel):
    output: str
    error: Optional[str] = None
    exit_code: int


@app.post("/api/terminal", response_model=TerminalResponse)
async def run_terminal_command(request: TerminalRequest):
    """
    Execute a shell command and return the output.
    Used by the integrated terminal in the Code Editor.
    """
    import subprocess
    import shlex
    
    command = request.command.strip()
    cwd = request.cwd or "D:\\All Projects\\My AI Agent"
    shell_type = request.shell or "powershell"
    
    logger.info(f"🖥️ Terminal [{shell_type}]: {command}")
    
    # Block dangerous commands
    dangerous = ['rm -rf /', 'format', 'del /f /s /q', 'rmdir /s /q C:', 'shutdown', 'restart']
    if any(d in command.lower() for d in dangerous):
        return TerminalResponse(
            output="",
            error="⚠️ Command blocked for safety",
            exit_code=1
        )
    
    try:
        import threading
        import time
        
        # Use appropriate shell
        if shell_type == "powershell":
            shell_cmd = ["powershell.exe", "-NoProfile", "-Command", command]
        else:
            shell_cmd = ["cmd.exe", "/c", command]
        
        # Use Popen for better control over output
        process = subprocess.Popen(
            shell_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Wait for process with timeout (5 sec for servers to produce output)
        try:
            stdout, stderr = process.communicate(timeout=5)
            output = stdout + stderr
            exit_code = process.returncode
            
            logger.info(f"✅ Command completed (exit: {exit_code})")
            
        except subprocess.TimeoutExpired:
            # Process is still running (like Flask/Node server)
            # Kill it and capture whatever output was produced
            process.kill()
            try:
                stdout, stderr = process.communicate(timeout=2)
                collected = (stdout or '') + (stderr or '')
                
                if collected.strip():
                    return TerminalResponse(
                        output=collected.strip(),
                        error=None,
                        exit_code=0
                    )
            except:
                pass
            
            return TerminalResponse(
                output="Server started. Check http://127.0.0.1:5000 or run in external terminal for full output.",
                error=None,
                exit_code=0
            )
        
        return TerminalResponse(
            output=output,
            error=error,
            exit_code=exit_code
        )
        
    except Exception as e:
        logger.error(f"❌ Terminal error: {e}")
        return TerminalResponse(
            output="",
            error=str(e),
            exit_code=1
        )


# Run with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
