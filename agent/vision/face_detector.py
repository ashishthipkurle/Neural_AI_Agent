
import logging
import cv2
import numpy as np

try:
    from insightface.app import FaceAnalysis
except ImportError:
    FaceAnalysis = None

class FaceDetector:
    def __init__(self, model_name='buffalo_l'):
        self.logger = logging.getLogger("FaceDetector")
        self.app = None
        self.cascade = None
        
        if not FaceAnalysis:
            self.logger.warning("InsightFace not installed. Falling back to Haar Cascade.")
            self._load_cascade()
            return

        try:
            self.app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            self.logger.info(f"InsightFace Detector ({model_name}) loaded.")
        except Exception as e:
            self.logger.error(f"Failed to load FaceDetector: {e}")
            self._load_cascade()

    def _load_cascade(self):
        try:
            path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.cascade = cv2.CascadeClassifier(path)
            self.logger.info("Haar Cascade loaded as fallback.")
        except Exception as e:
            self.logger.error(f"Failed to load Haar Cascade: {e}")

    def detect_faces(self, frame: np.ndarray):
        """
        Detects faces in a frame.
        Returns list of InsightFace objects (bbox, kps, etc) or Fallback objects.
        """
        # 1. Try InsightFace
        if self.app:
            try:
                faces = self.app.get(frame)
                return faces
            except Exception as e:
                self.logger.error(f"Detection Error: {e}")
                return []
        
        # 2. Try Haar Cascade (Fallback)
        if self.cascade:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            results = []
            for (x, y, w, h) in detections:
                # Mock an InsightFace object with a 'bbox' attribute
                # InsightFace bbox is [x1, y1, x2, y2]
                class FaceResult:
                    def __init__(self, x, y, w, h):
                        self.bbox = np.array([x, y, x + w, y + h])
                        self.kps = None
                        self.embedding = None
                results.append(FaceResult(x, y, w, h))
            return results

        return []
