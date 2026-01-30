"""
Embedding Store - Encrypted local face embeddings.

This module handles secure storage of face embeddings using
AES-256-GCM encryption.

PROFESSIONAL ASSUMPTION: Using AES-256-GCM for encryption.
"""
import logging
import os
import json
import base64
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import numpy as np
except ImportError:
    np = None


@dataclass
class StoredFace:
    """Stored face record."""
    name: str
    embedding_id: str
    created_at: str
    last_used: Optional[str] = None


class EmbeddingStore:
    """
    Encrypted storage for face embeddings.
    
    Security features:
    - AES-256-GCM encryption
    - Per-embedding unique nonce
    - No raw biometric storage
    - Key derived from system secret
    
    NO raw biometric data is ever stored unencrypted.
    """
    
    def __init__(
        self,
        store_path: str = "agent/db/face_embeddings.enc",
        key_seed: str = "neural_face_key"
    ):
        """
        Initialize the embedding store.
        
        Args:
            store_path: Path to encrypted store file.
            key_seed: Seed for key derivation.
        """
        self.logger = logging.getLogger("EmbeddingStore")
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._embeddings: Dict[str, bytes] = {}  # id -> encrypted embedding
        self._metadata: Dict[str, StoredFace] = {}  # id -> metadata
        self._key: Optional[bytes] = None
        
        if not CRYPTO_AVAILABLE:
            self.logger.error("cryptography package not available. Encryption disabled.")
        else:
            self._derive_key(key_seed)
            self._load_store()
        
        self.logger.info("EmbeddingStore initialized.")
    
    def _derive_key(self, seed: str) -> None:
        """Derive encryption key from seed."""
        # In production, this should use a hardware-backed key or user secret
        salt = b"neural_salt_v1"  # Fixed salt for deterministic key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=100000,
        )
        self._key = kdf.derive(seed.encode())
        self.logger.debug("Encryption key derived.")
    
    def _encrypt(self, data: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt data with AES-256-GCM.
        
        Returns:
            Tuple of (nonce, ciphertext).
        """
        if not self._key:
            raise RuntimeError("Encryption key not available")
        
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce, ciphertext
    
    def _decrypt(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """Decrypt data with AES-256-GCM."""
        if not self._key:
            raise RuntimeError("Encryption key not available")
        
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def _load_store(self) -> None:
        """Load encrypted store from disk."""
        if not self.store_path.exists():
            self.logger.debug("No existing store found.")
            return
        
        try:
            with open(self.store_path, 'r') as f:
                data = json.load(f)
            
            for record in data.get('embeddings', []):
                emb_id = record['id']
                self._embeddings[emb_id] = base64.b64decode(record['data'])
                self._metadata[emb_id] = StoredFace(
                    name=record['name'],
                    embedding_id=emb_id,
                    created_at=record['created_at'],
                    last_used=record.get('last_used')
                )
            
            self.logger.info(f"Loaded {len(self._embeddings)} face embeddings.")
            
        except Exception as e:
            self.logger.error(f"Failed to load embedding store: {e}")
    
    def _save_store(self) -> None:
        """Save encrypted store to disk."""
        try:
            records = []
            for emb_id, enc_data in self._embeddings.items():
                meta = self._metadata.get(emb_id)
                if meta:
                    records.append({
                        'id': emb_id,
                        'name': meta.name,
                        'data': base64.b64encode(enc_data).decode(),
                        'created_at': meta.created_at,
                        'last_used': meta.last_used
                    })
            
            with open(self.store_path, 'w') as f:
                json.dump({'embeddings': records}, f, indent=2)
            
            self.logger.debug("Embedding store saved.")
            
        except Exception as e:
            self.logger.error(f"Failed to save embedding store: {e}")
    
    def store_embedding(
        self,
        name: str,
        embedding: np.ndarray
    ) -> Optional[str]:
        """
        Store an encrypted face embedding.
        
        Args:
            name: Name to associate with face.
            embedding: Face embedding vector.
        
        Returns:
            Embedding ID or None if failed.
        """
        if not CRYPTO_AVAILABLE or np is None:
            self.logger.error("Cannot store embedding: missing dependencies")
            return None
        
        try:
            # Generate unique ID
            from datetime import datetime
            emb_id = hashlib.sha256(
                f"{name}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Serialize and encrypt embedding
            emb_bytes = embedding.tobytes()
            nonce, ciphertext = self._encrypt(emb_bytes)
            
            # Store nonce + ciphertext together
            encrypted_data = nonce + ciphertext
            
            self._embeddings[emb_id] = encrypted_data
            self._metadata[emb_id] = StoredFace(
                name=name,
                embedding_id=emb_id,
                created_at=datetime.now().isoformat()
            )
            
            self._save_store()
            self.logger.info(f"Stored encrypted embedding for: {name}")
            return emb_id
            
        except Exception as e:
            self.logger.error(f"Failed to store embedding: {e}")
            return None
    
    def get_embedding(self, emb_id: str) -> Optional[np.ndarray]:
        """
        Retrieve and decrypt a face embedding.
        
        Args:
            emb_id: Embedding ID.
        
        Returns:
            Decrypted embedding vector or None.
        """
        if not CRYPTO_AVAILABLE or np is None:
            return None
        
        encrypted_data = self._embeddings.get(emb_id)
        if not encrypted_data:
            return None
        
        try:
            # Split nonce and ciphertext
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Decrypt
            emb_bytes = self._decrypt(nonce, ciphertext)
            
            # Deserialize (assuming float32 embedding)
            embedding = np.frombuffer(emb_bytes, dtype=np.float32)
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to decrypt embedding: {e}")
            return None
    
    def get_all_embeddings(self) -> List[Tuple[str, str, np.ndarray]]:
        """
        Get all embeddings for matching.
        
        Returns:
            List of (id, name, embedding) tuples.
        """
        results = []
        for emb_id, meta in self._metadata.items():
            embedding = self.get_embedding(emb_id)
            if embedding is not None:
                results.append((emb_id, meta.name, embedding))
        return results
    
    def delete_embedding(self, emb_id: str) -> bool:
        """Delete an embedding."""
        if emb_id in self._embeddings:
            del self._embeddings[emb_id]
            self._metadata.pop(emb_id, None)
            self._save_store()
            self.logger.info(f"Deleted embedding: {emb_id}")
            return True
        return False
    
    def list_faces(self) -> List[StoredFace]:
        """List all registered faces."""
        return list(self._metadata.values())
    
    def face_exists(self, name: str) -> bool:
        """Check if a face with given name exists."""
        return any(m.name == name for m in self._metadata.values())
