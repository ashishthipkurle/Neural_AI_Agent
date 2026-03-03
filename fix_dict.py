file_path = r'd:\All Projects\My AI Agent\agent\core\pc_commands.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

names = [
    'WINDOW_COMMANDS',
    'COMMUNICATION_COMMANDS',
    'META_COMMANDS',
    'NOTES_COMMANDS',
    'DATA_ANALYTICS_COMMANDS',
    'ECOMMERCE_COMMANDS',
    'VM_COMMANDS',
    'WEBCAM_COMMANDS',
    'DATABASE_COMMANDS',
    'API_COMMANDS'
]

for name in names:
    text = text.replace('\\1', f'{name}: Dict[str, Dict[str, Any]] = {{', 1)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed dictionary names.")
