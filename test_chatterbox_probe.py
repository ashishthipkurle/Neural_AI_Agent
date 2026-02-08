
try:
    import chatterbox
    print("Chatterbox imported successfully")
    print(dir(chatterbox))
except ImportError as e:
    print(f"Failed to import chatterbox: {e}")

try:
    from chatterbox import Chatterbox
    print("Chatterbox class found")
except ImportError:
    print("Chatterbox class NOT found in top level")
