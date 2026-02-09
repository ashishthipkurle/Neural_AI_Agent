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
        
        # Load config
        self.config = self._load_config()
        self.vision_model = self.config.get('llm', {}).get('vision_model', "llava:latest")
        if self.vision_model == "llava" and "latest" not in self.vision_model:
             # Default to latest if just 'llava' is specified for backward compatibility in this tool
             # (though 'llava' tag exists too, usually 'latest' is safer)
             self.vision_model = "llava:latest"
             
        # Init Vision Engines
        self.detector = FaceDetector()
        self.encoder = FaceEncoder()
        self.db = FaceDatabase()
        self.cctv = CameraStream()
        self.screen_eye = ScreenEye()

    def _load_config(self):
        """Load configuration from YAML file."""
        import yaml
        import os
        config_path = "agent/config/settings.yaml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                expanded_content = os.path.expandvars(content)
                return yaml.safe_load(expanded_content) or {}
        except Exception as e:
            self.logger.error(f"Failed to load user config: {e}")
            return {}

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

    def describe_image(self, path: str = None, use_last_capture: bool = False) -> str:
        """
        Describes an image using llava vision model.
        
        Args:
            path: Path to the image file
            use_last_capture: If True, use the most recent screenshot
        """
        import glob
        import base64
        import requests
        
        # If use_last_capture, find the most recent screenshot
        if use_last_capture or not path:
            captures_dir = os.path.join(os.getcwd(), "captures")
            if os.path.exists(captures_dir):
                files = glob.glob(os.path.join(captures_dir, "screenshot_*.png"))
                if files:
                    path = max(files, key=os.path.getmtime)
                    self.logger.info(f"Using last capture: {path}")
        
        if not path:
            return "No image provided and no recent screenshots found."
            
        if not os.path.exists(path):
            return f"Error: Image not found at {path}"
        
        try:
            # Optimize image size before sending to LLM
            with Image.open(path) as img:
                # Resize if too large (max 1024px dimension) to speed up processing
                if max(img.size) > 1024:
                    ratio = 1024 / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save to buffer
                import io
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                image_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Call vision model via Ollama
            self.logger.info(f"Analyzing image with {self.vision_model}...")
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": "Describe what you see in this image in detail. Be specific about any text, UI elements, applications, or content visible.",
                    "images": [image_data],
                    "stream": False
                },
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get("response", "Could not generate description.")
                return description
            else:
                self.logger.error(f"Ollama llava error: {response.status_code}")
                return f"Vision analysis failed: HTTP {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Please ensure Ollama is running."
        except Exception as e:
            self.logger.error(f"describe_image error: {e}")
            return f"Error analyzing image: {e}"

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

