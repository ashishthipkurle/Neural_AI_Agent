"""
Sandbox Preview Widget - Code execution preview and approval UI.

This widget provides a visual preview of code before execution,
showing risk assessment and requiring explicit user approval.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QFrame, QScrollArea,
    QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor

import logging
from typing import Optional

# Import will be available when module is used
try:
    from agent.tools.code_executor import CodeAnalysis, RiskLevel
except ImportError:
    CodeAnalysis = None
    RiskLevel = None


class PythonHighlighter(QSyntaxHighlighter):
    """Simple Python syntax highlighter."""
    
    KEYWORDS = [
        'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
        'global', 'if', 'import', 'in', 'is', 'lambda', 'not', 'or',
        'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
        'True', 'False', 'None'
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._formats = {}
        
        # Keyword format
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#ff79c6"))
        keyword_fmt.setFontWeight(QFont.Weight.Bold)
        self._formats['keyword'] = keyword_fmt
        
        # String format
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#f1fa8c"))
        self._formats['string'] = string_fmt
        
        # Comment format
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6272a4"))
        self._formats['comment'] = comment_fmt
        
        # Function format
        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#50fa7b"))
        self._formats['function'] = func_fmt
    
    def highlightBlock(self, text: str):
        # Keywords
        import re
        for keyword in self.KEYWORDS:
            pattern = rf'\b{keyword}\b'
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), 
                             self._formats['keyword'])
        
        # Strings
        for pattern in [r'"[^"]*"', r"'[^']*'"]:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(),
                             self._formats['string'])
        
        # Comments
        if '#' in text:
            idx = text.index('#')
            self.setFormat(idx, len(text) - idx, self._formats['comment'])


class SandboxPreviewDialog(QDialog):
    """
    Code execution preview dialog.
    
    Shows code preview with risk assessment and requires
    explicit approval before execution.
    """
    
    # Signals
    approved = pyqtSignal()
    denied = pyqtSignal()
    dry_run_requested = pyqtSignal()
    
    # Risk level colors
    RISK_COLORS = {
        "low": "#50fa7b",      # Green
        "medium": "#f1fa8c",   # Yellow
        "high": "#ffb86c",     # Orange
        "critical": "#ff5555"  # Red
    }
    
    def __init__(
        self, 
        code: str, 
        language: str,
        analysis: Optional['CodeAnalysis'] = None,
        parent=None
    ):
        super().__init__(parent)
        self.code = code
        self.language = language
        self.analysis = analysis
        self.result = None
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("⚠️ Code Execution Preview")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("CODE EXECUTION PREVIEW")
        header.setObjectName("PreviewHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Risk badge
        risk_frame = QFrame()
        risk_frame.setObjectName("RiskBadge")
        risk_layout = QHBoxLayout(risk_frame)
        risk_layout.setContentsMargins(12, 8, 12, 8)
        
        risk_level = "unknown"
        if self.analysis and hasattr(self.analysis, 'risk_level'):
            risk_level = self.analysis.risk_level.value
        
        self.risk_label = QLabel(f"RISK: {risk_level.upper()}")
        self.risk_label.setObjectName("RiskLabel")
        risk_color = self.RISK_COLORS.get(risk_level, "#888888")
        self.risk_label.setStyleSheet(f"color: {risk_color}; font-weight: bold;")
        risk_layout.addWidget(self.risk_label)
        
        layout.addWidget(risk_frame)
        
        # Code display
        code_label = QLabel(f"Language: {self.language.upper()}")
        code_label.setObjectName("CodeLabel")
        layout.addWidget(code_label)
        
        self.code_display = QTextEdit()
        self.code_display.setObjectName("CodeDisplay")
        self.code_display.setReadOnly(True)
        self.code_display.setPlainText(self.code)
        self.code_display.setFont(QFont("Consolas", 11))
        
        # Apply syntax highlighting
        if self.language.lower() in ["python", "python3"]:
            self.highlighter = PythonHighlighter(self.code_display.document())
        
        layout.addWidget(self.code_display)
        
        # Analysis details
        if self.analysis:
            self._add_analysis_section(layout)
        
        # Warning for high risk
        if self.analysis and hasattr(self.analysis, 'risk_level'):
            if self.analysis.risk_level.value in ["high", "critical"]:
                warning = QLabel("⚠️ This code contains potentially dangerous operations!")
                warning.setObjectName("WarningLabel")
                warning.setStyleSheet("color: #ff5555; font-weight: bold;")
                warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.deny_btn = QPushButton("✖ Deny")
        self.deny_btn.setObjectName("DenyButton")
        self.deny_btn.clicked.connect(self._on_deny)
        button_layout.addWidget(self.deny_btn)
        
        self.dry_run_btn = QPushButton("🔍 Dry Run")
        self.dry_run_btn.setObjectName("DryRunButton")
        self.dry_run_btn.clicked.connect(self._on_dry_run)
        button_layout.addWidget(self.dry_run_btn)
        
        self.approve_btn = QPushButton("✓ Approve & Execute")
        self.approve_btn.setObjectName("ApproveButton")
        self.approve_btn.clicked.connect(self._on_approve)
        button_layout.addWidget(self.approve_btn)
        
        layout.addLayout(button_layout)
    
    def _add_analysis_section(self, layout: QVBoxLayout):
        """Add code analysis details."""
        if not self.analysis:
            return
        
        details_frame = QFrame()
        details_frame.setObjectName("AnalysisFrame")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setSpacing(8)
        
        # Imports
        if hasattr(self.analysis, 'imports') and self.analysis.imports:
            imports_label = QLabel(f"📦 Imports: {', '.join(self.analysis.imports[:5])}")
            imports_label.setObjectName("AnalysisLabel")
            details_layout.addWidget(imports_label)
        
        # Risk reasons
        if hasattr(self.analysis, 'risk_reasons') and self.analysis.risk_reasons:
            reasons_label = QLabel("⚠️ Risk Factors:")
            reasons_label.setObjectName("AnalysisLabel")
            reasons_label.setStyleSheet("color: #ffb86c;")
            details_layout.addWidget(reasons_label)
            
            for reason in self.analysis.risk_reasons[:5]:
                reason_item = QLabel(f"  • {reason}")
                reason_item.setObjectName("RiskReason")
                details_layout.addWidget(reason_item)
        
        layout.addWidget(details_frame)
    
    def _apply_styles(self):
        """Apply dark theme styles."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #f8f8f2;
            }
            #PreviewHeader {
                font-size: 18px;
                font-weight: bold;
                color: #00f3ff;
                padding: 10px;
            }
            #RiskBadge {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #CodeDisplay {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 12px;
            }
            #AnalysisFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 8px;
                padding: 12px;
            }
            #AnalysisLabel {
                color: #bd93f9;
            }
            #RiskReason {
                color: #f8f8f2;
                padding-left: 20px;
            }
            QPushButton {
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            #DenyButton {
                background-color: #ff5555;
                color: white;
                border: none;
            }
            #DenyButton:hover {
                background-color: #ff6e6e;
            }
            #DryRunButton {
                background-color: #6272a4;
                color: white;
                border: none;
            }
            #DryRunButton:hover {
                background-color: #7283b5;
            }
            #ApproveButton {
                background-color: #50fa7b;
                color: #1a1a2e;
                border: none;
            }
            #ApproveButton:hover {
                background-color: #69fb8f;
            }
        """)
    
    def _on_approve(self):
        """Handle approval."""
        self.result = "approved"
        self.approved.emit()
        self.accept()
    
    def _on_deny(self):
        """Handle denial."""
        self.result = "denied"
        self.denied.emit()
        self.reject()
    
    def _on_dry_run(self):
        """Handle dry run request."""
        self.result = "dry_run"
        self.dry_run_requested.emit()
        # Don't close dialog yet


class SandboxPreviewWidget(QFrame):
    """
    Inline sandbox preview widget for embedding in main UI.
    
    Compact version of the preview dialog for inline display.
    """
    
    approved = pyqtSignal(str, str)  # language, code
    denied = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SandboxPreviewWidget")
        self.code = ""
        self.language = ""
        self.analysis = None
        
        self._setup_ui()
        self._apply_styles()
        self.hide()  # Hidden by default
    
    def _setup_ui(self):
        """Setup inline widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header_layout = QHBoxLayout()
        self.header_label = QLabel("⚡ Code Execution Request")
        self.header_label.setObjectName("PreviewHeader")
        header_layout.addWidget(self.header_label)
        
        self.risk_badge = QLabel("RISK: ?")
        self.risk_badge.setObjectName("RiskBadge")
        header_layout.addWidget(self.risk_badge)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Code preview (compact)
        self.code_preview = QLabel()
        self.code_preview.setObjectName("CodePreviewLabel")
        self.code_preview.setWordWrap(True)
        layout.addWidget(self.code_preview)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.deny_btn = QPushButton("✖ Deny")
        self.deny_btn.setObjectName("DenyBtn")
        self.deny_btn.clicked.connect(self._on_deny)
        btn_layout.addWidget(self.deny_btn)
        
        self.approve_btn = QPushButton("✓ Approve")
        self.approve_btn.setObjectName("ApproveBtn")
        self.approve_btn.clicked.connect(self._on_approve)
        btn_layout.addWidget(self.approve_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        """Apply compact styles."""
        self.setStyleSheet("""
            #SandboxPreviewWidget {
                background-color: rgba(40, 42, 54, 0.95);
                border: 2px solid #ff79c6;
                border-radius: 12px;
            }
            #PreviewHeader {
                color: #ff79c6;
                font-weight: bold;
                font-size: 14px;
            }
            #RiskBadge {
                background-color: rgba(255, 121, 198, 0.2);
                color: #ff79c6;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            #CodePreviewLabel {
                color: #f8f8f2;
                background-color: rgba(0, 0, 0, 0.2);
                padding: 8px;
                border-radius: 6px;
                font-family: Consolas;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            #DenyBtn {
                background-color: #ff5555;
                color: white;
                border: none;
            }
            #ApproveBtn {
                background-color: #50fa7b;
                color: #1a1a2e;
                border: none;
            }
        """)
    
    def show_preview(self, code: str, language: str, analysis=None):
        """Show preview for code."""
        self.code = code
        self.language = language
        self.analysis = analysis
        
        # Update UI
        preview_text = code[:200] + "..." if len(code) > 200 else code
        self.code_preview.setText(preview_text)
        
        if analysis and hasattr(analysis, 'risk_level'):
            risk = analysis.risk_level.value.upper()
            colors = {
                "LOW": "#50fa7b",
                "MEDIUM": "#f1fa8c", 
                "HIGH": "#ffb86c",
                "CRITICAL": "#ff5555"
            }
            color = colors.get(risk, "#888888")
            self.risk_badge.setText(f"RISK: {risk}")
            self.risk_badge.setStyleSheet(
                f"background-color: {color}33; color: {color}; "
                "padding: 4px 8px; border-radius: 4px; font-size: 12px;"
            )
        
        self.show()
    
    def _on_approve(self):
        """Handle approval."""
        self.approved.emit(self.language, self.code)
        self.hide()
    
    def _on_deny(self):
        """Handle denial."""
        self.denied.emit()
        self.hide()
