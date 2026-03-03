import os
input_files = [
    r"d:\All Projects\My AI Agent\android_commands_1.txt",
    r"d:\All Projects\My AI Agent\android_commands_2.txt",
    r"d:\All Projects\My AI Agent\android_commands_3.txt",
    r"d:\All Projects\My AI Agent\android_commands_4.txt",
    r"d:\All Projects\My AI Agent\android_commands_5.txt"
]

total = 0
for fpath in input_files:
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith('- "'):
                    total += 1

print(f"Total commands in text files: {total}")
