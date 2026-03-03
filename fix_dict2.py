file_path = r'd:\All Projects\My AI Agent\agent\core\pc_commands.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('\\2', '\n}', 10)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed dictionary ends.")
