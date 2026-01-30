"""
Memory Editor - User-controlled memory management.

This module provides UI components and management for:
- Browsing stored memories
- Editing memory text and tags
- Deleting memories
- Explaining why memories exist
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QDialog, QDialogButtonBox, QFrame, QMessageBox,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime


class MemoryItemWidget(QFrame):
    """Widget for displaying a single memory item."""
    
    edit_requested = pyqtSignal(str)  # memory_id
    delete_requested = pyqtSignal(str)  # memory_id
    explain_requested = pyqtSignal(str)  # memory_id
    
    def __init__(self, memory: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.memory = memory
        self.memory_id = memory.get("id", "unknown")
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Setup the item UI."""
        self.setObjectName("MemoryItem")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header with type and timestamp
        header = QHBoxLayout()
        
        type_label = QLabel(self.memory.get("type", "episodic").upper())
        type_label.setObjectName("MemoryType")
        header.addWidget(type_label)
        
        timestamp = self.memory.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = timestamp[:16]
            time_label = QLabel(time_str)
            time_label.setObjectName("MemoryTime")
            header.addWidget(time_label)
        
        header.addStretch()
        
        if self.memory.get("edited"):
            edited_badge = QLabel("✏️ Edited")
            edited_badge.setObjectName("EditedBadge")
            header.addWidget(edited_badge)
        
        layout.addLayout(header)
        
        # Memory text
        text = self.memory.get("text", "")[:200]
        if len(self.memory.get("text", "")) > 200:
            text += "..."
        
        self.text_label = QLabel(text)
        self.text_label.setObjectName("MemoryText")
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        
        # Tags
        tags = self.memory.get("tags", [])
        if tags:
            tags_label = QLabel("🏷️ " + ", ".join(tags[:5]))
            tags_label.setObjectName("MemoryTags")
            layout.addWidget(tags_label)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        explain_btn = QPushButton("❓ Why?")
        explain_btn.setObjectName("ExplainBtn")
        explain_btn.clicked.connect(lambda: self.explain_requested.emit(self.memory_id))
        btn_layout.addWidget(explain_btn)
        
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.setObjectName("EditBtn")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.memory_id))
        btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.setObjectName("DeleteBtn")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.memory_id))
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        """Apply styles."""
        self.setStyleSheet("""
            #MemoryItem {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            #MemoryItem:hover {
                background-color: rgba(0, 243, 255, 0.05);
                border-color: rgba(0, 243, 255, 0.3);
            }
            #MemoryType {
                color: #bd93f9;
                font-size: 11px;
                font-weight: bold;
            }
            #MemoryTime {
                color: #6272a4;
                font-size: 11px;
            }
            #MemoryText {
                color: #f8f8f2;
                font-size: 13px;
            }
            #MemoryTags {
                color: #8be9fd;
                font-size: 11px;
            }
            #EditedBadge {
                color: #ffb86c;
                font-size: 11px;
            }
            QPushButton {
                background-color: transparent;
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #f8f8f2;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            #DeleteBtn:hover {
                background-color: rgba(255, 85, 85, 0.2);
                border-color: #ff5555;
            }
        """)


