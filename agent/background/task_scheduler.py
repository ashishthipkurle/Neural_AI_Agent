from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class TaskSchedulerLoop:
    def __init__(self, tick_seconds: float = 1.0) -> None:
        self.tick_seconds = tick_seconds
        self._running = False

    async def run(self, tick: Callable[[], Awaitable[None]]) -> None:
        self._running = True
        while self._running:
            await tick()
            await asyncio.sleep(self.tick_seconds)

    def stop(self) -> None:
        self._running = False
