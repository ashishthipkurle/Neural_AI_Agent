"""
INDRA OS — Message Bus

AsyncIO-based pub/sub message bus for inter-agent communication.
Agents publish events (progress, results, errors), INDRA subscribes
to monitor everything.

Design:
    - Topic-based pub/sub (e.g. "agent.trading.progress")
    - Wildcard subscriptions (e.g. "agent.*.error" catches all agent errors)
    - Request/response pattern for direct agent-to-agent communication
    - Thread-safe: can be called from sync code via run_coroutine_threadsafe
"""

import asyncio
import fnmatch
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("MessageBus")


@dataclass
class Message:
    """A message on the bus."""

    topic: str
    payload: Any
    sender: str = "system"
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None  # for request/response pattern

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "payload": self.payload,
            "sender": self.sender,
            "timestamp": self.timestamp,
        }


# Type alias for subscription callbacks
Callback = Callable[[Message], Coroutine[Any, Any, None]]


class MessageBus:
    """
    Central message bus for INDRA OS.

    Topics follow a dot-separated hierarchy:
        agent.{name}.status     — agent status changes
        agent.{name}.progress   — task progress updates
        agent.{name}.result     — task completion
        agent.{name}.error      — error reports
        indra.command            — INDRA issuing commands
        indra.broadcast          — INDRA announcements
        user.input               — user voice/text input
        system.shutdown          — system shutting down
    """

    def __init__(self):
        # topic -> list of (callback, subscriber_name)
        self._subscriptions: dict[str, list[tuple[Callback, str]]] = defaultdict(list)
        self._message_log: list[Message] = []
        self._max_log_size = 500
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    async def start(self) -> None:
        """Start the message bus."""
        self._loop = asyncio.get_event_loop()
        self._running = True
        logger.info("Message bus started")

    async def stop(self) -> None:
        """Stop the message bus and clear subscriptions."""
        self._running = False
        self._subscriptions.clear()
        logger.info("Message bus stopped")

    # ── Pub/Sub ───────────────────────────────────────────────────────────

    async def publish(self, topic: str, payload: Any, sender: str = "system") -> None:
        """
        Publish a message to a topic. All matching subscribers are notified.
        Supports wildcard matching (e.g. "agent.*.error").
        """
        msg = Message(topic=topic, payload=payload, sender=sender)

        # Log message
        self._message_log.append(msg)
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size // 2:]

        # Find matching subscribers (exact + wildcard)
        notified = 0
        for pattern, subscribers in self._subscriptions.items():
            if self._topic_matches(pattern, topic):
                for callback, sub_name in subscribers:
                    try:
                        await callback(msg)
                        notified += 1
                    except Exception as e:
                        logger.error(
                            f"Subscriber '{sub_name}' error on topic "
                            f"'{topic}': {e}"
                        )

        if notified == 0 and not topic.endswith(".progress"):
            # Don't warn for unhandled progress events (noisy)
            logger.debug(f"No subscribers for topic: {topic}")

    def publish_sync(self, topic: str, payload: Any, sender: str = "system") -> None:
        """
        Thread-safe publish for calling from sync code (e.g. agent workers).
        Schedules the async publish on the event loop.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.publish(topic, payload, sender),
                self._loop,
            )

    def subscribe(self, topic_pattern: str, callback: Callback, subscriber: str = "anonymous") -> None:
        """
        Subscribe to a topic pattern. Supports wildcards:
            "agent.trading.progress"  — exact match
            "agent.*.error"           — all agent errors
            "agent.trading.*"         — all trading events
            "*"                       — everything
        """
        self._subscriptions[topic_pattern].append((callback, subscriber))
        logger.debug(f"'{subscriber}' subscribed to '{topic_pattern}'")

    def unsubscribe(self, topic_pattern: str, subscriber: str) -> None:
        """Remove a subscriber from a topic."""
        if topic_pattern in self._subscriptions:
            self._subscriptions[topic_pattern] = [
                (cb, name) for cb, name in self._subscriptions[topic_pattern]
                if name != subscriber
            ]

    # ── Request/Response ──────────────────────────────────────────────────

    async def request(
        self,
        target_topic: str,
        payload: Any,
        sender: str = "system",
        timeout: float = 30.0,
    ) -> Optional[Any]:
        """
        Send a request and wait for a response.
        Uses a temporary reply topic for the response.
        """
        reply_topic = f"_reply.{id(asyncio.current_task())}.{time.time()}"
        response_future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def _on_reply(msg: Message):
            if not response_future.done():
                response_future.set_result(msg.payload)

        self.subscribe(reply_topic, _on_reply, subscriber=f"request-{sender}")

        # Send request with reply_to topic
        msg = Message(
            topic=target_topic,
            payload=payload,
            sender=sender,
            reply_to=reply_topic,
        )
        await self.publish(target_topic, payload, sender)

        try:
            result = await asyncio.wait_for(response_future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Request to '{target_topic}' timed out after {timeout}s")
            return None
        finally:
            self.unsubscribe(reply_topic, f"request-{sender}")

    # ── Query ─────────────────────────────────────────────────────────────

    def get_recent_messages(
        self, topic_filter: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get recent messages, optionally filtered by topic pattern."""
        msgs = self._message_log
        if topic_filter:
            msgs = [
                m for m in msgs
                if self._topic_matches(topic_filter, m.topic)
            ]
        return [m.to_dict() for m in msgs[-limit:]]

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern (supports * wildcard)."""
        if pattern == topic:
            return True
        # Convert dot-separated pattern to fnmatch-style
        # "agent.*.error" should match "agent.trading.error"
        return fnmatch.fnmatch(topic, pattern)
