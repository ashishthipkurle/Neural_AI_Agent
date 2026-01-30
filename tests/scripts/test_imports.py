
import sys
import os
import logging

# Add current dir to path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestImports")

print("Testing Imports...")

try:
    from agent.vision.face_db import FaceDatabase
    print("SUCCESS: FaceDatabase imported.")
except Exception as e:
    print(f"ERROR: FaceDatabase import failed: {e}")

try:
    from agent.vision.face_detector import FaceDetector
    print("SUCCESS: FaceDetector imported.")
except Exception as e:
    print(f"ERROR: FaceDetector import failed: {e}")

try:
    from agent.vision.camera_stream import CameraStream
    print("SUCCESS: CameraStream imported.")
except Exception as e:
    print(f"ERROR: CameraStream import failed: {e}")

try:
    from agent.memory.vector_store import VectorStore
    print("SUCCESS: VectorStore imported.")
except Exception as e:
    print(f"ERROR: VectorStore import failed: {e}")

try:
    from agent.core.router import ToolRouter
    router = ToolRouter()
    print("SUCCESS: ToolRouter instantiated.")
except Exception as e:
    print(f"ERROR: ToolRouter instantiation failed: {e}")

print("Import Test Complete.")
