"""
Command Router - Routes commands through orchestrator.

This module ensures ALL commands pass through proper validation
and consent before execution.
"""
import logging
import asyncio
import inspect
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime

from .state_machine import StateMachine, AgentState
from .consent_gate import ConsentGate, ConsentRequest, ConsentResult


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    required_consent: bool = False
    consent_approved: bool = False


class CommandRouter:
    """
    Central command routing system.
    
    ALL commands MUST pass through this router.
    NO module may act independently.
    
    Features:
    - Consent gate integration
    - State machine validation
    - Audit logging
    - Error handling
    - Async support
    """
    
    def __init__(
        self,
        state_machine: StateMachine,
        consent_gate: ConsentGate,
        audit_logger: Optional[Any] = None
    ):
        """
        Initialize the command router.
        
        Args:
            state_machine: Agent state machine.
            consent_gate: Consent gate for permissions.
            audit_logger: Optional audit logger.
        """
        self.logger = logging.getLogger("CommandRouter")
        self.state_machine = state_machine
        self.consent_gate = consent_gate
        self.audit_logger = audit_logger
        
        self._handlers: Dict[str, Callable] = {}
        self._command_history: List[Dict[str, Any]] = []
        
        self.logger.info("CommandRouter initialized.")
    
    def register_handler(self, command: str, handler: Callable) -> None:
        """
        Register a command handler.
        
        Args:
            command: Command/tool name.
            handler: Handler function.
        """
        self._handlers[command] = handler
        self.logger.debug(f"Registered handler: {command}")
    
    def get_handler(self, command: str) -> Optional[Callable]:
        """Get handler for a command."""
        return self._handlers.get(command)
    
    def list_commands(self) -> List[str]:
        """List all registered commands."""
        return list(self._handlers.keys())
    
    async def route(
        self,
        command: str,
        parameters: Dict[str, Any],
        skip_consent: bool = False
    ) -> CommandResult:
        """
        Route a command for execution.
        
        Args:
            command: Command/tool to execute.
            parameters: Command parameters.
            skip_consent: Skip consent check (DANGEROUS - only for internal use).
        
        Returns:
            CommandResult with execution details.
        """
        start_time = datetime.now()
        
        # Check agent state
        if self.state_machine.is_locked:
            return CommandResult(
                success=False,
                result=None,
                error="Agent is locked. Please authenticate to unlock."
            )
        
        # Get handler
        handler = self.get_handler(command)
        if not handler:
            return CommandResult(
                success=False,
                result=None,
                error=f"Unknown command: {command}"
            )
        
        # Check consent if needed
        requires_consent = not self.consent_gate.is_safe_action(command)
        consent_approved = False
        
        if requires_consent and not skip_consent:
            # Transition to confirming state
            self.state_machine.to_confirming(f"Awaiting consent for: {command}")
            
            # Create and process consent request
            consent_request = self.consent_gate.create_request(
                action=command,
                parameters=parameters
            )
            
            consent_result = await self.consent_gate.request_consent(consent_request)
            
            if not consent_result.approved:
                self.state_machine.to_idle("Consent denied")
                return CommandResult(
                    success=False,
                    result=None,
                    error=f"Action not approved: {consent_result.denial_reason}",
                    required_consent=True,
                    consent_approved=False
                )
            
            consent_approved = True
        
        # Transition to acting state
        self.state_machine.to_acting(f"Executing: {command}")
        
        try:
            # Execute handler
            result = await self._execute_handler(handler, parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log execution
            self._log_execution(command, parameters, result, None, execution_time)
            
            # Return to idle
            self.state_machine.to_idle("Execution complete")
            
            return CommandResult(
                success=True,
                result=result,
                execution_time_ms=execution_time,
                required_consent=requires_consent,
                consent_approved=consent_approved
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.logger.error(f"Command execution error: {e}")
            self._log_execution(command, parameters, None, str(e), execution_time)
            
            self.state_machine.to_error(f"Error: {e}")
            self.state_machine.recover()
            
            return CommandResult(
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time,
                required_consent=requires_consent,
                consent_approved=consent_approved
            )
    
    async def _execute_handler(self, handler: Callable, parameters: Dict[str, Any]) -> Any:
        """
        Execute a handler with proper parameter filtering.
        """
        # Filter parameters to match handler signature
        sig = inspect.signature(handler)
        valid_params = {}
        missing_params = []
        
        for name, param in sig.parameters.items():
            if name in parameters:
                valid_params[name] = parameters[name]
            elif param.default == inspect.Parameter.empty and param.kind != inspect.Parameter.VAR_KEYWORD:
                # Required parameter missing
                missing_params.append(name)
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                # Handler accepts **kwargs, pass everything
                valid_params.update(parameters)
                break
        
        if missing_params:
            raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")
        
        # Execute (handle async and sync handlers)
        if asyncio.iscoroutinefunction(handler):
            return await handler(**valid_params)
        else:
            return handler(**valid_params)
    
    def _log_execution(
        self,
        command: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str],
        execution_time_ms: float
    ) -> None:
        """Log command execution."""
        entry = {
            "command": command,
            "parameters": parameters,
            "result": str(result)[:200] if result else None,
            "error": error,
            "execution_time_ms": execution_time_ms,
            "timestamp": datetime.now().isoformat()
        }
        
        self._command_history.append(entry)
        
        # Also log to audit logger if available
        if self.audit_logger:
            try:
                self.audit_logger.log_command(
                    command=command,
                    parameters=parameters,
                    result=str(result)[:500] if result else None,
                    error=error
                )
            except Exception as e:
                self.logger.warning(f"Audit log failed: {e}")
    
    def route_sync(
        self,
        command: str,
        parameters: Dict[str, Any]
    ) -> CommandResult:
        """
        Synchronous wrapper for route().
        
        Args:
            command: Command to execute.
            parameters: Command parameters.
        
        Returns:
            CommandResult.
        """
        return asyncio.run(self.route(command, parameters))
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get command execution history."""
        return self._command_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear command history."""
        self._command_history.clear()
