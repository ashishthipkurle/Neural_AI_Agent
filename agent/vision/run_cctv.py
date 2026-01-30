import sys
import os
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import logging
# Configure standalone logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CCTV - %(message)s')

try:
    from agent.vision.camera_stream import CameraStream
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import CameraStream: {e}")
    sys.exit(1)

def main():
    try:
        print("Starting CCTV process...")
        camera_index = 1  # Default to Camera 1
        if len(sys.argv) > 1:
            camera_index = int(sys.argv[1])
            
        stream = CameraStream(source=camera_index)
        
        # We need to modify CameraStream to support blocking run or we handle the loop here
        # CameraStream.start() currently launches a thread.
        # But we need to keep the MAIN thread alive for this process.
        
        stream.start()
        
        print(f"CCTV Running on Camera {camera_index}. Press 'q' in window to exit.")
        
        # Keep process alive until stream stops
        while stream.running:
            time.sleep(0.5)
            # If the user closes the window, stream.running becomes False in typical implementations
            # (checked: CameraStream._monitor_loop sets self.running=False on 'q')
            
    except KeyboardInterrupt:
        print("Stopping CCTV...")
    except Exception as e:
        print(f"CCTV Crashed: {e}")
    finally:
        if 'stream' in locals():
            stream.stop()

if __name__ == "__main__":
    main()
