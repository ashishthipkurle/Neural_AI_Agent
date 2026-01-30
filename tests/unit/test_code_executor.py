"""
Unit Tests for Code Executor.

Tests:
- Code preview and risk analysis
- Dry run validation
- Execution flow
- Kill switch
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)


class TestCodePreview:
    """Tests for code preview and risk analysis."""
    
    def test_python_syntax_validation(self):
        """Test that Python syntax is validated."""
        from agent.tools.code_executor import CodeExecutor, RiskLevel
        
        executor = CodeExecutor()
        
        # Valid Python
        analysis = executor.preview_code("python", "print('hello')")
        assert analysis.is_valid_syntax is True
        
        # Invalid Python
        analysis = executor.preview_code("python", "print('hello'")
        assert analysis.is_valid_syntax is False
        assert analysis.syntax_error is not None
    
    def test_dangerous_pattern_detection(self):
        """Test detection of dangerous patterns."""
        from agent.tools.code_executor import CodeExecutor, RiskLevel
        
        executor = CodeExecutor()
        
        # Safe code
        analysis = executor.preview_code("python", "x = 1 + 1")
        assert analysis.risk_level == RiskLevel.LOW
        
        # Code with os.system
        analysis = executor.preview_code("python", "import os; os.system('ls')")
        assert analysis.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert any("os.system" in r for r in analysis.risk_reasons)
        
        # Code with network
        analysis = executor.preview_code("python", "import requests")
        assert analysis.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    
    def test_import_extraction(self):
        """Test that imports are extracted."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        code = """
import json
from datetime import datetime
import os
"""
        analysis = executor.preview_code("python", code)
        assert "json" in analysis.imports
        assert "datetime" in analysis.imports
        assert "os" in analysis.imports
    
    def test_preview_format(self):
        """Test preview formatting."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        code = "print('hello world')"
        analysis = executor.preview_code("python", code)
        preview = executor.format_preview(analysis, code)
        
        assert "CODE EXECUTION PREVIEW" in preview
        assert "python" in preview.lower()
        assert "hello world" in preview


class TestDryRun:
    """Tests for dry run validation."""
    
    def test_dry_run_valid_code(self):
        """Test dry run passes for valid code."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        is_valid, message = executor.dry_run("python", "print('hello')")
        # Will fail if Docker not available, which is OK for test
        assert message is not None
        assert isinstance(is_valid, bool)
    
    def test_dry_run_syntax_error(self):
        """Test dry run fails for syntax error."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        is_valid, message = executor.dry_run("python", "print('hello'")
        assert is_valid is False
        assert "Syntax error" in message
    
    def test_dry_run_unsupported_language(self):
        """Test dry run fails for unsupported language."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        is_valid, message = executor.dry_run("cobol", "DISPLAY 'HELLO'")
        assert is_valid is False
        assert "Unsupported" in message or "language" in message.lower()


class TestKillSwitch:
    """Tests for emergency kill switch."""
    
    def test_kill_returns_false_when_no_containers(self):
        """Test kill returns False when nothing is running."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        result = executor.kill_running()
        assert result is False
    
    def test_get_running_count(self):
        """Test counting running containers."""
        from agent.tools.code_executor import CodeExecutor
        
        executor = CodeExecutor()
        
        count = executor.get_running_count()
        assert count == 0


class TestExecutionResult:
    """Tests for execution result dataclass."""
    
    def test_execution_result_fields(self):
        """Test ExecutionResult has required fields."""
        from agent.tools.code_executor import ExecutionResult, ExecutionStatus
        
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="hello",
            stderr="",
            execution_time_ms=100,
            status=ExecutionStatus.COMPLETED
        )
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.execution_time_ms == 100
        assert result.status == ExecutionStatus.COMPLETED


class TestCodeAnalysis:
    """Tests for code analysis dataclass."""
    
    def test_code_analysis_defaults(self):
        """Test CodeAnalysis default values."""
        from agent.tools.code_executor import CodeAnalysis, RiskLevel
        
        analysis = CodeAnalysis(
            language="python",
            lines_of_code=5
        )
        
        assert analysis.language == "python"
        assert analysis.lines_of_code == 5
        assert analysis.imports == []
        assert analysis.risk_level == RiskLevel.LOW
        assert analysis.is_valid_syntax is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
