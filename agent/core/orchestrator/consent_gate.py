"""
Consent Gate - Permission enforcement with dual confirmation.

This module implements the consent system requiring explicit
user approval for dangerous actions, with both voice and UI confirmation.
"""
import logging
import asyncio
from typing import Optional, Callable, Dict, Any, Awaitable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import threading


class ConsentLevel(Enum):
    """Levels of consent required."""
    NONE = 0          # No confirmation needed
    SINGLE = 1        # Single confirmation (voice OR UI)
    DUAL = 2          # Dual confirmation (voice AND UI)
    CRITICAL = 3      # Dual + reason stated + countdown


class ConsentStatus(Enum):
    """Status of a consent request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ConsentRequest:
    """Request for user consent."""
    id: str
    action: str
    description: str
    level: ConsentLevel
    parameters: Dict[str, Any]
    created_at: str
    timeout_seconds: float = 30.0
    voice_confirmed: bool = False
    ui_confirmed: bool = False
    status: ConsentStatus = ConsentStatus.PENDING
    denial_reason: Optional[str] = None


@dataclass
class ConsentResult:
    """Result of a consent request."""
    request_id: str
    approved: bool
    confirmation_method: str  # voice, ui, dual, timeout, denied
    timestamp: str
    denial_reason: Optional[str] = None


class ConsentGate:
    """
    Permission enforcement system.
    
    All destructive or dangerous actions MUST pass through
    this gate before execution.
    
    Features:
    - Single and dual confirmation modes
    - Voice + UI confirmation
    - Timeout handling
    - Consent history logging
    - Dangerous action detection
    """
    
    # Actions requiring DUAL confirmation (voice AND UI)
    DUAL_CONFIRM_ACTIONS = frozenset({
        'delete', 'remove', 'format', 'shutdown', 'restart',
        'execute_code', 'forget_face', 'clear_memory'
    })
    
    # Actions requiring SINGLE confirmation
    SINGLE_CONFIRM_ACTIONS = frozenset({
        'write_file', 'install', 'download', 'send',
        'browser_navigate', 'shell_command'
    })
    
    # Actions requiring no confirmation
    SAFE_ACTIONS = frozenset({
        'read_file', 'list_files', 'search_memory',
        'capture_screen', 'get_time', 'chat_tool',
        'analyze_chart', 'analyze_screen_chart',       # Market analysis (read-only)
        'describe_image', 'calculate', 'search_online' # Other non-destructive tools
    })
    
    def __init__(
        self,
        voice_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        ui_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        default_timeout: float = 30.0
    ):
        """
        Initialize the consent gate.
        
        Args:
            voice_callback: Async function to get voice confirmation.
            ui_callback: Async function to get UI confirmation.
            default_timeout: Default timeout for consent requests.
        """
        self.logger = logging.getLogger("ConsentGate")
        self.voice_callback = voice_callback
        self.ui_callback = ui_callback
        self.default_timeout = default_timeout
        
        self._pending_requests: Dict[str, ConsentRequest] = {}
        self._history: list = []
        self._request_counter = 0
        self._lock = threading.RLock()
        
        self.logger.info("ConsentGate initialized.")
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        with self._lock:
            self._request_counter += 1
            return f"consent_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._request_counter}"
    
    def determine_consent_level(self, action: str) -> ConsentLevel:
        """
        Determine consent level required for an action.
        
        Args:
            action: The action to check.
        
        Returns:
            Required ConsentLevel.
        """
        action_lower = action.lower()
        
        # Check for dual confirmation keywords
        for keyword in self.DUAL_CONFIRM_ACTIONS:
            if keyword in action_lower:
                return ConsentLevel.DUAL
        
        # Check for single confirmation keywords
        for keyword in self.SINGLE_CONFIRM_ACTIONS:
            if keyword in action_lower:
                return ConsentLevel.SINGLE
        
        # Check if explicitly safe
        for keyword in self.SAFE_ACTIONS:
            if keyword in action_lower:
                return ConsentLevel.NONE
        
        # Default to single confirmation for unknown actions
        return ConsentLevel.SINGLE
    
    def create_request(
        self,
        action: str,
        parameters: Dict[str, Any],
        description: Optional[str] = None
    ) -> ConsentRequest:
        """
        Create a consent request.
        
        Args:
            action: The action requiring consent.
            parameters: Action parameters.
            description: Human-readable description.
        
        Returns:
            ConsentRequest object.
        """
        level = self.determine_consent_level(action)
        
        if description is None:
            param_str = ", ".join(f"{k}={v}" for k, v in list(parameters.items())[:3])
            description = f"Execute '{action}' with parameters: {param_str}"
        
        request = ConsentRequest(
            id=self._generate_request_id(),
            action=action,
            description=description,
            level=level,
            parameters=parameters,
            created_at=datetime.now().isoformat(),
            timeout_seconds=self.default_timeout
        )
        
        with self._lock:
            self._pending_requests[request.id] = request
        
        self.logger.info(f"Consent request created: {request.id} ({level.name})")
        return request
    
    async def request_consent(self, request: ConsentRequest) -> ConsentResult:
        """
        Request user consent asynchronously.
        
        Args:
            request: The consent request.
        
        Returns:
            ConsentResult with approval status.
        """
        if request.level == ConsentLevel.NONE:
            # No confirmation needed
            return self._approve(request, "auto")
        
        self.logger.info(f"Requesting {request.level.name} consent for: {request.action}")
        
        try:
            if request.level == ConsentLevel.DUAL:
                # Need both voice AND UI confirmation
                return await self._request_dual_consent(request)
            else:
                # Single confirmation (voice OR UI)
                return await self._request_single_consent(request)
                
        except asyncio.TimeoutError:
            return self._timeout(request)
        except Exception as e:
            self.logger.error(f"Consent request error: {e}")
            return self._deny(request, str(e))
    
    async def _request_single_consent(self, request: ConsentRequest) -> ConsentResult:
        """Request single confirmation."""
        prompt = f"Do you want me to: {request.description}?"
        
        # Try voice first if available
        if self.voice_callback:
            try:
                approved = await asyncio.wait_for(
                    self.voice_callback(prompt),
                    timeout=request.timeout_seconds
                )
                if approved:
                    request.voice_confirmed = True
                    return self._approve(request, "voice")
            except asyncio.TimeoutError:
                pass
        
        # Fall back to UI
        if self.ui_callback:
            try:
                approved = await asyncio.wait_for(
                    self.ui_callback(prompt),
                    timeout=request.timeout_seconds
                )
                if approved:
                    request.ui_confirmed = True
                    return self._approve(request, "ui")
            except asyncio.TimeoutError:
                pass
        
        # No confirmation method available or denied
        return self._deny(request, "No confirmation received")
    
    async def _request_dual_consent(self, request: ConsentRequest) -> ConsentResult:
        """Request dual confirmation (voice AND UI)."""
        prompt = f"[REQUIRES DUAL CONFIRMATION] {request.description}"
        
        voice_task = None
        ui_task = None
        
        # Request both confirmations
        if self.voice_callback:
            voice_task = asyncio.create_task(self.voice_callback(prompt))
        
        if self.ui_callback:
            ui_task = asyncio.create_task(self.ui_callback(prompt))
        
        # Wait for both
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    voice_task or asyncio.sleep(0.1),
                    ui_task or asyncio.sleep(0.1),
                    return_exceptions=True
                ),
                timeout=request.timeout_seconds
            )
            
            voice_approved = results[0] if voice_task else False
            ui_approved = results[1] if ui_task else False
            
            request.voice_confirmed = bool(voice_approved)
            request.ui_confirmed = bool(ui_approved)
            
            if request.voice_confirmed and request.ui_confirmed:
                return self._approve(request, "dual")
            else:
                return self._deny(request, "Dual confirmation not received")
                
        except asyncio.TimeoutError:
            return self._timeout(request)
    
    def approve_via_ui(self, request_id: str) -> bool:
        """
        Approve a pending request via UI.
        
        Args:
            request_id: ID of the request to approve.
        
        Returns:
            True if approved successfully.
        """
        with self._lock:
            request = self._pending_requests.get(request_id)
            if request:
                request.ui_confirmed = True
                self.logger.info(f"UI approval for: {request_id}")
                return True
        return False
    
    def deny_via_ui(self, request_id: str, reason: str = "User denied") -> bool:
        """
        Deny a pending request via UI.
        
        Args:
            request_id: ID of the request to deny.
            reason: Reason for denial.
        
        Returns:
            True if denied successfully.
        """
        with self._lock:
            request = self._pending_requests.get(request_id)
            if request:
                request.status = ConsentStatus.DENIED
                request.denial_reason = reason
                self.logger.info(f"UI denial for: {request_id} - {reason}")
                return True
        return False
    
    def _approve(self, request: ConsentRequest, method: str) -> ConsentResult:
        """Mark request as approved."""
        request.status = ConsentStatus.APPROVED
        result = ConsentResult(
            request_id=request.id,
            approved=True,
            confirmation_method=method,
            timestamp=datetime.now().isoformat()
        )
        self._record_result(request, result)
        self.logger.info(f"Consent APPROVED: {request.action} via {method}")
        return result
    
    def _deny(self, request: ConsentRequest, reason: str) -> ConsentResult:
        """Mark request as denied."""
        request.status = ConsentStatus.DENIED
        request.denial_reason = reason
        result = ConsentResult(
            request_id=request.id,
            approved=False,
            confirmation_method="denied",
            timestamp=datetime.now().isoformat(),
            denial_reason=reason
        )
        self._record_result(request, result)
        self.logger.info(f"Consent DENIED: {request.action} - {reason}")
        return result
    
    def _timeout(self, request: ConsentRequest) -> ConsentResult:
        """Mark request as timed out."""
        request.status = ConsentStatus.TIMEOUT
        result = ConsentResult(
            request_id=request.id,
            approved=False,
            confirmation_method="timeout",
            timestamp=datetime.now().isoformat(),
            denial_reason="Request timed out"
        )
        self._record_result(request, result)
        self.logger.info(f"Consent TIMEOUT: {request.action}")
        return result
    
    def _record_result(self, request: ConsentRequest, result: ConsentResult) -> None:
        """Record consent result in history."""
        with self._lock:
            self._history.append({
                "request": request,
                "result": result
            })
            # Remove from pending
            self._pending_requests.pop(request.id, None)
    
    def get_history(self, limit: int = 50) -> list:
        """Get consent history."""
        with self._lock:
            return self._history[-limit:]
    
    def is_safe_action(self, action: str) -> bool:
        """Check if action is safe (no consent needed)."""
        return self.determine_consent_level(action) == ConsentLevel.NONE
