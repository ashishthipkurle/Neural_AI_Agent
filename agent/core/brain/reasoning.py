"""
Reasoning Engine - Cognitive reasoning and decision making.

This module provides the reasoning capabilities of the agent including:
- Context understanding
- Decision making
- Response generation
- Logical inference
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class ReasoningMode(Enum):
    """Different reasoning modes for different tasks."""
    CONVERSATIONAL = "conversational"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    SAFETY_CHECK = "safety_check"


@dataclass
class ReasoningContext:
    """Context for a reasoning operation."""
    user_input: str
    system_prompt: str
    conversation_history: List[Dict[str, str]]
    memory_context: List[str]
    current_screen_context: Optional[str] = None
    mode: ReasoningMode = ReasoningMode.CONVERSATIONAL


@dataclass
class ReasoningResult:
    """Result of a reasoning operation."""
    response: str
    confidence: float
    reasoning_chain: List[str]
    suggested_actions: List[str]
    safety_flags: List[str]


class ReasoningEngine:
    """
    Core reasoning engine for the agent.
    
    Provides reasoning capabilities:
    - Context-aware response generation
    - Safety analysis
    - Action recommendation
    - Logical inference
    """
    
    # Safety keywords that trigger additional checks
    SAFETY_KEYWORDS = frozenset({
        'delete', 'remove', 'format', 'shutdown', 'kill',
        'password', 'credential', 'secret', 'private',
        'sudo', 'admin', 'root', 'system32'
    })
    
    def __init__(self, llm_interface=None, config: Dict[str, Any] = None):
        """
        Initialize the Reasoning Engine.
        
        Args:
            llm_interface: LLM interface for generation.
            config: Configuration dictionary.
        """
        self.logger = logging.getLogger("ReasoningEngine")
        self.llm = llm_interface
        self.config = config or {}
        
        # Load persona from config
        self.persona = self.config.get('system_prompt', self._default_persona())
        self.logger.info("ReasoningEngine initialized.")
    
    def _default_persona(self) -> str:
        """Return default agent persona."""
        return """You are a helpful, local AI assistant.
        You are running entirely on the user's local machine.
        You prioritize user privacy and security.
        You always explain your actions clearly.
        You ask for confirmation before destructive actions."""
    
    def analyze_safety(self, user_input: str) -> List[str]:
        """
        Analyze input for safety concerns.
        
        Args:
            user_input: The user's input text.
        
        Returns:
            List of safety flags/warnings.
        """
        flags = []
        input_lower = user_input.lower()
        
        for keyword in self.SAFETY_KEYWORDS:
            if keyword in input_lower:
                flags.append(f"SAFETY: Contains keyword '{keyword}'")
        
        # Check for potential command injection
        dangerous_patterns = ['&&', '||', ';', '`', '$(', '${']
        for pattern in dangerous_patterns:
            if pattern in user_input:
                flags.append(f"SAFETY: Potential command injection '{pattern}'")
        
        if flags:
            self.logger.warning(f"Safety analysis found {len(flags)} concerns.")
        
        return flags
    
    async def reason(self, context: ReasoningContext) -> ReasoningResult:
        """
        Perform reasoning on the given context.
        
        Args:
            context: ReasoningContext with all relevant information.
        
        Returns:
            ReasoningResult with response and metadata.
        """
        self.logger.info(f"Reasoning in mode: {context.mode.value}")
        
        # Analyze safety first
        safety_flags = self.analyze_safety(context.user_input)
        
        # Build prompt with memory context
        full_context = self._build_context(context)
        
        # Generate response using LLM
        if self.llm:
            try:
                response = self.llm.chat(full_context, context.user_input)
            except Exception as e:
                self.logger.error(f"LLM reasoning failed: {e}")
                response = "I encountered an error while thinking. Please try again."
        else:
            response = "Reasoning engine ready but no LLM configured."
        
        # Build reasoning chain (for explainability)
        reasoning_chain = [
            f"Input: {context.user_input}",
            f"Mode: {context.mode.value}",
            f"Memory items considered: {len(context.memory_context)}",
            f"Safety flags: {len(safety_flags)}"
        ]
        
        return ReasoningResult(
            response=response,
            confidence=0.8 if not safety_flags else 0.5,
            reasoning_chain=reasoning_chain,
            suggested_actions=[],
            safety_flags=safety_flags
        )
    
    def _build_context(self, context: ReasoningContext) -> str:
        """Build full context string for LLM."""
        parts = [context.system_prompt or self.persona]
        
        # Add memory context
        if context.memory_context:
            parts.append("\n--- RELEVANT MEMORIES ---")
            for mem in context.memory_context[:5]:  # Limit to 5 most relevant
                parts.append(f"- {mem}")
        
        # Add screen context if available
        if context.current_screen_context:
            parts.append(f"\n--- CURRENT SCREEN ---\n{context.current_screen_context}")
        
        # Add conversation history (last 5 exchanges)
        if context.conversation_history:
            parts.append("\n--- RECENT CONVERSATION ---")
            for entry in context.conversation_history[-5:]:
                role = entry.get('role', 'unknown')
                content = entry.get('content', '')
                parts.append(f"{role}: {content}")
        
        return "\n".join(parts)
    
    def should_confirm_action(self, action: str, parameters: Dict[str, Any]) -> bool:
        """
        Determine if an action requires user confirmation.
        
        Args:
            action: The action to check.
            parameters: Action parameters.
        
        Returns:
            True if confirmation is required.
        """
        # All destructive actions require confirmation
        destructive_actions = {
            'delete', 'remove', 'execute_code', 'write_file',
            'shell_command', 'format', 'shutdown', 'forget_face'
        }
        
        action_lower = action.lower()
        
        if any(da in action_lower for da in destructive_actions):
            return True
        
        # Check parameters for file paths to sensitive areas
        for value in parameters.values():
            if isinstance(value, str):
                sensitive_paths = ['system32', 'program files', 'windows', '/etc', '/bin']
                if any(sp in value.lower() for sp in sensitive_paths):
                    return True
        
        return False
    
    def generate_confirmation_prompt(self, action: str, parameters: Dict[str, Any]) -> str:
        """
        Generate a user-friendly confirmation prompt.
        
        Args:
            action: The action requiring confirmation.
            parameters: Action parameters.
        
        Returns:
            Human-readable confirmation prompt.
        """
        param_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
        return f"I'm about to {action}. Parameters: {param_str}. Do you want me to proceed?"
