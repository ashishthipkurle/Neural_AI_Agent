from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Dict, List, Callable, Any

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self.connections: List[WebSocket] = []
        self._snapshot_callback: Callable[[], Dict[str, Any]] = None

    def register_snapshot_callback(self, callback: Callable[[], Dict[str, Any]]) -> None:
        """Register a callback to fetch the latest state snapshot on new connections."""
        self._snapshot_callback = callback

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self.connections.append(socket)
        
        # Phase 4 Event-Driven Sync: Immediately push state snapshot on connect
        if self._snapshot_callback:
            try:
                snapshot = self._snapshot_callback()
                if snapshot:
                    await socket.send_text(json.dumps(snapshot))
            except Exception as e:
                print(f"Failed to generate WebSocket snapshot: {e}")

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
