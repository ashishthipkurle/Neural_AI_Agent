from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Dict, List

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self.connections: List[WebSocket] = []

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self.connections.append(socket)

    def disconnect(self, socket: WebSocket) -> None:
        if socket in self.connections:
            self.connections.remove(socket)

    async def broadcast(self, message: Dict[str, object]) -> None:
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(UTC).isoformat()
        payload = json.dumps(message)
        stale: List[WebSocket] = []
        for socket in self.connections:
            try:
                await socket.send_text(payload)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)
