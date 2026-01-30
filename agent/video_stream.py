"""
MJPEG Video Stream Server with Object Detection

Provides a /video_feed endpoint that streams camera frames as MJPEG
with YOLO object detection overlays.
"""
import cv2
import time
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger("VideoStream")

router = APIRouter()

# Global instances
camera = None
camera_index = 1  # Default to Camera 1
object_detector = None

def get_camera():
    """Get or create camera instance."""
    global camera
    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(camera_index)
        if not camera.isOpened():
            # Try camera 0 as fallback
            camera = cv2.VideoCapture(0)
    return camera

def get_detector():
    """Get or create YOLO detector instance."""
    global object_detector
    if object_detector is None:
        try:
            from agent.vision.object_detector import ObjectDetector
            object_detector = ObjectDetector()
            logger.info("YOLO Object Detector initialized for web stream")
        except Exception as e:
            logger.error(f"Failed to initialize YOLO: {e}")
    return object_detector

def generate_frames():
    """Generator that yields MJPEG frames with object detection."""
    cap = get_camera()
    detector = get_detector()
    
    while True:
        success, frame = cap.read()
        if not success:
            # Create a "No Signal" frame
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "NO SIGNAL", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 200), 2)
        else:
            # Run YOLO Object Detection
            if detector and detector.enabled:
                try:
                    objects = detector.detect_objects(frame)
                    for obj in objects:
                        x1, y1, x2, y2 = obj['bbox']
                        label = f"{obj['label']} {int(obj['conf']*100)}%"
                        
                        # Draw bounding box (Blue/Cyan)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 100, 0), 2)
                        
                        # Draw label background
                        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                        cv2.rectangle(frame, (x1, y1 - 20), (x1 + w, y1), (255, 100, 0), -1)
                        cv2.putText(frame, label, (x1, y1 - 5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                except Exception as e:
                    logger.error(f"Detection error: {e}")
            
            # Add "LIVE" indicator
            cv2.putText(frame, "LIVE", (frame.shape[1] - 60, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield as multipart MJPEG frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Limit frame rate to ~10 FPS (detection is heavy)
        time.sleep(0.1)

@router.get("/video_feed")
async def video_feed():
    """MJPEG video stream endpoint with object detection."""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get("/video_snapshot")
async def video_snapshot():
    """Single frame snapshot endpoint."""
    cap = get_camera()
    success, frame = cap.read()
    
    if not success:
        return {"error": "Failed to capture frame"}
    
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return {"error": "Failed to encode frame"}
    
    from fastapi.responses import Response
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
