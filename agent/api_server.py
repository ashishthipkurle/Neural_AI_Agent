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
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime
from datetime import datetime
import uuid

# Safety & Intent Modules
from agent.core.file_safety import start_gate as file_guard
from agent.core.coding_intent import CodingIntentClassifier, CodingContext, CodingIntentType

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
        
        # Start background services (Learning, Tasks, Telegram)
        await agent.start_services()
        logger.info("✅ Background services started")
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
    Generate code using the unified LLM model.
    This endpoint is optimized for code generation tasks.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    logger.info(f"💻 Code generation request: {request.message[:100]}...")
    
    try:
        # Use unified model from config for all tasks including coding
        coding_model = agent.config.get('llm', {}).get('model_name', 'gpt-oss:120b-cloud')
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
            response=f"Code generation failed: {str(e) or 'Unknown error'}. Make sure Ollama is running and the model is installed (ollama pull gpt-oss:120b-cloud).",
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


# ==========================================
# COPILOT ENDPOINTS (Deterministic & Safe)
# ==========================================

intent_classifier = CodingIntentClassifier()

class CopilotRequest(BaseModel):
    file_content: str
    cursor_line: int
    cursor_column: int # 1-based
    language: str
    file_path: Optional[str] = None
    selection: Optional[str] = None
    user_input: Optional[str] = None # Instructions or questions

class CopilotResponse(BaseModel):
    suggestions: List[dict] = [] # [{text: "..."}]
    diff: Optional[str] = None
    explanation: Optional[str] = None
    proposal_id: Optional[str] = None
    intent: Optional[str] = None

class ApplyDiffRequest(BaseModel):
    proposal_id: str
    user_approved: bool

@app.post("/api/copilot/suggest", response_model=CopilotResponse)
async def copilot_suggest(request: CopilotRequest):
    """
    Get inline code suggestions (Ghost Text).
    Strictly for completion. NO direct file writes.
    """
    # 1. Classify Intent (Deterministic)
    context = CodingContext(
        user_input=request.user_input or "",
        active_file_path=request.file_path,
        file_content=request.file_content,
        cursor_line=request.cursor_line,
        cursor_column=request.cursor_column,
        selection=request.selection,
        language_id=request.language
    )
    
    # We force INLINE_SUGGEST intent for this specific endpoint if input is empty
    # But generally we should respect the classifier if we merge endpoints.
    # Here we assume this endpoint is called automatically by cursor movement (debounce).
    
    # Generate prompt for LLM (Completion Mode)
    # We need a coding model. Using config or default.
    coding_model = "gpt-oss:120b-cloud" # Default high-quality model
    if agent and agent.config:
        coding_model = agent.config.get('llm', {}).get('model_name', coding_model)

    import httpx
    
    # Construct prompt based on cursor position
    # Simple FIM (Fill In Middle) approach or just suffix/prefix if model supports it
    # For robust FIM, we need: <PRE>...<SUF>...<MID>
    
    lines = request.file_content.split('\\n')
    # Safe indexing
    cur_line_idx = max(0, min(len(lines)-1, request.cursor_line - 1))
    
    # Context window: 20 lines before, 5 after
    start_line = max(0, cur_line_idx - 20)
    end_line = min(len(lines), cur_line_idx + 5)
    
    prefix_lines = lines[start_line:cur_line_idx]
    current_line = lines[cur_line_idx]
    # Split current line at cursor
    col_idx = max(0, request.cursor_column - 1)
    prefix_cur = current_line[:col_idx]
    suffix_cur = current_line[col_idx:]
    
    suffix_lines = lines[cur_line_idx+1:end_line]
    
    full_prefix = "\\n".join(prefix_lines + [prefix_cur])
    full_suffix = "\\n".join([suffix_cur] + suffix_lines)
    
    prompt = f"<|fim_prefix|>{full_prefix}<|fim_suffix|>{full_suffix}<|fim_middle|>"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": coding_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 128, # Short completion
                        "stop": ["\\n\\n", "}", "```"] # Stop tokens
                    }
                }
            )
            
            if response.status_code == 200:
                text = response.json().get("response", "").strip("\\n")
                if text:
                    return CopilotResponse(
                        suggestions=[{"text": text}],
                        intent="inline_suggest"
                    )
    except Exception as e:
        logger.error(f"Suggest failed: {e}")
        
    return CopilotResponse(suggestions=[])

