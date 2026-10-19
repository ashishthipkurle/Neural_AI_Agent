"""
INDRA Configuration -- All settings, model names, paths, thresholds.
Central config for every module. Import from here, never hardcode values.
"""

# -- Models ------------------------------------------------------------------
import urllib.request
import json
import os

def get_available_models():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def verify_model_works(model_name: str) -> bool:
    """Send a tiny request to verify the model actually loads (catches 403 AND 500 OOM)."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate", method="POST")
        req.add_header('Content-Type', 'application/json')
        payload = json.dumps({
            "model": model_name,
            "prompt": "hi",
            "stream": False,
            "options": {"num_predict": 1}
        })
        with urllib.request.urlopen(req, payload.encode(), timeout=30) as response:
            return response.status == 200
    except Exception:
        return False

def get_chat_model():
    """
    Auto-select the best CHAT model. Cloud models first (zero local RAM),
    then local fallbacks only if cloud is unavailable.
    """
    models = get_available_models()

    # Priority list -- matches installed cloud models on this system
    priority = [
        # -- Cloud Models (no local RAM needed) --
        "minimax-m2:cloud",
        "glm-5:cloud",
        "gpt-oss:120b-cloud",
        "kimi-k2.5:cloud",
        "gpt-oss:20b-cloud",
        "qwen3-coder:480b-cloud",
        # -- Local Fallback (works offline, no rate limits) --
        "phi3:mini",
        "deepseek-coder:6.7b",
    ]

    for m in priority:
        if m in models:
            print(f"[INDRA Config] Testing model: {m}...")
            if verify_model_works(m):
                print(f"[INDRA Config] [OK] Chat model selected: {m}")
                return m
            else:
                print(f"[INDRA Config] [FAIL] {m} failed (subscription/OOM/error)")

    # Nothing worked
    print("[INDRA Config] [WARN] No working chat model found!")
    return "phi3:mini"

def get_vision_model():
    """
    Auto-select the best VISION model. Cloud models first.
    """
    models = get_available_models()

    priority = [
        # -- Cloud Vision Model --
        "qwen3-vl:235b-instruct-cloud",
        # -- Cloud fallbacks that can handle vision --
        "minimax-m2:cloud",
        "glm-5:cloud",
        # -- Local Vision (works offline!) --
        "llava:latest",
        "llava",
    ]

    for m in priority:
        if m in models:
            print(f"[INDRA Config] Testing vision model: {m}...")
            if verify_model_works(m):
                print(f"[INDRA Config] [OK] Vision model selected: {m}")
                return m
            else:
                print(f"[INDRA Config] [FAIL] {m} failed")

    print("[INDRA Config] [WARN] No working vision model found!")
    return "llava"


print("[INDRA Config] Auto-routing models...")
CHAT_MODEL          = get_chat_model()
VISION_MODEL        = get_vision_model()
print(f"[INDRA Config] Final: CHAT={CHAT_MODEL}, VISION={VISION_MODEL}")

OLLAMA_HOST         = "http://localhost:11434"
WHISPER_MODEL       = "base"          # 'base' = much better accuracy, ~500ms on CPU
WHISPER_LANGUAGE    = None            # None = auto-detect (English/Hindi/Marathi)

# -- TTS Voice ---------------------------------------------------------------
# edge-tts voices -- realistic Microsoft Neural voices (free, no API key)
TTS_ENGINE          = "edge-tts"      # "edge-tts" (realistic) or "gtts" (fallback)
TTS_VOICE_ENGLISH   = "en-GB-RyanNeural"   # British male -- calm, INDRA-like
TTS_VOICE_HINDI     = "hi-IN-MadhurNeural"  # Hindi male
TTS_VOICE_MARATHI   = "mr-IN-ManoharNeural" # Marathi male
TTS_VOICE_RATE      = "+10%"          # Slightly faster for snappy responses
TTS_VOICE_PITCH     = "-5Hz"          # Slightly deeper for authority

# -- User --------------------------------------------------------------------
USER_NAME           = "Ashish"
USER_OS             = "Windows 11"
USER_LOCATION       = "Gadhinglaj, IST"
USER_LANGUAGES      = ["English", "Hindi", "Marathi"]
PRIMARY_LANGUAGE    = "English"

# -- Paths --------------------------------------------------------------------
MEMORY_DB_PATH      = "./indra_memory"
LOG_PATH            = "./indra.log"
SYSTEM_PROMPT_PATH  = "./system_prompt.txt"

# -- Voice --------------------------------------------------------------------
WAKE_WORD           = "hey indra"    # trigger phrase
WAKE_WORD_SENSITIVITY = 0.35          # 0.0–1.0, LOWER = easier to trigger (was 0.6)

# -- Eyes ---------------------------------------------------------------------
CAPTURE_FPS         = 60              # screen capture target framerate
CHANGE_THRESHOLD    = 0.02            # fraction of pixels that must change to fire event
VISION_COOLDOWN     = 0.5             # min seconds between consecutive vision LLM calls

# -- Execution ----------------------------------------------------------------
MAX_RETRIES         = 3               # retries per step before reporting stuck
ACTION_DELAY_MIN    = 0.1             # minimum human-like action delay (seconds)
ACTION_DELAY_MAX    = 0.3             # maximum human-like action delay (seconds)

# -- Context window -----------------------------------------------------------
MAX_CONTEXT_TOKENS  = 3500            # leave headroom below model's 4096 limit
MAX_HISTORY_TURNS   = 20              # max conversation turns before rolling
MEMORY_RECALL_N     = 10              # top-N memories to inject at startup

# -- Performance targets (from design spec) -----------------------------------
TARGET_STT_MS       = 800             # speech-to-text budget (base model is slower but accurate)
TARGET_LLM_MS       = 400             # chat brain reply budget
TARGET_TTS_MS       = 100             # first sentence TTS budget
TARGET_TOTAL_MS     = 800             # total voice round-trip target

# -- Safety -------------------------------------------------------------------
INJECTION_KEYWORDS  = [               # phrases that flag prompt injection attempts
    "ignore previous instructions",
    "disregard your system prompt",
    "you are now",
    "forget your instructions",
    "new persona",
    "act as",
    "jailbreak",
    "do anything now",
]

# -- Conversation continuity --------------------------------------------------
CONVERSATION_TIMEOUT = 30             # seconds -- skip wake word if within this window
