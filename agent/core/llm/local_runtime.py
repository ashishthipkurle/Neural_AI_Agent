"""
Local LLM Runtime - GGUF-compatible offline inference.

This module provides a unified interface for local LLM inference
supporting both Ollama (localhost API) and llama-cpp-python (pure local).
"""
import logging
import time
from typing import Optional, Dict, Any, Generator, List
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod


class LLMBackend(Enum):
    """Supported LLM backend types."""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    stop_sequences: List[str] = None
    
    def __post_init__(self):
        if self.stop_sequences is None:
            self.stop_sequences = []


@dataclass
class GenerationResult:
    """Result of text generation."""
    text: str
    tokens_generated: int
    finish_reason: str
    model_name: str
    tokens_per_second: float = 0.0


class BaseLLMBackend(ABC):
    """Abstract base class for LLM backends."""
    
    @abstractmethod
    def generate(self, prompt: str, config: GenerationConfig) -> GenerationResult:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def generate_stream(self, prompt: str, config: GenerationConfig) -> Generator[str, None, None]:
        """Stream text generation."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available."""
        pass


class OllamaBackend(BaseLLMBackend):
    """Ollama backend for local inference via localhost API."""
    
    def __init__(self, model_name: str = "phi3:mini", base_url: str = "http://localhost:11434"):
        self.logger = logging.getLogger("OllamaBackend")
        self.model_name = model_name
        self.base_url = base_url
        self.client = None
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                base_url=f"{base_url}/v1",
                api_key="ollama"
            )
            self.logger.info(f"Ollama backend initialized: {model_name}")
        except ImportError:
            self.logger.error("openai package not found for Ollama backend")
        except Exception as e:
            self.logger.error(f"Failed to initialize Ollama: {e}")
    
    def is_available(self) -> bool:
        if not self.client:
            return False
        try:
            # Simple ping to check if Ollama is running
            self.client.models.list()
            return True
        except Exception:
            return False
    
    def generate(self, prompt: str, config: GenerationConfig, images: Optional[List[str]] = None) -> GenerationResult:
        if not self.client:
            return GenerationResult(
                text="Error: Ollama backend not available",
                tokens_generated=0,
                finish_reason="error",
                model_name=self.model_name
            )
        
        start_time = time.time()
        try:
            # Construct message with standard OpenAI Vision format
            if images:
                content_parts = [{"type": "text", "text": prompt}]
                for img in images:
                    # Ensure base64 prefix is present
                    img_url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                messages = [{"role": "user", "content": content_parts}]
            else:
                messages = [{"role": "user", "content": prompt}]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                stop=config.stop_sequences if config.stop_sequences else None
            )
            
            duration = time.time() - start_time
            tokens = response.usage.completion_tokens if response.usage else 0
            tps = tokens / duration if duration > 0 else 0.0
            
            return GenerationResult(
                text=response.choices[0].message.content,
                tokens_generated=tokens,
                finish_reason=response.choices[0].finish_reason,
                model_name=self.model_name,
                tokens_per_second=tps
            )
        except Exception as e:
            self.logger.error(f"Ollama generation failed: {e}")
            return GenerationResult(
                text=f"Error: {e}",
                tokens_generated=0,
                finish_reason="error",
                model_name=self.model_name
            )
    
    def generate_stream(self, prompt: str, config: GenerationConfig, images: Optional[List[str]] = None) -> Generator[str, None, None]:
        if not self.client:
            yield "Error: Ollama backend not available"
            return
        
        try:
            # Construct message with standard OpenAI Vision format
            if images:
                content_parts = [{"type": "text", "text": prompt}]
                for img in images:
                    img_url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                messages = [{"role": "user", "content": content_parts}]
            else:
                messages = [{"role": "user", "content": prompt}]

            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.logger.error(f"Ollama stream failed: {e}")
            yield f"Error: {e}"


class LlamaCppBackend(BaseLLMBackend):
    """llama-cpp-python backend for pure offline GGUF inference."""
    
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        self.logger = logging.getLogger("LlamaCppBackend")
        self.model_path = model_path
        self.model = None
        
        try:
            from llama_cpp import Llama
            self.logger.info(f"Loading GGUF model from {model_path}...")
            self.model = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
            self.logger.info("GGUF model loaded successfully.")
        except ImportError:
            self.logger.error("llama-cpp-python not installed")
        except Exception as e:
            self.logger.error(f"Failed to load GGUF model: {e}")
    
    def is_available(self) -> bool:
        return self.model is not None
    
    def generate(self, prompt: str, config: GenerationConfig, images: Optional[List[str]] = None) -> GenerationResult:
        if not self.model:
            return GenerationResult(
                text="Error: llama-cpp backend not available",
                tokens_generated=0,
                finish_reason="error",
                model_name=self.model_path
            )
        
        if images:
             self.logger.warning("LlamaCppBackend does not support images yet.")

        try:
            output = self.model(
                prompt,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                repeat_penalty=config.repeat_penalty,
                stop=config.stop_sequences if config.stop_sequences else None
            )
            
            # Simple TPS calculation for LlamaCpp
            tokens = output['usage']['completion_tokens']
            # Note: llama-cpp doesn't easily expose duration in this dict without calculating it ourselves, 
            # but we can't easily wrap 'self.model' call efficiently without overhead.
            # For now, TPS is 0.0 for LlamaCpp unless we wrap it similarly.
            
            return GenerationResult(
                text=output['choices'][0]['text'],
                tokens_generated=tokens,
                finish_reason=output['choices'][0]['finish_reason'],
                model_name=self.model_path,
                tokens_per_second=0.0 # Placeholder
            )
        except Exception as e:
            self.logger.error(f"llama-cpp generation failed: {e}")
            return GenerationResult(
                text=f"Error: {e}",
                tokens_generated=0,
                finish_reason="error",
                model_name=self.model_path
            )
    
    def generate_stream(self, prompt: str, config: GenerationConfig, images: Optional[List[str]] = None) -> Generator[str, None, None]:
        if not self.model:
            yield "Error: llama-cpp backend not available"
            return
        
        try:
            stream = self.model(
                prompt,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                stream=True
            )
            
            for output in stream:
                if output['choices'][0]['text']:
                    yield output['choices'][0]['text']
        except Exception as e:
            self.logger.error(f"llama-cpp stream failed: {e}")
            yield f"Error: {e}"