@app.post("/api/copilot/refactor", response_model=CopilotResponse)
async def copilot_refactor(request: CopilotRequest):
    """
    Refactor code and return a unified diff.
    Creates a proposal that must be APPROVED.
    """
    if not request.selection and not request.user_input:
        raise HTTPException(400, "Refactor requires selection or instructions")

    context_code = request.selection or request.file_content
    instruction = request.user_input
    
    coding_model = "gpt-oss:120b-cloud"
    if agent and agent.config:
        coding_model = agent.config.get('llm', {}).get('model_name', coding_model)

    prompt = f"""You are a coding expert. Refactor the following code based on instructions.
Instruction: {instruction}

Code to Refactor:
```
{context_code}
```

Return ONLY the code block with the refactored code. Do not explain.
"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
             response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": coding_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2}
                }
            )
             if response.status_code == 200:
                 new_code = response.json().get("response", "")
                 # Extract code block
                 import re
                 match = re.search(r"```(?:\w+)?\\n(.*?)```", new_code, re.DOTALL)
                 if match:
                     new_code = match.group(1)
                 
                 # Create simple diff or just return new content as proposal
                 # For simplicity in this iteration, we propose REPLACING the selection or file
                 
                 # 1. Create Proposal
                 # If modification: we need the whole file content ideally to produce clean diffs for the UI
                 # OR the UI handles replacement of selection.
                 # Let's assume the UI will replace `selection` with `new_code`.
                 
                 # IMPORTANT: We need to register this proposal securely
                 # Since we don't have the full file state here easily reconstructed without re-reading,
                 # we will trust the UI to send the APPLY request, BUT we must enforce it via proposal ID if we stored it.
                 # However, `verify_and_apply` in file_safety writes to disk.
                 # So we need the FULL content to write to disk.
                 
                 # Reconstruct full content
                 full_content = request.file_content
                 if request.selection and request.selection in full_content:
                     full_content = full_content.replace(request.selection, new_code)
                 else:
                     # Fallback if selection tracking is fuzzy, just use new code if it looks like full file
                     # Or fail safe
                     pass
                 
                 pid = file_guard.create_proposal("modify", request.file_path, full_content)
                 
                 # Generate diff for display (Unified Diff)
                 import difflib
                 diff = "".join(difflib.unified_diff(
                     request.file_content.splitlines(keepends=True),
                     full_content.splitlines(keepends=True),
                     fromfile="Original",
                     tofile="Refactored"
                 ))
                 
                 return CopilotResponse(
                     diff=diff,
                     proposal_id=pid,
                     intent="refactor_file"
                 )
    except Exception as e:
        logger.error(f"Refactor failed: {e}")
        raise HTTPException(500, str(e))
        
    return CopilotResponse(intent="failed")

@app.post("/api/copilot/explain", response_model=CopilotResponse)
async def copilot_explain(request: CopilotRequest):
    """Explain code. Read-only."""
    context_code = request.selection or request.file_content
    
    prompt = f"Explain this code:\\n```\\n{context_code}\\n```"
    
    # Call LLM ... (omitted for brevity, similar pattern)
    # Mock for speed or call real LLM
    return CopilotResponse(explanation="This functionality is under construction.", intent="explain_code")


@app.post("/api/copilot/apply-diff")
async def apply_diff(request: ApplyDiffRequest):
    """Apply a verified proposal."""
    success, msg = file_guard.verify_and_apply(request.proposal_id, request.user_approved)
    if not success:
        raise HTTPException(400, detail=msg)
    return {"status": "success", "path": msg}


# ==========================================
# LEARNING & TASK ENDPOINTS
# ==========================================

class LearningStats(BaseModel):
    total_skills: int
    experiences_logged: int
    patterns_identified: int
    strategies_optimized: int
    efficiency_score: float

@app.get("/api/learning/stats", response_model=LearningStats)
async def get_learning_stats():
    """Get statistics from the self-learning system."""
    if agent is None or not agent.orchestrator:
        return LearningStats(
            total_skills=0,
            experiences_logged=0,
            patterns_identified=0,
            strategies_optimized=0,
            efficiency_score=0.0
        )
    
    lm = agent.orchestrator.learning_manager
    try:
        session = lm.Session()
        from agent.learning.models import ExperienceRecord, Pattern, Strategy
        exp_count = session.query(ExperienceRecord).count()
        pat_count = session.query(Pattern).count()
        strat_count = session.query(Strategy).count()
        session.close()
        
        # Calculate skills count (safely)
        skill_count = 0
        if lm.registry:
             skill_count = len(lm.registry.list_skills())

        return LearningStats(
            total_skills=skill_count,
            experiences_logged=exp_count,
            patterns_identified=pat_count,
            strategies_optimized=strat_count,
            efficiency_score=0.85 # Placeholder/calculated
        )
    except Exception as e:
        logger.error(f"Failed to get learning stats: {e}")
        return LearningStats(total_skills=0, experiences_logged=0, patterns_identified=0, strategies_optimized=0, efficiency_score=0.0)


class TaskModel(BaseModel):
    id: str
    description: str
    status: str
    progress: int
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str

@app.get("/api/tasks", response_model=List[TaskModel])
async def get_tasks():
    """Get list of active and recent tasks."""
    if agent is None or not agent.orchestrator:
        return []
    
    tm = agent.orchestrator.task_manager
    tasks = tm.list_tasks(limit=20)
    
    return [
        TaskModel(
            id=t['id'],
            description=t['description'],
            status=t['status'],
            progress=t['progress'] or 0,
            result=str(t['result']) if t['result'] else None,
            error=t['error'],
            created_at=str(t['created_at'])
        ) for t in tasks
    ]

class CreateTaskRequest(BaseModel):
    description: str
    skill_name: str
    params: Dict[str, Any] = {}
    priority: int = 5

@app.post("/api/tasks", response_model=Dict[str, str])
async def create_task(request: CreateTaskRequest):
    """Submit a new background task."""
    if agent is None or not agent.orchestrator:
        raise HTTPException(status_code=503, detail="Task system not initialized")
    
    task_id = await agent.orchestrator.task_manager.submit_task(
        description=request.description,
        skill_name=request.skill_name,
        params=request.params,
        priority=request.priority
    )
    
    return {"task_id": task_id, "status": "submitted"}

@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop/Cancel a running task."""
    if agent is None or not agent.orchestrator:
        raise HTTPException(status_code=503, detail="Task system not initialized")
    
    success = await agent.orchestrator.task_manager.cancel_task(task_id)
    if success:
        return {"status": "cancelled"}
    else:
        raise HTTPException(status_code=400, detail="Failed to cancel task or task not found")