class MemoryEditDialog(QDialog):
    """Dialog for editing a memory."""
    
    def __init__(self, memory: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.memory = memory
        self.result_data = None
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("Edit Memory")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("EDIT MEMORY")
        header.setObjectName("DialogHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Memory ID
        id_label = QLabel(f"ID: {self.memory.get('id', 'unknown')}")
        id_label.setObjectName("IdLabel")
        layout.addWidget(id_label)
        
        # Text editor
        text_label = QLabel("Memory Text:")
        text_label.setObjectName("FieldLabel")
        layout.addWidget(text_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("TextEditor")
        self.text_edit.setPlainText(self.memory.get("text", ""))
        layout.addWidget(self.text_edit)
        
        # Tags editor
        tags_label = QLabel("Tags (comma-separated):")
        tags_label.setObjectName("FieldLabel")
        layout.addWidget(tags_label)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setObjectName("TagsEditor")
        current_tags = self.memory.get("tags", [])
        self.tags_edit.setText(", ".join(current_tags))
        layout.addWidget(self.tags_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("SaveBtn")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _apply_styles(self):
        """Apply dialog styles."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #f8f8f2;
            }
            #DialogHeader {
                font-size: 16px;
                font-weight: bold;
                color: #00f3ff;
            }
            #IdLabel {
                color: #6272a4;
                font-size: 11px;
            }
            #FieldLabel {
                color: #bd93f9;
                font-size: 12px;
            }
            #TextEditor {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 6px;
                padding: 8px;
            }
            #TagsEditor {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            #SaveBtn {
                background-color: #50fa7b;
                color: #1a1a2e;
                border: none;
            }
        """)
    
    def _on_save(self):
        """Handle save button."""
        self.result_data = {
            "text": self.text_edit.toPlainText(),
            "tags": [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        }
        self.accept()


class MemoryEditorWidget(QWidget):
    """
    Main memory editor widget.
    
    Provides UI for browsing, editing, and deleting memories.
    """
    
    memory_updated = pyqtSignal()
    
    def __init__(self, memory_store=None, memory_explainer=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("MemoryEditor")
        self.memory_store = memory_store
        self.memory_explainer = memory_explainer
        self._memories = []
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Setup the widget UI."""
        self.setObjectName("MemoryEditor")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("📚 Memory Store")
        title.setObjectName("EditorTitle")
        header_layout.addWidget(title)
        
        self.count_label = QLabel("0 memories")
        self.count_label.setObjectName("CountLabel")
        header_layout.addWidget(self.count_label)
        
        header_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Search bar
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Search memories...")
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("🔍")
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)
        
        layout.addLayout(search_layout)
        
        # Memory list (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("MemoryScroll")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)
        
        # Footer with actions
        footer = QHBoxLayout()
        
        export_btn = QPushButton("📤 Export")
        export_btn.clicked.connect(self._on_export)
        footer.addWidget(export_btn)
        
        import_btn = QPushButton("📥 Import")
        import_btn.clicked.connect(self._on_import)
        footer.addWidget(import_btn)
        
        footer.addStretch()
        
        clear_btn = QPushButton("⚠️ Clear All")
        clear_btn.setObjectName("ClearBtn")
        clear_btn.clicked.connect(self._on_clear_all)
        footer.addWidget(clear_btn)
        
        layout.addLayout(footer)
    
    def _apply_styles(self):
        """Apply widget styles."""
        self.setStyleSheet("""
            #MemoryEditor {
                background-color: transparent;
            }
            #EditorTitle {
                font-size: 14px;
                font-weight: bold;
                color: #00f3ff;
            }
            #CountLabel {
                color: #6272a4;
                font-size: 12px;
            }
            #SearchInput {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 6px;
                padding: 8px;
            }
            #MemoryScroll {
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #f8f8f2;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(0, 243, 255, 0.1);
            }
            #ClearBtn {
                border-color: #ff5555;
                color: #ff5555;
            }
            #ClearBtn:hover {
                background-color: rgba(255, 85, 85, 0.2);
            }
        """)
    
    def set_memory_store(self, store):
        """Set the memory store reference."""
        self.memory_store = store
        self.refresh()
    
    def refresh(self):
        """Refresh the memory list."""
        if not self.memory_store:
            return
        
        # Clear existing items
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Load memories
        self._memories = self.memory_store.list_all(limit=50)
        self.count_label.setText(f"{self.memory_store.get_count()} memories")
        
        # Add memory widgets
        for mem in self._memories:
            item = MemoryItemWidget(mem)
            item.edit_requested.connect(self._on_edit)
            item.delete_requested.connect(self._on_delete)
            item.explain_requested.connect(self._on_explain)
            self.list_layout.addWidget(item)
        
        if not self._memories:
            empty_label = QLabel("No memories stored yet.")
            empty_label.setStyleSheet("color: #6272a4; padding: 20px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_label)
    
    def _on_search(self):
        """Handle search."""
        if not self.memory_store:
            return
        
        query = self.search_input.text().strip()
        if not query:
            self.refresh()
            return
        
        results = self.memory_store.search(query, k=20)
        
        # Clear and show results
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for mem in results:
            item = MemoryItemWidget(mem)
            item.edit_requested.connect(self._on_edit)
            item.delete_requested.connect(self._on_delete)
            item.explain_requested.connect(self._on_explain)
            self.list_layout.addWidget(item)
        
        self.count_label.setText(f"{len(results)} results")
    
    def _on_edit(self, memory_id: str):
        """Handle edit request."""
        memory = self.memory_store.get_by_id(memory_id)
        if not memory:
            return
        
        dialog = MemoryEditDialog(memory, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            self.memory_store.update_memory(
                memory_id,
                dialog.result_data["text"],
                dialog.result_data["tags"]
            )
            self.refresh()
            self.memory_updated.emit()
    
    def _on_delete(self, memory_id: str):
        """Handle delete request."""
        reply = QMessageBox.question(
            self,
            "Delete Memory",
            "Are you sure you want to delete this memory?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.memory_store.delete_memory(memory_id)
            self.refresh()
            self.memory_updated.emit()
    
    def _on_explain(self, memory_id: str):
        """Handle explain request."""
        memory = self.memory_store.get_by_id(memory_id)
        if not memory:
            return
        
        explanation = "This memory was stored because:\n\n"
        
        if self.memory_explainer:
            explanation = self.memory_explainer.explain_storage(
                memory.get("text", ""),
                memory.get("type", "episodic"),
                memory.get("tags", [])
            )
        else:
            # Default explanation
            mem_type = memory.get("type", "episodic")
            if mem_type == "user_request":
                explanation += "You explicitly asked me to remember this."
            elif mem_type == "preference":
                explanation += "This appears to be a preference you shared."
            else:
                explanation += "This was recorded during our conversation for future context."
        
        QMessageBox.information(
            self,
            "Memory Explanation",
            explanation,
            QMessageBox.StandardButton.Ok
        )
    
    def _on_export(self):
        """Handle export."""
        if not self.memory_store:
            return
        
        memories = self.memory_store.export_memories()
        # In a full implementation, show file save dialog
        QMessageBox.information(
            self,
            "Export",
            f"Would export {len(memories)} memories.\n(File dialog not implemented in this preview)",
            QMessageBox.StandardButton.Ok
        )
    
    def _on_import(self):
        """Handle import."""
        QMessageBox.information(
            self,
            "Import",
            "Import from file not implemented in this preview.\nUse memory_store.import_memories() directly.",
            QMessageBox.StandardButton.Ok
        )
    
    def _on_clear_all(self):
        """Handle clear all."""
        reply = QMessageBox.warning(
            self,
            "Clear All Memories",
            "⚠️ This will DELETE ALL memories!\n\nThis action CANNOT be undone.\n\nAre you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Double confirm
            reply2 = QMessageBox.critical(
                self,
                "Final Confirmation",
                "This is your LAST chance to cancel.\n\nClick Yes to permanently delete ALL memories.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply2 == QMessageBox.StandardButton.Yes:
                self.memory_store.clear_all(confirm=True)
                self.refresh()
                self.memory_updated.emit()