class LocalLLMRuntime:
    """
    Unified Local LLM Runtime.
    
    Provides a single interface for local LLM inference supporting
    multiple backends (Ollama, llama-cpp-python).
    """
    
    def __init__(
        self,
        backend: LLMBackend = LLMBackend.OLLAMA,
        model_name: str = "phi3:mini",
        model_path: Optional[str] = None,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the Local LLM Runtime.
        """
        self.logger = logging.getLogger("LocalLLMRuntime")
        self.backend_type = backend
        self.config = config or {}
        self._backend: Optional[BaseLLMBackend] = None
        self.last_tps: float = 0.0  # Track performance
        
        # Initialize appropriate backend
        if backend == LLMBackend.OLLAMA:
            self._backend = OllamaBackend(
                model_name=model_name,
                base_url=self.config.get('ollama_url', 'http://localhost:11434')
            )
        elif backend == LLMBackend.LLAMA_CPP:
            if not model_path:
                self.logger.error("model_path required for llama-cpp backend")
            else:
                self._backend = LlamaCppBackend(
                    model_path=model_path,
                    n_ctx=self.config.get('context_size', 4096),
                    n_gpu_layers=self.config.get('gpu_layers', -1)
                )
        
        self.logger.info(f"LocalLLMRuntime initialized with backend: {backend.value}")
    
    def is_available(self) -> bool:
        """Check if the LLM runtime is available."""
        return self._backend is not None and self._backend.is_available()
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        images: Optional[List[str]] = None
    ) -> GenerationResult:
        """
        Generate text from prompt.
        """
        if not self._backend:
            return GenerationResult(
                text="Error: No LLM backend available",
                tokens_generated=0,
                finish_reason="error",
                model_name="none"
            )
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        
        if isinstance(self._backend, OllamaBackend):
             result = self._backend.generate(full_prompt, config or GenerationConfig(), images=images)
             self.last_tps = result.tokens_per_second
             return result
        else:
             if hasattr(self._backend, 'generate') and 'images' in self._backend.generate.__code__.co_varnames:
                 result = self._backend.generate(full_prompt, config or GenerationConfig(), images=images)
             else:
                 result = self._backend.generate(full_prompt, config or GenerationConfig())
             
             self.last_tps = result.tokens_per_second
             return result

    
    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        images: Optional[List[str]] = None
    ) -> Generator[str, None, None]:
        """
        Stream text generation.
        """
        if not self._backend:
            yield "Error: No LLM backend available"
            return
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
            
        if isinstance(self._backend, OllamaBackend):
             yield from self._backend.generate_stream(full_prompt, config or GenerationConfig(), images=images)
        else:
             yield from self._backend.generate_stream(full_prompt, config or GenerationConfig())
    
    def chat(self, system_prompt: str, user_input: str, images: Optional[List[str]] = None) -> str:
        """
        Simple chat interface for compatibility.
        """
        if not self._backend or not isinstance(self._backend, OllamaBackend):
            # Fall back to generate for non-Ollama backends
            result = self.generate(user_input, system_prompt=system_prompt, images=images)
            self.last_tps = result.tokens_per_second
            return result.text
        
        # Use proper chat format for Ollama to prevent hallucinated conversations
        start_time = time.time()
        try:
            if not self._backend.client:
                return "Error: LLM not available"
            
            # Construct message with standard OpenAI Vision format
            if images:
                content_parts = [{"type": "text", "text": user_input}]
                for img in images:
                    img_url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                user_message = {"role": "user", "content": content_parts}
            else:
                user_message = {"role": "user", "content": user_input}

            response = self._backend.client.chat.completions.create(
                model=self._backend.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    user_message
                ],
                max_tokens=256,  # Keep response concise
                temperature=0.7,
                stop=["User:", "Human:", "\n\nUser", "\n\nHuman"]  # Stop before hallucinating next turn
            )
            
            duration = time.time() - start_time
            tokens = response.usage.completion_tokens if response.usage else 0
            tps = tokens / duration if duration > 0 else 0.0
            self.last_tps = tps # Update tracker
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Chat failed: {e}")
            return f"Error: {e}"
