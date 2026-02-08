"""
NEURAL Text_to_Speech Engine (Edge TTS + Fallback).

Primary Engine: Microsoft Edge Neural TTS (Cloud, High Quality)
Secondary Engine: Piper Neural TTS (Local, Medium Quality)
Fallback Engine: pyttsx3 (System, Robotic)

Features:
- Natural, human-like voice (Emma/Jenny)
- Prosody & Emotion modulation
- Async generation (wrapped for sync usage)
- Resilient fallback chain
"""

import logging
import os
import subprocess
import time
import tempfile
import threading
import asyncio
from typing import Optional

# Audio Libraries
try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sd = None
    sf = None

try:
    from playsound import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False

# Local Modules
try:
    from agent.voice.emotion_controller import (
        EmotionController, Emotion, EmotionSettings, EMOTION_PROFILES
    )
except ImportError:
    EmotionController = None
    EMOTION_PROFILES = {}

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    from agent.voice.prosody_processor import ProsodyProcessor
except ImportError:
    ProsodyProcessor = None


try:
    from chatterbox import ChatterboxTTS
    CHATTERBOX_AVAILABLE = True
except ImportError:
    CHATTERBOX_AVAILABLE = False
    ChatterboxTTS = None


class TextToSpeech:
    """
    Production-Ready Neural TTS Engine.
    
    Priority:
    1. Edge Neural TTS (Online, Human-like)
    2. Chatterbox TTS (Local, High Quality)
    3. Piper TTS (Local, Medium Quality)
    4. pyttsx3 (Offline, Robotic)
    """
    
    # Edge TTS Configuration
    EDGE_VOICE = "en-US-EmmaNeural" # Alternatives: en-US-JennyNeural, en-US-GuyNeural
    
    def __init__(self, piper_path="piper/piper.exe", model_path="piper/en_US-ryan-high.onnx"):
        self.logger = logging.getLogger("TTS")
        self.piper_path = piper_path
        self.model_path = model_path
        
        # State
        self.use_fallback_only = False
        
        # Check components
        self._check_piper()
        
        # Prosody
        self.prosody = ProsodyProcessor() if ProsodyProcessor else None
        

        # Init emergency fallback
        self._init_fallback()
        
        # Chatterbox (Local Neurual)
        self.chatterbox = None
        if CHATTERBOX_AVAILABLE:
            try:
                # Initialize with default settings (CPU/CUDA auto-detect)
                # Note: First run will download models (~1GB)
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.logger.info(f"Loading Chatterbox TTS on {device}...")
                # self.chatterbox = ChatterboxTTS.from_pretrained(device)
                # self.logger.info("Chatterbox TTS Loaded.")
                self.logger.warning("Chatterbox TTS disabled (stability)")
            except Exception as e:
                self.logger.error(f"Failed to load Chatterbox: {e}")
        
        if not EDGE_TTS_AVAILABLE:
            self.logger.warning("Edge TTS library not installed (pip install edge-tts).")
        
        self.logger.info(f"TTS Engine Initialized. Primary: EdgeTTS ({self.EDGE_VOICE})")
        if PLAYSOUND_AVAILABLE:
            self.logger.info("Audio Playback: playsound (Native)")
        else:
             self.logger.info("Audio Playback: PowerShell (Fallback)")

    def _check_piper(self):
        """Check availability of Piper (Secondary)."""
        self.has_piper = False
        if os.path.exists(self.piper_path):
             # Check model
            if os.path.exists(self.model_path):
                self.has_piper = True
            else:
                # Try glob
                import glob
                onnx = glob.glob("piper/*.onnx")
                if onnx:
                    self.model_path = onnx[0]
                    self.has_piper = True
        
        if self.has_piper:
            self.logger.info(f"secondary: Piper enabled ({self.model_path})")
        else:
            self.logger.warning("secondary: Piper NOT available.")

    def _init_fallback(self):
        """Initialize pyttsx3 (Tertiary)."""
        try:
            import pyttsx3
            # Test init
            e = pyttsx3.init()
            del e
        except Exception as e:
            self.logger.error(f"pyttsx3 init failed: {e}")

    def speak(self, text: str, emotion: str = "neutral", wait: bool = True):
        """
        Speak text with best available engine.
        
        Args:
           text: Raw text.
           emotion: Emotional context key.
           wait: Block until finished (highly recommended).
        """
        if not text:
            return

        self.logger.info(f"🗣 Speaking ({emotion}): {text[:60]}")

        # 1. Get Emotion Settings
        settings = None
        if EMOTION_PROFILES and Emotion:
            try:
                em_enum = Emotion(emotion.lower())
                settings = EMOTION_PROFILES.get(em_enum)
            except:
                pass
        
        # 2. Prosody Processing
        processed_text = text
        if self.prosody:
            processed_text = self.prosody.process(text, settings)
        
        # 3. Try Engines in priority order
        
        # Priority 1: Edge TTS (Online)
        if EDGE_TTS_AVAILABLE and not self.use_fallback_only:
            try:
                success = self._speak_edge(processed_text, settings)
                if success:
                    return
            except Exception as e:
                self.logger.error(f"Edge TTS failed: {e}")
                # Don't disable permanently on one error (might be transient net issue)
                # But could decrement a health counter.
        
        # Priority 1.5: Chatterbox (Local Neural)
        if self.chatterbox and not self.use_fallback_only:
             try:
                self._speak_chatterbox(processed_text, settings)
                return
             except Exception as e:
                self.logger.error(f"Chatterbox attempt failed: {e}")

        # Priority 2: Piper (Local Neural)
        if self.has_piper:
            try:
                self._speak_piper(processed_text, settings)
                return
            except Exception as e:
                self.logger.error(f"Piper failed: {e}")
        
        # Priority 3: System (Robotic)
        self._speak_system(text, settings)

    def _speak_edge(self, text: str, settings) -> bool:
        """
        Execute Edge TTS generation and playback.
        Returns True if successful.
        """
        try:
            # Map settings to Edge parameters
            rate = "+0%"
            volume = "+0%"
            pitch = "+0Hz"
            
            if settings:
                speed_pct = int((settings.speed_modifier - 1.0) * 100)
                rate = f"+{speed_pct}%" if speed_pct >= 0 else f"{speed_pct}%"
                
                vol_pct = int((settings.volume_modifier - 1.0) * 100)
                volume = f"+{vol_pct}%" if vol_pct >= 0 else f"{vol_pct}%"
            
            # Generate to temp file (MP3)
            fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            fp.close()
            output_file = fp.name
            
            # Wrapper to run async generator
            def _run_async():
                async def _gen():
                    communicate = edge_tts.Communicate(text, self.EDGE_VOICE, rate=rate, volume=volume, pitch=pitch)
                    await communicate.save(output_file)
                asyncio.run(_gen())

            t = threading.Thread(target=_run_async)
            t.start()
            t.join(timeout=60) # Increased to 60s to prevent premature timeout
            
            if t.is_alive():
                self.logger.error("Edge TTS timeout (Generation)")
                return False
            
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                self.logger.error("Edge TTS produced empty file")
                return False
            
            self.logger.info(f"Audio generated ({os.path.getsize(output_file)} bytes). Playing...")
            
            # Playback
            if PLAYSOUND_AVAILABLE:
                try:
                    playsound(output_file)
                    # self.logger.info("Playback finished (playsound).")
                except Exception as ps_e:
                    self.logger.warning(f"playsound failed: {ps_e}. Trying PowerShell...")
                    self._play_mp3_windows(output_file)
            else:
                self._play_mp3_windows(output_file)
            
            # Cleanup
            try:
                os.remove(output_file)
            except:
                pass
                
            return True

        except Exception as e:
            self.logger.warning(f"Edge TTS attempt error: {e}")
            return False

    def _play_mp3_windows(self, file_path):
        """Play MP3 using Windows Media Player COM object (via PowerShell)."""
        # Added timeout logic to prevent hanging
        ps_script = f"""
        $w = New-Object -ComObject WMPlayer.OCX
        $w.settings.autoStart = $True
        $w.settings.volume = 100
        $w.URL = '{file_path}'
        $start = Get-Date
        while ($w.playState -ne 1) {{ 
            Start-Sleep -Milliseconds 100 
            if ((Get-Date) - $start -gt (New-TimeSpan -Seconds 15)) {{ break }}
        }}
        """
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        try:
            subprocess.run(cmd, startupinfo=startupinfo, timeout=15)
        except subprocess.TimeoutExpired:
            self.logger.error("PowerShell playback timed out.")
        except Exception as e:
            self.logger.error(f"PowerShell playback error: {e}")

    def _speak_piper(self, text: str, settings):
        """Execute Piper TTS."""
        if not self.has_piper:
            raise Exception("Piper not configured")
            
        length_scale = 1.0
        if settings:
             base = 1.0
             length_scale = base / settings.speed_modifier
        
        temp_wav = "temp_piper.wav"
        
        cmd = [
            self.piper_path,
            "--model", self.model_path,
            "--output_file", temp_wav,
            "--length_scale", str(length_scale),
            "--sentence_silence", "0.2"
        ]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, encoding='utf-8')
        process.communicate(input=text)
        
        if process.returncode == 0 and os.path.exists(temp_wav):
            if sd and sf:
                data, fs = sf.read(temp_wav)
                sd.play(data, fs)
                sd.wait()
            try: os.remove(temp_wav)
            except: pass
        else:
             raise Exception("Piper execution failed")

    def _speak_chatterbox(self, text: str, settings):
        """Execute Chatterbox TTS (High Quality Local)."""
        if not self.chatterbox:
            raise Exception("Chatterbox not loaded")
        
        try:
            self.logger.info("Generating with Chatterbox...")
            # Determine device (simple check)
            # Default generation
            wav_tensor = self.chatterbox.generate(text)
            
            # Convert to numpy
            wav_numpy = wav_tensor.squeeze().cpu().numpy()
            sr = self.chatterbox.sr
            
            # Playback
            if sd:
                sd.play(wav_numpy, sr)
                sd.wait()
            else:
                # Fallback to file playback if sounddevice not avail
                fp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                fp.close()
                import soundfile as sf
                sf.write(fp.name, wav_numpy, sr)
                self._play_mp3_windows(fp.name) # Renamed to _play_media_windows ideally, but works for wav
                try: os.remove(fp.name)
                except: pass
                
        except Exception as e:
            self.logger.error(f"Chatterbox generation failed: {e}")
            raise e

    def _speak_system(self, text: str, settings):
        """Fallback to robotic system voice."""
        self.logger.warning("Fallback: using pyttsx3")
        try:
             import multiprocessing
             rate = 200
             if settings:
                 rate = int(200 * settings.speed_modifier)
             
             p = multiprocessing.Process(target=_run_pyttsx3, args=(text, rate))
             p.start()
             p.join()
        except:
            pass

def _run_pyttsx3(text, rate):
    try:
        import pyttsx3
        e = pyttsx3.init()
        e.setProperty('rate', rate)
        e.say(text)
        e.runAndWait()
    except:
        pass
