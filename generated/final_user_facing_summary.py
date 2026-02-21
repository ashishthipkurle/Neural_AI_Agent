import os
from datetime import datetime

# Define source summary files (order matters)
sources = [
    "summary.txt",
    "final_summary.txt",
    "formatted_summary.txt",
    "section1.txt",
    "section2.txt",
    "section3.txt",
]

# Base directory (workspace root)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Helper to read file if exists
def read_if_exists(rel_path):
    path = os.path.join(base_dir, rel_path)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

# Collect contents
collected = []
for src in sources:
    content = read_if_exists(src)
    if content:
        header = f"=== {os.path.basename(src).replace('.txt', '').replace('_', ' ').title()} ===\n"
        collected.append(header + content.strip() + "\n\n")

# Combine into final summary
final_summary = "\n".join(collected)

# Output path
output_path = os.path.join(base_dir, "generated", "user_facing_summary.txt")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as out_f:
    out_f.write(f"User-Facing Summary generated on {datetime.now().isoformat()}\n\n")
    out_f.write(final_summary)

print(f"User-facing summary written to {output_path}")
