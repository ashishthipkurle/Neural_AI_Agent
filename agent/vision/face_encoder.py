
import logging
import numpy as np

# In InsightFace, the 'app.get(frame)' already returns embeddings if the model includes recognition!
# So this class is mostly a helper to extract the embedding from the detection result.
# Or if we want to run recognition separately on a crop.

class FaceEncoder:
    def __init__(self):
        self.logger = logging.getLogger("FaceEncoder")

    def encode(self, face_obj):
        """
        Extracts embedding from an InsightFace object.
        FaceAnalysis already computes this during 'get'.
        """
        if hasattr(face_obj, 'embedding'):
            return face_obj.embedding
        return None
        
    def encode_batch(self, faces):
        return [f.embedding for f in faces if hasattr(f, 'embedding')]
