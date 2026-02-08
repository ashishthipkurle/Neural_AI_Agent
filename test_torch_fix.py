
try:
    import torch
    import torchvision
    print(f"Torch: {torch.__version__}")
    print(f"Torchvision: {torchvision.__version__}")
    
    # Try to access ops to trigger the error if it exists
    from torchvision import ops
    print("Torchvision ops imported successfully")
    
    print("SUCCESS")
except Exception as e:
    print(f"FAILURE: {e}")
