"""
Stream Handler - Token streaming for real-time responses.

This module provides utilities for handling streaming LLM output
including buffering, text processing, and event dispatching.
"""
import logging
import asyncio
from typing import Generator, Callable, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from queue import Queue
import threading


class StreamEventType(Enum):
    """Types of stream events."""
    TOKEN = "token"
    SENTENCE = "sentence"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StreamEvent:
    """Event from the stream handler."""
    type: StreamEventType
    data: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class StreamBuffer:
    """
    Buffer for accumulating and processing stream tokens.
    
    Provides sentence-level chunking for TTS integration.
    """
    
    SENTENCE_ENDINGS = frozenset({'.', '!', '?', '\n'})
    
    def __init__(self, min_sentence_length: int = 10):
        """
        Initialize the stream buffer.
        
        Args:
            min_sentence_length: Minimum characters before emitting sentence.
        """
        self.buffer = ""
        self.min_sentence_length = min_sentence_length
        self.sentences: list = []
    
    def add_token(self, token: str) -> Optional[str]:
        """
        Add a token to the buffer.
        
        Args:
            token: Token to add.
        
        Returns:
            Complete sentence if one was formed, None otherwise.
        """
        self.buffer += token
        
        # Check for sentence boundary
        for ending in self.SENTENCE_ENDINGS:
            if ending in self.buffer:
                idx = self.buffer.index(ending)
                if idx >= self.min_sentence_length:
                    sentence = self.buffer[:idx + 1].strip()
                    self.buffer = self.buffer[idx + 1:].strip()
                    if sentence:
                        self.sentences.append(sentence)
                        return sentence
        
        return None
    
    def flush(self) -> Optional[str]:
        """
        Flush remaining buffer content.
        
        Returns:
            Remaining content or None if empty.
        """
        if self.buffer.strip():
            sentence = self.buffer.strip()
            self.buffer = ""
            self.sentences.append(sentence)
            return sentence
        return None
    
    def get_full_text(self) -> str:
        """Get all accumulated text."""
        return " ".join(self.sentences) + (" " + self.buffer if self.buffer else "")
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer = ""
        self.sentences = []


class StreamHandler:
    """
    Manages streaming LLM output with callbacks.
    
    Features:
    - Token-by-token streaming
    - Sentence-level buffering for TTS
    - Async and sync support
    - Event-based callbacks
    """
    
    def __init__(
        self,
        on_token: Optional[Callable[[str], None]] = None,
        on_sentence: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        """
        Initialize the stream handler.
        
        Args:
            on_token: Callback for each token.
            on_sentence: Callback for each complete sentence.
            on_complete: Callback when generation completes.
            on_error: Callback for errors.
        """
        self.logger = logging.getLogger("StreamHandler")
        self.on_token = on_token
        self.on_sentence = on_sentence
        self.on_complete = on_complete
        self.on_error = on_error
        self.buffer = StreamBuffer()
        self._is_streaming = False
    
    def process_stream(self, token_generator: Generator[str, None, None]) -> str:
        """
        Process a stream of tokens synchronously.
        
        Args:
            token_generator: Generator yielding tokens.
        
        Returns:
            Complete generated text.
        """
        self._is_streaming = True
        self.buffer.clear()
        
        try:
            for token in token_generator:
                # Call token callback
                if self.on_token:
                    self.on_token(token)
                
                # Buffer for sentences
                sentence = self.buffer.add_token(token)
                if sentence and self.on_sentence:
                    self.on_sentence(sentence)
            
            # Flush remaining buffer
            remaining = self.buffer.flush()
            if remaining and self.on_sentence:
                self.on_sentence(remaining)
            
            full_text = self.buffer.get_full_text()
            
            if self.on_complete:
                self.on_complete(full_text)
            
            return full_text
            
        except Exception as e:
            self.logger.error(f"Stream processing error: {e}")
            if self.on_error:
                self.on_error(e)
            raise
        finally:
            self._is_streaming = False
    
    async def process_stream_async(
        self,
        token_generator: AsyncGenerator[str, None]
    ) -> str:
        """
        Process a stream of tokens asynchronously.
        
        Args:
            token_generator: Async generator yielding tokens.
        
        Returns:
            Complete generated text.
        """
        self._is_streaming = True
        self.buffer.clear()
        
        try:
            async for token in token_generator:
                # Call token callback
                if self.on_token:
                    if asyncio.iscoroutinefunction(self.on_token):
                        await self.on_token(token)
                    else:
                        self.on_token(token)
                
                # Buffer for sentences
                sentence = self.buffer.add_token(token)
                if sentence and self.on_sentence:
                    if asyncio.iscoroutinefunction(self.on_sentence):
                        await self.on_sentence(sentence)
                    else:
                        self.on_sentence(sentence)
            
            # Flush remaining buffer
            remaining = self.buffer.flush()
            if remaining and self.on_sentence:
                if asyncio.iscoroutinefunction(self.on_sentence):
                    await self.on_sentence(remaining)
                else:
                    self.on_sentence(remaining)
            
            full_text = self.buffer.get_full_text()
            
            if self.on_complete:
                if asyncio.iscoroutinefunction(self.on_complete):
                    await self.on_complete(full_text)
                else:
                    self.on_complete(full_text)
            
            return full_text
            
        except Exception as e:
            self.logger.error(f"Async stream processing error: {e}")
            if self.on_error:
                if asyncio.iscoroutinefunction(self.on_error):
                    await self.on_error(e)
                else:
                    self.on_error(e)
            raise
        finally:
            self._is_streaming = False
    
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._is_streaming
    
    def stop(self) -> None:
        """Request stream stop."""
        self._is_streaming = False


class StreamQueue:
    """
    Thread-safe queue for streaming between threads.
    
    Useful for bridging async LLM generation with sync consumers.
    """
    
    def __init__(self):
        self._queue = Queue()
        self._done = threading.Event()
        self._error: Optional[Exception] = None
    
    def put(self, token: str) -> None:
        """Add token to queue."""
        self._queue.put(StreamEvent(StreamEventType.TOKEN, token))
    
    def put_sentence(self, sentence: str) -> None:
        """Add complete sentence to queue."""
        self._queue.put(StreamEvent(StreamEventType.SENTENCE, sentence))
    
    def put_error(self, error: Exception) -> None:
        """Signal an error."""
        self._error = error
        self._queue.put(StreamEvent(StreamEventType.ERROR, str(error)))
        self._done.set()
    
    def complete(self, full_text: str) -> None:
        """Signal stream completion."""
        self._queue.put(StreamEvent(StreamEventType.COMPLETE, full_text))
        self._done.set()
    
    def get(self, timeout: float = None) -> Optional[StreamEvent]:
        """Get next event from queue."""
        try:
            return self._queue.get(timeout=timeout)
        except:
            return None
    
    def iter_tokens(self) -> Generator[str, None, None]:
        """Iterate over tokens until complete."""
        while True:
            event = self.get(timeout=0.1)
            if event is None:
                if self._done.is_set():
                    break
                continue
            
            if event.type == StreamEventType.TOKEN:
                yield event.data
            elif event.type == StreamEventType.COMPLETE:
                break
            elif event.type == StreamEventType.ERROR:
                raise Exception(event.data)
    
    def is_done(self) -> bool:
        """Check if stream is complete."""
        return self._done.is_set()
