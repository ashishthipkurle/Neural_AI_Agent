import os, hashlib, json

base_path = r'D:\All Projects\My AI Agent\autonomous_system_audit'

# Write README.md
readme_path = os.path.join(base_path, 'README.md')
readme_content = '''# Autonomous System Audit

This directory contains resources for auditing autonomous systems, including documentation, configuration files, and visual diagrams illustrating the LangGraph flow used in the audit process.

## Contents
- `README.md`: This file.
- `diagram.png`: A 12‑node LangGraph flow diagram.
- `config.json`: Configuration adhering to the required schema.
'''
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write(readme_content)

# Write config.json
config_path = os.path.join(base_path, 'config.json')
config_data = {
    "name": "autonomous_system_audit",
    "version": "1.0",
    "description": "Configuration for autonomous system audit",
    "schema_version": "2023-09-01",
    "parameters": {
        "audit_level": "full",
        "report_format": "pdf"
    }
}
with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config_data, f, indent=4)

# Generate diagram.png using graphviz
from graphviz import Digraph

dot = Digraph(comment='LangGraph Flow', format='png')
# Create 12 nodes
for i in range(1, 13):
    dot.node(f'Node{i}', f'Node {i}')
# Connect nodes in a sample flow (simple chain and some branches)
for i in range(1, 12):
    dot.edge(f'Node{i}', f'Node{i+1}')
# Add some extra edges to make it interesting
extra_edges = [(1,5), (3,7), (6,10), (2,9), (4,12)]
for src, dst in extra_edges:
    dot.edge(f'Node{src}', f'Node{dst}')

# Render to file
output_path = os.path.join(base_path, 'diagram')
# This will create diagram.png
dot.render(filename=output_path, cleanup=True)

# Compute SHA-256 hashes
files = [readme_path, config_path, os.path.join(base_path, 'diagram.png')]
hashes = {}
for file in files:
    with open(file, 'rb') as f:
        data = f.read()
        sha256 = hashlib.sha256(data).hexdigest()
        hashes[os.path.basename(file)] = sha256

# Write hashes to a file for reference
hash_path = os.path.join(base_path, 'hashes.txt')
with open(hash_path, 'w') as f:
    for name, h in hashes.items():
        f.write(f"{name}: {h}\n")

print('Done')
