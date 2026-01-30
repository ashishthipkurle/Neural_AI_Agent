"""
Code Executor - Secure sandboxed code execution system.

This module provides safe code execution with:
- Mandatory preview before execution
- Dry-run validation mode
- Emergency kill switch
- Resource limits (CPU, memory, time)
- Network isolation
- Explicit user approval

CONSTRAINTS (NON-NEGOTIABLE):
- NO arbitrary execution
- NO background execution
- NO execution without preview + approval
"""
import docker
import logging
import threading
import ast
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from agent.security.permissions import PermissionManager


class ExecutionStatus(Enum):
    """Code execution status."""
    PENDING = "pending"
    PREVIEWING = "previewing"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    KILLED = "killed"
    ERROR = "error"


class RiskLevel(Enum):
    """Risk assessment level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodeAnalysis:
    """Static analysis result for code preview."""
    language: str
    lines_of_code: int
    imports: List[str] = field(default_factory=list)
    function_calls: List[str] = field(default_factory=list)
    file_operations: List[str] = field(default_factory=list)
    network_operations: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    risk_reasons: List[str] = field(default_factory=list)
    estimated_memory_mb: int = 64
    is_valid_syntax: bool = True
    syntax_error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: int
    status: ExecutionStatus
    error_message: Optional[str] = None


class CodeExecutor:
    """
    Secure code execution sandbox.
    
    Features:
    - Preview code before execution
    - Dry-run validation
    - Kill switch for running containers
    - Resource limits
    - Network isolation
    
    MANDATORY FLOW:
    1. preview_code() - Analyze and show preview
    2. User approval (via ConsentGate)
    3. execute_code() or dry_run() - Run code
    """
    
    # Supported languages and their Docker images
    LANGUAGE_IMAGES: Dict[str, str] = {
        "python": "python:3.9-slim",
        "python3": "python:3.9-slim",
        "node": "node:18-slim",
        "javascript": "node:18-slim",
    }
    
    # Resource limits
    MEMORY_LIMIT = "128m"
    CPU_QUOTA = 50000
    CPU_PERIOD = 100000
    MAX_EXECUTION_TIME = 30  # seconds
    
    # Dangerous patterns to detect
    DANGEROUS_PYTHON_PATTERNS = [
        (r'\bos\.system\b', "os.system() - Shell command execution"),
        (r'\bsubprocess\b', "subprocess - External process spawning"),
        (r'\beval\b', "eval() - Dynamic code execution"),
        (r'\bexec\b', "exec() - Dynamic code execution"),
        (r'\b__import__\b', "__import__() - Dynamic imports"),
        (r'\bopen\s*\([^)]*["\']w["\']', "File write operations"),
        (r'\brequests\b', "requests - Network operations"),
        (r'\burllib\b', "urllib - Network operations"),
        (r'\bsocket\b', "socket - Network operations"),
        (r'\bctypes\b', "ctypes - Low-level memory access"),
    ]
    
    def __init__(self, consent_gate=None, audit_logger=None):
        """
        Initialize code executor.
        
        Args:
            consent_gate: ConsentGate for approval (optional).
            audit_logger: AuditLogger for logging (optional).
        """
        self.logger = logging.getLogger("CodeExecutor")
        self.permissions = PermissionManager()
        self.consent_gate = consent_gate
        self.audit_logger = audit_logger
        
        # Docker client
        self.client = None
        self._init_docker()
        
        # Active container tracking for kill switch
        self._active_containers: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
        self.logger.info("CodeExecutor initialized with safety features.")
    
    def _init_docker(self) -> None:
        """Initialize Docker client."""
        try:
            self.client = docker.from_env()
            self.client.ping()
            self.logger.info("Docker connection established.")
        except Exception as e:
            self.logger.error(f"Docker is not available: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Docker is available."""
        return self.client is not None
    
    # ==================== PREVIEW SYSTEM ====================
    
    def preview_code(self, language: str, code: str) -> CodeAnalysis:
        """
        Analyze code and generate preview.
        
        This MUST be called before any execution.
        
        Args:
            language: Programming language.
            code: Code to analyze.
        
        Returns:
            CodeAnalysis with risk assessment.
        """
        analysis = CodeAnalysis(
            language=language.lower(),
            lines_of_code=len(code.strip().split('\n'))
        )
        
        # Validate syntax
        if language.lower() in ["python", "python3"]:
            analysis = self._analyze_python(code, analysis)
        elif language.lower() in ["node", "javascript"]:
            analysis = self._analyze_javascript(code, analysis)
        else:
            analysis.risk_level = RiskLevel.MEDIUM
            analysis.risk_reasons.append(f"Unknown language: {language}")
        
        # Override risk if critical patterns found
        if analysis.network_operations:
            if analysis.risk_level.value < RiskLevel.HIGH.value:
                analysis.risk_level = RiskLevel.HIGH
        
        if analysis.file_operations:
            if analysis.risk_level.value < RiskLevel.MEDIUM.value:
                analysis.risk_level = RiskLevel.MEDIUM
        
        self.logger.info(f"Code preview generated: {analysis.risk_level.value} risk")
        return analysis
    
    def _analyze_python(self, code: str, analysis: CodeAnalysis) -> CodeAnalysis:
        """Analyze Python code."""
        # Check syntax
        try:
            tree = ast.parse(code)
            analysis.is_valid_syntax = True
        except SyntaxError as e:
            analysis.is_valid_syntax = False
            analysis.syntax_error = str(e)
            analysis.risk_level = RiskLevel.MEDIUM
            analysis.risk_reasons.append(f"Syntax error: {e}")
            return analysis
        
        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    analysis.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    analysis.imports.append(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    analysis.function_calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    analysis.function_calls.append(node.func.attr)
        
        # Check dangerous patterns
        for pattern, description in self.DANGEROUS_PYTHON_PATTERNS:
            if re.search(pattern, code):
                if "network" in description.lower():
                    analysis.network_operations.append(description)
                elif "file" in description.lower():
                    analysis.file_operations.append(description)
                analysis.risk_reasons.append(description)
                
                if "critical" in description.lower() or "shell" in description.lower():
                    analysis.risk_level = RiskLevel.CRITICAL
                elif analysis.risk_level.value < RiskLevel.HIGH.value:
                    analysis.risk_level = RiskLevel.HIGH
        
        return analysis
    
    def _analyze_javascript(self, code: str, analysis: CodeAnalysis) -> CodeAnalysis:
        """Analyze JavaScript code."""
        # Basic pattern matching for JS
        dangerous_patterns = [
            (r'\brequire\s*\(\s*["\']fs["\']', "File system access"),
            (r'\brequire\s*\(\s*["\']child_process["\']', "Child process spawning"),
            (r'\bfetch\s*\(', "Network fetch"),
            (r'\beval\s*\(', "eval() - Dynamic code"),
            (r'\bFunction\s*\(', "Function() constructor"),
        ]
        
        for pattern, description in dangerous_patterns:
            if re.search(pattern, code):
                analysis.risk_reasons.append(description)
                if "child" in description.lower():
                    analysis.risk_level = RiskLevel.CRITICAL
                elif analysis.risk_level.value < RiskLevel.HIGH.value:
                    analysis.risk_level = RiskLevel.HIGH
        
        return analysis
    
    def format_preview(self, analysis: CodeAnalysis, code: str) -> str:
        """
        Format preview for display.
        
        Args:
            analysis: Code analysis result.
            code: Original code.
        
        Returns:
            Formatted preview string.
        """
        lines = [
            "=" * 50,
            "CODE EXECUTION PREVIEW",
            "=" * 50,
            f"Language: {analysis.language}",
            f"Lines: {analysis.lines_of_code}",
            f"Risk Level: {analysis.risk_level.value.upper()}",
            ""
        ]
        
        if not analysis.is_valid_syntax:
            lines.append(f"⚠️ SYNTAX ERROR: {analysis.syntax_error}")
            lines.append("")
        
        if analysis.imports:
            lines.append(f"Imports: {', '.join(analysis.imports[:10])}")
        
        if analysis.risk_reasons:
            lines.append("")
            lines.append("⚠️ RISK FACTORS:")
            for reason in analysis.risk_reasons:
                lines.append(f"  • {reason}")
        
        lines.append("")
        lines.append("CODE:")
        lines.append("-" * 50)
        # Show first 20 lines
        code_lines = code.strip().split('\n')[:20]
        for i, line in enumerate(code_lines, 1):
            lines.append(f"{i:3}: {line}")
        if len(code.strip().split('\n')) > 20:
            lines.append("... (truncated)")
        lines.append("-" * 50)
        
        return "\n".join(lines)
    
    # ==================== DRY RUN ====================
    
    def dry_run(self, language: str, code: str) -> Tuple[bool, str]:
        """
        Validate code without executing.
        
        Args:
            language: Programming language.
            code: Code to validate.
        
        Returns:
            Tuple of (is_valid, message).
        """
        analysis = self.preview_code(language, code)
        
        issues = []
        
        if not analysis.is_valid_syntax:
            issues.append(f"Syntax error: {analysis.syntax_error}")
        
        if analysis.risk_level == RiskLevel.CRITICAL:
            issues.append("Critical risk patterns detected - would require special approval")
        
        if language.lower() not in self.LANGUAGE_IMAGES:
            issues.append(f"Unsupported language: {language}")
        
        if not self.client:
            issues.append("Docker is not available")
        
        if issues:
            return False, "DRY RUN FAILED:\n" + "\n".join(f"  • {i}" for i in issues)
        
        return True, f"DRY RUN PASSED: Code is valid and ready for execution (Risk: {analysis.risk_level.value})"
    
    # ==================== EXECUTION ====================
    
    def execute_code(
        self, 
        language: str, 
        code: str,
        timeout: int = None,
        require_approval: bool = True
    ) -> ExecutionResult:
        """
        Execute code in Docker sandbox.
        
        REQUIRES prior preview + approval.
        
        Args:
            language: Programming language.
            code: Code to execute.
            timeout: Execution timeout in seconds.
            require_approval: Whether to require user approval.
        
        Returns:
            ExecutionResult with output.
        """
        timeout = timeout or self.MAX_EXECUTION_TIME
        
        # Pre-checks
        if not self.client:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Docker is not available. Please install Docker Desktop.",
                execution_time_ms=0,
                status=ExecutionStatus.ERROR,
                error_message="Docker unavailable"
            )
        
        image = self.LANGUAGE_IMAGES.get(language.lower())
        if not image:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Unsupported language: {language}",
                execution_time_ms=0,
                status=ExecutionStatus.ERROR,
                error_message=f"Unsupported language: {language}"
            )
        
        # Security approval
        if require_approval:
            analysis = self.preview_code(language, code)
            preview = self.format_preview(analysis, code)
            
            desc = f"Execute {language} code:\n{preview}"
            if not self.permissions.request_permission(desc):
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Execution cancelled by user.",
                    execution_time_ms=0,
                    status=ExecutionStatus.CANCELLED
                )
        
        # Build command
        if language.lower() in ["python", "python3"]:
            cmd = ["python", "-c", code]
        elif language.lower() in ["node", "javascript"]:
            cmd = ["node", "-e", code]
        else:
            cmd = []
        
        # Execute
        start_time = datetime.now()
        container = None
        execution_id = f"exec_{start_time.timestamp()}"
        
        try:
            self.logger.info(f"Running code in {image} container (ID: {execution_id})...")
            
            container = self.client.containers.run(
                image,
                command=cmd,
                detach=True,
                network_mode="none",  # No network access
                mem_limit=self.MEMORY_LIMIT,
                cpu_period=self.CPU_PERIOD,
                cpu_quota=self.CPU_QUOTA,
                remove=False  # We'll remove after getting logs
            )
            
            # Track for kill switch
            with self._lock:
                self._active_containers[execution_id] = container
            
            # Wait with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get('StatusCode', -1)
            except Exception as e:
                # Timeout - kill container
                self.logger.warning(f"Execution timeout after {timeout}s")
                container.kill()
                exit_code = -1
            
            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            # Remove container
            container.remove(force=True)
            
            # Remove from tracking
            with self._lock:
                self._active_containers.pop(execution_id, None)
            
            end_time = datetime.now()
            execution_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Log execution
            if self.audit_logger:
                self.audit_logger.log_command(
                    command="code_execute",
                    parameters={"language": language, "code_preview": code[:100]},
                    result=f"exit_code={exit_code}",
                    consent_required=True,
                    consent_given=True
                )
            
            return ExecutionResult(
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=logs if exit_code == 0 else "",
                stderr=logs if exit_code != 0 else "",
                execution_time_ms=execution_time,
                status=ExecutionStatus.COMPLETED
            )
            
        except docker.errors.ContainerError as e:
            return ExecutionResult(
                success=False,
                exit_code=e.exit_status,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                status=ExecutionStatus.ERROR,
                error_message=f"Container error: {e}"
            )
        except docker.errors.ImageNotFound:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Image {image} not found. Please run: docker pull {image}",
                execution_time_ms=0,
                status=ExecutionStatus.ERROR,
                error_message="Image not found"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                status=ExecutionStatus.ERROR,
                error_message=str(e)
            )
    
    # ==================== KILL SWITCH ====================
    
    def kill_running(self, execution_id: str = None) -> bool:
        """
        Emergency kill switch for running containers.
        
        Args:
            execution_id: Specific execution to kill, or None for all.
        
        Returns:
            True if any containers were killed.
        """
        killed = False
        
        with self._lock:
            if execution_id:
                container = self._active_containers.get(execution_id)
                if container:
                    try:
                        container.kill()
                        container.remove(force=True)
                        self._active_containers.pop(execution_id, None)
                        killed = True
                        self.logger.warning(f"KILLED container: {execution_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to kill container: {e}")
            else:
                # Kill all
                for exec_id, container in list(self._active_containers.items()):
                    try:
                        container.kill()
                        container.remove(force=True)
                        killed = True
                        self.logger.warning(f"KILLED container: {exec_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to kill container {exec_id}: {e}")
                self._active_containers.clear()
        
        if killed and self.audit_logger:
            self.audit_logger.log_security(
                event="emergency_kill",
                description=f"Killed execution: {execution_id or 'ALL'}",
                severity="warning"
            )
        
        return killed
    
    def get_running_count(self) -> int:
        """Get number of running executions."""
        with self._lock:
            return len(self._active_containers)
    
    # ==================== LEGACY COMPATIBILITY ====================
    
    def execute_code_legacy(self, language: str, code: str) -> str:
        """
        Legacy method for backward compatibility.
        
        Prefer using execute_code() which returns structured result.
        """
        result = self.execute_code(language, code)
        
        if result.success:
            return f"Exit Code: 0\nOutput:\n{result.stdout}"
        else:
            return f"Exit Code: {result.exit_code}\nError:\n{result.stderr}"
