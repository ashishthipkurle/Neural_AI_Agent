"""Fix regex again."""
import pathlib
f = pathlib.Path("agent/graph/nodes/coder.py")
content = f.read_text("utf-8")
old = r"re.findall(r'(\{.*?" + "\"name\"" + r"\s*:\s*\"[^\"]+\".*?\})', text, re.DOTALL)"
# Use a pattern that doesn't rely entirely on non-greedy match, giving up too easily
new = r"re.findall(r'(\{[^{}]*\"name\"\s*:\s*\"[^\"]+\"[^{}]*\{[^{}]*\}[^{}]*\})', text, re.DOTALL)"
content = content.replace(old, new)
# Also add a fallback if the above isn't matched exactly
old2 = r"for block in re.findall(r'(\{.*?\"name\"\s*:\s*\"[^\"]+\".*?\})', text, re.DOTALL):"
new2 = r"for block in re.findall(r'(\{[^{}]*\"name\"\s*:\s*\"[^\"]+\"[^{}]*(?:\{[^{}]*\}[^{}]*)?\})', text, re.DOTALL):"
content = content.replace(old2, new2)

f.write_text(content, "utf-8")
print(f"Updated content.")
