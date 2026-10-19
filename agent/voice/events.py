"""
Voice Events Publisher

Publishes voice state events over the existing WebSocket.
Event format: {type: "voice_state", state: str, level: float, transcript: str, message: str, task_id: str, step: str}
"""
import logging
import uuid
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger("VoiceEvents")

class VoiceEvents:
    def __init__(self, broadcast_callback: Optional[Callable] = None):
        self.broadcast_callback = broadcast_callback

    def publish(self, state: str, level: float = 0.0, transcript: str = "", message: str = "", task_id: str = "", step: str = ""):
        event = {
            "type": "voice_state",
            "state": state,
            "level": level,
            "transcript": transcript,
            "message": message,
            "task_id": task_id,
            "step": step,
            "timestamp": datetime.utcnow().isoformat()
        }
        if self.broadcast_callback:
            try:
                self.broadcast_callback(event)
            except Exception as e:
                logger.error(f"Failed to broadcast voice event: {e}")
        else:
            logger.debug(f"Voice Event (no broadcaster): {event}")
