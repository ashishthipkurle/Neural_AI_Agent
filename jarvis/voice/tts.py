"""
INDRA TTS -- Text-to-Speech engine using Microsoft Edge Neural Voices.
Provides realistic, natural-sounding speech via edge-tts (free, no API key).
Falls back to gTTS if edge-tts is unavailable.
"""

import io
import sys
import asyncio
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    TTS_ENGINE, TTS_VOICE_ENGLISH, TTS_VOICE_HINDI,
    TTS_VOICE_MARATHI, TTS_VOICE_RATE, TTS_VOICE_PITCH
)
from voice.language_detector import detect_language
from utils.logger import get_logger

logger = get_logger("TTS")

# -- edge-tts (Primary -- Realistic Neural Voices) --
try:
    import edge_tts
    HAS_EDGE_TTS = True
    logger.info(f"edge-tts loaded -- voice: {TTS_VOICE_ENGLISH}")
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts not installed -- run: pip install edge-tts")

# -- gTTS (Fallback) --
try:
    from gtts import gTTS as GTTS_Class
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False
    logger.warning("gTTS not installed -- fallback TTS unavailable")

# -- Kokoro (Legacy fallback) --
HAS_KOKORO = False
try:
    from kokoro import KPipeline
    _kokoro_pipeline = KPipeline(lang_code='a')
    HAS_KOKORO = True
    logger.info("Kokoro TTS loaded (legacy fallback)")
except Exception:
    pass


def _get_or_create_event_loop():
    """Get existing event loop or create a new one for the current thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


class TTS:
    """
    Multi-language text-to-speech engine using Microsoft Edge Neural voices.
    
    Primary engine: edge-tts (realistic, free, 300+ neural voices)
    Fallback: gTTS (Google Translate TTS)
    """

    def __init__(self):
        self._voice_map = {
            "english": TTS_VOICE_ENGLISH,
            "hindi": TTS_VOICE_HINDI,
            "marathi": TTS_VOICE_MARATHI,
        }

    def synthesise(self, text: str) -> bytes:
        """
        Convert text to audio bytes. Auto-detects language.
        Returns: Raw audio bytes (MP3 format).
        """
        if not text or not text.strip():
            return b""

        lang = detect_language(text)

        if HAS_EDGE_TTS:
            return self._edge_tts_synth(text, lang)
        elif HAS_GTTS:
            return self._gtts_synth(text, lang)
        elif HAS_KOKORO and lang == "english":
            return self._kokoro_synth(text)
        else:
            logger.error("No TTS engine available!")
            return b""

    def _edge_tts_synth(self, text: str, lang: str) -> bytes:
        """Synthesise using Microsoft Edge Neural Voices -- returns MP3 bytes."""
        voice = self._voice_map.get(lang, TTS_VOICE_ENGLISH)

        async def _generate():
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=TTS_VOICE_RATE,
                pitch=TTS_VOICE_PITCH
            )
            # Collect audio chunks into memory
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            return b"".join(audio_chunks)

        try:
            loop = _get_or_create_event_loop()
            if loop.is_running():
                # We're inside an async context -- run in a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_generate()))
                    audio_bytes = future.result(timeout=15)
            else:
                audio_bytes = loop.run_until_complete(_generate())

            if audio_bytes:
                return audio_bytes
            else:
                logger.warning("edge-tts returned empty audio, falling back")
                return self._gtts_synth(text, lang) if HAS_GTTS else b""

        except Exception as e:
            logger.error(f"edge-tts synthesis failed: {e}")
            return self._gtts_synth(text, lang) if HAS_GTTS else b""

    def _gtts_synth(self, text: str, lang: str) -> bytes:
        """Synthesise text using Google TTS -- returns MP3 bytes."""
        lang_code = {"hindi": "hi", "marathi": "mr", "english": "en"}.get(lang, "en")
        try:
            tts = GTTS_Class(text=text, lang=lang_code, slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception as e:
            logger.error(f"gTTS synthesis failed: {e}")
            return b""

    def _kokoro_synth(self, text: str) -> bytes:
        """Legacy Kokoro synthesis -- returns WAV bytes."""
        try:
            import numpy as np
            import wave
            generator = _kokoro_pipeline(text, voice="af_heart", speed=1.0)
            audio_chunks = []
            for _, _, audio in generator:
                if audio is not None:
                    audio_chunks.append(audio)

            if not audio_chunks:
                return self._gtts_synth(text, "english") if HAS_GTTS else b""

            combined = np.concatenate(audio_chunks)
            pcm = (combined * 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(pcm.tobytes())
            buf.seek(0)
            return buf.read()
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}")
            return self._gtts_synth(text, "english") if HAS_GTTS else b""

    def get_engine_name(self, text: str) -> str:
        """Returns which engine would be used for this text (for logging)."""
        if HAS_EDGE_TTS:
            return "edge-tts"
        lang = detect_language(text)
        if lang == "english" and HAS_KOKORO:
            return "kokoro"
        return "gtts"
