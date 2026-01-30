
import cv2
import time
import logging
import threading
import json
import os
from datetime import datetime
from agent.vision.face_detector import FaceDetector
from agent.vision.face_encoder import FaceEncoder
from agent.vision.face_db import FaceDatabase
from agent.vision.object_detector import ObjectDetector

class CameraStream:
    def __init__(self, source=0, db_path="agent/db/faces.db"):
        self.logger = logging.getLogger("CCTV")
        self.source = source
        self.running = False
        self.cap = None
        
        # Init Vision Pipeline
        self.db = FaceDatabase(db_path=db_path)
        self.detector = FaceDetector()
        self.encoder = FaceEncoder()
        self.object_detector = ObjectDetector() # Initialize YOLO
        self.on_event = None # Callback for UI updates
        
        self.log_path = "logs/entry_log.json"
        os.makedirs("logs", exist_ok=True)

    def start(self):
        """Start the camera loop in a separate thread."""
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"CCTV Started on {self.source}")

    def stop(self):
        self.running = False
        if hasattr(self, 'thread') and self.thread and self.thread.is_alive():
            self.thread.join()
        if self.cap:
            self.cap.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass  # Ignore if no GUI available

    def _connect(self):
        """
        Robust camera connection: 
        1. Tries DirectShow (Windows) then Default for current source.
        2. If that fails, SCANS for any working camera.
        """
        # 1. Try Requested Source
        cap = self._try_open(self.source)
        if cap: return cap

        # 2. Search for ANY working camera
        self.logger.warning(f"Camera {self.source} failed. Scanning for available cameras...")
        for i in range(4):
            if i == self.source: continue
            cap = self._try_open(i)
            if cap:
                self.logger.info(f"Auto-switched to Camera {i} (Working).")
                self.source = i
                return cap
        
        self.logger.error("No working cameras found on system.")
        return None

    def _try_open(self, index):
        if os.name == 'nt':
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret: return cap
                cap.release()
            except Exception as e:
                self.logger.warning(f"DirectShow open failed for Camera {index}: {e}")
            
        try:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret: return cap
            cap.release()
        except Exception as e:
            self.logger.warning(f"Default open failed for Camera {index}: {e}")
            
        return None

    def get_frame(self):
        """
        Captures a single frame safely.
        """
        # If camera is already running, just grab from it
        if self.running and self.cap:
             ret, frame = self.cap.read()
             if ret: return frame
             return None
        
        # Otherwise try to connect briefly
        cap = self._connect()
        if cap:
            ret, frame = cap.read()
            cap.release()
            if ret: return frame
        return None

    def _monitor_loop(self):
        self.cap = self._connect()
        
        while self.running:
            if self.cap is None:
                self.logger.warning("No camera connected. Retrying...")
                time.sleep(2)
                self.cap = self._connect()
                continue

            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning("Failed to read frame via OpenCV. Reconnecting...")
                time.sleep(2)
                if self.cap: self.cap.release()
                self.cap = self._connect()
                continue

            # --- VISUAL STATUS ---
            cv2.putText(frame, "CCTV ACTIVE", (20, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # --- 1. OBJECT DETECTION (YOLO) ---
            objects = self.object_detector.detect_objects(frame)
            for obj in objects:
                x1, y1, x2, y2 = obj['bbox']
                label = f"{obj['label']} {int(obj['conf']*100)}%"
                
                # Draw Box (Blue/Cyan style)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 100, 0), 2)
                
                # Draw Label Background
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - 20), (x1 + w, y1), (255, 100, 0), -1)
                cv2.putText(frame, label, (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # --- 2. FACE DETECTION ---
            faces = self.detector.detect_faces(frame)
            
            for face in faces:
                if hasattr(face, 'bbox'):
                    bbox = face.bbox.astype(int)
                    # Green box for faces to distinguish from objects
                    cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

            if not faces and not objects:
                # Still show feed even if empty
                pass

            # Resize if needed (optional)
            # frame = cv2.resize(frame, (640, 480))
            
            # Show Feed
            cv2.imshow("CCTV Surveillance", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
               self.stop()
               break
            
            # --- 3. FACE RECOGNITION (Optional/Debounced) ---
            # (Uncomment if needed, heavy on CPU)
            # for face in faces:
            #     embedding = self.encoder.encode(face)
            #     if embedding is None: continue
            #     name, conf = self.db.match_face(embedding)
            #     if conf > 0.5:
            #         # ... draw name logic ...
            #         pass

    def _log_event(self, name):
        """
        Log entry event with cool-down to avoid spam.
        """
        # Load existing LOG (naive implementation, huge logs will be slow)
        # Better: Append to file or use SQL.
        # For prototype: simple JSON append
        
        entry = {
            "name": name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera": str(self.source)
        }
        
        # Debounce logic: Don't log same person within 1 minute
        if self._should_log(name):
            self.logger.info(f"Person Sighted: {name}")
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _should_log(self, name):
        # Todo: Implement efficient debounce
        return True
