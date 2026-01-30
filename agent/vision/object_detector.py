import logging
import cv2
import numpy as np

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

class ObjectDetector:
    def __init__(self, model_path="yolov8n.pt"):
        self.logger = logging.getLogger("ObjectDetector")
        self.model = None
        self.enabled = False

        if ULTRALYTICS_AVAILABLE:
            try:
                self.logger.info(f"Loading YOLO model: {model_path}...")
                self.model = YOLO(model_path)
                self.enabled = True
                self.logger.info("YOLO Object Detection initialized successfully.")
            except Exception as e:
                self.logger.error(f"Failed to load YOLO model: {e}")
        else:
            self.logger.warning("Ultralytics not installed. Object Detection disabled.")

    def detect_objects(self, frame):
        """
        Detect objects in frame and return results.
        Returns a list of dicts: {'bbox': [x1, y1, x2, y2], 'label': str, 'conf': float}
        """
        if not self.enabled or self.model is None:
            return []

        results = []
        try:
            # Run inference (verbose=False to reduce log spam)
            predictions = self.model(frame, verbose=False)
            
            for result in predictions:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    label = self.model.names[cls]
                    
                    if conf > 0.4:  # Threshold
                        results.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'label': label,
                            'conf': conf
                        })
        except Exception as e:
            self.logger.error(f"Detection failed: {e}")
            
        return results
