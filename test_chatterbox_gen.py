
import logging
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ChatterboxTest")

try:
    from chatterbox import ChatterboxTTS
    import torch
    import soundfile as sf
    
    logger.info("Import successful.")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    logger.info("Loading model (this may download weights)...")
    tts = ChatterboxTTS.from_pretrained(device)
    logger.info("Model loaded.")
    
    text = "Hello! This is a test of the Chatterbox text to speech system."
    logger.info(f"Generating audio for: '{text}'")
    
    wav_tensor = tts.generate(text)
    logger.info(f"Generation complete. Shape: {wav_tensor.shape}")
    
    # Save to file
    output_file = "chatterbox_test.wav"
    wav_numpy = wav_tensor.squeeze().cpu().numpy()
    sf.write(output_file, wav_numpy, tts.sr)
    logger.info(f"Saved to {output_file}")
    
    if os.path.exists(output_file):
        print("SUCCESS")
    else:
        print("FAILURE: File not created")
        
except Exception as e:
    logger.error(f"Test failed: {e}")
    import traceback
    traceback.print_exc()
