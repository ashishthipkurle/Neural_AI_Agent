from PIL import Image
import logging
import cv2
import numpy as np
from agent.security.permissions import PermissionManager
from agent.vision.face_detector import FaceDetector
from agent.vision.face_encoder import FaceEncoder
from agent.vision.face_db import FaceDatabase
from agent.vision.camera_stream import CameraStream
from agent.vision.screen_eye import ScreenEye
import os

class VisionTools:
    """
    Tools for loading and analyzing images, including Face Recognition, CCTV, and Screen Capture.
    """
    def __init__(self):
        self.permissions = PermissionManager()
        self.logger = logging.getLogger("VisionTools")
        
        # Init Vision Engines
        self.detector = FaceDetector()
        self.encoder = FaceEncoder()
        self.db = FaceDatabase()
        self.cctv = CameraStream()
        self.screen_eye = ScreenEye()

    def set_event_callback(self, callback):
        """
        Sets the callback for UI events.
        """
        self.cctv.on_event = callback

    def start_surveillance(self, camera_index=0):
        """
        Starts the CCTV monitoring loop in a separate process.
        """
        import subprocess
        import sys
        
        # Stop existing if any
        self.stop_surveillance()
        
        try:
            script_path = os.path.join("agent", "vision", "run_cctv.py")
            if not os.path.exists(script_path):
                 return f"Error: Helper script not found at {script_path}"

            # Launch separate process
            # We use 'python' assuming it's in path, or sys.executable
            cmd = [sys.executable, script_path, str(camera_index)]
            
            self.cctv_process = subprocess.Popen(cmd, cwd=os.getcwd(), shell=False)
            
            return f"CCTV Surveillance process started (PID: {self.cctv_process.pid}). Window should appear momentarily."
        except Exception as e:
            self.logger.error(f"Failed to launch CCTV: {e}")
            return f"Failed to start CCTV: {e}"

    def stop_surveillance(self):
        """
        Stops the CCTV monitoring process.
        """
        if hasattr(self, 'cctv_process') and self.cctv_process:
            self.cctv_process.terminate()
            self.cctv_process = None
            return "CCTV Surveillance stopped."
            
        return "No active surveillance process found."

    def capture_screen(self) -> str:
        """
        Captures the current screen and returns the file path.
        """
        path = self.screen_eye.capture()
        if path:
            return f"Screen captured and saved to: {path}"
        return "Failed to capture screen."

    def _load_image(self, path: str):
        if not self.permissions.is_path_allowed(path):
            return None, f"Error: Access denied to {path}"
        if not os.path.exists(path):
            return None, f"Error: File not found at {path}"
            
        # Load using OpenCV
        img = cv2.imread(path)
        if img is None:
            return None, "Error: Failed to decode image."
        return img, None

    def describe_image(self, path: str) -> str:
        """
        Placeholder for BLIP-2 Integration.
        """
        return "Image description feature requires BLIP-2 integration (Phase 3 pending)."

    def detect_faces(self, path: str) -> str:
        img, err = self._load_image(path)
        if err: return err
        
        faces = self.detector.detect_faces(img)
        return f"Detected {len(faces)} faces."

    def recognize_faces(self, path: str) -> str:
        img, err = self._load_image(path)
        if err: return err
        
        faces = self.detector.detect_faces(img)
        if not faces: return "No faces detected."
        
        results = []
        for face in faces:
            emb = self.encoder.encode(face)
            if emb is not None:
                name, conf = self.db.match_face(emb)
                results.append(f"{name} ({conf:.2f})")
                
        return "Identified: " + ", ".join(results)

    def register_face(self, name: str, path: str) -> str:
        """
        Registers a face from an image.
        """
        img, err = self._load_image(path)
        if err: return err
        
        faces = self.detector.detect_faces(img)
        if not faces: return "No face found to register."
        if len(faces) > 1: return "Error: Multiple faces found. Please use a photo with a single face."
        
        emb = self.encoder.encode(faces[0])
        if emb is None: return "Error: Could not encode face."
        
        self.db.add_face(name, emb)
        return f"Successfully registered face for {name}."

    def forget_face(self, name: str) -> str:
        # TODO: Implement delete in DB
        return "Forget face feature pending implementation in DB layer."

    def authenticate_user(self) -> str:
        """
        Captures a frame from the camera and attempts to recognize a registered user.
        """
        # Ensure camera is not monitored by another process if possible, or just grab a frame
        if not self.cctv.cap or not self.cctv.cap.isOpened():
             # Try to temporarily open camera
             # This depends on CameraStream implementation. 
             # Assuming CameraStream has a verify method or similar would be better.
             # For now, let's use the camera stream's internal method if accessible, 
             # or just start/stop quickly.
             pass

        # Use CameraStream to get a single frame
        frame = self.cctv.get_frame() 
        if frame is None:
            return "Error: Camera not available for authentication."
            
        faces = self.detector.detect_faces(frame)
        if not faces:
            return "Authentication Failed: No face detected."
            
        for face in faces:
            emb = self.encoder.encode(face)
            if emb is not None:
                name, conf = self.db.match_face(emb)
                if name != "Unknown":
                    return f"Authorized: {name}"
                    
        return "Authentication Failed: Face not recognized."

