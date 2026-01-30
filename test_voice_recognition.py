import os
import sys
import json
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer

def test_mic_and_vosk():
    model_path = "voice_models/vosk-model-small-en-us-0.15"
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return

    print(f"Loading model from {model_path}...")
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    print("--- LISTENING TEST (10 SECONDS) ---")
    print("Please say 'hii bro' or just talk...")
    
    try:
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            import time
            start = time.time()
            while time.time() - start < 10:
                data = q.get()
                if rec.AcceptWaveform(data):
                    print(f"FINAL: {json.loads(rec.Result())['text']}")
                else:
                    partial = json.loads(rec.PartialResult())['partial']
                    if partial:
                        print(f"PARTIAL: {partial}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_mic_and_vosk()
