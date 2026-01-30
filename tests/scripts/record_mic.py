import sounddevice as sd
import soundfile as sf
import os

def record_test():
    samplerate = 16000  # 16kHz for Vosk
    duration = 3  # seconds
    filename = 'mic_test.wav'

    print(f"Recording for {duration} seconds...")
    try:
        # Request 1 channel (mono)
        myrecording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()  # Wait until recording is finished
        print("Recording finished.")
        
        # Save as wav
        sf.write(filename, myrecording, samplerate)
        print(f"Saved to {filename} (Size: {os.path.getsize(filename)} bytes)")
        
        # Check max amplitude
        import numpy as np
        max_amp = np.abs(myrecording).max()
        print(f"Max Amplitude: {max_amp}")
        if max_amp == 0:
            print("WARNING: Max amplitude is 0! Mic is likely muted or disconnected.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    record_test()
