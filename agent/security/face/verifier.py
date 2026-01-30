"""
Face Verifier - Face authentication logic.

This module handles face detection, encoding, and verification
for authentication purposes.
"""
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass

try:
    import numpy as np
except ImportError:
    np = None

from .camera import FaceCamera
from .embedding_store import EmbeddingStore


@dataclass
class VerificationResult:
    """Result of face verification."""
    success: bool
    user_name: Optional[str]
    confidence: float
    message: str


class FaceVerifier:
    """
    Face verification system.
    
    Uses face detection and embedding comparison
    to authenticate users.
    
    Threshold tuning:
    - Higher threshold = more strict (fewer false positives)
    - Lower threshold = more lenient (better usability)
    """
    
    DEFAULT_THRESHOLD = 0.6  # Cosine similarity threshold
    
    def __init__(
        self,
        camera: FaceCamera,
        embedding_store: EmbeddingStore,
        threshold: float = None
    ):
        """
        Initialize face verifier.
        
        Args:
            camera: Face camera instance.
            embedding_store: Encrypted embedding store.
            threshold: Verification threshold.
        """
        self.logger = logging.getLogger("FaceVerifier")
        self.camera = camera
        self.store = embedding_store
        self.threshold = threshold or self.DEFAULT_THRESHOLD
        
        # Initialize face detection/encoding
        self._detector = None
        self._encoder = None
        self._init_models()
        
        self.logger.info(f"FaceVerifier initialized (threshold={self.threshold})")
    
    def _init_models(self) -> None:
        """Initialize face detection and encoding models."""
        try:
            from insightface.app import FaceAnalysis
            self._detector = FaceAnalysis(
                name='buffalo_l',
                allowed_modules=['detection', 'recognition'],
                providers=['CPUExecutionProvider']
            )
            self._detector.prepare(ctx_id=0)
            self.logger.info("InsightFace initialized for face verification.")
        except ImportError:
            self.logger.warning("InsightFace not available. Using fallback.")
        except Exception as e:
            self.logger.error(f"Failed to initialize InsightFace: {e}")
    
    def _detect_and_encode(self, frame) -> Optional[np.ndarray]:
        """
        Detect face and extract embedding.
        
        Args:
            frame: Image frame.
        
        Returns:
            Face embedding or None.
        """
        if self._detector is None:
            return None
        
        try:
            faces = self._detector.get(frame)
            if not faces:
                return None
            
            # Use the largest/most prominent face
            largest_face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
            return largest_face.embedding
            
        except Exception as e:
            self.logger.error(f"Face detection error: {e}")
            return None
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings."""
        if np is None:
            return 0.0
        
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        
        if a_norm == 0 or b_norm == 0:
            return 0.0
        
        return float(np.dot(a, b) / (a_norm * b_norm))
    
    def verify(self) -> VerificationResult:
        """
        Perform face verification.
        
        Returns:
            VerificationResult with authentication status.
        """
        # Capture frames
        frames = self.camera.capture_for_verification(num_frames=3)
        
        if not frames:
            return VerificationResult(
                success=False,
                user_name=None,
                confidence=0.0,
                message="Camera not available or no frames captured."
            )
        
        # Get all stored embeddings
        stored = self.store.get_all_embeddings()
        
        if not stored:
            return VerificationResult(
                success=False,
                user_name=None,
                confidence=0.0,
                message="No faces registered. Please register a face first."
            )
        
        # Try to match against stored embeddings
        best_match = None
        best_confidence = 0.0
        best_name = None
        
        for frame in frames:
            current_embedding = self._detect_and_encode(frame)
            
            if current_embedding is None:
                continue
            
            for emb_id, name, stored_embedding in stored:
                similarity = self._cosine_similarity(
                    current_embedding,
                    stored_embedding
                )
                
                if similarity > best_confidence:
                    best_confidence = similarity
                    best_name = name
                    best_match = emb_id
        
        # Check against threshold
        if best_confidence >= self.threshold:
            self.logger.info(f"Face verified: {best_name} ({best_confidence:.2f})")
            return VerificationResult(
                success=True,
                user_name=best_name,
                confidence=best_confidence,
                message=f"Verified as {best_name}"
            )
        else:
            self.logger.warning(f"Face verification failed. Best: {best_confidence:.2f}")
            return VerificationResult(
                success=False,
                user_name=None,
                confidence=best_confidence,
                message="Face not recognized."
            )
    
    def register_face(self, name: str, num_samples: int = 5) -> bool:
        """
        Register a new face.
        
        Args:
            name: Name for the face.
            num_samples: Number of sample frames to capture.
        
        Returns:
            True if registration succeeded.
        """
        if self.store.face_exists(name):
            self.logger.warning(f"Face already registered: {name}")
            return False
        
        # Capture multiple frames and average embeddings
        embeddings = []
        frames = self.camera.capture_for_verification(num_frames=num_samples)
        
        for frame in frames:
            embedding = self._detect_and_encode(frame)
            if embedding is not None:
                embeddings.append(embedding)
        
        if len(embeddings) < 2:
            self.logger.error("Not enough valid face samples captured.")
            return False
        
        # Average embeddings for robustness
        if np is not None:
            avg_embedding = np.mean(embeddings, axis=0).astype(np.float32)
        else:
            return False
        
        # Store encrypted embedding
        emb_id = self.store.store_embedding(name, avg_embedding)
        
        if emb_id:
            self.logger.info(f"Face registered: {name}")
            return True
        
        return False
    
    def is_available(self) -> bool:
        """Check if face verification is available."""
        return (
            self.camera.is_available() and
            self._detector is not None
        )
