
import importlib.util
import sys

dependencies = ['vosk', 'sounddevice', 'pyttsx3']
missing = []

for dep in dependencies:
    if importlib.util.find_spec(dep) is None:
        missing.append(dep)

if missing:
    print(f"MISSING: {', '.join(missing)}")
    sys.exit(1)
else:
    print("ALL INSTALLED")
