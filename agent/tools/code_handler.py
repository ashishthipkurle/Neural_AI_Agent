"""
Code Execution Handler - Integrates sandbox preview with code execution.

This module provides the bridge between the GUI sandbox preview dialog
and the code executor, ensuring all code executions are previewed
and approved before running.
"""
import logging
from typing import Optional, Callable, Any
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal


class CodeExecutionHandler(QObject):
    """
    Handler for code execution with GUI integration.
    
    Shows preview dialog → gets approval → executes code → returns result.
    
    Signals:
        execution_started: Emitted when execution begins
        execution_completed: Emitted with result when done
        execution_cancelled: Emitted if user cancels
    """
    
    execution_started = pyqtSignal(str, str)  # language, code_preview
    execution_completed = pyqtSignal(bool, str)  # success, output
    execution_cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("CodeExecutionHandler")
        
        # Lazy import to avoid circular dependencies
        self._executor = None
        self._preview_dialog_class = None
    
    def _get_executor(self):
        """Get or create code executor (lazy init)."""
        if self._executor is None:
            try:
                from agent.tools.code_executor import CodeExecutor
                self._executor = CodeExecutor()
            except ImportError as e:
                self.logger.error(f"Failed to import CodeExecutor: {e}")
                return None
        return self._executor
    
    def _get_preview_dialog_class(self):
        """Get preview dialog class (lazy init)."""
        if self._preview_dialog_class is None:
            try:
                from agent.tools.sandbox_preview import SandboxPreviewDialog
                self._preview_dialog_class = SandboxPreviewDialog
            except ImportError as e:
                self.logger.error(f"Failed to import SandboxPreviewDialog: {e}")
                return None
        return self._preview_dialog_class
    
    def execute_with_preview(
        self, 
        language: str, 
        code: str,
        parent_widget=None
    ) -> Optional[str]:
        """
        Execute code with preview dialog.
        
        Shows preview → waits for approval → executes if approved.
        
        Args:
            language: Programming language.
            code: Code to execute.
            parent_widget: Parent widget for dialog.
        
        Returns:
            Execution output string or None if cancelled.
        """
        executor = self._get_executor()
        if not executor:
            return "Error: Code executor not available"
            
        if not executor.is_available():
            return "Error: Code execution disabled (Docker is not available). Refusing to run unsandboxed code."

        
        # Generate preview analysis
        analysis = executor.preview_code(language, code)
        
        # Try to show GUI dialog
        dialog_class = self._get_preview_dialog_class()
        if dialog_class and QApplication.instance():
            dialog = dialog_class(code, language, analysis, parent_widget)
            
            # Connect dry run handler
            def on_dry_run():
                is_valid, msg = executor.dry_run(language, code)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(dialog, "Dry Run Result", msg)
            
            dialog.dry_run_requested.connect(on_dry_run)
            
            # Show dialog and wait for response
            result = dialog.exec()
            
            if dialog.result == "approved":
                self.execution_started.emit(language, code[:50])
                
                # Execute code (skip internal approval since we already have it)
                exec_result = executor.execute_code(
                    language, code, require_approval=False
                )
                
                if exec_result.success:
                    output = exec_result.stdout
                else:
                    output = f"Error: {exec_result.stderr}"
                
                self.execution_completed.emit(exec_result.success, output)
                return output
            else:
                self.execution_cancelled.emit()
                return None
        else:
            # Fallback: CLI mode - use text preview
            preview = executor.format_preview(analysis, code)
            self.logger.info(f"Preview (no GUI):\n{preview}")
            
            # In CLI mode, use the executor's built-in approval
            exec_result = executor.execute_code(language, code)
            return f"Exit: {exec_result.exit_code}\n{exec_result.stdout or exec_result.stderr}"
    
    def dry_run(self, language: str, code: str) -> str:
        """
        Dry run code without preview dialog.
        
        Args:
            language: Programming language.
            code: Code to validate.
        
        Returns:
            Validation result message.
        """
        executor = self._get_executor()
        if not executor:
            return "Error: Code executor not available"
            
        if not executor.is_available():
            return "Error: Code execution disabled (Docker is not available). Refusing to run unsandboxed code."
        
        is_valid, message = executor.dry_run(language, code)
        return message
    
    def kill_all(self) -> bool:
        """Emergency kill all running code executions."""
        executor = self._get_executor()
        if executor:
            return executor.kill_running()
        return False


# Global instance for easy access
_handler_instance = None

def get_code_execution_handler() -> CodeExecutionHandler:
    """Get or create the global code execution handler."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = CodeExecutionHandler()
    return _handler_instance
