from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class VoiceLoop:
    def __init__(self, interval_seconds: float = 0.5) -> None:
        self.interval_seconds = interval_seconds
        self._running = False

    async def run(self, poll_voice_input: Callable[[], Awaitable[None]]) -> None:
        self._running = True
        while self._running:
            await poll_voice_input()
            await asyncio.sleep(self.interval_seconds)

    def stop(self) -> None:
        self._running = False
