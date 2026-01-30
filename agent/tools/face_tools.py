import cv2
import numpy as np
import logging
import os
from agent.memory.sql_store import SQLStore
from agent.memory.vector_store import VectorStore
from agent.security.permissions import PermissionManager

# Dynamic import to handle potential missing dependencies on Windows
try:
    import insightface
    from insightface.app import FaceAnalysis
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False

class FaceTools:
    """
    Tools for detecting, recognizing, and managing faces.
    """
    def __init__(self):
        self.logger = logging.getLogger("FaceTools")
        self.sql = SQLStore()
        self.vectors = VectorStore()
        self.permissions = PermissionManager()
        
        self.app = None
        if HAS_INSIGHTFACE:
            try:
                # Use 'buffalo_l' model pack (robust)
                self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
                self.app.prepare(ctx_id=0, det_size=(640, 640))
                self.logger.info("InsightFace model loaded successfully.")
            except Exception as e:
                self.logger.error(f"Failed to initialize InsightFace: {e}")
                self.app = None
        else:
             self.logger.warning("InsightFace not installed. Face tools will be limited.")

    def _load_image(self, path: str):
        if not os.path.exists(path):
            return None
        return cv2.imread(path)

    def detect_faces(self, path: str) -> str:
        """
        Detects faces in an image and returns count/positions.
        """
        if not self.app:
            return "Error: Face Recognition capabilities are not active (Missing libraries)."
        
        if not self.permissions.is_path_allowed(path):
            return f"Error: Access denied to {path}"

        img = self._load_image(path)
        if img is None:
            return f"Error: Could not load image at {path}"

        faces = self.app.get(img)
        count = len(faces)
        return f"Detected {count} faces."

    def recognize_faces(self, path: str) -> str:
        """
        Identifies people in the image.
        """
        if not self.app:
            return "Error: Face Recognition capabilities are not active."

        if not self.permissions.is_path_allowed(path):
            return f"Error: Access denied to {path}"

        img = self._load_image(path)
        if img is None:
             return f"Error: Could not load image at {path}"

        faces = self.app.get(img)
        if not faces:
            return "No faces detected."

        results = []
        for face in faces:
            embedding = face.embedding
            norm_embedding = embedding / np.linalg.norm(embedding)
            
            match = self.vectors.find_similar(norm_embedding, threshold=0.4) # Tuned threshold
            if match:
                name, score = match
                results.append(f"{name} ({score:.2f})")
                
                # Log encounter
                self.sql.log_event("face_recognition", f"Recognized {name}", path)
            else:
                results.append("Unknown Person")

        return f"Identified: {', '.join(results)}"

    def register_face(self, path: str, name: str) -> str:
        """
        Learns a new face.
        """
        if not self.app:
            return "Face tool inactive."
        
        if not self.permissions.is_path_allowed(path):
            return f"Access denied."

        # Privacy check: Confirm storing biometric data?
        # In a real app, this should be a permissions prompt.
        if not self.permissions.request_permission(f"Store biometric face data for '{name}'"):
             return "Action cancelled."

        img = self._load_image(path)
        if img is None: return "Image load error."

        faces = self.app.get(img)
        if len(faces) == 0:
            return "No face detected to register."
        if len(faces) > 1:
            return "Error: Multiple faces detected. Please provide an image with a single person."

        embedding = faces[0].embedding
        norm_embedding = embedding / np.linalg.norm(embedding)
        
        # Save to DB and Vector Store
        self.sql.add_face(name)
        self.vectors.add_embedding(name, norm_embedding)
        
        return f"Successfully registered face: {name}"

    def forget_face(self, name: str) -> str:
        """
        Removes face data (Privacy).
        """
        self.sql.remove_face(name)
        self.vectors.remove_embedding(name)
        return f"Forgot person: {name}"
