
print("1. Importing libraries...")
import cv2
try:
    from ultralytics import YOLO
    print("   Ultralytics imported.")
except ImportError as e:
    print(f"   Ultralytics IMPORT FAILED: {e}")

print("2. Initializing YOLO...")
try:
    model = YOLO("yolov8n.pt")
    print("   YOLO Initialized.")
except Exception as e:
    print(f"   YOLO Init FAILED: {e}")

print("3. Testing Camera...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("   Camera 0 FAILED to open.")
else:
    print("   Camera 0 Opened successfully.")
    ret, frame = cap.read()
    if ret:
        print(f"   Frame captured: {frame.shape}")
        print("4. Running Inference...")
        results = model(frame)
        print(f"   Inference complete. Detected: {len(results[0].boxes)} objects.")
    else:
        print("   Failed to read frame.")
    cap.release()

print("5. Done.")