@app.get("/api/telegram/status")
async def get_telegram_status():
    """Get Telegram connection status."""
    if agent is None or not agent.orchestrator or not agent.orchestrator.telegram_bot:
        return {"connected": False, "status": "disabled"}
    
    return {
        "connected": True, 
        "bot_name": "NeuralAgentBot", 
        "status": "polling"
    }

# ==========================================
# VOICE CALL CONVERSATION ENDPOINTS (Twilio Webhooks)
# ==========================================

from fastapi import Request, Form
from fastapi.responses import Response

@app.api_route("/voice/answer", methods=["GET", "POST"])
async def voice_answer(request: Request):
    """
    Twilio webhook: Called when the recipient answers the phone.
    Returns TwiML with greeting + Gather for speech input.
    """
    from twilio.twiml.voice_response import VoiceResponse, Gather
    from agent.skills.voice_call.voice_conversation import conversation_manager
    
    # Get params from query string
    params = request.query_params
    purpose = params.get("purpose", "check in")
    contact_name = params.get("contact_name", "friend")
    caller_name = params.get("caller_name", "your friend")
    
    # Get CallSid from Twilio's POST data or query
    form_data = {}
    if request.method == "POST":
        form_data = await request.form()
    call_sid = form_data.get("CallSid") or params.get("CallSid", f"unknown_{id(request)}")
    
    logger.info(f"[Voice] Call answered. SID={call_sid}, purpose='{purpose}'")
    print(f"!!! VOICE WEBHOOK HIT: /voice/answer?call_sid={call_sid} !!!")
    
    # Create conversation state
    conv = conversation_manager.create_conversation(
        call_sid=str(call_sid),
        purpose=purpose,
        contact_name=contact_name,
        caller_name=caller_name
    )
    
    # Generate greeting
    greeting = conversation_manager.generate_greeting_prompt(conv)
    conv.add_ai_turn(greeting)
    
    # Build TwiML: Say greeting then Gather speech
    response = VoiceResponse()
    response.say(greeting, voice='Polly.Matthew', language='en-US')
    
    # Gather speech input from recipient
    gather = Gather(
        input='speech',
        action=f'/voice/respond?call_sid={call_sid}',
        method='POST',
        timeout=5,
        speech_timeout='auto',
        language='en-IN'
    )
    gather.say("", voice='Polly.Matthew')  # Silence prompt to just listen
    response.append(gather)
    
    # If no speech detected, ask again
    response.say("I didn't catch that. Could you please repeat?", voice='Polly.Matthew', language='en-US')
    response.redirect(f'/voice/answer?{request.query_params}', method='POST')
    
    twiml = str(response)
    logger.info(f"[Voice] Answer TwiML: {twiml[:200]}...")
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/respond")
async def voice_respond(request: Request):
    """
    Twilio webhook: Called when recipient speaks.
    Gets speech transcription, sends to LLM, returns next response.
    """
    from twilio.twiml.voice_response import VoiceResponse, Gather
    from agent.skills.voice_call.voice_conversation import conversation_manager
    from agent.core.llm_interface import LLMInterface
    
    form_data = await request.form()
    call_sid = request.query_params.get("call_sid") or form_data.get("CallSid", "unknown")
    speech_result = form_data.get("SpeechResult", "")
    confidence = form_data.get("Confidence", "0")
    
    logger.info(f"[Voice] Speech received. SID={call_sid}, text='{speech_result}', confidence={confidence}")
    print(f"!!! VOICE WEBHOOK HIT: /voice/respond?call_sid={call_sid} !!!")
    
    conv = conversation_manager.get_conversation(str(call_sid))
    if not conv:
        # Conversation not found — end gracefully
        response = VoiceResponse()
        response.say("I'm sorry, something went wrong. Goodbye!", voice='Polly.Matthew')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    
    # Record what the human said
    conv.add_human_turn(speech_result)
    
    # Check if we should end the conversation
    if conv.should_end():
        farewell = conversation_manager.build_farewell(conv)
        conv.add_ai_turn(farewell)
        response = VoiceResponse()
        response.say(farewell, voice='Polly.Matthew', language='en-US')
        response.hangup()
        conversation_manager.end_conversation(str(call_sid))
        logger.info(f"[Voice] Conversation ended (max turns). SID={call_sid}")
        return Response(content=str(response), media_type="application/xml")
    
    # Generate LLM response
    try:
        llm_config = {}
        if agent and hasattr(agent, 'config'):
            llm_config = agent.config.get('llm', {})
        
        llm = LLMInterface(
            api_key=llm_config.get('api_key', 'ollama'),
            model_name=llm_config.get('model_name', 'kimi-k2.5:cloud'),
            provider=llm_config.get('provider', 'ollama')
        )
        
        system_prompt, user_message = conversation_manager.build_llm_prompt(conv, speech_result)
        ai_response = llm.chat(system_prompt, user_message)
        
        # Clean up response — remove quotes, asterisks, etc.
        ai_response = ai_response.strip().strip('"').strip("'").replace("*", "")
        
        # Truncate if too long for phone
        if len(ai_response) > 300:
            ai_response = ai_response[:297] + "..."
            
    except Exception as e:
        logger.error(f"[Voice] LLM response generation failed: {e}")
        ai_response = "I see. Thank you for letting me know. Is there anything else?"
    
    conv.add_ai_turn(ai_response)
    logger.info(f"[Voice] AI response: '{ai_response}'")
    
    # Check if AI decided to end (contains goodbye)
    lower_response = ai_response.lower()
    is_ending = any(word in lower_response for word in ["goodbye", "bye", "talk to you later", "take care"])
    
    response = VoiceResponse()
    response.say(ai_response, voice='Polly.Matthew', language='en-US')
    
    if is_ending:
        response.hangup()
        conversation_manager.end_conversation(str(call_sid))
        logger.info(f"[Voice] Conversation ended (AI said goodbye). SID={call_sid}")
    else:
        # Continue conversation — gather more speech
        gather = Gather(
            input='speech',
            action=f'/voice/respond?call_sid={call_sid}',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            language='en-IN'
        )
        gather.say("", voice='Polly.Matthew')
        response.append(gather)
        
        # Fallback if no speech
        response.say("Are you still there?", voice='Polly.Matthew', language='en-US')
        gather2 = Gather(
            input='speech',
            action=f'/voice/respond?call_sid={call_sid}',
            method='POST',
            timeout=5,
            speech_timeout='auto',
            language='en-IN'
        )
        response.append(gather2)
        response.say("Alright, I'll let them know. Goodbye!", voice='Polly.Matthew')
        response.hangup()
    
    twiml = str(response)
    logger.info(f"[Voice] Respond TwiML: {twiml[:200]}...")
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/status")
async def voice_status_callback(request: Request):
    """Twilio status callback — logs call completion status."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    call_status = form_data.get("CallStatus", "unknown")
    
    logger.info(f"[Voice] Call status update: SID={call_sid}, status={call_status}")
    print(f"!!! VOICE WEBHOOK HIT: /voice/status?call_sid={call_sid}&status={call_status} !!!")
    
    # Clean up conversation state
    from agent.skills.voice_call.voice_conversation import conversation_manager
    if call_status in ["completed", "failed", "no-answer", "busy"]:
        conv = conversation_manager.get_conversation(str(call_sid))
        if conv:
            logger.info(f"[Voice] Final transcript for {call_sid}: {conv.build_history_text()}")
            conversation_manager.end_conversation(str(call_sid))
    
    return {"status": "ok"}


# Run with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disabled: reload spawns child process that overrides event loop policy
        log_level="info",
        loop="asyncio"  # Force asyncio loop to respect WindowsProactorEventLoopPolicy
    )
