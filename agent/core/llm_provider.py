"""
Unified LLM Provider — single factory for all LangGraph nodes.

Replaces the 3 duplicate LLM layers:
  - LLMInterface (agent/core/llm_interface.py)
  - Brain (agent/core/brain.py)
  - LocalLLMRuntime (agent/core/llm/local_runtime.py)

All graph nodes import from here instead of instantiating their own clients.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_ollama import ChatOllama

logger = logging.getLogger("LLMProvider")


def get_llm(config: Dict[str, Any], *, temperature: float = 0.1) -> ChatOllama:
    """Return the primary text/code ChatOllama model.

    Parameters
    ----------
    config : dict
        Full settings dict (must contain ``llm.model_name`` at minimum).
    temperature : float, optional
        Sampling temperature — low for deterministic tool‐calling,
        higher for creative chat.
    """
    llm_cfg = config.get("llm", {})
    model = llm_cfg.get("model_name", "llama3")
    base_url = llm_cfg.get("ollama_url", "http://localhost:11434")

    logger.info(f"Creating ChatOllama: model={model}  url={base_url}")
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        timeout=300,   # 5 min per-chunk timeout for large code generation
        num_predict=16384,  # enough for full file writes and multi-function responses
        num_ctx=32768,  # 32K context window for system prompt + code + tool results
    )


def get_vision_llm(config: Dict[str, Any]) -> ChatOllama:
    """Return the vision/multimodal ChatOllama model.

    Falls back to the primary model if ``llm.vision_model`` is not set.
    """
    llm_cfg = config.get("llm", {})
    model = llm_cfg.get("vision_model") or llm_cfg.get("model_name", "llava")
    base_url = llm_cfg.get("ollama_url", "http://localhost:11434")

    logger.info(f"Creating vision ChatOllama: model={model}  url={base_url}")
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0.2,
    )


def get_llm_with_tools(
    config: Dict[str, Any],
    tools: List[Any],
    *,
    temperature: float = 0.1,
) -> ChatOllama:
    """Return a ChatOllama model with tools bound.

    This is used by agent nodes that need structured tool calling.
    If the model does not support ``bind_tools``, the raw model is
    returned and tool routing must be done via prompt engineering.
    """
    llm = get_llm(config, temperature=temperature)
    try:
        return llm.bind_tools(tools)
    except Exception as exc:
        logger.warning(f"bind_tools failed ({exc}) — returning raw model")
        return llm
