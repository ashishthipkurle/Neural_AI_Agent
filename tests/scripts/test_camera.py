
import cv2
import os

print("Checking available cameras...")
for index in range(5):
    if os.name == 'nt':
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index)
    
    if not cap.isOpened():
        print(f"Camera {index}: Failed to open.")
        continue
        
    ret, frame = cap.read()
    if ret:
        print(f"Camera {index}: WORKING! (Resolution: {frame.shape[1]}x{frame.shape[0]})")
    else:
        print(f"Camera {index}: Opened but failed to capture frame.")
    
    cap.release()
print("Done.")
