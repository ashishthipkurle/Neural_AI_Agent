"""
Unit Tests for Security Module.

Tests:
- Audit logging
- Face embedding encryption
- PIN fallback
- Lock controller
"""
import pytest
import os
import tempfile
from datetime import datetime

from agent.security.audit_log import AuditLogger
from agent.security.face.pin_fallback import PINFallback
from agent.security.face.embedding_store import EmbeddingStore


class TestAuditLogger:
    """Tests for AuditLogger class."""
    
    def test_log_entry(self, tmp_path):
        """Test logging an entry."""
        logger = AuditLogger(log_dir=str(tmp_path / "audit"))
        
        entry_id = logger.log(
            event_type="test",
            action="test_action",
            description="Test description"
        )
        
        assert entry_id is not None
        assert entry_id.startswith("audit_")
    
    def test_sanitize_sensitive_params(self, tmp_path):
        """Test sensitive parameter redaction."""
        logger = AuditLogger(log_dir=str(tmp_path / "audit"))
        
        sanitized = logger._sanitize_params({
            "password": "secret123",
            "username": "testuser"
        })
        
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["username"] == "testuser"
    
    def test_get_entries(self, tmp_path):
        """Test retrieving entries."""
        logger = AuditLogger(log_dir=str(tmp_path / "audit"))
        
        logger.log(event_type="test", action="action1")
        logger.log(event_type="test", action="action2")
        
        entries = logger.get_entries(limit=10)
        assert len(entries) >= 2


class TestPINFallback:
    """Tests for PINFallback class."""
    
    def test_set_and_verify_pin(self, tmp_path):
        """Test setting and verifying PIN."""
        pin = PINFallback(pin_file=str(tmp_path / "test.pin"))
        
        assert pin.set_pin("1234")
        assert pin.verify("1234")
        assert not pin.verify("4321")
    
    def test_invalid_pin_format(self, tmp_path):
        """Test rejection of invalid PIN format."""
        pin = PINFallback(pin_file=str(tmp_path / "test.pin"))
        
        assert not pin.set_pin("abc")  # Not digits
        assert not pin.set_pin("12")   # Too short
        assert not pin.set_pin("123456789")  # Too long
    
    def test_failed_attempts_lockout(self, tmp_path):
        """Test lockout after max failed attempts."""
        pin = PINFallback(pin_file=str(tmp_path / "test.pin"))
        pin.set_pin("1234")
        
        # Max attempts is 5
        for i in range(5):
            pin.verify("0000")  # Wrong PIN
        
        # Should be locked out now
        assert not pin.verify("1234")  # Even correct PIN fails


class TestEmbeddingStore:
    """Tests for EmbeddingStore class."""
    
    def test_store_initialization(self, tmp_path):
        """Test embedding store initialization."""
        store = EmbeddingStore(
            store_path=str(tmp_path / "face_embeddings.enc")
        )
        
        assert store is not None
    
    def test_face_exists_check(self, tmp_path):
        """Test checking if face exists."""
        store = EmbeddingStore(
            store_path=str(tmp_path / "face_embeddings.enc")
        )
        
        assert not store.face_exists("nonexistent_user")
    
    def test_list_faces_empty(self, tmp_path):
        """Test listing faces when empty."""
        store = EmbeddingStore(
            store_path=str(tmp_path / "face_embeddings.enc")
        )
        
        faces = store.list_faces()
        assert len(faces) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
