import logging
import time
import os
from agent.voice.wake_word import WakeWordEngine
from agent.voice.stt import SpeechToText
from agent.voice.tts import TextToSpeech
from agent.voice.emotion_mapper import EmotionMapper

class VoiceInterface:
    def __init__(self, config=None):
        self.logger = logging.getLogger("VoiceInterface")
        self.config = config or {}
        
        # Paths (should be in config, defaulting for now)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # Assuming user downloaded models to 'models/' folder or similiar.
        # For robustness, we will try to use a local 'voice_models' folder
        voice_models_dir = os.path.join(base_dir, "voice_models")
        os.makedirs(voice_models_dir, exist_ok=True)
        
        vosk_model_path = os.path.join(voice_models_dir, "vosk-model-small-en-us-0.15")
        piper_model_path = os.path.join(voice_models_dir, "en_US-lessac-medium.onnx")
        
        # Initialize Subsystems
        # Get wake words from config or default
        wake_words = self.config.get("voice_settings", {}).get("wake_words", ["hey jarvis", "hi bro"])
        self.wake_engine = WakeWordEngine(model_path=vosk_model_path, wake_words=wake_words)
        self.stt_engine = SpeechToText(model_path=vosk_model_path)
        self.tts_engine = TextToSpeech(model_path=piper_model_path)
        
        self.logger.info("Voice 2.0 Interface Initialized")

    def wait_for_wake_word(self):
        """
        Blocking call waiting for wake word.
        Returns detected wake word string.
        """
        return self.wake_engine.wait_for_wake_word()

    def listen(self, timeout=10):
        """
        Listen for command.
        """
        return self.stt_engine.listen(timeout=timeout)

    def speak(self, text: str, emotion: str = None, intent: str = None):
        """
        Speak text with optional emotion or inferred from intent.
        """
        if not emotion:
            if intent:
                emotion = EmotionMapper.get_emotion(intent, text)
            else:
                emotion = "neutral"
                
        self.tts_engine.speak(text, emotion=emotion)

