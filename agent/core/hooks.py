import logging
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("core.hooks")

class HookEvent(Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    POST_TOOL_USE_FAILURE = "post_tool_use_failure"

@dataclass
class HookContext:
    tool_name: str
    tool_input: Dict[str, Any]
    session_id: Optional[str] = None
    permission_mode: Optional[str] = None

@dataclass 
class HookResult:
    denied: bool = False
    deny_reason: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None  # Mutated input
    permission_override: Optional[str] = None        # Force allow/deny
    messages: List[str] = field(default_factory=list)

class HookAbortSignal:
    def __init__(self):
        self._aborted = False

    def abort(self):
        self._aborted = True

    @property
    def is_aborted(self) -> bool:
        return self._aborted

class HookRunner:
    """Claw-parity hook runner — executes pre/post hooks for tool calls."""
    
    def __init__(self):
        self.abort_signal = HookAbortSignal()
        self._hooks: Dict[HookEvent, List[Callable]] = {
            HookEvent.PRE_TOOL_USE: [],
            HookEvent.POST_TOOL_USE: [],
            HookEvent.POST_TOOL_USE_FAILURE: []
        }
    
    def register_hook(self, event: HookEvent, handler: Callable) -> None:
        """Register a hook for a specific event."""
        self._hooks[event].append(handler)
        
    async def run_pre_hooks(self, context: HookContext) -> HookResult:
        """Run all registered pre-tool hooks."""
        combined_result = HookResult()
        
        for hook_fn in self._hooks[HookEvent.PRE_TOOL_USE]:
            if self.abort_signal.is_aborted:
                combined_result.denied = True
                combined_result.deny_reason = "Hook execution aborted."
                break
                
            try:
                if asyncio.iscoroutinefunction(hook_fn):
                    result = await hook_fn(context)
                else:
                    result = hook_fn(context)
                    
                if isinstance(result, HookResult):
                    if result.denied:
                        combined_result.denied = True
                        combined_result.deny_reason = result.deny_reason
                        break
                    
                    if result.updated_input:
                        combined_result.updated_input = result.updated_input
                        context.tool_input = result.updated_input
                        
                    if result.permission_override:
                        combined_result.permission_override = result.permission_override
                        
                    combined_result.messages.extend(result.messages)
            except Exception as e:
                logger.error(f"Error executing pre-hook: {e}")
                
        return combined_result
        
    async def run_post_hooks(self, context: HookContext, tool_result: Any) -> HookResult:
        """Run all registered post-tool hooks."""
        combined_result = HookResult()
        
        for hook_fn in self._hooks[HookEvent.POST_TOOL_USE]:
            if self.abort_signal.is_aborted:
                break
                
            try:
                if asyncio.iscoroutinefunction(hook_fn):
                    result = await hook_fn(context, tool_result)
                else:
                    result = hook_fn(context, tool_result)
                    
                if isinstance(result, HookResult):
                    combined_result.messages.extend(result.messages)
            except Exception as e:
                logger.error(f"Error executing post-hook: {e}")
                
        return combined_result

    async def run_post_failure_hooks(self, context: HookContext, error: Exception) -> HookResult:
        """Run all registered post-tool-failure hooks."""
        combined_result = HookResult()
        
        for hook_fn in self._hooks[HookEvent.POST_TOOL_USE_FAILURE]:
            if self.abort_signal.is_aborted:
                break
                
            try:
                if asyncio.iscoroutinefunction(hook_fn):
                    result = await hook_fn(context, error)
                else:
                    result = hook_fn(context, error)
                    
                if isinstance(result, HookResult):
                    combined_result.messages.extend(result.messages)
            except Exception as e:
                logger.error(f"Error executing post-failure-hook: {e}")
                
        return combined_result
