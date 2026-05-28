"""
INDRA Main Entry Point — Orchestrator and main voice loop.
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    CHAT_MODEL, TARGET_STT_MS, TARGET_LLM_MS,
    USER_NAME
)
from utils.logger import get_logger
from utils.latency_tracker import LatencyTracker

# Subsystems
from memory.store import MemoryStore
from memory.projects import ProjectManager
from memory.loader import load_startup_context
from memory.updater import extract_and_save_preferences
from memory.conversations import ConversationLogger

from voice.tts import TTS
from voice.speaker import Speaker

from brain.context_manager import ContextManager
from brain.chat_brain import ChatBrain
from brain.vision_brain import VisionBrain
from brain.router import Router

from senses.eyes import Eyes
from senses.accessibility import AccessibilityLayer
from senses.ears import Ears
from senses.wake_word import WakeWordDetector

from hands.mouse import Mouse
from hands.keyboard import Keyboard
from hands.browser import Browser

from tasks.executor import Executor
from security.injection_guard import InjectionGuard
from setup.first_run import is_first_run, run_onboarding
import api  # INDRA API Bridge

logger = get_logger("Main")

# Global instances (set in startup)
latency = LatencyTracker()
memory = None
projects = None
speaker = None
chat_brain = None
ears = None
router = None
executor = None
injection_guard = None
keyboard_sys = None
wake_detector = None
conv_logger = None


def _extract_app_name(text: str) -> str | None:
    """
    Extract just the application name from a command like:
      "Open Telegram and send hi" → "telegram"
      "Open Chrome" → "chrome"
      "Launch VS Code" → "vs code"
    Returns None if no app name can be extracted.
    """
    import re
    text_lower = text.lower().strip().rstrip(".")
    
    # Match "open/launch/start X" — stop at "and", "then", comma, period
    match = re.match(
        r'^(?:open|launch|start|run)\s+(.+?)(?:\s+and\s+|\s+then\s+|,|\.|$)',
        text_lower
    )
    if match:
        return match.group(1).strip()
    return None

def _is_simple_launch(text: str) -> bool:
    """
    Check if this is ONLY an app launch (no further actions).
    "Open Chrome" → True
    "Open Telegram and send hi to Ashish" → False
    """
    text_lower = text.lower().strip().rstrip(".")
    multi_step_markers = [" and ", " then ", " send ", " type ", " write ", 
                          " message ", " search for ", " go to ", " navigate ",
                          " click ", " schedule "]
    for marker in multi_step_markers:
        if marker in text_lower:
            return False
    return True

def try_direct_launch(text: str) -> bool:
    """
    Try to launch an application directly (no AI needed).
    ONLY handles simple "Open X" commands — NOT multi-step tasks.
    """
    import subprocess
    
    app_name = _extract_app_name(text)
    if not app_name:
        return False
    
    # Known shortcuts
    APP_SHORTCUTS = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "firefox": "firefox",
        "telegram": None,   # No direct exe, use Start Menu
        "whatsapp": None,
        "discord": None,
        "spotify": None,
        "teams": None,
        "microsoft teams": None,
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "file explorer": "explorer",
        "explorer": "explorer",
        "files": "explorer",
        "terminal": "wt",
        "cmd": "cmd",
        "command prompt": "cmd",
        "powershell": "powershell",
        "settings": "ms-settings:",
        "task manager": "taskmgr",
    }
    
    exe = APP_SHORTCUTS.get(app_name)
    
    if exe:
        try:
            subprocess.Popen(exe, shell=True)
            logger.info(f"[DirectLaunch] Opened '{app_name}' via '{exe}'")
            speaker.enqueue(f"Opening {app_name}.")
            return True
        except Exception as e:
            logger.warning(f"[DirectLaunch] Failed to open '{exe}': {e}")
    
    # Fallback: Start Menu search — ONLY the app name, not the whole command
    try:
        import pyautogui
        pyautogui.hotkey('win')
        time.sleep(0.8)
        pyautogui.typewrite(app_name, interval=0.03)
        time.sleep(0.5)
        pyautogui.press('enter')
        logger.info(f"[DirectLaunch] Searched Start Menu for '{app_name}'")
        speaker.enqueue(f"Opening {app_name}.")
        return True
    except Exception as e:
        logger.warning(f"[DirectLaunch] Start menu fallback failed: {e}")
        return False


def handle_wake():
    """Called when wake word is detected."""
    logger.info("Wake word handled — listening for command")
    
    # ── VISUAL FEEDBACK ONLY — no speech (causes mic feedback!) ──
    # Edge lights turn cyan, chime already played by wake_word.py
    try:
        api.broadcast_state("listening")
    except Exception:
        pass
    
    # Brief pause so chime finishes before mic starts recording
    import time as _time
    _time.sleep(0.2)
    
    with latency.measure("stt", target_ms=TARGET_STT_MS):
        text = ears.listen_once()
    
    # Notify UI we're now thinking
    try:
        api.broadcast_state("thinking" if text else "idle")
    except Exception:
        pass
        
    if not text or not text.strip():
        try:
            api.broadcast_state("idle")
        except Exception:
            pass
        return
        
    logger.info(f"[INPUT] {USER_NAME} said: '{text}'")
    
    # Log user message to conversation history
    if conv_logger:
        conv_logger.log_user(text)
    
    # ── SECURITY SCAN ──
    # Not strictly required for voice input unless Ashish is dictating a malicious string,
    # but good practice.
    is_safe = injection_guard.scan(text, source="voice")
    if not is_safe:
        speaker.enqueue("I've detected a prohibited instruction sequence. Ignoring.", priority=True)
        return
        
    # ── CLASSIFY & ROUTE ──
    with latency.measure("router", target_ms=100):
        intent_type = router.classify(text)
        
    logger.info(f"Intent classified as: {intent_type}")
    
    if intent_type in ("TYPE1", "TYPE2"):
        # Conversation / Hybrid
        with latency.measure("llm_queue", target_ms=TARGET_LLM_MS):
            future = chat_brain.respond_async(text)
            
        # We don't block here. The chat brain streams to the speaker.
        # But we do want to extract preferences after it finishes
        def post_chat_callback(f):
            try:
                reply = f.result()
                extract_and_save_preferences(memory, text, reply)
                # Log INDRA reply to conversation history
                if conv_logger and reply:
                    conv_logger.log_indra(reply)
                    conv_logger.save_current()
            except Exception as e:
                logger.error(f"Chat brain callback error: {e}")
                
        future.add_done_callback(post_chat_callback)
        
        # If TYPE2, we might also want to trigger a quick action in parallel,
        # but the prompt implies we just let the chat brain answer and then it does it.
        # For true TYPE2, we'd need the LLM to output a tool call. The prompt says
        # "answer verbally first, then do the quick action", which usually requires Tool Calling.
        # Given the scope, treating TYPE2 exactly like TYPE1 for now (conversation only).
        
    elif intent_type == "TYPE3":
        # Computer Task — smart routing
        if _is_simple_launch(text):
            # Simple "Open Chrome" — just launch it directly
            launched = try_direct_launch(text)
            if not launched:
                threading.Thread(target=executor.run_task, args=(text,), daemon=True).start()
        else:
            # Multi-step: "Open Telegram and send hi to Ashish"
            # Step 1: Launch the app first
            app_name = _extract_app_name(text)
            if app_name:
                try_direct_launch(f"open {app_name}")
                logger.info(f"[MultiStep] Launched '{app_name}', handing rest to executor")
                time.sleep(3)  # Wait for app to load
            
            # Step 2: Hand the FULL task to the AI executor
            try:
                api.broadcast_state("executing")
            except Exception:
                pass
            threading.Thread(target=executor.run_task, args=(text,), daemon=True).start()
        
    elif intent_type == "TYPE4":
        # Ambiguous
        clarification = router.get_clarification(text)
        speaker.enqueue(clarification)
        
    # Report total latency for this interaction
    latency.report_round_trip()
    
    # Reset edge lights after short delay (let speech finish)
    def reset_state():
        import time as _t
        _t.sleep(5)
        try:
            api.broadcast_state("idle")
        except Exception:
            pass
    threading.Thread(target=reset_state, daemon=True).start()


def emergency_stop():
    """F9 Emergency Stop."""
    logger.warning("[EMERGENCY] F9 pressed — full stop initiated")
    if executor:
        executor.stop()
    if speaker:
        speaker.stop_immediately()
    if chat_brain:
        chat_brain.cancel()
    if keyboard_sys:
        keyboard_sys.release_all()
    # Mouse release
    try:
        import pyautogui
        pyautogui.mouseUp()
    except Exception:
        pass
        
    if speaker:
        speaker.enqueue("Stopped. Ready for your next command.", priority=True)


def startup():
    """Full INDRA initialization sequence."""
    global memory, projects, speaker, chat_brain, ears, router
    global executor, injection_guard, keyboard_sys, wake_detector, conv_logger
    
    logger.info("==================================================")
    logger.info("  INDRA Initializing...")
    logger.info("==================================================")
    
    try:
        import keyboard
        HAS_KEYBOARD_LIB = True
    except ImportError:
        HAS_KEYBOARD_LIB = False
        logger.warning("keyboard library not installed — F9 hotkey unavailable")
    
    # 1. Initialize core subsystems
    memory = MemoryStore()
    projects = ProjectManager()
    context_mgr = ContextManager()
    
    tts = TTS()
    speaker = Speaker(tts)
    
    chat_brain = ChatBrain(speaker, context_mgr, memory)
    vision_brain = VisionBrain()
    router = Router(chat_brain, vision_brain)
    
    eyes = Eyes()
    accessibility = AccessibilityLayer()
    ears = Ears()
    wake_detector = WakeWordDetector(on_wake_callback=handle_wake)
    
    mouse = Mouse()
    keyboard_sys = Keyboard()
    browser = Browser()
    
    executor = Executor(eyes, accessibility, vision_brain, mouse, keyboard_sys, browser, speaker)
    injection_guard = InjectionGuard()
    conv_logger = ConversationLogger()
    
    # 2. Start daemon threads
    speaker.start()
    eyes.start()
    accessibility.start()
    
    # 3. First-run onboarding check
    if is_first_run(memory):
        run_onboarding(speaker, memory, ears)
        
    # 4. Warm up LLM models
    logger.info("Warming up models...")
    try:
        import ollama
        ollama.chat(model=CHAT_MODEL, messages=[{"role":"user","content":"ready"}])
        logger.info("Models warm.")
    except Exception as e:
        logger.warning(f"Model warmup failed (is Ollama running?): {e}")
        
    # 5. Build and speak greeting
    memory_context, project_briefing = load_startup_context(memory, projects)
    greeting = chat_brain.build_greeting(memory_context, project_briefing)
    
    logger.info(f"Greeting: {greeting}")
    speaker.enqueue(greeting)
    
    # 6. Register F9 emergency stop
    if HAS_KEYBOARD_LIB:
        try:
            keyboard.add_hotkey('f9', emergency_stop)
            logger.info("F9 emergency stop registered")
        except Exception as e:
            logger.warning(f"Could not register F9 hotkey: {e} (Must run as Administrator)")
            
    # 7. Start API Bridge for UI integration
    api.init_bridge(router, chat_brain, executor, speaker, latency, memory, injection_guard)
    api.init_conv_logger(conv_logger)
    api.start_api_server_in_thread(port=8001)
    
    # 8. Start listening
    wake_detector.start()
    
    logger.info("==================================================")
    logger.info("  INDRA Ready. Say 'Hey INDRA' to begin.")
    logger.info("  API Bridge listening on port 8001.")
    logger.info("==================================================")


if __name__ == "__main__":
    try:
        startup()
        # Keep main thread alive
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("INDRA shutting down gracefully")
        if wake_detector:
            wake_detector.stop()
        if eyes:
            eyes.stop()
        if speaker:
            speaker.stop()
        if memory:
            memory.save_session_summary()
