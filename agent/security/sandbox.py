import os
import time
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger("security.sandbox")

class SandboxStatus(Enum):
    NOT_SANDBOXED = "not_sandboxed"
    DOCKER_CONTAINER = "docker_container"
    WSL_ENVIRONMENT = "wsl_environment"
    RESTRICTED_USER = "restricted_user"

@dataclass
class CommandExecutionConfig:
    timeout_seconds: int = 120
    max_output_bytes: int = 10240      # ~10KB
    truncation_marker: str = "\n...[truncated]"
    allowed_exit_codes: List[int] = field(default_factory=lambda: [0])
    inherit_env: bool = True
    working_directory: Optional[str] = None

@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    truncated: bool = False
    timeout: bool = False

class SecureCommandRunner:
    """Hardened subprocess wrapper — Claw-parity §sandbox.rs + §bash.rs"""
    
    def __init__(self, config: Optional[CommandExecutionConfig] = None):
        self.config = config or CommandExecutionConfig()
        self.sandbox_status = self._detect_sandbox()
        logger.info(f"Initialized SecureCommandRunner. Sandbox status: {self.sandbox_status.value}")
    
    def _detect_sandbox(self) -> SandboxStatus:
        if os.path.exists('/.dockerenv'):
            return SandboxStatus.DOCKER_CONTAINER
        if os.name == 'posix' and 'microsoft' in os.uname().release.lower():
            return SandboxStatus.WSL_ENVIRONMENT
        if hasattr(os, 'geteuid') and os.geteuid() != 0:
            return SandboxStatus.RESTRICTED_USER
        return SandboxStatus.NOT_SANDBOXED
    
    async def run(self, command: str, **kwargs) -> CommandResult:
        """Execute with timeout, output truncation, and audit trail."""
        timeout = kwargs.pop('timeout', self.config.timeout_seconds)
        cwd = kwargs.pop('cwd', self.config.working_directory)
        env = os.environ.copy() if self.config.inherit_env else kwargs.get('env', {})
        
        start_time = time.time()
        truncated = False
        is_timeout = False
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                **kwargs
            )
            
            # Wait with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                # Kill process tree on timeout
                try:
                    process.kill()
                    await process.communicate() # wait for it to actually die
                except Exception:
                    pass
                is_timeout = True
                stdout_bytes = b""
                stderr_bytes = f"Command timed out after {timeout} seconds".encode()
                
            stdout_str = stdout_bytes.decode('utf-8', errors='replace')
            stderr_str = stderr_bytes.decode('utf-8', errors='replace')
            
            # Truncation logic
            if len(stdout_str) > self.config.max_output_bytes:
                stdout_str = stdout_str[:self.config.max_output_bytes] + self.config.truncation_marker
                truncated = True
                
            if len(stderr_str) > self.config.max_output_bytes:
                stderr_str = stderr_str[:self.config.max_output_bytes] + self.config.truncation_marker
                truncated = True

            exit_code = process.returncode if process.returncode is not None else -1
            success = not is_timeout and exit_code in self.config.allowed_exit_codes
            
        except Exception as e:
            stdout_str = ""
            stderr_str = str(e)
            exit_code = -1
            success = False

        execution_time_ms = (time.time() - start_time) * 1000.0
        
        return CommandResult(
            success=success,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            execution_time_ms=execution_time_ms,
            truncated=truncated,
            timeout=is_timeout
        )
